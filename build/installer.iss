; Inno Setup script for FBGroupPosterPro (Windows installer)
; Build:
;   1. Run pyinstaller build\build_win.spec to produce dist\FBGroupPosterPro\
;   2. Run "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
;   3. Output: dist\FBGroupPosterPro-Setup-{version}.exe

#define MyAppName "FBGroupPosterPro"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Rain AI Studio"
#define MyAppURL "https://fbgroupposter.vercel.app"
#define MyAppExeName "FBGroupPosterPro.exe"

[Setup]
AppId={{8B7E2C46-3F4D-4BAB-9D26-FBP-RAIN-001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=auto
LicenseFile=
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=FBGroupPosterPro-Setup-{#MyAppVersion}
SetupIconFile=..\icons\icon.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english";    MessagesFile: "compiler:Default.isl"
Name: "chinesetrad"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "啟動時自動執行"; GroupDescription: "其他選項："; Flags: unchecked

[Files]
; Pull in everything PyInstaller produced. The bundle is one folder so we copy
; the whole tree under dist\FBGroupPosterPro\ -> {app}.
Source: "..\dist\FBGroupPosterPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; The user data directory ({localappdata}\fbgroupposter or %USERPROFILE%\.fbgroupposter)
; is intentionally NOT touched on uninstall — license cache, cookies, and the
; SQLite DB live there, and we don't want to wipe them when the user re-installs.
[UninstallDelete]
Type: filesandordirs; Name: "{app}"
