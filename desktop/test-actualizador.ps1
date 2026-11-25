# Pruebas del selector de releases; nunca ejecutan un instalador ni abren el navegador.
$ErrorActionPreference = 'Stop'
$updater = Join-Path $PSScriptRoot 'instalar-windows.ps1'
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("loco-updater-" + [guid]::NewGuid())
$originalLocal = $env:LOCALAPPDATA
$asset = @{ name='LOCO-Windows-x64.exe'; browser_download_url='https://example.invalid/test.exe'; digest='sha256:' + ('0' * 64) }
$release = @{ tag_name='v1.1.1'; assets=@($asset); draft=$false; prerelease=$false }
function Invoke-RestMethod($Uri, $TimeoutSec) {
    if ($Uri -like 'https://api.github.com/*') { return $release }
    return @{ application='LOCO Detector'; ready=$true; version='1.1.1' }
}
function Invoke-WebRequest($Uri, $OutFile, [switch]$UseBasicParsing) {
    if ($Uri -ne $asset.browser_download_url) { throw 'URL de prueba inesperada.' }
    Copy-Item -LiteralPath "$fixture/prueba.exe" -Destination $OutFile
}
function Start-Process($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait, [switch]$PassThru) {
    if (!$FilePath.EndsWith('pythonw.exe')) { throw 'Se intentó ejecutar un instalador.' }
}
function ExpectFailure($pattern) {
    try { & $updater -Tag v1.1.1 } catch {
        if ($_.Exception.Message -notmatch $pattern) { throw }
        return
    }
    throw "Faltó el rechazo esperado: $pattern"
}
try {
    $env:LOCALAPPDATA = $fixture
    $app = Join-Path $fixture 'Programs/LOCO Detector'
    New-Item -ItemType Directory -Path $app -Force | Out-Null
    [IO.File]::WriteAllText("$fixture/prueba.exe",'fixture')
    $release.assets = @()
    ExpectFailure 'digest'
    $release.assets = @($asset)
    ExpectFailure 'SHA-256'
    $asset.digest = 'sha256:' + (Get-FileHash "$fixture/prueba.exe").Hash.ToLowerInvariant()
    ExpectFailure 'Firma'
    [IO.File]::WriteAllText("$app/VERSION",'2.0.0')
    ExpectFailure 'reciente'
    [IO.File]::WriteAllText("$app/VERSION",'1.1.1')
    $result = (& $updater -Tag v1.1.1) | ConvertFrom-Json
    if (!$result.ready -or $result.version -ne '1.1.1') { throw 'Falló la verificación sin actualización.' }
    Write-Output 'OK: ausencia de instalador, digest, firma, downgrade y versión vigente.'
} finally {
    $env:LOCALAPPDATA = $originalLocal
    foreach ($file in @("$app/VERSION","$fixture/prueba.exe")) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    }
    foreach ($dir in @($app,"$fixture/Programs",$fixture)) {
        if (Test-Path -LiteralPath $dir) { [IO.Directory]::Delete($dir) }
    }
}
