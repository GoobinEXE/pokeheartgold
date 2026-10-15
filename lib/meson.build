lib_asm_includes = [
    include_directories('asm/include'),
    include_directories('NitroDWC/asm/include'),
]

lib_includes = include_directories('include', 'syscall')

lib_link_args = [
    '-library',
    '-nothumb',
    '-main', '""',
    '-nostdlib',
]

##############
###  IRC   ###
##############
libirc_srcs = files('asm/libirc.s')

if build_target == 'arm'
    libirc = static_library('irc',
        sources : libirc_srcs,
        nasm_args : asm_args,
        link_args : lib_link_args,
        include_directories : [public_includes, lib_asm_includes],
        dependencies : [nitrosdk_dep, nitrosystem_dep],
        pic : false
    )
endif

subdir('dsprot')
subdir('NitroDWC')
subdir('spl')
if build_target == 'arm'
    subdir('syscall')
endif

