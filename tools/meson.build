subdir('nitrorom')

subdir('nitroarc') # libnitroarc
subdir('dataproc') # Requires libnitroarc and libenum

subdir('compstatic')
subdir('csv2bin')
subdir('jsonproc')
subdir('msgenc')
subdir('nitrogfx')
subdir('o2narc')
subdir('postconf')
subdir('scripts')

# Tools from the subprojects
if build_target == 'arm'
    makelcf_exe = find_program('makelcf', native: true)
endif

# Native tools
arm_none_eabi_gcc_exe = find_program('arm-none-eabi-gcc', native: true)