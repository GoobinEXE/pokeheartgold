#!/usr/bin/env python3

import argparse
import ast
import collections
import dataclasses
import pathlib
import re
import subprocess
import sys

FUNC_START = re.compile(r'^\s*(local_)?(?:thumb|arm|non_word_aligned_thumb)_func_start\s+(\w+)')
FUNC_END = re.compile(r'^\s*(?:thumb|arm)_func_end\b')
LABEL = re.compile(r'^([A-Za-z_]\w*):(.*)$')
SECTION = re.compile(r'^\s*\.(text|rodata|data|bss)\b|^\s*\.section\s+\.?(\w+)')
PUBLIC = re.compile(r'^\s*\.(?:public|global)\s+(\w+)')
INCLUDE = re.compile(r'^\s*#\s*include\s+["<][^">]+[">]')
DIRECTIVE = re.compile(r'^\s*\.(\w+)\b\s*(.*)$')
IDENTIFIER = re.compile(r'^[A-Za-z_]\w*$')
OVERLAY_ID = re.compile(r'^SDK_OVERLAY_\w+_ID$')
ADDRESS_SUFFIX = re.compile(r'_([0-9A-Fa-f]{8})$')
NUMBER = re.compile(r'^-?(0[xX][0-9A-Fa-f]+|\d+)$')

INT_SIZES = {
    'byte': 1,
    'short': 2, 'hword': 2, '2byte': 2, 'half': 2,
    'word': 4, '4byte': 4, 'long': 4, 'int': 4,
}
C_TYPES = {1: 'unsigned char', 2: 'unsigned short', 4: 'unsigned int'}
IGNORED = {'public', 'global', 'extern', 'include', 'size', 'type', 'thumb', 'arm', 'code', 'syntax', 'local', 'weak', 'hidden'}


@dataclasses.dataclass
class Item:
    kind: str  # int, space, align, bytes
    size: int
    value: object = None


@dataclasses.dataclass
class Block:
    name: str
    file: str
    section: str
    address: int
    items: list
    includes: list
    error: str = None


@dataclasses.dataclass
class AsmFile:
    path: str
    funcs: dict  # name -> is local
    blocks: dict
    public: set


Symbol = collections.namedtuple('Symbol', 'kind file name')


def split_operands(text):
    operands, depth, quote, current = [], 0, None, ''
    for ch in text:
        if quote:
            current += ch
            if ch == quote and not current.endswith('\\' + quote):
                quote = None
        elif ch in '"\'':
            quote = ch
            current += ch
        elif ch == '(':
            depth += 1
            current += ch
        elif ch == ')':
            depth -= 1
            current += ch
        elif ch == ',' and depth == 0:
            operands.append(current.strip())
            current = ''
        else:
            current += ch
    if current.strip():
        operands.append(current.strip())
    return operands


def strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in '"\'':
            quote = ch
        elif ch in ';@' or line.startswith('//', i):
            return line[:i]
    return line


def parse_directive(block, directive, text):
    operands = split_operands(text)
    try:
        if directive in INT_SIZES:
            block.items += [Item('int', INT_SIZES[directive], op) for op in operands]
        elif directive in ('space', 'skip', 'zero'):
            block.items.append(Item('space', int(operands[0], 0), operands[1] if len(operands) > 1 else '0'))
        elif directive in ('balign', 'align'):
            alignment = int(operands[0], 0)
            block.items.append(Item('align', 1 << alignment if directive == 'align' else alignment,
                                    operands[1] if len(operands) > 1 else '0'))
        elif directive in ('ascii', 'asciz', 'string'):
            data = b''.join(ast.literal_eval('b' + op) for op in operands)
            if directive != 'ascii':
                data += b'\0'
            block.items.append(Item('bytes', len(data), data))
        elif directive not in IGNORED:
            block.error = f'unsupported directive .{directive}'
    except (ValueError, SyntaxError, IndexError) as e:
        block.error = f'cannot parse ".{directive} {text.strip()}" ({e})'


