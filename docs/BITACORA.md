# Bitácora de desarrollo

Registro de lo que se hizo en cada sesión, qué decisiones se tomaron y qué
quedó pendiente. Se actualiza al cerrar cada paso.

---

## Paso 1 — Modelo de datos e intérprete

**16 de octubre de 2026**

### Qué se hizo

Se creó el repositorio y se implementaron los dos primeros módulos:
`modelo.py`, con las estructuras que comparten los tres componentes, e
`interprete.py`, que lee un archivo de texto y lo convierte en una lista de
instrucciones validadas.

Se empezó por aquí y no por el motor por dos razones. La primera es que el
intérprete es el módulo con el contrato más claro y puede probarse por
completo sin que exista nada más. La segunda es que es la pieza de mayor
riesgo: el profesor evaluará el simulador cargando sus propios archivos
`.txt`, de modo que un validador frágil hace fracasar la entrega aunque el
resto funcione.

### Archivos añadidos

```
src/tanques/modelo.py        Direccion, Tipo, Condicion, Instruccion, Programa
src/tanques/interprete.py    cargar(), analizar(), formato_errores()
tests/test_interprete.py     47 pruebas
tanques/*.txt                tres programas de ejemplo y uno con errores
main.py                      orden `validar`
config.json                  parámetros de la partida
README.md
```

### Decisiones tomadas

| Decisión | Resolución | Motivo |
|---|---|---|
| Lenguaje | Python 3 con Tkinter | Acordado con el equipo |
| Coordenadas | Base 1; `(x, y)` = (columna, fila); fila 1 al norte | Coincide con el documento de arquitectura |
| Validación | Recorre el archivo completo y reporta todos los errores | Un error por ejecución obligaría a corregir de uno en uno |
| Mayúsculas | El validador no las distingue | El archivo lo escribe una persona |
| `DAÑAR` / `DANAR` | Ambas grafías se aceptan | Evita que un teclado sin eñe invalide el archivo |
| Codificación | UTF-8 y, si falla, Latin-1 | El Bloc de notas de Windows guarda en Latin-1 |
| Coordenada del misil | Se valida contra el tamaño del tablero al cargar | Un misil fuera del mapa es un error de escritura, no de ejecución |

### Tolerancias que cubre el validador

Comprobadas con pruebas: mayúsculas y minúsculas, espacios de sobra dentro de
los paréntesis, comentarios con `#`, líneas vacías, finales de línea de
Windows, marca BOM al inicio del archivo, las dos grafías de `DAÑAR` y
archivos en Latin-1.

### Verificación

```
$ python3 -m pytest tests/ -q
47 passed in 0.08s
```

Salida real del validador con el archivo de errores deliberados:

```
Errores de sintaxis, la partida no inicia:
  con_errores.txt, línea 3: dirección inválida: 'X' (admitidas: N, S, E, O)
  con_errores.txt, línea 4: estructura IF inválida (use: IF RADAR(dir) > 0 ...)
  con_errores.txt, línea 5: acción no permitida en IF: 'MOV(N)'
  con_errores.txt, línea 6: instrucción desconocida o mal formada: 'MISIL(3)'
  con_errores.txt, línea 7: instrucción desconocida o mal formada: 'DISPARAR'
  con_errores.txt, línea 8: coordenada fuera del tablero: (99,99)
```

Las seis líneas con error se detectan en una sola pasada y las líneas válidas
del mismo archivo se reconocen igual.

### Pendiente para el paso 2

El motor necesita que antes se cierren estos puntos, heredados de la sección 8
del documento de arquitectura:

1. **¿`RADAR` consume un turno propio?** De ello depende si la instrucción
   suelta sirve de algo o si conviene que el `IF` explore por su cuenta.
2. **Duración exacta del escudo** con el orden de turnos sorteado: puede durar
   casi dos rondas o casi ninguna según el sorteo.
3. **Armado de la mina**: ¿dos rondas o dos turnos del propietario? Con orden
   aleatorio ambas medidas difieren.
