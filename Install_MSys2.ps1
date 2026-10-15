# Installs a portable MSYS2 under .\msys2 with everything the PC port build needs.
# Run from the repository root: powershell -ExecutionPolicy Bypass -File .\Install_MSys2.ps1

if (Test-Path ".\msys2") {
    Write-Host "MSYS2 is already installed in .\msys2"
    exit
}

$installer = ".\msys2-installer.exe"
Invoke-WebRequest https://github.com/msys2/msys2-installer/releases/latest/download/msys2-x86_64-latest.exe -OutFile $installer
& $installer in --confirm-command --accept-messages --root="$PWD\msys2"
Remove-Item $installer

$bash = ".\msys2\usr\bin\bash.exe"
$repo = & $bash -c "pwd"
# The first update can replace the core runtime and stop early, so it runs twice.
& $bash -l -c "pacman -Syu --noconfirm"
& $bash -l -c "pacman -Syu --noconfirm"
& $bash -l -c "'$repo/tools/scripts/setup_msys2.sh'"
