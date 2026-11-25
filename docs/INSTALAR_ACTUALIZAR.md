# Instalar o actualizar LOCO con un agente local

Pedido de ejemplo: **«Instala LOCO desde github.com/AzAlejandro/fiber-detector y comprueba la conexión»**. Para futuras versiones basta **«Actualiza LOCO»**.

1. Identifica el sistema, la arquitectura y la modalidad instalada. La edición de escritorio está destinada a Windows x64 y macOS Apple Silicon (15 o posterior). Una instalación en Docker o un checkout de desarrollo conserva su propio almacenamiento: usa el procedimiento de esa modalidad. Si coexisten instalaciones y el pedido no identifica cuál, pregunta antes de actualizarlas.
2. Consulta la [última release estable](https://github.com/AzAlejandro/fiber-detector/releases/latest). El número tras la `v` del tag es la versión que debe devolver el motor. Si ya coincide, comprueba la conexión existente y registra el conector si falta. La edición Docker histórica se descarga desde [v1.0.0](https://github.com/AzAlejandro/fiber-detector/releases/tag/v1.0.0).
3. Lee las notas de esa release. Para instalar **v1.1.2**, descarga **LOCO-Windows-x64.exe** o **LOCO-macOS-arm64.dmg** y verifica el SHA-256 del archivo frente a su `digest` en la [API oficial](https://api.github.com/repos/AzAlejandro/fiber-detector/releases/latest). Esta edición es de instalación manual. Windows carece de firma Authenticode y macOS lleva firma ad hoc sin notarización. Conserva las comprobaciones de seguridad del sistema. Guarda cualquier edición en curso. En Windows abre el instalador. En Mac, si hay una versión anterior, detén su motor con `"$HOME/Applications/LOCO.app/Contents/MacOS/LOCO" stop`. Copia la aplicación del DMG a `~/Applications` y ábrela.
4. Para versiones que ofrezcan un **actualizador firmado del programa** y el script de instalación, descarga el script de la misma release y verifica su SHA-256 frente al `digest` publicado por GitHub. En Windows ejecuta `./instalar-windows.ps1 -Tag TAG` y en Mac `/bin/bash instalar-mac.sh TAG`, usando el tag consultado. Los scripts comprueban la firma del programa antes de instalarlo.
5. Comprueba **Configuración → Comprobar conexión con el agente**, o consulta `GET http://127.0.0.1:5181/api/agent/connection`. Verifica `application`, la versión publicada, `ready=true`, `skill=loco-inicio` y el proyecto activo. Un proyecto vacío es normal en una instalación nueva. Abre un proyecto existente después de la actualización y comprueba sus imágenes o mediciones.

## Conectar un agente

Cuando alguien pida «instala LOCO y comprueba la conexión», registra el conector que admita su agente local en esa misma instalación y ejecuta la comprobación. Para «actualiza LOCO», lee primero `guia_mantenimiento_loco` si el conector está disponible, anota la versión y el proyecto, y ejecuta el actualizador desde una terminal local. Reconecta el cliente tras el reinicio y comprueba que devuelve el mismo proyecto y la versión prevista.

Un agente con acceso al equipo puede leer `GET /api/agent/guide` en la misma dirección y usar la API local. Para un cliente con MCP local, registra LOCO una sola vez con transporte **stdio**. En Codex CLI:

**Windows, PowerShell**

```powershell
$app = Join-Path $env:LOCALAPPDATA 'Programs\LOCO Detector'
codex mcp add loco -- "$app\runtime\python.exe" "$app\launch.py" mcp
```

**Mac**

```sh
codex mcp add loco -- "$HOME/Applications/LOCO.app/Contents/MacOS/LOCO" mcp
```

Si ya existe la entrada, comprueba su ruta antes de cambiarla. En un chat nuevo, prueba `conexion_loco` y `guia_loco`. El conector inicia el motor cuando hace falta. La ruta de registro se conserva entre versiones. El chat web sin acceso local puede guiar a la persona por la instalación manual.

## Proyectos y recuperación

La edición de escritorio guarda `outputs/` y `data/` en **%LOCALAPPDATA%\LOCO Detector** o **~/Library/Application Support/LOCO Detector**. Los instaladores reemplazan los archivos del programa y sus skills distribuidas. Las skills aprendidas de cada proyecto, las calibraciones y los resultados viven en la carpeta de datos. Para una copia de seguridad completa, cierra LOCO y copia esa carpeta. Al pasar por primera vez desde el repositorio, copia sus carpetas `outputs/` y `data/` a una carpeta de datos de escritorio vacía, con ambos motores cerrados. Para un destino con datos, acuerda la importación antes de mezclar proyectos.

El desarrollo usa los puertos y las carpetas del checkout; aquí el diagnóstico está en `/api/agent/connection` del backend (habitualmente 8011). Actualiza un checkout limpio mediante avance rápido de su rama y vuelve a compilar/probar. Si hay cambios locales, consérvalos y acuerda cómo integrarlos. Para Docker sigue la [guía de la distribución Docker](GITHUB_RELEASES_WINDOWS_MAC.md) y conserva los volúmenes y las calibraciones durante el cambio de imágenes.