4. **Acreditación del daño en el choque**: si el embestidor se anota el daño
   del rival, el propio o ambos. Afecta directamente al desempate.

Los cuatro pueden implementarse como opciones de `config.json` para no
bloquear el avance, pero conviene fijar el valor por omisión.

---

## Correcciones al primer reporte

**16 de octubre de 2026**

Retroalimentación recibida del profesor sobre el primer entregable y cómo se
atendió cada punto.

| Observación | Corrección |
|---|---|
| Revisar ortografía, faltan acentos | Se corrigió el nombre del profesor en la portada («Omar Díaz González Boyer»), se completaron los campos que iban en blanco y se unificaron los acentos de la gramática. El cuerpo del texto ya estaba acentuado. |
| El objetivo general no es el correcto | Se renombró a «Objetivo general» y «Objetivos específicos», se redactó en una sola oración con verbo, acción, contexto y finalidad, y se retiró el párrafo sobre aplicar conocimientos, que es justificación y no objetivo. |
| ¿Van a construir un intérprete lexicográfico? | Se añadió la sección 5.2, «Naturaleza del intérprete», que responde que sí y describe las dos fases —análisis léxico y análisis sintáctico— junto con la gramática en notación BNF. |
| No veo limitaciones de hardware, navegadores o SO | Se añadió la sección 4.3, «Limitaciones técnicas»: sistema operativo, entorno de ejecución, hardware mínimo, resolución de pantalla y la aclaración de que es una aplicación de escritorio, no web. |

### Consecuencia sobre el código

La sección 5.2 compromete una separación explícita entre análisis léxico y
análisis sintáctico. El intérprete del paso 1 validaba con expresiones
regulares por línea, lo que cumplía la misma función pero no exhibía las dos
fases por separado. **Atendido en el paso 2**, que lo reescribió como
`lexico.py` y `sintactico.py` dentro de la capa `lenguaje/`.

---

## Paso 2 — Arquitectura en capas, intérprete en dos fases y configuración

**16 de octubre de 2026**

### Qué se hizo

Tres cosas, en este orden:

1. Se reorganizó el proyecto en **cuatro capas** con dependencias en un solo
   sentido, en lugar de los tres módulos planos del paso 1.
2. Se reescribió el intérprete como **dos fases separadas** —análisis léxico y
   análisis sintáctico— tal como se comprometió en la sección 5.2 del reporte.
3. Se centralizaron todos los parámetros ajustables en `config.py` +
   `config.json`, incluidas las cuatro reglas que quedaban abiertas.

No se tocó el motor todavía: el paso 2 deja preparado el terreno para que el
paso 3 solo tenga que escribir reglas de juego.

### La arquitectura

```
lenguaje/   →  modelo/        (el intérprete solo necesita las direcciones)
controlador/ →  modelo/, vista/, lenguaje/
vista/      →  modelo/        (dibuja; no contiene reglas)
modelo/     →  nada
```

Es el patrón Modelo–Vista–Controlador con una capa más, `lenguaje/`, porque el
intérprete no es parte del modelo del juego ni de su presentación: es un
traductor que existe antes de que la partida empiece.

La regla que importa es que **el modelo no importa Tkinter**. Si lo hiciera,
no se podría probar el motor sin abrir una ventana, ni ejecutar cien partidas
seguidas para medir el equilibrio del juego. Por eso `vista/` definirá una
interfaz abstracta y el controlador decidirá si usa la versión gráfica o la de
consola.

### Separación en dos fases

| Fase | Archivo | Entrada | Salida |
|---|---|---|---|
| Léxico | `lenguaje/lexico.py` | una línea de texto | lista de tokens |
| Sintáctico | `lenguaje/sintactico.py` | lista de tokens | una `Instruccion` |
| Fachada | `lenguaje/interprete.py` | el archivo completo | `Programa` + errores |

