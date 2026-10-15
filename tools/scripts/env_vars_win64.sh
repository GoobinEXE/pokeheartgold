#!/bin/bash

# Sourced by Launch_MSys2.ps1: the UCRT64 toolchain has to win over the MSYS one.

export PATH=/ucrt64/bin:/usr/local/bin:/usr/bin:/bin:/c/Windows/System32:/c/Windows
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