def parse_asm(path):
    asm = AsmFile(str(path), {}, {}, set())
    includes = []
    section, current, in_func = 'text', None, False
    for raw in path.read_text(errors='replace').splitlines():
        if INCLUDE.match(raw):
            includes.append(raw.strip())
            continue
        line = strip_comment(raw)
        m = FUNC_START.match(line)
        if m:
            asm.funcs[m.group(2)] = bool(m.group(1))
            in_func, current = True, None
            continue
        if FUNC_END.match(line):
            in_func = False
            continue
        if in_func:
            continue
        m = PUBLIC.match(line)
        if m:
            asm.public.add(m.group(1))
            continue
        m = SECTION.match(line)
        if m:
            section, current = m.group(1) or m.group(2), None
            continue
        m = LABEL.match(line)
        if m:
            name = m.group(1)
            addr = ADDRESS_SUFFIX.search(name)
            current = Block(name, path.name, section, int(addr.group(1), 16) if addr else 0, [], includes)
            asm.blocks[name] = current
            line = m.group(2)
        if current is None or not line.strip():
            continue
        m = DIRECTIVE.match(line)
        if m:
            parse_directive(current, m.group(1), m.group(2))
        else:
            current.error = f'unexpected line "{line.strip()}"'
    return asm


def read_symbols(nm, archive, prefix):
    result = subprocess.run([nm, '-g', '-P', str(archive)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f'gen_asm_stubs: warning: {nm} failed on {archive}: {result.stderr.strip()}', file=sys.stderr)
        return set(), set()
    defined, undefined = set(), set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or len(parts[1]) != 1:
            continue
        name = parts[0]
        if prefix and name.startswith(prefix):
            name = name[len(prefix):]
        (undefined if parts[1] in 'Uwv' else defined).add(name)
    return defined, undefined


class SymbolTable:
    def __init__(self, asm_files, external):
        self.files = {asm.path: asm for asm in asm_files}
        self.external = external
        self.defs = collections.defaultdict(list)
        for asm in asm_files:
            for name in asm.funcs:
                self.defs[name].append(Symbol('func', asm.path, name))
            for name in asm.blocks:
                self.defs[name].append(Symbol('data', asm.path, name))

    def exported(self, sym):
        asm = self.files[sym.file]
        return not asm.funcs[sym.name] if sym.kind == 'func' else sym.name in asm.public

    def resolve(self, name, home=None):
        """Binds a name the way the linker did: own file first, then C/SDK, then other files' exports."""
        if home is not None:
            asm = self.files[home]
            if name in asm.funcs:
                return Symbol('func', home, name)
            if name in asm.blocks:
                return Symbol('data', home, name)
            if name in self.external:
                return None
        candidates = self.defs.get(name, [])
        exported = [c for c in candidates if self.exported(c)]
        if len(exported) > 1:
            sys.exit(f'gen_asm_stubs: {name} is exported by several files: {", ".join(c.file for c in exported)}')
        if exported:
            return exported[0]
        if home is None and len(candidates) == 1:
            return candidates[0]
        return None

    def block(self, sym):
        return self.files[sym.file].blocks[sym.name]

    def c_name(self, sym):
        if self.exported(sym) or (len(self.defs[sym.name]) == 1 and sym.name not in self.external):
            return sym.name
        return f'{sym.name}__{pathlib.Path(sym.file).stem}'

    def is_reference(self, value, home):
        return IDENTIFIER.match(value) and (value in self.external or self.resolve(value, home) is not None)


def is_zero(expr):
    return bool(NUMBER.match(expr)) and int(expr, 0) == 0


def pointer_layout(block, table, home):
    """Returns the words of a block that can be laid out as one pointer-sized slot per word.

    That matches the 64-bit struct layout as long as no two plain integers are adjacent:
    a lone 32-bit field before or after a pointer is padded to 8 bytes anyway.
    """
    words = [it for it in block.items if it.kind != 'align']
    if not words or any(it.kind != 'int' or it.size != 4 for it in words):
        return None
    values = [it.value for it in words]
    refs = [bool(table.is_reference(v, home)) for v in values]
    if not any(refs):
        return None
    if all(r or is_zero(v) for r, v in zip(refs, values)):
        return values
    if any(not r and not (NUMBER.match(v) or OVERLAY_ID.match(v)) for r, v in zip(refs, values)):
        return None
    # OverlayManagerTemplate: init/main/exit (possibly NULL) followed by the overlay ID.
    if len(values) == 4 and all(r or is_zero(v) for r, v in zip(refs[:3], values[:3])):
        return values
    if any(not a and not b for a, b in zip(refs, refs[1:])):
        return None
    return values


def has_references(block, table, home):
    return any(it.kind == 'int' and table.is_reference(it.value, home) for it in block.items)


def numeric_definition(block, c_name):
    fields, values, offset = [], [], 0
    for it in block.items:
        if it.kind == 'int':
            fields.append(f'{C_TYPES[it.size]} f{len(fields)};')
            values.append(f'({C_TYPES[it.size]})({it.value})')
            offset += it.size
        elif it.kind == 'bytes':
            fields.append(f'unsigned char f{len(fields)}[{it.size}];')
            values.append('{' + ', '.join(str(b) for b in it.value) + '}')
            offset += it.size
        else:
            size = it.size if it.kind == 'space' else (-(block.address + offset)) % it.size
            if size:
                fields.append(f'unsigned char f{len(fields)}[{size}];')
                values.append('{' + ', '.join([f'(unsigned char)({it.value})'] * size) + '}')
                offset += size
    if not fields:
        return None
    ints = [it for it in block.items if it.kind == 'int']
    if len(ints) == len(block.items) and len({it.size for it in ints}) == 1:
        return f'{C_TYPES[ints[0].size]} {c_name}[{len(ints)}] __attribute__((aligned(4))) = {{\n    ' + \
            ',\n    '.join(values) + '\n};\n'
    return f'struct __attribute__((packed)) PortAsmData_{c_name} {{\n    ' + '\n    '.join(fields) + '\n};\n' + \
        f'struct PortAsmData_{c_name} {c_name} __attribute__((aligned(4))) = {{\n    ' + ',\n    '.join(values) + '\n};\n'


def main():
    parser = argparse.ArgumentParser(description='Generate C stand-ins for every symbol the PC build still takes from assembly')
    parser.add_argument('--nm', required=True)
    parser.add_argument('--game-lib', required=True, type=pathlib.Path)
    parser.add_argument('--provided-lib', nargs='*', default=[], type=pathlib.Path,
                        help='Libraries whose definitions win over the assembly (libntr, libspl, ...)')
    parser.add_argument('--asm', nargs='+', required=True, type=pathlib.Path)
    parser.add_argument('--funcs-out', required=True, type=pathlib.Path)
    parser.add_argument('--data-out', required=True, type=pathlib.Path)
    parser.add_argument('--symbol-prefix', default='', help='Leading character the platform adds to C symbols (Mach-O: _)')
    args = parser.parse_args()

    game_defined, game_undefined = read_symbols(args.nm, args.game_lib, args.symbol_prefix)
    provided = set()
    for lib in args.provided_lib:
        provided |= read_symbols(args.nm, lib, args.symbol_prefix)[0]
    external = game_defined | provided
    table = SymbolTable([parse_asm(path) for path in args.asm], external)

    needed = {sym for name in game_undefined - external if (sym := table.resolve(name)) is not None}
    pending = list(needed)
    while pending:
        sym = pending.pop()
        if sym.kind != 'data':
            continue
        layout = pointer_layout(table.block(sym), table, sym.file)
        for value in layout or []:
            ref = table.resolve(value, sym.file) if IDENTIFIER.match(value) else None
            if ref is not None and ref not in needed:
                needed.add(ref)
                pending.append(ref)

    stub_funcs = sorted((s for s in needed if s.kind == 'func'), key=table.c_name)
    pointer_blocks, numeric_blocks, placeholders = [], [], []
    for sym in sorted((s for s in needed if s.kind == 'data'), key=table.c_name):
        block = table.block(sym)
        if block.error:
            placeholders.append((sym, block.error))
        elif pointer_layout(block, table, sym.file) is not None:
            pointer_blocks.append(sym)
        elif has_references(block, table, sym.file):
            placeholders.append((sym, 'pointers mixed with plain data'))
        elif block.section != 'bss' and numeric_definition(block, sym.name) is None:
            placeholders.append((sym, 'empty block'))
        else:
            numeric_blocks.append(sym)

    def slot(value, home):
        if OVERLAY_ID.match(value):
            return '(void *)0'
        if NUMBER.match(value):
            return f'(void *)(intptr_t)({value})' if value.startswith('-') else f'(void *)(uintptr_t){value}u'
        ref = table.resolve(value, home)
        return f'(void *){table.c_name(ref) if ref else value}'

    header = '/* Generated by tools/port/gen_asm_stubs.py. Do not edit. */\n'
    out = [header, '#include <stdint.h>\n\n',
           'uintptr_t PortAsm_Unimplemented(const char *name, const char *file);\n\n']
    out += [f'uintptr_t {table.c_name(s)}(void) {{ return PortAsm_Unimplemented("{s.name}", "{pathlib.Path(s.file).name}"); }}\n'
            for s in stub_funcs]

    defined_here = set(stub_funcs) | set(pointer_blocks) | {s for s, _ in placeholders}
    externs = set()
    for sym in pointer_blocks:
        for value in pointer_layout(table.block(sym), table, sym.file):
            if not IDENTIFIER.match(value) or OVERLAY_ID.match(value):
                continue
            ref = table.resolve(value, sym.file)
            if ref is None:
                externs.add(value)
            elif ref not in defined_here:
                externs.add(table.c_name(ref))
    out.append('\n')
    out += [f'extern char {name}[];\n' for name in sorted(externs)]
    out += [f'extern void *{table.c_name(s)}[];\n' for s in pointer_blocks]
    for sym in pointer_blocks:
        slots = [slot(v, sym.file) for v in pointer_layout(table.block(sym), table, sym.file)]
        out.append(f'\n/* {pathlib.Path(sym.file).name} */\n'
                   f'void *{table.c_name(sym)}[{len(slots)}] = {{\n    ' + ',\n    '.join(slots) + '\n};\n')
    for sym, reason in placeholders:
        size = sum(it.size for it in table.block(sym).items if it.kind != 'align') or 4
        # Data that holds pointers grows on 64-bit hosts, so placeholders get twice the room.
        out.append(f'\n/* {pathlib.Path(sym.file).name}: placeholder, {reason} */\n'
                   f'unsigned char {table.c_name(sym)}[{2 * size}] __attribute__((aligned(8)));\n')
    out.append('\nconst char *const gPortAsmPlaceholderData[] = {\n' +
               ''.join(f'    "{s.name} ({pathlib.Path(s.file).name})",\n' for s, _ in placeholders) + '    0,\n};\n')
    args.funcs_out.write_text(''.join(out))

    includes = ['#include "global.h"']
    for sym in numeric_blocks:
        block = table.block(sym)
        if any(it.kind != 'bytes' and isinstance(it.value, str) and not NUMBER.match(it.value) for it in block.items):
            includes += [inc for inc in block.includes if inc not in includes]
    data = [header] + [inc + '\n' for inc in includes] + ['\n']
    for sym in numeric_blocks:
        block = table.block(sym)
        if block.section == 'bss':
            size = sum(it.size for it in block.items if it.kind == 'space')
            data.append(f'/* {block.file}: grown for 64-bit pointers */\n'
                        f'unsigned char {table.c_name(sym)}[{2 * size}] __attribute__((aligned(8)));\n\n')
        else:
            data.append(f'/* {block.file} */\n{numeric_definition(block, table.c_name(sym))}\n')
    args.data_out.write_text(''.join(data))

    print(f'gen_asm_stubs: {len(stub_funcs)} function stubs, {len(pointer_blocks)} pointer tables, '
          f'{len(numeric_blocks)} data blocks, {len(placeholders)} placeholders')
    for sym, reason in placeholders:
        print(f'gen_asm_stubs: warning: {sym.name} ({pathlib.Path(sym.file).name}) is a placeholder: {reason}',
              file=sys.stderr)


if __name__ == '__main__':
    main()