El analizador léxico recorre la línea carácter por carácter y clasifica cada
pieza —palabra reservada, dirección, entero, operador relacional, paréntesis,
coma— sin juzgar si el conjunto tiene sentido. El sintáctico recibe esos
tokens y comprueba que formen alguna producción de la gramática, construyendo
la instrucción.

La gramática está escrita en el encabezado de `sintactico.py`, en la misma
notación del reporte. Ninguna producción es recursiva: la única anidación
posible es la acción dentro de un `IF`, que a su vez no admite otro `IF`. Por
eso basta un descenso recursivo de un nivel, sin tabla de análisis.

Lo que se gana con la separación, además de responder a la pregunta del
profesor: los mensajes de error indican línea y columna, y una sola pieza mal
escrita no invalida el resto de la línea.

### Las cuatro reglas abiertas, resueltas

Se resolvieron las cuatro preguntas que el paso 1 dejó pendientes. Cada una
quedó como opción de `config.json` con un valor por omisión, y el motivo está
escrito en [`DECISIONES.md`](DECISIONES.md).

| Pregunta | Decisión | Clave |
|---|---|---|
| ¿Qué lectura usa `IF RADAR(dir)`? | Modo híbrido: el registro si existe, exploración en el momento si no | `reglas.modo_radar` |
| Duración del escudo con orden sorteado | Se cambió el orden de turnos a rotativo; así el escudo dura siempre lo mismo | `reglas.orden_turnos` |
| ¿Mina: dos rondas o dos turnos propios? | Dos turnos del propietario — que con el orden rotativo equivalen a dos rondas | `reglas.mina.medida` |
| ¿A quién se acredita el choque? | Al embestidor, solo los 15 que causó | `reglas.acredita_choque` |

La segunda merece una nota: la pregunta era sobre el escudo, pero la causa
real era el sorteo del orden. Cambiar el orden a rotativo arregla el escudo y
de paso quita la ventaja permanente del tanque que actuaba primero. Las
posiciones iniciales siguen siendo aleatorias, como pidió el profesor.

### Archivos

```
src/tanques/modelo/direccion.py      Direccion con sus vectores
src/tanques/lenguaje/tokens.py       categorías de token y palabras reservadas
src/tanques/lenguaje/lexico.py       análisis léxico
src/tanques/lenguaje/sintactico.py   análisis sintáctico y gramática
src/tanques/lenguaje/instrucciones.py  Instruccion, Condicion, Programa
src/tanques/lenguaje/errores.py      mensajes de error en un solo lugar
src/tanques/lenguaje/interprete.py   fachada de las dos fases
src/tanques/config.py                Configuracion y lectura de config.json
src/tanques/vista/                   (preparada, vacía)
src/tanques/controlador/             (preparada, vacía)
tests/test_lexico.py                 19 pruebas
tests/test_sintactico.py             51 pruebas
tests/test_config.py                 17 pruebas
```

Se eliminaron `modelo.py`, `interprete.py` y `test_interprete.py` del paso 1.
`main.py` ganó la orden `config`, que imprime la configuración tal como la
entiende el programa; sirve para comprobar que un `config.json` editado a mano
se está leyendo como se cree.

### Verificación

```
$ python3 -m pytest tests/ -q
87 passed in 0.13s
```

Se comprobó además que la reescritura no cambió el comportamiento: los tres
programas de ejemplo siguen dando el mismo número de instrucciones y
`con_errores.txt` sigue reportando los mismos seis errores en las líneas 3 a 8,
con los mismos mensajes.

### Pendiente para el paso 3

El motor de simulación, en `modelo/`: `tablero.py`, `entidades.py`,
`acciones.py` —una clase por acción, para poder añadir instrucciones sin
modificar el motor— y `motor.py` con el ciclo de ronda. Después la vista y el
controlador.

Queda por confirmar con el equipo la **fecha de entrega final**: una nota
anterior dice 10 de noviembre y el cronograma del documento de arquitectura
marca el 22. También sigue vacía la tabla de reparto de trabajo de ese
documento.

---

## Paso 3 — Motor de simulación

