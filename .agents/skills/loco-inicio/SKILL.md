---
name: loco-inicio
description: Usar LOCO para procesar imágenes TEM, continuar una etapa o consultar diámetros en el proyecto activo. Punto de entrada del coordinador y del agente de cada imagen.
---

# Empezar en LOCO

Al importar, LOCO limita el lado mayor a 900 px y mantiene la proporción. Al reabrir una imagen se conserva su tamaño guardado. Usa los píxeles de esa copia de trabajo para trazos, círculos, recortes y calibración.

Comprueba la escala antes de medir. En una regla graduada, marca un solo tramo entre dos marcas consecutivas. Si la leyenda corresponde al tramo, usa el valor rotulado. Si corresponde a toda la regla, divide el valor entre el número de intervalos iguales. En una barra simple, marca ambos extremos y usa el valor completo. Si el usuario ya fijó el valor de un tramo para el proyecto, guarda ese valor directamente. Registra por separado cualquier discrepancia con la cartela. Cuando falte ese criterio, consulta la leyenda y los metadatos del instrumento.

1. **Coordinador.** Antes de delegar, consulta `agent_model` en `conexion_loco` o `GET /api/agent/connection`. Al crear cada subagente, incluido el supervisor si se solicita, usa ese identificador en `model` y `fork_turns="none"`. Si el usuario indica otro modelo para el pedido, usa el que indique. Envía a cada subagente de imagen el pedido literal, un archivo o ID y el proyecto. Por defecto usa `payload.active_project_id` de `GET /api/projects/list`. Pregunta solo si el destino queda ambiguo.
2. **Subagente.** Usa una sesión propia. Consulta las imágenes guardadas con `GET /api/agent/worklist?project=…&image=…`. Importa los adjuntos por `POST /api/agent/images/import`. Para inspección visual abre `view.overview_url`; confirma trazos, bordes y escala en recortes nativos de `view.crop_url`. Guarda las marcas en coordenadas nativas.
3. Carga la skill activa con los objetivos resueltos del proyecto en cada etapa. En scribbles mide los píxeles etiquetados del campo útil y amplía zonas seguras si falta cobertura. En círculos distribuye el objetivo entre tramos fiables. Si la morfología impide alcanzar el margen, entrega la diferencia y la razón visual. Consulta [herramientas](references/herramientas.md) para la llamada concreta.
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
