---
name: loco-inicio
description: Usar LOCO para procesar imágenes TEM, continuar una etapa o consultar diámetros en el proyecto activo. Punto de entrada del coordinador y del agente de cada imagen.
---

# Empezar en LOCO

Al importar, LOCO limita el lado mayor a 900 px y mantiene la proporción. Al reabrir una imagen se conserva su tamaño guardado. Usa los píxeles de esa copia de trabajo para trazos, círculos, recortes y calibración.

Antes de pintar o medir, lee la ficha «Lectura visual del proyecto» incluida en la skill de etapa. Si es la primera imagen o encuentras una diferencia importante, abre la foto limpia y un recorte. Describe en lenguaje cotidiano qué se ve, dónde se ve y cómo reconocer los dos bordes. Guarda el ejemplo con el nombre de la imagen según [herramientas](references/herramientas.md). Incorpora las correcciones humanas y circunscribe cada observación a las imágenes en las que se verificó.

Comprueba la escala antes de medir. En las micrografías TEM, calibra con la barra inferior completa. En una regla graduada, marca el centro de la primera graduación y el de la última. En una barra continua, marca sus dos extremos. Guarda una sola vez el valor y la unidad impresos. Una barra de diez intervalos rotulada 1 µm mide 1 µm de extremo a extremo. Contrasta la calibración con los metadatos de la copia de trabajo y registra cualquier discrepancia.

Las líneas agente y manuales dibujadas por el usuario se aceptan y cuentan en Análisis al trazarlas. Conserva las que tengan bordes dudosos y documenta el motivo con el ID de la geometría y la ejecución en Validación trazable. En Detección de fibras y bordes, «Para revisar» permite localizarlas. El usuario decide cuáles eliminar.

1. **Coordinador.** Antes de delegar, consulta `agent_model` en `conexion_loco` o `GET /api/agent/connection`. Al crear cada subagente, incluido el supervisor si se solicita, usa ese identificador en `model` y `fork_turns="none"`. Si el usuario indica otro modelo para el pedido, usa el que indique. Envía a cada subagente de imagen el pedido literal, un archivo o ID y el proyecto. Por defecto usa `payload.active_project_id` de `GET /api/projects/list`. Pregunta solo si el destino queda ambiguo.
2. **Subagente.** Usa una sesión propia. Consulta las imágenes guardadas con `GET /api/agent/worklist?project=…&image=…`. Importa los adjuntos por `POST /api/agent/images/import`. Para inspección visual abre `view.overview_url`; confirma trazos, bordes y escala en recortes nativos de `view.crop_url`. Guarda las marcas en coordenadas nativas.
3. Carga la skill activa con los objetivos resueltos del proyecto en cada etapa. En scribbles mide los píxeles etiquetados del campo útil y amplía zonas seguras si falta cobertura. En círculos recorre el campo útil por zonas sobre la foto limpia. Sigue las hebras visibles que aún carecen de centro, incluso si ya mediste otra hebra en la misma zona. Antes de repetir un tramo, revisa los huecos entre centros y propone círculos en otras hebras con ambos bordes distinguibles. Si la morfología impide alcanzar el margen, entrega la diferencia y la razón visual. Consulta [herramientas](references/herramientas.md) para la llamada concreta.
   En cruces, cuando haya bandas internas de distinto contraste, sigue las dos orillas exteriores sobre la foto limpia en cortes vecinos y confirma que el diámetro llega a ambas.
4. **Coordinador.** Antes de entregar una imagen procesada, aplica [loco-revision](../loco-revision/SKILL.md) a las etapas alcanzadas. Por API usa `GET /api/agent/guide?review=true`; por MCP, `guia_loco(revision=true)`.

| Pedido | Qué ejecutar y dónde terminar |
|---|---|
| «Procesa estas imágenes» | En Modo agente, scribbles → máscaras → círculos → cruces → diámetros. Guarda y verifica en Análisis. |
| «Pinta» / «obtén la máscara» | Skill `scribbles`. Guarda los trazos en Obtención de máscara. Genera la máscara si la pidió o si el flujo continúa. |
| «Detecta fibras» / «marca círculos» | Skill `circulos`. En Detección de fibras y bordes, usa la máscara configurada y guarda los círculos. |
| «Marca bordes/cruces» | Skill `cruces`. Completa los contactos pendientes de los círculos existentes, incluidos los manuales. |
| «Mide solo los diámetros» | Abre Medición de diámetros para los círculos vigentes. Si faltan cruces, completa únicamente esos con `cruces`. Si faltan todos los círculos, informa el requisito. |
| «Muéstrame los diámetros» / «histograma» | Consulta Análisis por proyecto e imagen. Es una lectura. |

Sigue `marcar_bordes → medir → registrar` desde la primera acción pendiente. Conserva los registrados y deja `revisar` para revisión explícita. Informa resultados, unidad y pendientes por imagen. Si se piden tokens, separa subagentes y coordinación.

Para repetir un ensayo en otro proyecto, crea el proyecto en la misma biblioteca de LOCO. Importa los TIFF con `independent_copy=true` y el ID del proyecto nuevo (por MCP, `copia_independiente=true`). Así cada ensayo conserva sus trazos, calibraciones y mediciones. Antes de entregar, abre ambos proyectos desde el mismo selector y comprueba en Análisis los recuentos y las escalas de cada uno.