**19 de octubre de 2026**

### Qué se hizo

Se implementó el motor en `modelo/` siguiendo el ciclo de ronda de la
Figura 4 y el contrato de la sección 2.2 del documento de arquitectura:
`paso()`, `ronda()`, `estado()`, `terminada()` y `resultado()`, más
`jugar()` para correr la partida completa. El motor no imprime nada:
devuelve eventos, que es lo que consumirán la bitácora y la interfaz.

`main.py` ganó la orden `jugar`, que corre una partida en la consola con los
tanques de `config.json`.

### Archivos

```
src/tanques/modelo/tablero.py      límites y recorrido en línea recta
src/tanques/modelo/entidades.py    Tanque, Mina, Refaccion
src/tanques/modelo/eventos.py      Evento y sus tipos
src/tanques/modelo/acciones.py     una clase por instrucción, con registro
src/tanques/modelo/motor.py        ciclo de ronda, daño, minas y término
src/tanques/controlador/partida.py carga los programas y crea el motor
tests/test_motor.py                58 pruebas
```

### Cómo quedó la dependencia con `lenguaje/`

El modelo no importa nada de `lenguaje/`: las acciones se buscan por
`instruccion.tipo.name` y la condición del `IF` solo necesita `fuente`,
`direccion` y `evalua()`. Así se respeta la regla «modelo → nada». La única
excepción es `config.py`, que no depende de nadie y que todas las capas
pueden leer.

### Decisiones

Se añadieron **D-05** (la mina se pisa al entrar) y **D-06** (resolución de
los casos borde de la sección 7.3) en [`DECISIONES.md`](DECISIONES.md). La
más llamativa: con las reglas actuales el escudo nunca puede estar activo al
pisar una mina.

### Verificación

```
$ python -m pytest tests/ -q
145 passed
```

Las pruebas cubren las reglas de cada instrucción, las opciones de
`config.json` de D-01 a D-04, los casos borde de la sección 7.3 y la
reproducibilidad: la misma semilla da la misma partida evento por evento.

### Primer lote de 100 partidas (semillas 1 a 100)

| Tanque | Victorias | Daño infligido | Daño autoinfligido |
|---|---|---|---|
| cazador | 72 | 645 | 8255 |
| defensivo | 22 | 4000 | 6390 |
| explorador | 6 | 3780 | 4775 |

99 partidas terminaron por destrucción y una por desempate; duraron 86
rondas de media (de 45 a 118).

El dato que importa es la última columna: **el daño autoinfligido es más del
doble del causado a los rivales**. Es justo el síntoma que la sección 8 pedía
vigilar: los programas de ejemplo se pasan la partida chocando contra las
paredes, y el cazador gana sobre todo porque sobrevive, no porque ataque. No
dice nada todavía sobre el equilibrio entre armas; primero hay que escribir
programas que no se estrellen.

### Pendiente para el paso 4

1. La vista de consola y la interfaz Tkinter, alimentadas con
   `Motor.estado()` y los eventos.
2. La bitácora de partida en archivo, a partir de los mismos eventos.
3. Una orden `torneo` que automatice el lote de 100 partidas.
4. El escenario de referencia de la sección 7.2: diez rondas escritas a mano.
5. Mejorar los programas de ejemplo para que no choquen con las paredes.

---

## Paso 4 — Vista de consola

**19 de octubre de 2026**

### Qué se hizo

Se implementó la primera vista, la de consola, y con ella el contrato común
que también cumplirá la interfaz Tkinter:

```
Vista.inicio(estado, eventos)    la partida está colocada
Vista.ronda(estado, eventos)     terminó una ronda; False si el usuario sale
Vista.fin(estado, resultado)     la partida terminó (resultado None si se salió)
```

El controlador ganó `ejecutar(motor, vista)`, que juega ronda por ronda y le
entrega a la vista el estado y los eventos. Ni el motor ni el controlador
saben si del otro lado hay una consola o una ventana.

### Lo que muestra

