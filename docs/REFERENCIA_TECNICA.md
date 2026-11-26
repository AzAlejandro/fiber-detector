# Referencia técnica de LOCO Detector

Instalación desde el código, detector por aprendizaje automático, rutas de la API y archivos de trabajo. Para usar la aplicación de escritorio, consulta la [guía de instalación y conexión](INSTALAR_ACTUALIZAR.md).

## Instalación de desarrollo en Windows

### Requisitos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

### Instalación paso a paso

```bat
git clone https://github.com/AzAlejandro/fiber-detector.git
cd fiber-detector
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### Arranque local en Windows

```bat
run_local.bat
```

### Arranque local manual

En la primera terminal, inicia el motor.

```bash
venv/Scripts/python app.py
```

En otra terminal PowerShell, conecta la interfaz a ese motor.

```powershell
cd frontend
$env:VITE_API_BASE = "http://127.0.0.1:8011"
npm run dev -- --port 5173 --host localhost
```

### Configuración de puertos

Los puertos se leen desde `.env` en la raíz del repo. No subas `.env` a Git.

```env
BACKEND_PORT=8011
BACKEND_HOST=127.0.0.1
FRONTEND_PORT=5173
FRONTEND_HOST=localhost
DEV_RELOAD=true
VITE_API_BASE=http://127.0.0.1:8011
```

Para diagnosticar puertos ocupados:

```powershell
.\tools\diagnose_ports.ps1
```

Para detener procesos locales del proyecto:

```powershell
.\tools\stop_servers.ps1
```

## Detector por aprendizaje automático

```text
Image -> Support Region -> Candidate Grid + Radii -> Feature Extraction
    -> Binary Model -> Multiclass Model -> Combined Filter
    -> Circle-NMS -> Spatial Filter -> Accepted Circles
    -> Diameter Measurement -> Calibration -> Distribution
```

| Paso | Descripción |
|---|---|
| Image | Imagen TEM cargada desde navegador o biblioteca. |
| Support Region | Región de soporte derivada desde máscara/scribbles aprobados. |
| Candidate Grid + Radii | Muestreo de centros y radios candidatos. |
| Feature Extraction | Extracción de patches, intensidad, gradientes y variables geométricas. |
| Binary Model | Clasificación inicial círculo válido / no válido. |
| Multiclass Model | Clasificación valid / crossing / other. |
| Combined Filter | Fusión de umbrales y criterios de aceptación. |
| Circle-NMS | Supresión de círculos redundantes mediante IoU/distancia. |
| Spatial Filter | Filtro espacial posterior para reducir falsos positivos. |
| Accepted Circles | Candidatos aceptados para revisión o medición. |
| Diameter Measurement | Medición por círculo, línea o máscara según método. |
| Calibration | Conversión px -> nm/um con escala por imagen. |
| Distribution | Métricas e histogramas exportables. |

## API local

La API corre por defecto en `http://127.0.0.1:8011`. En Docker se publica en el puerto configurado por `DOCKER_BACKEND_PORT`, normalmente `8011`.

### Agente conectado

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/agent/connection` | Consultar la conexión, el proyecto activo y el modelo para nuevos agentes. |
| GET | `/api/agent/guide` | Leer las instrucciones de trabajo. Con `review=true` devuelve la guía de revisión. |
| POST | `/api/agent/images/import` | Importar una imagen. Con `project_id` e `independent_copy=true` crea una copia para ese ensayo. |
| GET | `/api/agent/worklist` | Consultar el trabajo guardado por proyecto e imagen. |

### Session & Image

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/session/new` | Create new session |
| POST | `/api/image/load` | Load image into session |
| GET | `/api/library/images` | List saved images |
| POST | `/api/library/load` | Load saved image |
| POST | `/api/library/delete` | Delete saved image |
| POST | `/api/local-images/upload-browser` | Upload browser-selected image |

### Projects & Tags

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/projects/list` | List projects and active project |
| POST | `/api/projects/upsert` | Create or update project |
| POST | `/api/projects/activate` | Activate project |
| POST | `/api/projects/delete` | Delete project metadata |
| GET | `/api/projects/images` | List images by project view |
| GET | `/api/projects/tag-catalog` | List structured tag catalog |
| POST | `/api/projects/image/update` | Update image project/tags |

### Scribbles

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/scribble/draft/save` | Save scribble draft |
| GET | `/api/scribble/draft/load` | Load scribble draft |
| POST | `/api/scribble/draft/clear` | Clear scribble draft |

