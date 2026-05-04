[Setup]
AppName=Forix
AppVersion=1.0
AppPublisher=Forix
AppPublisherURL=https://spdly.xo.je
AppSupportURL=https://spdly.xo.je/forix
AppUpdatesURL=https://spdly.xo.je/updates

DefaultDirName={pf}\Forix
DefaultGroupName=Forix

OutputDir=output
OutputBaseFilename=Forix_Setup

Compression=lzma
SolidCompression=yes

SetupIconFile=assets\forix.ico

; UI Customization
WizardStyle=modern
WizardImageFile=assets\installer_banner.bmp
WizardSmallImageFile=assets\installer_small.bmp

; Behavior
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Forix.exe

; Optional polish
PrivilegesRequired=admin
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
AppName=Forix
AppTagline=Forging Better Projects
AppDescription=Forix is an advanced project, file, and inventory management system designed for developers and engineers.

[Messages]
WelcomeLabel1=Welcome to the Forix Setup Wizard
WelcomeLabel2=This will install Forix on your system.\n\nForix helps you organize, version, and manage projects efficiently.

SelectDirLabel3=Choose the folder where Forix will be installed.
FinishedLabel=Setup has finished installing Forix on your system.

[Files]
; Main application (Nuitka output)
Source: "build_nuitka\main.dist\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; VC++ Redistributable
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Forix"; Filename: "{app}\Forix.exe"
Name: "{commondesktop}\Forix"; Filename: "{app}\Forix.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; Flags: unchecked

[Run]
; Install VC++ only if not already installed
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; \
    StatusMsg: "Installing required components..."; \
    Check: not IsVCRedistInstalled()

; Launch app after install
Filename: "{app}\Forix.exe"; Description: "Launch Forix"; Flags: nowait postinstall skipifsilent

[Code]
function IsVCRedistInstalled(): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(
    HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Version',
    Version
  );
end;