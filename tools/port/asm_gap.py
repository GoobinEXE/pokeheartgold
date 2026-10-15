#!/usr/bin/env python3

import argparse
import collections
import json
import pathlib
import re

ASM_FUNC = re.compile(r'^\s*(?:thumb|arm|non_word_aligned_thumb)_func_start\s+(\w+)', re.M)
C_FUNC = re.compile(
    r'^(?:static\s+)?(?:inline\s+)?(?:const\s+)?(?:struct\s+|enum\s+|unsigned\s+)?'
    r'[A-Za-z_]\w*[\s\*]+([A-Za-z_]\w*)\s*\([^;{}()]*(?:\([^;{}()]*\)[^;{}()]*)*\)\s*\{',
    re.M,
)
C_OVY_REF = re.compile(r'FS_OVERLAY_ID\((\w+)\)')
ASM_OVY_REF = re.compile(r'SDK_OVERLAY_(\w+?)_ID')
LSF_SECTION = re.compile(r'^(Static|Overlay|Autoload)\s+(\S+)')
LSF_OBJECT = re.compile(r'^Object\s+\S+?/(\S+)\.o$')

# Link battles (OVY_5), Pokewalker/Wii menus (OVY_112, OVY_75) and Wi-Fi (OVY_0) are not on these routes.
ROUTES = {
    'first-battle': [
        'intro_title', 'OVY_74', 'OVY_53', 'OVY_36', 'OVY_61',
        'field', 'OVY_2', 'OVY_3', 'OVY_4',
        'OVY_114', 'OVY_115', 'OVY_116', 'OVY_117', 'OVY_118', 'OVY_119', 'OVY_120',
        'OVY_12', 'OVY_6', 'OVY_7', 'OVY_8', 'OVY_10',
    ],
}


def index_sources(root):
    sources = {}
    for top in ('src', 'asm'):
        for path in (root / top).rglob('*'):
            if path.suffix in ('.c', '.s'):
                rel = path.relative_to(root).as_posix()
                sources[rel.replace('/', '_')] = rel
    return sources


def parse_lsf(root, sources):
    modules = collections.OrderedDict()
    overlay_ids = {}
    current = None
    for line in (root / 'main.lsf').read_text().splitlines():
        line = line.strip()
        section = LSF_SECTION.match(line)
        if section:
            current = section.group(2)
            modules[current] = []
            if section.group(1) == 'Overlay':
                overlay_ids[current] = len(overlay_ids)
            continue
        obj = LSF_OBJECT.match(line)
        if obj and current and obj.group(1) in sources:
            modules[current].append(sources[obj.group(1)])
    return modules, overlay_ids


def measure(root):
    modules, overlay_ids = parse_lsf(root, index_sources(root))
    result = collections.OrderedDict()
    for name, files in modules.items():
        asm_funcs = c_funcs = 0
        refs = set()
        for rel in files:
            text = (root / rel).read_text(errors='replace')
            if rel.endswith('.s'):
                asm_funcs += len(ASM_FUNC.findall(text))
                refs.update(ASM_OVY_REF.findall(text))
            else:
                c_funcs += len(C_FUNC.findall(text))
                refs.update(C_OVY_REF.findall(text))
        refs.discard(name)
        result[name] = {
            'id': overlay_ids.get(name),
            'asm': asm_funcs,
            'c': c_funcs,
            'loads': sorted(refs),
            'asm_files': [rel for rel in files if rel.endswith('.s')],
        }
    return result


def pct(c_funcs, asm_funcs):
    total = c_funcs + asm_funcs
    return 100.0 * c_funcs / total if total else 100.0


def print_modules(stats):
    print(f'{"module":<24}{"id":>4}{"asm":>7}{"c":>7}{"C%":>8}  loads')
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1]['asm']):
        if s['asm'] == 0 and s['c'] == 0:
            continue
        ovy_id = '' if s['id'] is None else s['id']
        print(f'{name:<24}{ovy_id:>4}{s["asm"]:>7}{s["c"]:>7}{pct(s["c"], s["asm"]):>7.1f}%  {",".join(s["loads"])}')


def print_route(stats, route, show_files):
    names = ['main'] + ROUTES[route]
    asm_funcs = sum(stats[n]['asm'] for n in names)
    c_funcs = sum(stats[n]['c'] for n in names)
    print(f'\nroute "{route}": asm={asm_funcs} c={c_funcs} ({pct(c_funcs, asm_funcs):.1f}% C)')
    for name in sorted(names, key=lambda n: -stats[n]['asm']):
        s = stats[name]
        if s['asm']:
            files = f'  files={", ".join(s["asm_files"])}' if show_files else ''
            print(f'  {name:<12} asm={s["asm"]:>5}{files}')
    done = [n for n in names if stats[n]['asm'] == 0]
    print(f'  already 100% C: {", ".join(done)}')


def main():
    parser = argparse.ArgumentParser(description='Measure how much game code is still assembly, per module and per route')
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument('--route', choices=sorted(ROUTES), default='first-battle')
    parser.add_argument('--files', action='store_true', help='List the assembly files left on the route')
    parser.add_argument('--json', type=pathlib.Path, help='Also write the per-module numbers to this file')
    args = parser.parse_args()

    stats = measure(args.root)
    game = [s for n, s in stats.items() if n not in ('ITCM', 'DTCM')]
    asm_funcs = sum(s['asm'] for s in game)
    c_funcs = sum(s['c'] for s in game)
    print(f'game code: asm={asm_funcs} c={c_funcs} ({pct(c_funcs, asm_funcs):.1f}% C, C count is approximate)\n')
    print_modules(stats)
    print_route(stats, args.route, args.files)
    if args.json:
        args.json.write_text(json.dumps(stats, indent=1))


if __name__ == '__main__':
    main()
