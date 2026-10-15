#!/bin/bash

# Installs the MSYS2 packages used by `make win64`.

set -euo pipefail

pacman -S --needed --noconfirm \
    make git python flex bison wget p7zip zip \
    mingw-w64-ucrt-x86_64-gcc \
    mingw-w64-ucrt-x86_64-ninja \
    mingw-w64-ucrt-x86_64-nasm \
    mingw-w64-ucrt-x86_64-pkg-config \
    mingw-w64-ucrt-x86_64-libpng \
    mingw-w64-ucrt-x86_64-SDL2 \
    mingw-w64-ucrt-x86_64-enet \
    mingw-w64-ucrt-x86_64-arm-none-eabi-gcc \
    mingw-w64-ucrt-x86_64-gdb
