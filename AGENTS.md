# LOCO

Para instalar, actualizar o conectar un agente, sigue [loco-instalacion](.agents/skills/loco-instalacion/SKILL.md). La versión oficial se consulta en la [última release estable](https://github.com/AzAlejandro/fiber-detector/releases/latest).

Para «instala LOCO», «actualiza LOCO» o «conecta mi agente», sigue [Instalar y actualizar](docs/INSTALAR_ACTUALIZAR.md). Comprueba la versión y la conexión antes de dar la tarea por terminada.

Para operar LOCO sobre imágenes o mediciones, el coordinador y cada subagente leen primero [loco-inicio](.agents/skills/loco-inicio/SKILL.md). El coordinador delega un archivo por subagente nuevo (`fork_turns="none"`). Un subagente que ya recibió un archivo ejecuta el pedido directamente.

Para desarrollo del programa, consulta [AGENT.md](AGENT.md).
