#ifndef Stage
  #error Supply /DStage=<absolute staging folder> and /DReleaseVersion=x.y.z
#endif
[Setup]
AppId=LOCO-Detector-Desktop
AppName=LOCO Detector
AppVersion={#ReleaseVersion}
AppPublisher=LOCO Detector
AppPublisherURL=https://github.com/AzAlejandro/LOCO-detector
DefaultDirName={localappdata}\Programs\LOCO Detector
PrivilegesRequired=lowest
#ifdef IsolatedTest
Uninstallable=no
CreateUninstallRegKey=no
UsePreviousAppDir=no
#endif
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
OutputDir={#Stage}
OutputBaseFilename=LOCO-Windows-x64
Compression=lzma2/fast
SolidCompression=no
UninstallDisplayIcon={app}\runtime\pythonw.exe
[Files]
Source: "{#Stage}\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
#ifndef IsolatedTest
Name: "{userprograms}\LOCO Detector"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launch.py"""; WorkingDir: "{app}"
#endif
[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launch.py"""; Description: "Abrir LOCO Detector"; Flags: postinstall nowait skipifsilent
[Code]
function StopPrevious(): Boolean;
var ExitCode: Integer;
begin
  Result := not FileExists(ExpandConstant('{app}\launch.py'));
  if not Result then
    Result := Exec(ExpandConstant('{app}\runtime\python.exe'), '"' + ExpandConstant('{app}\launch.py') + '" stop', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  if not StopPrevious() then Result := 'Cierra LOCO Detector antes de actualizar.';
end;
function InitializeUninstall(): Boolean;
begin
  Result := StopPrevious();
end;
