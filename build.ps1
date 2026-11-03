# Builds dist\AutoClicker.exe (PyInstaller) and dist\AutoClicker-Setup.exe (Inno Setup). Run from anywhere.
# -Release also publishes a GitHub release tagged with the version in AutoClicker.pyw (what the app's update check looks for).
param([switch]$Release)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$src = "$root\src"
$work = "$env:TEMP\AutoClicker-build"
$ver = (Select-String -Path "$src\AutoClicker.pyw" -Pattern 'AUTOCLICKER_VERSION", "([\d.]+)"').Matches[0].Groups[1].Value
"version $ver"

python -m PyInstaller --noconfirm --onefile --noconsole --name AutoClicker `
    --icon "$src\AutoClicker.ico" `
    --add-data "$src\jd-icon-dark.png;." `
    --add-data "$src\AutoClicker.ico;." `
    --distpath "$root\dist" --workpath $work --specpath $work "$src\AutoClicker.pyw"
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$iscc = Get-ChildItem "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
& $iscc.FullName /Q "/DAppVersion=$ver" "$root\installer\AutoClicker.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }

Get-Item "$root\dist\AutoClicker.exe", "$root\dist\AutoClicker-Setup.exe" | Format-Table Name, @{n="MB"; e={[math]::Round($_.Length / 1MB, 1)}}

if ($Release) {
    gh release create "v$ver" "$root\dist\AutoClicker-Setup.exe" --title "AutoClicker $ver" --generate-notes
    if ($LASTEXITCODE) { throw "gh release failed" }
}
