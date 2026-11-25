# Guerra de tanques

Simulador de combate autónomo entre tanques sobre un tablero de dos
dimensiones. Cada tanque ejecuta un programa escrito en un lenguaje de
instrucciones reducido; el usuario no controla ninguna unidad, solo observa el
desarrollo de la partida.

Proyecto de la asignatura **Sistemas Interactivos** — Facultad de Ingeniería,
UAEMéx. Semestre 2026-B.

---

## Estado

| Módulo | Estado |
|---|---|
| Direcciones y coordenadas | Terminado |
| Analizador léxico | Terminado |
| Analizador sintáctico y validador | Terminado |
| Configuración de la partida | Terminado |
| Motor de simulación | Terminado |
| Vista de consola | Terminado |
| Interfaz gráfica | Terminado |
| Bitácora de partida | Terminado |
| Torneo de partidas | Terminado |

El avance detallado está en [`docs/BITACORA.md`](docs/BITACORA.md) y las
decisiones de diseño, con su motivo, en
[`docs/DECISIONES.md`](docs/DECISIONES.md).

```
$ python3 -m pytest tests/ -q
226 passed
```

## Requisitos

- Python 3.11 o posterior
- `pytest` para ejecutar las pruebas (`pip install pytest`)

Tkinter viene incluido en la instalación estándar de Python. En algunas
distribuciones de Linux hay que instalarlo aparte (`sudo apt install
python3-tk`).

## Uso

Validar un programa de tanque:

```bash
python3 main.py validar tanques/cazador.txt
python3 main.py validar tanques/*.txt --detalle
```

El validador revisa el archivo completo y reporta **todos** los errores de una
vez, con su número de línea. Devuelve código de salida 1 si encontró alguno.

Abrir la interfaz gráfica (menú, configuración y ventana de partida):

```bash
python3 main.py ventana
python3 main.py ventana --config config_dinamico.json   # partida de exhibición
```

La **partida de exhibición** (`config_dinamico.json`) junta cuatro tanques
escritos para que se luzcan las animaciones, en un tablero de 6 × 6 donde se
cruzan más seguido. Las reglas son las mismas de `config.json`; solo cambian
el tablero, el límite de rondas (150) y los tanques:

| Tanque | Qué se ve |
|---|---|
| `artillero` | torreta: barre con el radar, dispara a los cuatro lados y lanza misiles al centro |
| `embestidor` | va y viene por su fila disparando hacia donde avanza; choca con quien se cruce |
| `minador` | avanza hacia el este sembrando minas detrás de sí |
| `patrulla` | recorre un cuadro de 2 × 2 disparando en todas direcciones, con un misil por vuelta |

A velocidad 5 cada ronda de cuatro tanques dura unos 4 segundos; entre 7 y
8 se ve igual de bien y va el doble de rápido.

En la ventana, **Iniciar** reproduce la partida sola a la velocidad elegida,
**Pausar** la detiene en el siguiente turno, **Una ronda** avanza de una en
una y **Reiniciar** vuelve a jugar la misma partida, que con la misma
semilla sale idéntica. Los cuatro van en una fila bajo el tablero; lo demás
(volver a la configuración, terminar, ir al menú principal y el sonido) está
en el menú ☰ de arriba a la derecha. Cada partida se guarda en
`bitacoras/`.

La ventana se puede maximizar o poner en pantalla completa: el tablero
crece con ella (es lo que más espacio toma) y va centrado junto al
escuadrón, cuya columna crece poco y tiene tope; la configuración y la
portada también se centran y se acomodan al tamaño. Al volver a la ventana
normal todo regresa a su tamaño de siempre.

**Programar un tanque dentro del juego.** El botón **Programar** de cada
tanque (y **Editar** en el visor de un programa) abre el editor del juego,
sin pasar por el Bloc de notas:

