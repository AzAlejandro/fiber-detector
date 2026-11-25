# Preparar una versión de escritorio

## Prueba previa

El flujo **Probar distribución de escritorio** en GitHub Actions recibe una versión candidata, compila la interfaz y el motor en Windows x64 y macOS Apple Silicon, instala dos versiones de prueba y usa un cliente MCP para comprobar que la segunda recupera el proyecto, la imagen y su calibración. Descarga los dos artefactos desde la ejecución para probar la interfaz. El flujo tiene acceso de lectura al repositorio. La publicación es un paso posterior.

Las ramas de ensayo `codex/distribucion-escritorio-*` ejecutan ese flujo al subirlas y toman el número del archivo `VERSION`. Los instaladores quedan como artefactos de la ejecución.

Para reproducir el empaquetado local hacen falta Node 22, npm, uv y Python 3.12 administrado por uv (`uv python install 3.12`). Windows utiliza el compilador de Inno Setup. Mac utiliza las herramientas de Xcode y `brew install libomp`. Usa una carpeta de salida nueva. Los dos archivos lock fijan las versiones y hashes de las dependencias del motor. Al cambiar dependencias, regenera cada lock con el comando de su cabecera y ejecuta la prueba de ambas plataformas.

**Windows PowerShell**

```powershell
$version = (Get-Content -Raw VERSION).Trim()
uv run --no-project --python 3.12 python desktop/build.py stage $version
$stage = (Resolve-Path stage).Path
ISCC.exe "/DStage=$stage" "/DReleaseVersion=$version" desktop/windows.iss
```

**macOS Apple Silicon**

```bash
uv run --no-project --python 3.12 python desktop/build.py stage "$(cat VERSION)"
bash desktop/empaquetar-mac.sh stage/LOCO.app stage/LOCO-macOS-arm64.dmg
```

La prueba de persistencia se puede repetir con `desktop/smoke.py` y el Python que contiene la instalación. Ejecuta `seed RUTA_APP CARPETA_DATOS VERSION` antes de actualizar y `verify RUTA_APP CARPETA_DATOS VERSION_NUEVA` después. Usa la misma carpeta aislada en ambos pasos. En Windows RUTA_APP contiene `launch.py`. En Mac corresponde a `LOCO.app/Contents/Resources`.

## Distribución pública

El número del producto se mantiene en `VERSION`. Sincroniza los manifiestos npm y el changelog al cambiarlo. Integra el desarrollo aprobado en `main`. Publica el tag estable `vX.Y.Z` sobre el commit exacto usado para compilar los instaladores y marca esa release como **Latest**. Si se promueven los mismos binarios de una candidata, comprueba los hashes de ambos y conserva el tag anterior para que sus enlaces sigan funcionando.

Para una entrega manual como v1.1.2, adjunta los binarios probados y un `SHA256SUMS.txt` que incluya los dos. Documenta el estado de firma de cada archivo y enlaza la guía de conexión. Para habilitar el actualizador automático, sigue además el proceso de firma siguiente.

1. Elige un tag estable `vX.Y.Z` que coincida con la versión compilada. En Windows firma el instalador con el certificado Authenticode del editor y sello de tiempo. Comprueba que `Get-AuthenticodeSignature` devuelve `Valid`.
2. En Mac, con el certificado Developer ID Application instalado, ejecuta el mismo script de empaquetado con `LOCO_SIGN_IDENTITY` y `LOCO_NOTARY_PROFILE` (perfil de credenciales de notarytool). Firma y notariza la aplicación y el DMG. Comprueba en un Mac que Gatekeeper acepta la aplicación descargada. Los artefactos de prueba generados sin credenciales sirven para validación interna.
3. En el borrador de GitHub Release adjunta **LOCO-Windows-x64.exe**, **LOCO-macOS-arm64.dmg**, **instalar-windows.ps1** e **instalar-mac.sh**, todos del mismo tag. Conserva aparte el ZIP de Docker si se distribuye esa edición. Comprueba nombres, hashes y aprobación de las pruebas antes de publicar como estable.
4. Cuando la release sea pública, ejecuta la [guía del agente](INSTALAR_ACTUALIZAR.md) en dos cuentas de prueba limpias y sobre una instalación de la versión anterior. Comprueba el proyecto y la calibración antes y después. Esta última prueba incluye la descarga desde GitHub y las firmas que recibe el usuario.
