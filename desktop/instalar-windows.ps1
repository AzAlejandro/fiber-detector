# Instala o actualiza la edición estable para el usuario actual.
[CmdletBinding()]
param([ValidatePattern('^v\d+\.\d+\.\d+$')][string]$Tag)
$ErrorActionPreference = 'Stop'
if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
    throw 'Esta edición de LOCO requiere Windows x64.'
}
$endpoint = if ($Tag) { "tags/$Tag" } else { 'latest' }
$release = Invoke-RestMethod "https://api.github.com/repos/AzAlejandro/fiber-detector/releases/$endpoint"
if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v(\d+\.\d+\.\d+)$') {
    throw 'No se encontró una versión estable de escritorio.'
}
$version = $Matches[1]
if ($Tag -and $release.tag_name -cne $Tag) { throw 'La versión recibida no coincide con la solicitada.' }
$asset = @($release.assets | Where-Object name -eq 'LOCO-Windows-x64.exe')
if ($asset.Count -ne 1 -or $asset[0].digest -notmatch '^sha256:[0-9a-fA-F]{64}$') {
    throw 'La release estable todavía no ofrece el instalador de Windows con su digest.'
}
$app = Join-Path $env:LOCALAPPDATA 'Programs\LOCO Detector'
$installed = if (Test-Path -LiteralPath "$app\VERSION") { [version](Get-Content -Raw -LiteralPath "$app\VERSION").Trim() }
if ($installed -and $installed -gt [version]$version) { throw "La instalación $installed es más reciente que $version." }
if ($installed -ne [version]$version) {
    $file = Join-Path ([IO.Path]::GetTempPath()) ("LOCO-" + [guid]::NewGuid() + '.exe')
    try {
        Invoke-WebRequest $asset[0].browser_download_url -OutFile $file -UseBasicParsing
        if (('sha256:' + (Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant()) -ne $asset[0].digest) {
            throw 'El SHA-256 del instalador no coincide con GitHub.'
        }
        if ((Get-AuthenticodeSignature -LiteralPath $file).Status -ne 'Valid') { throw 'Firma de Windows inválida.' }
        $installer = Start-Process -FilePath $file -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Wait -PassThru -WindowStyle Hidden
        if ($installer.ExitCode -ne 0) { throw "Instalador: salida $($installer.ExitCode)." }
    } finally {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
}
Start-Process -FilePath "$app\runtime\pythonw.exe" -ArgumentList ('"' + "$app\launch.py" + '"') -WindowStyle Hidden
$port = if ($env:LOCO_DESKTOP_PORT) { [int]$env:LOCO_DESKTOP_PORT } else { 5181 }
for ($i = 0; $i -lt 60; $i++) {
    try { $status = Invoke-RestMethod "http://127.0.0.1:$port/api/agent/connection" -TimeoutSec 2 } catch { $status = $null }
    if ($status.application -eq 'LOCO Detector' -and $status.ready -and $status.version -eq $version) {
        $status | ConvertTo-Json -Compress
        return
    }
    Start-Sleep -Seconds 1
}
throw "No se pudo verificar LOCO $version. Revisa el registro server.log en la carpeta de datos."
