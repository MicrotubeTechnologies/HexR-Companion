; Inno Setup script for HEXR Companion.
;
; Build it with:   BUILD-INSTALLER.bat        (from the app\ folder)
; or by hand:      iscc packaging\HexR-Companion.iss
;
; Input : dist\HexR-Companion\   (the PyInstaller folder build)
; Output: Installer\HexR-Companion-Setup.exe
;
; This folder is called packaging\, not installer\, because the OUTPUT folder
; is called Installer\. Windows filenames are case-insensitive, so two folders
; whose names differ only in case are the same folder to any tool that cleans
; one of them - a `rm -rf Installer` wipes the source.
;
; The output filename carries no version number, on purpose: GitHub resolves
; /releases/latest/download/<name> by exact asset name, so a version in the
; name breaks that link on every release. The version still appears in the
; exe's properties, the wizard, the app footer, and Add/Remove Programs.
;
; Get Inno Setup from https://jrsoftware.org/isdl.php (free). GitHub's
; windows-latest runners already have it, so CI needs no extra install.

#define MyAppName        "HEXR Companion"

; The version comes from the repo's VERSION file - the same one the app and the
; spec read - so an installer can never disagree with the app inside it about
; what version this is. CI writes the git tag into that file.
;
; SourcePath is the folder holding THIS script, so the lookup works no matter
; which directory the compiler was invoked from.
#define VersionFile FileOpen(AddBackslash(SourcePath) + "..\VERSION")
#define MyAppVersion Trim(FileRead(VersionFile))
#expr FileClose(VersionFile)
#if MyAppVersion == ""
  #error VERSION file is missing or empty
#endif
#define MyAppPublisher   "Microtube Technologies"
#define MyAppURL         "https://github.com/MicrotubeTechnologies/HexR-Companion"
#define MyAppExeName     "HexR-Companion.exe"
#define SourceDir        AddBackslash(SourcePath) + "..\dist\HexR-Companion"

[Setup]
; AppId must never change between releases - it is how Windows recognises an
; upgrade rather than stacking a second entry in Add/Remove Programs. This is a
; NEW id, distinct from FLEXR Controller's: the two apps install side by side
; and must never be mistaken for versions of each other. It is also why the
; rename from HEXR Window Tester to HEXR Companion (0.4.0) installs as an
; upgrade of the old app rather than beside it: the id stayed, the name moved.
AppId={{3D7B94E1-2C58-4A6F-B0D3-7E19A4F62C88}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}

; Installs for the current user only, into their own profile. No admin rights,
; no UAC prompt, no "install for everyone?" question - so it also works on a
; locked-down laptop where the person is not an administrator.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\HEXR Companion
DefaultGroupName={#MyAppName}
UsePreviousAppDir=no
UsePreviousGroup=no

; The whole wizard is: welcome, progress, finish. Every page that asked the
; user to decide something has been removed - where it installs and what the
; Start Menu group is called are questions with one sensible answer.
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
AllowNoIcons=no

; Bluetooth LE here goes through WinRT, which needs Windows 10 or newer.
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir={#SourcePath}\..\Installer
; This exact filename is load-bearing - see the note at the top.
OutputBaseFilename=HexR-Companion-Setup
SetupIconFile={#SourcePath}\..\assets\icon.ico

; Wizard artwork. Several sizes so Inno picks one for the user's display
; scaling rather than upscaling a small bitmap. These must be BMP - Inno does
; not read PNG here.
WizardImageFile={#SourcePath}\art\wizard-164x314.bmp,{#SourcePath}\art\wizard-192x386.bmp,{#SourcePath}\art\wizard-246x459.bmp,{#SourcePath}\art\wizard-328x628.bmp
WizardSmallImageFile={#SourcePath}\art\small-55.bmp,{#SourcePath}\art\small-64.bmp,{#SourcePath}\art\small-92.bmp,{#SourcePath}\art\small-110.bmp,{#SourcePath}\art\small-138.bmp
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

; --- Code signing ------------------------------------------------------------
; There is none, deliberately: no certificate has been bought, so there is no
; SignTool directive here and nothing in the build reads a secret. Windows
; SmartScreen will warn on first run, which is expected and documented rather
; than worked around. What replaces it is free and verifiable: the SHA-256 of
; every published file, plus GitHub build provenance attesting which workflow,
; commit and repository produced the exact bytes.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[InstallDelete]
; Until 0.4.0 this app was HEXR Window Tester, installed under that name. The
; AppId above is the same, so Windows already treats this as an upgrade and the
; uninstaller entry moves over; what would be left behind is the old folder and
; its shortcuts, still launching the old version beside the new one.
Type: filesandordirs; Name: "{localappdata}\Programs\HEXR Window Tester"
Type: files; Name: "{autodesktop}\HEXR Window Tester.lnk"
Type: filesandordirs; Name: "{autoprograms}\HEXR Window Tester"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

; The APK Sideload screen runs the adb inside the app, and adb leaves its server running after
; the app closes, since another program may be using it by then. That server would hold
; adb.exe open, and an upgrade could not replace it or an uninstall remove it, so both stop it
; first. Whatever next needs adb starts a server again.
[UninstallRun]
Filename: "{app}\_internal\assets\adb\adb.exe"; Parameters: "kill-server"; \
    Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "StopAdb"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Adb: String;
  ResultCode: Integer;
begin
  Adb := ExpandConstant('{app}\_internal\assets\adb\adb.exe');
  if FileExists(Adb) then
    Exec(Adb, 'kill-server', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