- Se escribe una instrucción por línea y se revisa mientras se escribe: el
  margen marca ✓ (bien escrita) o ✗ (con error); las líneas con error se
  pintan de rojo, el motivo aparece debajo (un clic lleva a la línea) y en
  un globo al pasar el ratón, y un aviso dice si todo el programa está bien.
- A la derecha están las **instrucciones disponibles**; un clic inserta una.
- **Aleatorio** escribe un programa válido al azar que luego se puede
  modificar como cualquier otro.
- **Guardar** (Ctrl+S) lo guarda en `tanques/` con el nombre elegido y se lo
  asigna al tanque. Si quedan líneas con errores, avisa antes de guardar.

Todas las ventanas emergentes tienen el diseño del juego, sin cuadros de
Windows: las confirmaciones (las que borran, reemplazan o pierden cambios
van en rojo), los avisos de error, el selector de color (paleta, tanque de
muestra y código #RRGGBB) y el selector de programas, que recorre carpetas,
dice si cada programa es válido y lo muestra con colores antes de elegirlo.

En el formulario, cada programa se revisa en cuanto se elige: el aviso de
la fila dice cuántas instrucciones tiene o cuántos errores, y un clic en el
aviso rojo los muestra. Abajo hay dos paneles:

- **Campo de batalla**: una miniatura del tablero con su medida; ancho y
  alto con − y +, un eslabón que los mantiene iguales y medidas rápidas
  (4, 6, 8, 10 y 12). También el límite de rondas y la semilla (el dado
  sortea otra). **Por omisión no hay límite**: se juega hasta el último
  tanque en pie; si los tanques se quedan en un ciclo, *Terminar la partida
  aquí* (menú ☰) la corta. Con el botón **∞** apagado se elige un límite;
  al llegar a él gana quien más daño infligió.
- **Arsenal y defensa**: daño de la ametralladora (con el daño que de ahí
  sale para misil, mina y choque), misiles, minas, armado de la mina,
  REPARAR y escudo. Cada uno tiene su color, su rango y una pista con
  perilla: se arrastra, se pulsa − o +, se gira la rueda del ratón o se
  escribe el número; si queda fuera del rango, la caja se pone roja.

**Valores por omisión** vuelve a los del reglamento.

El tablero es de **al menos 4 × 4**, que alcanza para 4 tanques; cada tanque
más pide una casilla más por lado (5 tanques: 5 × 5; 6 tanques: 6 × 6). Al
agregar un tanque, el formulario agranda el tablero si hace falta y lo dice
bajo el campo; `config.json` con un tablero más chico no se acepta.

Durante la partida, la tarjeta del tanque que juega se marca con su color,
la franja azul bajo la vida es el escudo que le queda, y al pasar el ratón
sobre una casilla se lee qué hay en ella. Al terminar, el cartel muestra la
clasificación.

| Tecla | Acción |
|---|---|
| Enter | iniciar (menú y configuración) |
| F1 | ayuda (menú) |
| Espacio | iniciar o pausar |
| → | una ronda |
| + / − | más rápido / más lento |
| R | reiniciar la misma partida |
| Esc | abre o cierra el menú ☰ (portada y partida) |

Cada turno se anima y cada arma suena:

| Acción | Animación | Sonido |
|---|---|---|
| Turno de un tanque | esquinas doradas; el cañón gira hacia la dirección que usa | |
| `AMT` | tres balas trazadoras con fogonazo, retroceso y casquillos; chispas donde pega | ráfaga; golpe metálico si pega en un tanque |
| `MISIL` | fogonazo y humo al salir, el lanzador retrocede; misil en arco con estela y mira giratoria | silbido del misil |
| Explosión | destello, bola de fuego, ondas, brasas que caen y humo; las grandes sacuden el tablero y dejan una quemadura que se borra con las rondas | explosión (grande o chica) |
| `MINA` | la mina sale volando del tanque a la esquina; al armarse, su luz parpadea | clic y pitido; doble pitido al armarse |
| Pisar una mina | explosión grande | explosión |
| `MOV` | el tanque avanza dejando polvo y la huella de las orugas | motor |
| Choque | el tanque se lanza contra el otro (o la pared), el tablero tiembla y saltan chispas | motor y golpe de metal |
| `IF RADAR` | ondas en abanico y un haz verde; pulso rojo si encontró un tanque, gris si es la pared | ping del radar |
| `ESCUDO` | el hexágono cian se forma girando, con destellos | zumbido de energía |
| Daño | el tanque destella en rojo y se sacude; la cifra `−5` salta | |
| Escudo que bloquea | el hexágono destella y se ondula; lo absorbido en azul | zap |
| `REPARAR`, refacción | cruces verdes que suben; `+20` en verde | campanitas |
| Destrucción | explosión con dos réplicas y columna de humo; queda la refacción | explosión |
| Fin de la partida | cartel con la clasificación | fanfarria si hay ganador |
| `IF` falso | una ✗ gris | |

Entre turnos, las minas armadas laten, las refacciones brillan y el escudo
gira. La interfaz también suena, con el mismo estilo de consola
de mando: la portada arranca con un zumbido grave y un acorde dorado, y
entra la **música**, una marcha original al estilo de los arcades de guerra
de los noventa: metales en golpes cortos, bajo funky, guitarra con power
chords y batería con redobles. Sigue en bucle en todas las pantallas,
también durante la partida. El radar del título da un pulso cada vez
que pasa por arriba. Los botones hacen un tic al pasar el ratón y suenan al pulsarlos
según su jerarquía: el dorado confirma, *Volver* y *Salir* bajan de tono, el
resto hace clic y un botón apagado responde con un zumbido corto. Las teclas
suenan como el botón que reemplazan.

El sonido se controla solo desde el menú ☰ de arriba a la derecha, en
cualquier pantalla: **música** y **efectos** (armas, botones) se encienden y
apagan por separado, y la música tiene su volumen de 0 a 10 (− y +, un clic
en las barras o la rueda del ratón; subirla la enciende si estaba apagada).
Los sonidos se sintetizan al arrancar (no hay archivos de audio ni
dependencias nuevas) y se guardan en la carpeta temporal del sistema. En
Windows suenan con `winmm`; en macOS y Linux con `afplay`, `paplay` o
`aplay` si están instalados. Con la variable de entorno
`TANQUES_SIN_SONIDO=1` el juego queda en silencio.

**Menú de la partida.** El botón ☰ de arriba a la derecha (o Esc)
despliega el menú **sin pausar la partida**: sigue jugándose detrás y el
menú muestra la ronda al momento.

| Opción | Qué hace |
|---|---|
| Volver a la partida | cierra el menú |
| Pausar / Reanudar | detiene la partida o la deja seguir sola |
| Reiniciar la partida | la misma partida desde el principio |
| Volver a los tanques | regresa a la configuración |
| Terminar la partida aquí | la termina tal como está: gana el tanque en pie con más daño infligido (si coinciden, empate), se muestra la clasificación y la bitácora lo registra |
| Menú principal | regresa a la portada |

Abajo están la música (encendida o apagada, y su volumen) y los efectos.

La velocidad también estira o acorta las animaciones; en las velocidades
9 y 10 no se anima, para avanzar rápido.

Jugar una partida en la consola con los tanques de `config.json`:

```bash
python3 main.py jugar                       # todas las rondas seguidas
python3 main.py jugar --semilla 7           # otra semilla, otra partida
python3 main.py jugar --paso                # Enter avanza una ronda; q sale
python3 main.py jugar --pausa 0.3 --animar  # animada en el mismo lugar
python3 main.py jugar --resumen             # solo el resultado
python3 main.py jugar --bitacora            # además la guarda en bitacoras/
```

Jugar cien partidas con semillas consecutivas y resumir el equilibrio:

```bash
python3 main.py torneo                       # semillas 1 a 100
python3 main.py torneo --partidas 500 --csv lote.csv
```

El resumen separa las victorias por destrucción de las que se ganan por
desempate, y el daño causado a rivales del autoinfligido (choques con la
pared y minas propias). El CSV tiene una fila por partida.

Después de cada ronda se muestran sus eventos, el tablero y el panel de
estado:

```
=== Ronda 3 =================================
  #3 explorador  L4: MOV(O)
      explorador avanza al O (8, 6) -> (7, 6)
  #1 cazador  L4: IF RADAR(S) > 0 THEN AMT(S)
      cazador explora al S: pared a 5
      cazador: RADAR(S) > 0 es falso (-5)

     1   2   3   4   5   6   7   8
  1   .   .   .   .   .   .   .   .
  2  2^   .   .   .   .   .   .   .
  3   *   .   .   .   .   .   .   .
  4   .   .   .   .   .   .  1>   .
  ...

#1 cazador     [##########]  100            minas 3 misiles 3 rep 1  daño     0  L4 IF RADAR(S) > 0 THEN AMT(S)
#2 defensivo   [#########.] 92.5  esc 15    minas 3 misiles 3 rep 1  daño     5  L4 IF RADAR(O) > 0 THEN AMT(O)
```

| En el tablero | Significa |
|---|---|
| `1>` | tanque 1; la flecha es su cañón, que apunta a la última dirección usada |
| `[1>]` | tanque 1 con escudo (el panel dice cuántos puntos le quedan) |
| `*` / `o` | mina armada / mina que aún no se arma |
| `+` | tanque destruido: repara a quien pasa encima |

Cada tanque se identifica por su número, y el color de `config.json` solo
lo acompaña: sin color (`--sin-color`, una salida redirigida a archivo o la
variable `NO_COLOR`) la partida se sigue igual.

Ejecutar las pruebas:

```bash
python3 -m pytest tests/ -q
```

## El lenguaje de instrucciones

Cada tanque se programa en un archivo de texto, una instrucción por línea. Las
líneas vacías se ignoran y `#` marca un comentario.

```
instruccion := MOV(d) | AMT(d) | MISIL(d) | MINA(esq)
             | ESCUDO | REPARAR | ESPERAR
             | IF condicion THEN accion

condicion   := RADAR(d) cmp entero  |  V cmp entero
accion      := cualquier instrucción salvo otro IF

d           := N | S | E | O
esq         := NE | NO | SE | SO   (sin coma: una norte-sur y una este-oeste)
cmp         := >  |  <  |  >=  |  <=  |  ==
```

Todo se escribe en **mayúsculas**, también las direcciones: `mov(n)` es un
error. Cada instrucción consume exactamente un turno, incluida la que no
produce efecto porque su condición resultó falsa.

El daño no es una instrucción: es la consecuencia de las armas, las minas y
los choques. `RADAR` tampoco se usa suelto: solo existe como condición de un
`IF`, que explora en ese momento.

Las posiciones iniciales de los tanques se sortean, pero el orden de los
turnos es rotativo: gira una posición en cada ronda, de modo que nadie
conserva la ventaja de actuar primero y el escudo dura siempre lo mismo
(ver [`docs/DECISIONES.md`](docs/DECISIONES.md)).

| Instrucción | Efecto |
|---|---|
| `MOV(d)` | Avanza una casilla. Contra la pared sufre 12; contra un tanque, choque de 12 a los dos |
| `AMT(d)` | Ametralladora: daño base al primer tanque de esa dirección. Munición ilimitada |
| `MISIL(d)` | En línea recta como `AMT`, con el doble de daño. Gasta munición aunque no alcance a nadie |
| `MINA(esq)` | Lanza una mina a la esquina contigua, escrita sin coma; desde (2,2), `MINA(NO)` cae en (1,1). Se activa de inmediato y causa 1.5 veces la `AMT` |
| `ESCUDO` | Vida extra: absorbe daño hasta agotarse. Activarlo lo recarga, no lo acumula |
| `REPARAR` | Recupera vida. Un solo uso por partida |
| `RADAR(d)` | Solo en un `IF`: distancia al primer tanque (positiva) o a la pared (negativa) |
| `ESPERAR` | No hace nada y cede el turno |
| `V` | Variable con la vida restante; solo dentro de una condición (`IF V < 50 ...`) |
| `IF ... THEN ...` | Ejecuta la acción si la condición se cumple. La acción puede ser cualquier instrucción (`MOV`, `AMT`, `MISIL`, `MINA`, `ESCUDO`, `REPARAR`, `ESPERAR`), pero no otro `IF` |

Ejemplo (`tanques/defensivo.txt`):

```
# Defensivo — torreta: no se mueve, vigila los cuatro lados y se protege
IF RADAR(N) > 0 THEN AMT(N)
IF RADAR(E) > 0 THEN AMT(E)
IF RADAR(S) > 0 THEN AMT(S)
IF RADAR(O) > 0 THEN AMT(O)
IF V < 50 THEN ESCUDO
IF V < 40 THEN REPARAR
```

Además, pasar por encima de un tanque destruido repara de 15 a 35 puntos
al azar.

### Valores por omisión y rangos

Se cambian en `config.json` o en el formulario de la interfaz gráfica antes
de la partida. Fuera de rango, la partida no inicia.

| Valor | Por omisión | Rango |
|---|---|---|
| Vida | 100 | — |
| Daño de `AMT` | 5 | 5 a 20 |
| Daño de `MISIL` | `AMT` × 2 = 10 | derivado |
| Daño de `MINA` | `AMT` × 1.5 = 7.5, sin redondear | derivado |
| Choque contra pared / contra tanque | 12 / 12 a cada uno | — |
| Misiles | 3 | 0 a 10 |
| Minas | 3 | 0 a 10 |
| Rondas para armar la mina | 0 (inmediato) | 0 a 10 |
| `REPARAR` | +20, un uso | 15 a 30 |
| `ESCUDO` | 20 | 5 a 50 |
| Tanque destruido | +15 a +35 al azar | — |
| Tanques por partida | — | 1 a 6 |

Consejos para escribir programas, que salen de medir cien partidas:

- **Usa el radar para no chocar.** `MOV` se admite dentro de un `IF`, así
  que un tanque puede esquivar la pared al verla:
  `IF RADAR(N) < -1 THEN MOV(N)` solo avanza si hay espacio libre.
- **`AMT(d)` a secas rinde lo mismo que `IF RADAR(d) > 0 THEN AMT(d)`.** El
  `IF` también gasta el turno, así que si no hay blanco se pierde igual; sin
  `IF` al menos se ve la ráfaga. Con `MISIL` es al revés: conviene el `IF`
  para no gastar munición al vacío.
- **Las minas y los recorridos cerrados no se llevan.** Un tanque que pasa
  por la esquina donde lanzó una mina la pisa. El `minador` lanza sus minas
  hacia atrás (al oeste) y avanza hacia el este sin volver.

### Tolerancias del validador

El profesor evaluará el simulador cargando sus propios archivos, así que el
validador acepta variaciones razonables de escritura (pero no minúsculas):

- Espacios de sobra (`MINA ( NE )`)
- La esquina de `MINA` en cualquier orden (`MINA(EN)` = `MINA(NE)`)
- Finales de línea de Windows y marca BOM
- Archivos guardados en UTF-8 o en Latin-1

## Coordenadas

Se escribe `(x, y)` en base 1: `x` es la columna y `y` la fila. La columna 1 es
el oeste y la fila 1 el norte.

```
N disminuye y    S aumenta y    E aumenta x    O disminuye x
```

## Estructura

```
guerra-de-tanques/
├── main.py                       punto de entrada
├── config.json                   parámetros de la partida
├── src/tanques/
│   ├── config.py                 lectura y validación de config.json
│   ├── lenguaje/                 el intérprete, en dos fases
│   │   ├── tokens.py             categorías de token
│   │   ├── lexico.py             análisis léxico
│   │   ├── sintactico.py         análisis sintáctico y gramática
│   │   ├── instrucciones.py      Instruccion, Condicion, Programa
│   │   ├── errores.py            mensajes de error
│   │   └── interprete.py         fachada de las dos fases
│   ├── modelo/                   estado y reglas del juego
│   │   ├── direccion.py          direcciones y sus vectores
│   │   ├── tablero.py            límites y recorrido en línea recta
│   │   ├── entidades.py          Tanque, Mina, Refaccion
│   │   ├── acciones.py           una clase por instrucción
│   │   ├── eventos.py            lo que el motor publica
│   │   └── motor.py              ciclo de ronda, daño y término
│   ├── vista/                    presentación
│   │   ├── base.py               contrato común de las vistas
│   │   ├── consola.py            tablero, panel y registro en texto
│   │   ├── bitacora.py           la partida completa en un archivo
│   │   ├── sprites.py            tanques, minas y refacciones en Canvas
│   │   ├── animaciones.py        disparos, explosiones y movimientos
│   │   └── grafica.py            menú, configuración y partida en Tkinter
│   └── controlador/              coordinación de la partida
│       ├── partida.py            crea el motor y lo conduce con la vista
│       ├── torneo.py             lotes de partidas y su resumen
│       └── aplicacion.py         flujo de la interfaz gráfica
├── tanques/                      programas de ejemplo
├── tests/                        pruebas automáticas
└── docs/                         arquitectura, bitácora y decisiones
```

Es Modelo–Vista–Controlador con una capa más, `lenguaje/`, porque el
intérprete no pertenece al modelo del juego ni a su presentación: traduce
archivos de texto antes de que la partida empiece.

Las dependencias van en un solo sentido:

```
controlador/  →  modelo/, vista/, lenguaje/
lenguaje/     →  modelo/     (solo necesita las direcciones)
vista/        →  modelo/     (dibuja; no contiene reglas)
modelo/       →  nada        (salvo config.py, que no depende de nadie)
```

El motor reconoce las instrucciones por el nombre de su tipo, sin importar
`lenguaje/`, y busca en `acciones.py` la clase que la ejecuta. Añadir una
instrucción es escribir una clase nueva, sin tocar el motor.

La regla que más importa es que **el modelo no importa Tkinter**. Gracias a
eso el motor se puede probar sin abrir una ventana y se pueden ejecutar cien
partidas seguidas para medir el equilibrio del juego.

### El intérprete

| Fase | Entrada | Salida |
|---|---|---|
| Análisis léxico | una línea de texto | lista de tokens |
| Análisis sintáctico | lista de tokens | una instrucción validada |

El léxico recorre la línea carácter por carácter y clasifica cada pieza sin
juzgar si el conjunto tiene sentido; el sintáctico comprueba que los tokens
formen alguna producción de la gramática. La gramática completa está en el
encabezado de `lenguaje/sintactico.py`.

## Configuración

`"rondas_maximas": 0` (o `null`) en `config.json` quiere decir **sin
límite**: la partida sigue hasta que quede un tanque. Como en la consola y
en el torneo no hay botón para terminarla, ahí se usa un tope de seguridad
de 1000 rondas (en la consola, `--paso` juega sin tope porque `q` sale).

Todos los parámetros ajustables viven en `config.json`: tamaño del tablero,
vida, munición, daños, y las cuatro reglas que el reglamento dejaba abiertas
—modo del radar, orden de los turnos, armado de la mina y acreditación del
choque—, cada una explicada en [`docs/DECISIONES.md`](docs/DECISIONES.md).

Incluye también la **semilla aleatoria**: con la misma semilla, la partida se
reproduce de forma idéntica. Sin eso no es posible depurar ni comparar
resultados entre versiones.

Para ver cómo está interpretando el programa un `config.json` editado a mano:

```bash
python3 main.py config
```

## Equipo

- García Urbina, Iván Daniel
- Méndez Reyes, Arturo Dante
- Romero Martínez, Erick Raúl
- Suárez Solares, Josué Abisaí
