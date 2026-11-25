# LOCO Detector - Uso rapido

Esta version permite ejecutar LOCO Detector sin instalar Python, Node ni dependencias manualmente.

## Procesar imÃ¡genes con el agente

Con el proyecto abierto, adjunta los archivos y escribe **Â«ProcÃ©same estas dos imÃ¡genes en LOCOÂ»**. El agente usa el proyecto activo, continÃºa desde lo guardado y entrega los diÃ¡metros en AnÃ¡lisis. Para trabajar solo en una etapa, basta con decir **Â«Mide los diÃ¡metros de estos cÃ­rculosÂ»**. Para consultar mediciones existentes, di **Â«MuÃ©strame los diÃ¡metrosÂ»**.

Para repetir una prueba desde cero, indÃ­calo en la peticiÃ³n. Cada subagente procesa su propia copia y entrega sus imÃ¡genes para revisiÃ³n. En la comparaciÃ³n de tokens se distinguen entrada nueva, entrada en cachÃ© y salida. El trabajo compartido de coordinaciÃ³n se informa aparte. [Instrucciones del agente](../AGENTS.md)

Al importar una imagen nueva, el agente usa el mismo tamaÃ±o de trabajo que Scribble: hasta 900 pÃ­xeles en el lado mayor, manteniendo la proporciÃ³n. El archivo original se conserva. Al reabrir una imagen guardada, LOCO usa las dimensiones que ya tiene en la biblioteca. Para esas imÃ¡genes, la vista general del agente puede reducirse a 1024 pÃ­xeles y el zoom permite revisar el detalle de la copia guardada. Las marcas y la calibraciÃ³n usan pÃ­xeles de esa copia.

## Instalación de escritorio

Para Windows x64 y macOS con Apple Silicon, sigue la [guía de instalación y conexión del agente](INSTALAR_ACTUALIZAR.md).

## Requisitos del paquete Docker v1.0.0

Instala Docker Desktop:

https://www.docker.com/products/docker-desktop/

Despues de instalarlo, abre Docker Desktop y espera a que termine de iniciar.

## Docker en Windows

1. Descomprime `LOCO-detector-v1.0.0-release.zip`.
2. Entra a la carpeta descomprimida.
3. Haz doble click en `iniciar_loco_detector.bat`.
4. Espera a que se abra el navegador.
5. Si no se abre automaticamente, entra a `http://localhost:5178`.

Para cerrar LOCO Detector, haz doble click en `detener_loco_detector.bat`.

## Docker en macOS

1. Descomprime `LOCO-detector-v1.0.0-release.zip`.
2. Entra a la carpeta descomprimida.
3. Si macOS no permite abrir el archivo `.command`, abre Terminal en esa carpeta y ejecuta:

```bash
chmod +x iniciar_loco_detector.command
chmod +x detener_loco_detector.command
```

4. Haz doble click en `iniciar_loco_detector.command`.
5. Espera a que se abra el navegador.
6. Si no se abre automaticamente, entra a `http://localhost:5178`.

Para cerrar LOCO Detector, haz doble click en `detener_loco_detector.command`.

## Como cargar un proyecto

Si recibiste un archivo como `proyecto-exportado-desde-configuracion.zip`, abre LOCO Detector y entra a:

`Configuracion` -> `Exportar e importar`

Luego usa la opcion de importar proyecto.

## Si la interfaz aparece vacia

No significa que Docker haya fallado. Significa que la aplicacion abrio correctamente, pero todavia no has importado un proyecto.
```

## 7. Preparar una release nueva

Abre PowerShell en Windows o Terminal en macOS y entra a la raiz del repositorio.

En Windows:

```powershell
cd "C:\ruta\donde\clonaste\LOCO-detector"
```

En macOS, usa la ruta donde tengas clonado el repo:

```bash
cd ~/Documents/GitHub/LOCO-detector
```

Verifica que Docker Desktop este abierto:

```bash
docker info
```

Prueba que la app funciona desde el compose de desarrollo:

```bash
docker compose up --build -d
```

Abre:

```text
http://localhost:5178
```

Verifica que la interfaz abre y que puedes entrar a `Configuracion`. Luego detiene:

```bash
docker compose down
```

Construye las imagenes limpias:

```bash
docker compose build
```

Confirma que existen:

```bash
docker images
```

Debes ver algo equivalente a:

```text
loco-detector-backend    latest
loco-detector-frontend   latest
```
