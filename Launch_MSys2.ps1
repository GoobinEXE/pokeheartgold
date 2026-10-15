# Opens a UCRT64 shell at the repository root, or runs one command in it:
#   powershell -ExecutionPolicy Bypass -File .\Launch_MSys2.ps1 -command "make win64 GAME_VERSION=SOULSILVER"

param (
    [string]$command
)

$bash = ".\msys2\usr\bin\bash.exe"
$repo = & $bash -c "pwd"
$env:MSYSTEM = "UCRT64"
$env:CHERE_INVOKING = "1"

if ($command) {
    & $bash --rcfile "$repo/tools/scripts/env_vars_win64.sh" -ci "$command"
} else {
    & $bash --rcfile "$repo/tools/scripts/env_vars_win64.sh" -i
}
