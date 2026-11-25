# Herramientas por etapa

Usa la API de la instancia conectada (5181 en escritorio, habitualmente 8011 en desarrollo). Comprueba `GET /api/agent/connection`. Por MCP, `conexion_loco`, `guia_loco`, `importar_imagen`, `ver_imagen` y `flujo_loco` dan acceso al motor local. Filtra las respuestas antes de mostrarlas al agente.

**Proyecto.** Consulta `GET /api/projects/list`. Si se solicita un proyecto nuevo, usa `POST /api/projects/upsert` con `name` y `active=true`; conserva el ID devuelto. Para cambiar al proyecto solicitado usa `POST /api/projects/activate` con `project_id`.

**Entrada.** Abre una sesión con `POST /api/session/new`. Importa con `POST /api/agent/images/import` (multipart: `session_id`, `project_id`, `file`). Para una imagen guardada usa `POST /api/library/load` con sesión, ID y `agent_view=true`. Ambas respuestas devuelven el ID y `payload.view`. Usa `overview_url` para ubicar tramos y detectar regiones que requieren ampliación. Para llevar el centro de un píxel de la vista al raster de LOCO, aplica por eje `(p + 0.5) * factor - 0.5`, con `native_per_view_xy`. Pide `crop_url?x=X&y=Y&w=W&h=H` en píxeles nativos; suma el origen del recorte a cada marca local. Comprueba zonas con fibras finas también fuera de los candidatos de la vista general.

**Escala.** Usa la calibración guardada de esa imagen. Si falta, revisa la barra horizontal en un recorte nativo y guarda extremos, longitud y unidad con `POST /api/diameter-research/calibration/save`. Si la escala sigue sin resolverse, conserva el diámetro en px y señala que falta calibrar.

**Skill de etapa.** Lee `active.version`, `active.execution_body` y `targets` de `GET /api/agent-training/{proyecto}/{tipo}/state`. Por MCP el texto resuelto llega en `active.body`. Los tipos son `scribbles`, `circulos` y `cruces`. En las plantillas se pueden usar `{{porcentaje_pintado}}`, `{{cantidad_circulos}}`, `{{tolerancia_puntos}}` y `{{tolerancia_circulos}}`. Al guardar una máscara o una ejecución, envía el objeto leído en `expected_targets`; si devuelve 409, relee la configuración.

**Scribbles y máscara.** Guarda los trazos de fibra, halo y fondo en coordenadas nativas con `POST /api/scribble/draft/save` (origen `modelo`). En `/api/agent/scribble-masks`, GET lista las máscaras de la imagen y el proyecto; POST genera una con el mapa de trazos. Conserva el ID que corresponde al borrador utilizado.

**Revisión del mapa guardado.** Para ese ID, abre `GET /api/agent/scribble-masks/{mask_id}/layers/scribble` (superposición) o `/layers/labels` (etiquetas). Compáralas con la foto limpia en las mismas coordenadas. La capa `/layers/mascara` muestra la segmentación derivada.

**Círculos y cruces.** `POST /api/agent/runs` acepta la fuente de máscara (`agente`, `scribble`, `ambas`), parámetros y círculos. Para una ejecución existente usa `GET /api/agent/runs/{run_id}`. Revisa en el original que los cuatro contactos pertenezcan a los dos bordes de una sola fibra. En los siguientes pasos, las rutas son relativas a `/api/diameter-research`.

**Diámetros.** Abre `POST /agent-editor/{run_id}` con sesión e imagen y recupera la geometría vigente. Para añadir contactos faltantes al editor abierto usa `POST /agent-editor/{run_id}/contacts`, con `contacts` por `geometry_id`. Para los pendientes `medir`, usa `POST /run` con `method_id=circle_square_mask_diameter`, `source_mode=prior_mask`, `prior_run_id=agent:{run_id}` y los centros como `points`. En `params`, usa `circle_square_seed_mode=manual_circle` y `circle_square_circles_by_point` con centro, radio, ID y `agent_contacts_xy` de cada geometría. El editor arma ese mismo lote en `buildCircleBatch` de `frontend/src/App.jsx`. Comprueba los cuatro vértices del cuadrilátero y el segmento transversal.

**Análisis.** Para `registrar`, recupera el ID del **run de medición** vigente y usa `POST /measurements/save-from-run`. Para consultar o verificar usa `GET /measurements/query` con `project_ids`, `image_ids`, `unit` e `include_uncalibrated=true`. Filtra los resultados por geometría cuando el pedido se limite a círculos concretos.