Después de cada ronda: el registro de eventos, agrupado por turno bajo la
instrucción que lo produjo; el tablero; y el panel de estado con la vida, la
munición, el daño infligido y la línea en ejecución de cada tanque. Al final,
el ganador, el motivo y la clasificación.

Se aplicaron los criterios de la sección 6.1 del documento de arquitectura:

| Criterio | Cómo se cumple en la consola |
|---|---|
| Codificación redundante | Cada tanque lleva su número; el color de `config.json` solo lo acompaña |
| Estado siempre visible | El panel se redibuja completo en cada ronda |
| Correspondencia directa | El mismo `#n` aparece en el tablero, el panel y el registro |
| Orientación del cañón (fig. 8) | Una flecha junto al número: `1>`, `1^`, `<`, `v` |
| Mina armada o no (fig. 9) | `*` armada, `o` sin armar |

Todo se dibuja en ASCII porque la consola de Windows no garantiza los
caracteres de caja. El color usa ANSI de 24 bits; en Windows se activa el
modo de terminal virtual y, si no se puede, se dibuja sin color. Tampoco hay
color si la salida va a un archivo o si existe la variable `NO_COLOR`.

### Modos de `jugar`

| Opción | Efecto |
|---|---|
| (ninguna) | Todas las rondas seguidas, una debajo de otra |
| `--paso` | Espera Enter después de cada ronda; `q` sale |
| `--pausa S --animar` | Animación: redibuja en el mismo lugar cada `S` segundos |
| `--resumen` | Solo el tablero inicial, el final y el resultado |
| `--sin-color` | Fuerza la salida sin color |

### Archivos

```
src/tanques/vista/base.py          contrato abstracto Vista
src/tanques/vista/consola.py       VistaConsola y las funciones de dibujo
src/tanques/controlador/partida.py + ejecutar(motor, vista)
tests/test_vista_consola.py        19 pruebas
```

Las funciones de dibujo (`dibujar_tablero`, `dibujar_panel`,
`dibujar_eventos`) son puras: reciben el estado y devuelven texto. Por eso
se prueban sin terminal, comparando casillas concretas del tablero dibujado.

### Verificación

```
$ python -m pytest tests/ -q
164 passed
```

### Pendiente para el paso 5

1. La interfaz Tkinter, implementando el mismo contrato `Vista`.
2. La bitácora de partida en archivo, a partir de los mismos eventos.
3. Una orden `torneo` que automatice el lote de 100 partidas.
4. El escenario de referencia de la sección 7.2: diez rondas escritas a mano.
5. Mejorar los programas de ejemplo para que no choquen con las paredes.

---

## Paso 5 — Interfaz gráfica, bitácora, torneo y escenario de referencia

**19 de octubre de 2026**

### Qué se hizo

Los cinco pendientes del paso 4:

1. La **interfaz Tkinter**, con las tres pantallas de los bosquejos.
2. La **bitácora de partida** en archivo.
3. La orden **`torneo`**, que automatiza el lote de partidas.
4. El **escenario de referencia** de la sección 7.2.
5. **Programas de ejemplo** que no se estrellan contra la pared.

### Interfaz gráfica

`python main.py ventana` abre una sola ventana que pasa por las tres
pantallas de los bosquejos: el menú de inicio (fig. 10), la configuración
(fig. 11) y la partida (fig. 12). Los sprites, los íconos y los colores
siguen las figuras 6, 7 y 9; todo se dibuja con primitivas del Canvas, sin
imágenes, así que el tablero escala con el tamaño de casilla.

La ventana de partida implementa el mismo contrato `Vista` que la consola,
y el controlador la conduce con el mismo `ejecutar()`. Para lograrlo, cada
método espera la orden del usuario con `wait_variable`, que sigue atendiendo
los eventos de Tk mientras espera. No hizo falta un segundo bucle de juego
para la ventana.

