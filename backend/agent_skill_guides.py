"""Initial process guides for the project skill library."""

BASE = {
    'descripcion': """Primera lectura visual pendiente. Abre la foto limpia y un recorte representativo. Describe en lenguaje cotidiano cómo se ven las fibras, el fondo y los bordes. Identifica la imagen de cada observación y dónde se ve. Si una textura puede confundirse con un borde, explica qué detalle permite distinguirlos y cuándo conviene dejar la medida pendiente. Guarda las observaciones verificadas en esta ficha y añade las diferencias que encuentres entre imágenes del proyecto.""",
    'scribbles': """Preparar el campo
Lee el proyecto, la imagen y los parámetros de la propuesta. Toma de la ejecución la cantidad o cobertura solicitada. Comprueba el tamaño de la foto de biblioteca y usa sus coordenadas para dibujar. Excluye la leyenda, el borde instrumental y la barra de escala. Conserva el borrador manual como referencia separada hasta cerrar la propuesta.

Decidir qué pintar
Recorre primero el campo completo para localizar hebras gruesas, hebras finas y fondo de distintas texturas. Amplía las regiones granulosas. Para fibra, sigue el eje y los dos flancos antes y después del tramo. Las bandas claras dentro de una hebra ancha siguen perteneciendo a la fibra mientras queden entre esos flancos. Para halo, identifica una franja exterior que acompaña al mismo borde. Una variación de brillo aislada también puede ser grano o una partícula.

Adaptar la pincelada
Elige ancho y longitud por tramo en la foto de trabajo. En una fibra gruesa, localiza ambos flancos y ensancha la pincelada hasta aprovechar el interior reconocible. Sigue la curva mientras puedas seguir ambos bordes. Cuando la hebra se estreche, divide el trazo y reduce el pincel; conserva también las fibras finas que puedas seguir. En halo, sigue la franja exterior del mismo lado y acorta o estrecha el trazo donde se pierda su límite.

En fondo despejado, delimita una zona continua de fondo y pinta una banda amplia o varias pasadas contiguas dentro de ella. Alarga y ensancha mientras los laterales y extremos sigan sobre fondo reconocible. Detente antes de hebras tenues, halos o partículas. El grano justifica acortar una marca donde impide distinguir la clase; compruébalo de nuevo en la zona siguiente.

Antes de usar la máscara, alterna foto limpia y etiquetas guardadas en las mismas coordenadas. Busca el interior ancho o el claro de fondo más desaprovechado, y una hebra fina o un halo en riesgo de quedar cubiertos. Si cabe una pincelada mayor con margen visible, amplía ese tramo, guarda y vuelve a mirarlo. Si solo caben marcas finas, señala dónde y qué borde las limita. Entrega al coordinador la versión de la skill, el ID del mapa o máscara, los píxeles por clase y las coordenadas de esos ejemplos. La cantidad y cobertura objetivo vienen de los parámetros.

Resolver dudas y comprobar la máscara
Guarda la primera pasada sobre la foto limpia. En una curva ambigua, compara el recorte en contexto con una vista enderezada de la misma hebra y vuelve a situar el tramo en el original. Si se pierde el flanco, hay un artefacto similar a fibra o las vistas discrepan, recorta la parte dudosa y déjala sin etiqueta. Cuando esté configurada una segunda opinión, úsala para localizar discrepancias después de fijar la propuesta. Inspecciona el mapa de etiquetas guardado superpuesto al original. Al obtener la máscara binaria, comprueba en particular si el halo engrosó los bordes o si desaparecieron hebras finas.

Aprender de la revisión
Conserva la procedencia y la versión de la propuesta. Compara con los trazos manuales solo en el solapamiento etiquetado y comprueba el esquema de clases de los borradores antiguos. Registra cobertura por clase, confusiones, tramos excluidos y veredictos individuales. Una zona manual sin pintar queda fuera del denominador. Contrasta cada nueva regla en otro campo, incluyendo regiones donde la versión anterior acertaba.""",

    'circulos': """Elegir dónde medir
Lee la imagen, la ejecución, la máscara seleccionada y el máximo de círculos de sus parámetros. Reparte las propuestas entre tramos distinguibles del campo útil, incluyendo hebras finas y gruesas. Si varios centros caen en la misma porción continua, conserva el que mejor muestre ambos flancos. Al agotarse los tramos fiables, registra la cobertura alcanzada. Una serie de círculos en la misma hebra cuenta como varias observaciones de esa hebra.

Repartir los centros por zonas y por hebras
Antes de elegir los círculos, recorre la foto limpia completa, incluida la periferia, sin la cartela. Usa una cuadrícula orientativa (por ejemplo 4 × 4) para localizar zonas con fibras medibles. Sigue también las hebras visibles que atraviesan varias celdas. Si la máscara o la lista automática omitió una de ellas, inspecciona un recorte de la foto original y propón un centro donde puedas seguir sus dos flancos.

Haz una primera pasada por las distintas zonas y hebras medibles. Da prioridad a una hebra visible que todavía carece de centro aunque su celda ya contenga círculos sobre hebras vecinas. En las pasadas siguientes, entre candidatos de igual calidad, prefiere el tramo más alejado de los centros elegidos y evita repetir la misma porción de fibra. En una hebra larga busca otro tramo separado solo después de considerar las demás. Deja libres el fondo, los haces y las uniones ambiguas.

Antes de guardar, superpón un centro por círculo sobre la foto completa. Los cuatro contactos de borde corresponden a una sola medición. Revisa los claros más grandes y sigue las hebras largas sin centro. Si encuentras un tramo con cuatro cruces fiables y ya alcanzaste el objetivo, sustituye una propuesta redundante de un grupo denso y valida los contactos del nuevo círculo. Conserva las marcas aprobadas. Entrega el recuento de centros por zona y la razón visual de las omisiones relevantes.

Ajustar el disco en la foto original
Sigue una sola fibra antes de la entrada y después de la salida del círculo. Centra el disco sobre el eje y ajusta el radio para dejar visibles el ancho completo y fondo a cada lado. Recorre el perímetro y el interior. Cada flanco de esa misma hebra debe cortar el perímetro dos veces. Una unión, un haz o un vecino pueden producir cuatro transiciones en la máscara aunque la figura encierre más de una fibra.

Aplicar la revisión experta
«Multifibra» corresponde a un cruce, ramal o haz. «Doble fibra» indica dos hebras separadas por fondo dentro del disco. «No hay fibra» incluye fondo, halo y partículas cuyo supuesto borde desaparece al seguirlo en el original. «Fibra incompleta» abarca dos fallos: si falta un lateral, recentra o amplía el disco; si sobra fibra o entra una estructura vecina, reduce el radio o busca otro tramo. Comprueba otra vez ambos flancos tras cada ajuste. Cuando la causa precisa quede indeterminada, conserva la etiqueta del revisor.

Contrastar y guardar
Alterna la foto limpia y la máscara de scribble, de agente o combinada que indique la ejecución. Comprueba la resolución antes de transferir centro y radio. Conserva los círculos dibujados o corregidos por la persona y trabaja sobre los pendientes del proyecto con su ID de geometría. Guarda propuesta, imagen, ejecución y geometría en LOCO. Si se mueve el centro o cambia el radio, vuelve a determinar sus puntos de borde. Si se eliminó una geometría, respeta su eliminación.

Entregar a Cruces
Pasa los círculos vigentes a la skill Cruces y deja identificados los que requieren revisión. Registra por separado candidatos, rechazos por motivo, círculos pendientes y diámetros medidos. Para evaluar una mejora, compara los motivos de error en marcas revisadas individualmente y vigila qué tipos de fibra quedaron fuera al hacer la selección más estricta.""",

    'cruces': """Recuperar el círculo correcto
En Detección de fibras y bordes, parte de los círculos pendientes de la ejecución solicitada. Identifica proyecto, imagen, ejecución, ID de geometría, centro y radio en píxeles nativos. Reutiliza contactos ya revisados cuando correspondan a la misma geometría. Incluye los círculos dibujados a mano. Lee el recorte original con un margen suficiente para seguir la fibra fuera del disco; amplía el campo si hay una bifurcación o un artefacto cerca.

Localizar entrada y salida
Oculta la superposición y sigue los dos flancos de una sola hebra en la foto. En una entrada válida se ven los dos extremos del ancho; en la salida deben reaparecer esos mismos flancos. Ubica en el perímetro los extremos de ambos arcos ocupados por fibra. El resultado son cuatro contactos, dos por flanco. La curvatura y una entrada oblicua pueden romper la simetría. Usa la continuidad de los flancos para emparejar los puntos.

Resolver candidatos en exceso
Superpón la máscara seleccionada para proponer transiciones y comprueba el cambio de intensidad en la foto suavizada cerca de cada una. Vuelve al original para decidir el borde físico. Cuando haya muchos puntos juntos en un arco, sigue ese flanco desde fuera del círculo hasta el perímetro. Descarta las transiciones explicadas por el borde exterior del halo, una banda interna, grano o una hebra vecina. Un punto sostenido solo por la máscara queda como tentativo. Si dos interpretaciones siguen siendo plausibles, registra el arco dudoso y deja el círculo pendiente. Evita completar el conjunto por simetría o por proximidad a los puntos de mayor contraste.

Medir fibras con contraste interno
En una hebra ancha o estriada, oculta la máscara y los puntos. Sigue cada flanco desde fuera del círculo y compara varios cortes transversales cercanos, a ambos lados del centro. En cada corte avanza desde el fondo o halo exterior hacia la fibra. Una banda clara u oscura que sigue dentro de la estructura a lo largo de esos cortes pertenece a su interior, incluso si produce el salto de intensidad más fuerte. Prolonga ambas orillas exteriores hasta sus cuatro cruces con el perímetro. Comprueba en la foto limpia que el segmento de diámetro abarca toda la anchura reconocible y termina en esas dos orillas.

Cuando la persona señala cruces, relaciona esas marcas con el perímetro del círculo guardado y comprueba los otros contactos siguiendo los mismos flancos. Si las orillas delimitan varias hebras inseparables, identifica el resultado como ancho exterior de un posible haz. Si falta una orilla reconocible en la foto o hay dos interpretaciones igualmente plausibles, deja el círculo en revisión.

Verificar y entregar a medición
Marca cada contacto confirmado con un punto rojo pequeño sobre el contorno. Comprueba alternando foto y superposición que son posiciones distintas de la geometría vigente. Guarda sus coordenadas, el ID del círculo y las dudas separadas. Si cambian centro o radio, descarta los contactos anteriores para esa geometría y vuelve a localizarlos. Entrega los conjuntos confirmados al editor de Medición de diámetros de LOCO. Inspecciona que el cuadrilátero siga los dos flancos y que el segmento de diámetro atraviese el ancho de la hebra.

Comprobar la escala y aprender
Comprueba la escala guardada de esa imagen. En las micrografías TEM, calibra con la barra inferior completa. En una regla graduada, marca el centro de la primera graduación y el de la última. En una barra continua, marca sus dos extremos. Guarda una sola vez el valor y la unidad impresos. Una barra de diez intervalos rotulada 1 µm mide 1 µm de extremo a extremo. Registra cualquier discrepancia con la cartela. Si aparece un valor extremo en Análisis, abre su intervalo en el histograma y vuelve al círculo original para distinguir un problema de contactos de uno de calibración. Conserva por separado los contactos confirmados, tentativos, corregidos y pendientes. Al proponer otra versión, documenta qué señal visual habría cambiado la decisión y compruébala en otra micrografía.""",
}
