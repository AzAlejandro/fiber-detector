---
name: loco-revision
description: Revisar como coordinador los resultados guardados por un agente de LOCO antes de entregar una imagen procesada.
---

# Revisión del coordinador

1. Confirma proyecto, imagen, dimensiones de trabajo y última etapa solicitada. Reabre el resultado por ID. Comprueba la versión usada en el registro de la ejecución o de la lectura del subagente; si falta, indícalo.
   Consulta `GET /api/agent/target-review` con `project_id`, `image_id` y el `mask_id` o `run_id` entregado. Informa el objetivo guardado, el resultado y el margen. Para una propuesta en archivos, cuenta las etiquetas de fibra, halo y fondo sobre el campo útil y los círculos vigentes con los objetivos usados al pintar. Un objetivo vacío se informa como libre. Si queda fuera del margen, localiza qué puede corregirse con confianza o explica el límite visual.
2. **Scribbles.** Alterna la foto limpia y el mapa de etiquetas guardado. Elige tú un claro de fondo y una fibra ancha, si existen. ¿Cabe ensanchar o alargar la pincelada manteniendo toda su huella en la misma clase? Comprueba también una hebra fina y un halo: sigue sus curvas, laterales y extremos. Usa los píxeles por clase como contexto; el juicio de cobertura requiere mirar la foto.
3. **Etapas alcanzadas.** En la máscara busca fibras finas perdidas y halos incorporados. En los círculos sigue una sola hebra en la foto: cada flanco cruza dos veces el perímetro. Si se pidieron diámetros, verifica el segmento transversal y el registro en Análisis. En un recorte nativo comprueba que la escala de una regla graduada mida entre marcas consecutivas y que el valor corresponda a ese intervalo. Para una barra simple comprueba sus dos extremos y el valor completo.
4. Si algo falla, devuelve al subagente la coordenada, el defecto y el ajuste. Reabre la corrección y revisa los resultados que dependían de ella. Entrega lo comprobado y señala cualquier etapa pendiente o evidencia que falte.
