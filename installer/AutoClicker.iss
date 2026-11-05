; Inno Setup script: wraps dist\AutoClicker.exe into dist\AutoClicker-Setup.exe.
; Asks for admin up front (UAC), defaults to Program Files, and lets the user pick any folder on the directory page.
#define AppName "AutoClicker"
#ifndef AppVersion
  #define AppVersion "0.0"  ; build.ps1 passes the real one from AutoClicker.pyw via /DAppVersion=
#endif
#define AppExe "AutoClicker.exe"

[Setup]
AppId={{7D2F0B6E-5C8A-4F1B-9E3D-2A6C4B1F0E77}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Jadan Duffin
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=admin
DisableDirPage=no
OutputDir=..\dist
OutputBaseFilename=AutoClicker-Setup
SetupIconFile=..\src\AutoClicker.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
; make Windows re-read icons when setup finishes: an update kept showing the old icon on shortcuts and the taskbar
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{userappdata}\AutoClicker.json"