El contrato cambió en un punto: `Vista.inicio()` ahora puede devolver
`False` para cancelar la partida antes de la primera ronda. En la ventana,
la partida no empieza hasta pulsar «Iniciar» y se puede salir antes. Las
vistas que devuelven `None` siguen funcionando igual.

**Resolución.** El reporte promete funcionar a 1280 × 720. En vez de fijar
un tamaño, la ventana mide lo que ocupan los controles y el panel con las
fuentes reales del equipo, y el tablero se queda con el alto que sobra.
Medido con cuatro tanques:

| Pantalla y escala | Ventana | Casilla |
|---|---|---|
| 1920 × 1080 al 125 % | 1182 × 822 | 65 px |
| 1440 × 900 al 125 % | cabe en 810 px de alto | 63 px |
| 1280 × 720 al 100 % | 907 × 623 | 45 px |

### Bitácora y torneo

La bitácora es una vista más (`VistaBitacora`) y recibe los mismos eventos
que la pantalla. Lleva la semilla y las reglas vigentes, lo necesario para
reproducir la partida. `VistaMultiple` reparte la partida entre varias
vistas a la vez. La ventana guarda cada partida en `bitacoras/`; en consola
se pide con `jugar --bitacora`.

`torneo` sigue la sección 8 del documento de arquitectura: separa las
victorias por destrucción de las que se ganan por desempate, y el daño
causado a rivales del autoinfligido. Con `--csv` guarda una fila por partida.

### Escenario de referencia

`tests/test_escenario_referencia.py` tiene tres tanques con posiciones fijas
y las diez primeras rondas calculadas a mano, turno por turno, antes de
correr el motor. El escenario pasa por ametralladora, misil bloqueado por el
escudo, misil a una casilla vacía, `IF` falso por un límite exacto
(`80 < 80`), una mina propia que se arma y estalla, una segunda mina,
`REPARAR` y la rotación de turnos. **El motor coincidió con el cálculo a mano
en las diez rondas al primer intento.**

### Programas de ejemplo

Se reescribieron los tres. Dos cambios de fondo:

- **Recorridos cerrados.** `MOV` no se admite dentro de un `IF`, así que un
  tanque no puede esquivar la pared al verla. La solución es que sus salidas
  y vueltas se compensen: el cazador patrulla un cuadro de 2 × 2, el
  explorador uno de 3 × 3 y el defensivo no se mueve. Si un tanque arranca
  junto a la pared, choca un par de veces y su circuito queda corrido hacia
  dentro para siempre.
- **Sin `RADAR` suelto.** Con el modo híbrido (D-01), `IF RADAR(d)` explora
  por su cuenta y con una lectura más fresca. El `RADAR` previo solo gastaba
  un turno.

Lote de 100 partidas, antes y después:

| | Antes | Después |
|---|---|---|
| Daño autoinfligido por partida (los tres) | 194.2 | 5.9 |
| Daño a rivales por partida (los tres) | 84.3 | 197.8 |
| Rondas por partida, media | 86 | 179 |
| Partidas decididas por desempate o empate | 1 | 75 |

| Tanque | Victorias | Por destrucción | Por desempate |
|---|---|---|---|
| defensivo | 53 | 11 | 42 |
| cazador | 23 | 8 | 15 |
| explorador | 14 | 6 | 8 |

Hay 10 empates.

**Hallazgo nuevo:** con tanques que ya no se destruyen solos, el combate
resulta lento. La mayoría de las partidas llega al límite de 200 rondas y
la decide el desempate, justo el riesgo que la sección 8 asociaba a un
máximo de rondas demasiado alto. La torreta defensiva gana sobre todo por
desempate: dispara en cuatro direcciones sin moverse. Es una decisión de
equilibrio para el equipo —más daño por disparo, un tablero más chico o
menos rondas— y no se tocó `config.json`.

### Un problema de las pruebas en Windows

