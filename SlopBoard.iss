; Inno Setup script for SlopBoard.

#define AppName    "SlopBoard"
#define AppVersion "0.3"
#define AppExe     "SlopBoard.exe"
#define AppURL     "https://rick9117.github.io/"

[Setup]
AppId={{7F3A9C2E-5B14-4E8A-9D6F-2C1B8A4E7D30}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
; Per-user install: no administrator rights, and the install folder stays
; writable so SlopBoard can save its data (CSVs, logs) next to itself.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=assets\slopboard.ico
OutputDir=installer
OutputBaseFilename=SlopBoard-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Everything the build produced, including the bundled Python runtime.
Source: "dist\SlopBoard\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; On uninstall, also remove the data SlopBoard created after install.
Type: filesandordirs; Name: "{app}"
