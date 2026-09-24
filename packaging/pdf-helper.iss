; Installer for the onedir build. Compiled by build.ps1 with /DAppVersion=<VERSION>.
; Per-user by design: PrivilegesRequired=lowest means no UAC prompt, which is one less trust
; dialog on a build that is not yet code-signed, and the tool needs no machine-wide state.
; AppId is fixed forever - it is what makes the next version upgrade this one in place.

[Setup]
AppId={{BE05918A-0D78-4177-8343-846B50580F04}
AppName=PDF Helper
AppVersion={#AppVersion}
AppVerName=PDF Helper {#AppVersion}
AppPublisher=AragusNZ
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\PDF Helper
DefaultGroupName=PDF Helper
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PdfHelper-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\pdf_helper\assets\icon.ico
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\PdfHelper.exe

[Files]
Source: "..\dist\PdfHelper\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\PDF Helper"; Filename: "{app}\PdfHelper.exe"
Name: "{userdesktop}\PDF Helper"; Filename: "{app}\PdfHelper.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\PdfHelper.exe"; Description: "Launch PDF Helper"; Flags: nowait postinstall skipifsilent