Las pruebas de la ventana fallaban de forma intermitente al crear la
ventana de Tk («couldn't read file init.tcl: No error»). Se aisló la causa:
ocurre solo cuando pytest captura la salida a nivel de descriptor de
archivo. Con `--capture=sys` pasan siempre (seis corridas seguidas sin
fallos), y quedó fijado en `pytest.ini`. Las pruebas de la ventana se saltan
solas si no hay pantalla.

### Archivos

```
src/tanques/vista/bitacora.py        VistaBitacora
src/tanques/vista/base.py            + VistaMultiple; inicio() puede cancelar
src/tanques/vista/sprites.py         tanques, minas y refacciones en Canvas
src/tanques/vista/grafica.py         AppGrafica, configuración, VentanaPartida
src/tanques/controlador/torneo.py    jugar_torneo, resumen y CSV
src/tanques/controlador/aplicacion.py  flujo menú → configuración → partida
tests/test_escenario_referencia.py   7 pruebas
tests/test_bitacora_torneo.py        13 pruebas
tests/test_grafica.py                15 pruebas
pytest.ini                           captura de salida compatible con Tk
tanques/*.txt                        cazador, defensivo y explorador nuevos
```

También se corrigió el cuarto color de reserva del motor: era `#B91C1C`,
el rojo de la mina armada, y debía ser `#6D4C9F`, el del tanque 4.

### Verificación

```
$ python -m pytest -q
199 passed
```

### Pendiente

1. Decidir con el equipo el ajuste de equilibrio que pide el hallazgo de
   arriba y volver a medir con `torneo`.
2. Confirmar con el profesor las decisiones D-01 a D-06.
3. Empaquetar el ejecutable para la entrega.

---

## Paso 6 — Animaciones en la ventana de partida

**19 de octubre de 2026**

### Qué se hizo

Hasta el paso 5 la ventana solo se redibujaba al final de cada ronda: un
disparo, una mina o un choque no se veían ocurrir, solo su resultado. Ahora
cada turno se anima.

| Acción | Animación |
|---|---|
| Turno de un tanque | Recuadro amarillo; el cañón gira hacia la dirección que usa |
| `AMT` | Ráfaga de tres balas trazadoras y chispas donde pega (tanque o pared) |
| `MISIL` | Mira roja sobre la casilla, misil en arco con estela y explosión |
| `MINA` | La mina sale del tanque y se asienta; pulso rojo al armarse |
| Pisar una mina | Explosión grande |
| `MOV` | El tanque se desliza; contra la pared rebota con chispas |
| `DAÑAR` o choque | Se lanza contra el otro tanque y regresa |
| `RADAR` | Haz verde; pulso rojo si encontró un tanque, gris si es la pared |
| `ESCUDO` | Anillo azul que se expande |
| Daño, curación, bloqueo | Cifra flotante: `−10` rojo, `+20` verde, «bloqueado» azul |
| Destrucción | Explosión y humo; después aparece la refacción |
| `IF` falso | Una ✗ gris |

Además, una mina bajo un tanque se dibuja pequeña en la esquina de la
casilla. Antes quedaba tapada y no se sabía que estaba ahí.

### Cómo se hizo

- **Un turno a la vez.** `Vista` ganó un método opcional, `turno()`, y
  `ejecutar()` avanza con `motor.paso()` en vez de `motor.ronda()`. La
  consola no lo implementa y sigue dibujando por rondas. La bitácora ahora
  escribe por turnos, para que una partida interrumpida a media ronda quede
  registrada hasta donde se jugó. El motor ganó la propiedad
  `ronda_completa`.
- **Las animaciones no deciden nada.** Se reproducen sobre el estado
  anterior y al final se dibuja el estado real del turno. Si una animación
  tuviera un error de cálculo, el tablero quedaría igual de correcto.
- **Algunos eventos traen la dirección.** El motor añade `direccion` en
  `datos` a la ráfaga sin blanco, al choque con la pared y al embiste al
  vacío; sin ella no había forma de saber hacia dónde dibujarlos.
- **`animaciones.py` no importa Tkinter.** Recibe el canvas y una función
  `esperar(ms)`: en la ventana es `wait_variable` con un temporizador, de
  modo que los botones responden durante la animación. Tk no tiene
  transparencia; lo que se desvanece se mezcla con el color del fondo.
- **Velocidad.** El deslizador también estira o acorta las animaciones. En
  9 y 10 no se anima: avance rápido. «Pausar» ahora detiene la partida en el
  siguiente turno, no al final de la ronda; «Una ronda» juega la ronda
  completa sin detenerse entre turnos.

### Verificación

Se jugó con la ventana real un escenario de cuatro tanques que usa todas las
acciones, capturando cuadros a media animación, y se revisaron las capturas.
De esa revisión salió un ajuste: la mina recién puesta era demasiado pequeña
y no se distinguía, así que ahora cae grande desde el tanque y termina con
una onda roja.

```
$ python -m pytest -q
221 passed
```

`tests/test_animaciones.py` (20 pruebas) comprueba que cada acción dispara
su animación, que cada efecto borra lo que dibuja, que la animación se corta
si el usuario sale y que la pausa a media ronda se detiene en el siguiente
turno.

---

## Paso 7 — Partida de exhibición

**19 de octubre de 2026**

### Qué se hizo

Con las animaciones del paso 6 quedó a la vista que los programas de ejemplo
casi no hacían nada vistoso. Se midió en 50 partidas con `config.json`:

| Por partida | Ejemplos actuales | Exhibición |
|---|---|---|
| `IF` falsos (✗ gris) | 324 | 34 |
| Ráfagas (con o sin blanco) | 18 | 186 |
| Barridos de radar | 0 | 50 |
| Misiles | 0 | 5.8 |
| Minas sembradas | 0 | 3 |
| Choques entre tanques | 1.4 | 2.1 |
| Tanques destruidos | 1.1 | 1.9 |
| Rondas | 186 | 142 |

Se añadieron cuatro tanques y `config_dinamico.json`, que los junta en un
tablero de 6 × 6 con 150 rondas como máximo. Las reglas son las mismas de
`config.json` (hay una prueba que lo comprueba); los tres programas de
ejemplo y `config.json` no se tocaron.

```
python main.py ventana --config config_dinamico.json
```

### Lo que se aprendió del lenguaje

- **`AMT(d)` a secas rinde lo mismo que `IF RADAR(d) > 0 THEN AMT(d)`.** El
  `IF` también consume el turno: si no hay blanco, el turno se pierde de
  todas formas. Disparar sin condición causa el mismo daño y además se ve.
  De ahí salía casi todo el «aburrimiento» de los ejemplos.
- **Las minas no se llevan con los recorridos cerrados.** Como `MOV` no cabe
  en un `IF` y el programa se repite, un tanque que vuelve a su punto de
  partida termina pisando la mina que dejó ahí. Por D-05 el escudo nunca lo
  protege, y armar la mina tarda justo lo mismo que ir y volver. La única
  forma de sembrar sin pisarse es avanzar sin regresar: el `minador` termina
  cada vuelta una columna más al este. El precio es que, al llegar a la pared
  oriental, choca contra ella en cada vuelta (37 puntos autoinfligidos por
  partida), y si empieza a menos de dos columnas de esa pared puede pisar la
  última mina que siembre ahí (0.6 veces por partida).
- **Los misiles van a casillas fijas.** No hay coordenadas relativas: el
  artillero apunta a (3,4) y la patrulla a (4,3). Si alguno empieza justo en
  su casilla objetivo, se lo lanza a sí mismo. Está anotado en sus
  comentarios.

### Verificación

Se jugó la exhibición en la ventana real (semilla 42, velocidad 5) y se
revisaron capturas: ráfagas en las cuatro direcciones, radar, impactos,
siembra y armado de minas, todo en las primeras seis rondas. A velocidad 5
cada ronda de cuatro tanques dura unos 4 segundos, así que una partida
completa toma varios minutos; entre 7 y 8 va el doble de rápido.

```
$ python -m pytest -q
226 passed
```