### Experiments & Review

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/experiments/catalog` | List available experiments |
| POST | `/api/experiments/run` | Run single experiment |
| POST | `/api/experiments/run-batch` | Run batch experiments |
| GET | `/api/results/list` | List experiment results |
| GET | `/api/results/get` | Get result details |
| GET | `/api/results/mask-thumb` | Get mask thumbnail |
| POST | `/api/review/mark` | Mark run decision/tier |
| GET | `/api/review/list` | List review metadata |
| GET | `/api/reports/export` | Export reports |

### Assist Models

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/assist-models/dataset/images` | List trainable images |
| GET | `/api/assist-models/list` | List assist models |
| POST | `/api/assist-models/train` | Train assist model |
| POST | `/api/assist-models/set-default` | Set default assist model |
| POST | `/api/assist-models/update-meta` | Update model metadata |
| POST | `/api/assist-models/delete` | Delete assist model |
| POST | `/api/assist-models/predict` | Predict class probabilities |
| POST | `/api/assist-models/predict-mask` | Predict mask |

### Diameter Research

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/diameter-research/points/update` | Update diameter points |
| POST | `/api/diameter-research/points/save` | Save diameter points |
| GET | `/api/diameter-research/points/load` | Load diameter points |
| GET | `/api/diameter-research/points/list` | List point files |
| POST | `/api/diameter-research/run` | Run diameter measurement |
| GET | `/api/diameter-research/results/list` | List diameter results |
| GET | `/api/diameter-research/results/get` | Get diameter result details |
| GET | `/api/diameter-research/reports/export` | Export report |

### LOCO Dataset, Training & Detector

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/diameter-research/loco-dataset/circles/load` | Load LOCO dataset circles |
| POST | `/api/diameter-research/loco-dataset/circles/sync` | Sync LOCO dataset circles |
| POST | `/api/diameter-research/loco-dataset/features` | Extract dataset features |
| POST | `/api/diameter-research/loco-dataset/save` | Save LOCO dataset |
| POST | `/api/diameter-research/loco-dataset/augment/preview` | Preview augmentation |
| POST | `/api/diameter-research/loco-dataset/augment/apply` | Apply augmentation |
| POST | `/api/diameter-research/loco-training/train` | Train LOCO models |
| POST | `/api/diameter-research/loco-training/tune` | Tune LOCO model |
| GET | `/api/diameter-research/loco-training/saved-models` | List saved LOCO models |
| POST | `/api/diameter-research/loco-training/save-model` | Save LOCO model |
| POST | `/api/diameter-research/loco-training/test-circles` | Test circles with model |
| POST | `/api/diameter-research/loco-models/detect-base` | Run base detector |
| POST | `/api/diameter-research/loco-models/apply-threshold` | Apply threshold |
| POST | `/api/diameter-research/loco-models/apply-nms` | Apply NMS |
| POST | `/api/diameter-research/loco-models/apply-spatial` | Apply spatial filter |
| POST | `/api/diameter-research/loco-models/measure-accepted` | Measure accepted circles |

### Calibration & Analysis

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/diameter-research/calibration/save` | Save scale calibration |
| GET | `/api/diameter-research/calibration/load` | Load scale calibration |
| GET | `/api/diameter-research/measurements/summary-by-image` | Measurement summary per image |
| POST | `/api/diameter-research/measurements/save-from-run` | Save internal measurements |
| GET | `/api/diameter-research/measurements/query` | Query measurements |
| GET | `/api/diameter-research/analysis/list` | List saved analyses |
| POST | `/api/diameter-research/analysis/save` | Save analysis |
| GET | `/api/diameter-research/analysis/export/download` | Download analysis export |

### Project Transfer

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/project-transfer/catalog` | Inspect exportable categories |
| POST | `/api/project-transfer/export/prepare` | Prepare export ZIP |
| GET | `/api/project-transfer/export/download` | Download export ZIP |
| POST | `/api/project-transfer/import/inspect` | Inspect import ZIP |
| POST | `/api/project-transfer/import/start` | Start import job |
| GET | `/api/project-transfer/import/progress` | Poll import progress |
| POST | `/api/project-transfer/import/apply` | Legacy synchronous import |

### Validation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/diameter-research/validation/case/upsert` | Create/update validation case |
| GET | `/api/diameter-research/validation/cases` | List validation cases |
| POST | `/api/diameter-research/validation/run-case` | Run validation case |
| GET | `/api/diameter-research/validation/export` | Export validation results |

## Archivos de trabajo

La distribución Docker persiste el trabajo en `outputs/`. Algunos flujos históricos y tests también usan `data/`.

```text
data/
├── calibration/          # Scale calibration files (*.json)
├── images/               # Loaded images
├── runs/                 # Diameter measurement runs
├── loco_dataset/         # LOCO training dataset
├── loco_training/        # Trained models
└── reports/              # Exported reports
```

```text
outputs/scribble_research/
├── library/              # Copias registradas de imágenes y metadata
├── projects/             # Proyectos, tags y proyecto activo
├── drafts/               # Scribbles guardados
├── runs/                 # Experimentos Scribble completos
├── assist_models/        # Modelos de asistencia Scribble
└── diameter_research/    # Dataset LOCO, modelos LOCO, mediciones y análisis
```

## Pruebas

Desde la raíz del repositorio, con el entorno Python activo, ejecuta `python -m pytest -q tests`.
