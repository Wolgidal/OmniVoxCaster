; OmniVox Caster - Inno Setup Installer Script
; Benoetigt: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)

#define AppName      "OmniVox Caster"
#define AppVersion   "0.5"
#define AppPublisher "Wolgidal"
#define AppExeName   "start.bat"

[Setup]
AppId={{A3F8C2D1-7E4B-4F29-9A6C-1D8B3E5F7A02}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/Wolgidal/OmniVoxCaster
AppSupportURL=https://github.com/Wolgidal/OmniVoxCaster/issues
DefaultDirName={localappdata}\OmniVoxCaster
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=OmniVoxCaster_v{#AppVersion}_Setup
SetupIconFile=assets\omni_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
; Kein Admin noetig - Installation ins Benutzerverzeichnis
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
WizardSizePercent=120
; Mindestanforderung: Windows 10
MinVersion=10.0
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\start.bat
; Nach Installation direkt starten ermoglichen
DisableFinishedPage=no

[Languages]
Name: "german";  MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
german.WelcomeLabel1=Willkommen beim Setup von [name]
german.WelcomeLabel2=Dieses Programm installiert [name/ver] auf Ihrem Computer.%n%nBeim ersten Start werden KI-Modelle heruntergeladen (~2 GB). Eine Internetverbindung ist erforderlich.%n%nEs wird empfohlen, alle anderen Programme zu beenden, bevor Sie fortfahren.
german.FinishedLabel=Die Installation von [name] wurde abgeschlossen.%n%nDie App kann jetzt über das Startmenü oder den Desktop gestartet werden.%n%nHinweis: Beim ersten Start werden KI-Modelle heruntergeladen (~2 GB).

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Symbole:"; Flags: unchecked

[Files]
; Hauptprogramm
Source: "main_overlay.py";   DestDir: "{app}"; Flags: ignoreversion
Source: "start.bat";         DestDir: "{app}"; Flags: ignoreversion
Source: "install_setup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt";  DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE";           DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE";            DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";         DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*";         DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Startmenü
Name: "{group}\{#AppName}";         Filename: "{app}\start.bat";         IconFilename: "{app}\assets\omni_icon.ico"; WorkingDir: "{app}"
Name: "{group}\Deinstallieren";     Filename: "{uninstallexe}"

; Desktop (optional)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\start.bat";         IconFilename: "{app}\assets\omni_icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Python-Umgebung nach der Dateiextraktion einrichten
Filename: "{app}\install_setup.bat"; \
    Description: "Python-Umgebung einrichten (Abhängigkeiten installieren)"; \
    Flags: waituntilterminated; \
    StatusMsg: "Installiere Abhängigkeiten (kann einige Minuten dauern) ..."

; App direkt nach Installation starten (optional)
Filename: "{app}\start.bat"; \
    Description: "{#AppName} jetzt starten"; \
    Flags: nowait postinstall skipifsilent unchecked; \
    WorkingDir: "{app}"

[UninstallRun]
; Virtuelle Umgebung und Cache bereinigen
Filename: "cmd.exe"; Parameters: "/c rmdir /s /q ""{app}\venv""";   Flags: runhidden waituntilterminated
Filename: "cmd.exe"; Parameters: "/c rmdir /s /q ""{app}\__pycache__"""; Flags: runhidden waituntilterminated; Check: DirExists(ExpandConstant('{app}\__pycache__'))

[UninstallDelete]
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files;          Name: "{app}\install.log"
Type: files;          Name: "{app}\startup.log"
Type: files;          Name: "{app}\config.ini"

[Code]
// Hilfsfunktion: Dateiinhalt lesen (muss vor erster Verwendung stehen)
function FileContents(FileName: String): String;
var
  Lines: TArrayOfString;
  I: Integer;
begin
  Result := '';
  if LoadStringsFromFile(FileName, Lines) then
    for I := 0 to GetArrayLength(Lines) - 1 do
      Result := Result + Lines[I] + #13#10;
end;

// Zeige Installationslog nach dem Setup an, falls Fehler aufgetreten sind
procedure CurStepChanged(CurStep: TSetupStep);
var
  LogPath: String;
  ErrorCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    LogPath := ExpandConstant('{app}\install.log');
    if FileExists(LogPath) then
    begin
      if Pos('[FEHLER]', FileContents(LogPath)) > 0 then
      begin
        if MsgBox('Bei der Installation sind Fehler aufgetreten.' + #13#10 +
                  'Möchten Sie das Protokoll (install.log) öffnen?',
                  mbError, MB_YESNO) = IDYES then
          ShellExec('open', 'notepad.exe', LogPath, '', SW_SHOW, ewNoWait, ErrorCode);
      end;
    end;
  end;
end;
