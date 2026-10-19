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
semilla sale idéntica. **Configurar** regresa al formulario para cambiar
programas, colores, tablero, semilla o rondas. Cada partida se guarda en
`bitacoras/`.

Cada turno se anima:

| Acción | Animación |
|---|---|
| Turno de un tanque | recuadro amarillo; el cañón gira hacia la dirección que usa |
| `AMT` | ráfaga de tres balas trazadoras y chispas donde pega |
| `MISIL` | mira roja sobre la casilla, misil en arco con estela de humo y explosión |
| `MINA` | la mina sale del tanque y se asienta; un pulso rojo al armarse |
| Pisar una mina | explosión grande |
| `MOV` | el tanque se desliza; contra la pared, rebota con chispas |
| `DAÑAR` o choque | el tanque se lanza contra el otro y regresa |
| `RADAR` | haz verde; pulso rojo si encontró un tanque, gris si es la pared |
| `ESCUDO` | anillo azul que se expande |
| Daño, curación, bloqueo | cifra flotante: `−10` en rojo, `+20` en verde, «bloqueado» en azul |
| Destrucción | explosión y humo; queda la refacción |
| `IF` falso | una ✗ gris |

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
pared, minas y misiles propios). El CSV tiene una fila por partida.

Después de cada ronda se muestran sus eventos, el tablero y el panel de
estado:

```
=== Ronda 3 =================================
  #3 explorador  L4: MOV(O)
      explorador avanza al O (8, 6) -> (7, 6)
  #1 cazador  L4: RADAR(E)
      cazador explora al E: pared a 2

     1   2   3   4   5   6   7   8
  1   .   .   .   .   .   .   .   .
  2  2^   .   .   .   .   .   .   .
  3   *   .   .   .   .   .   .   .
  4   .   .   .   .   .   .  1>   .
  ...

#1 cazador     [##########] 100          minas 3 misiles 3 rep 1  daño    0  L4 RADAR(E)
#2 defensivo   [##########] 100          minas 2 misiles 3 rep 1  daño    0  L4 RADAR(N)
```

| En el tablero | Significa |
|---|---|
| `1>` | tanque 1; la flecha es su cañón, que apunta a la última dirección usada |
| `[1>]` | tanque 1 con el escudo activo |
| `*` / `o` | mina armada / mina que aún no se arma |
| `+` | refacción |

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
instruccion := MOV(d) | AMT(d) | RADAR(d) | DAÑAR(d)
             | MISIL(x, y) | MINA | ESCUDO | REPARAR | ESPERAR
             | IF condicion THEN accion

condicion   := RADAR(d) cmp entero  |  VIDA cmp entero
accion      := AMT(d) | MISIL(x, y) | ESCUDO | REPARAR

d           := N | S | E | O
cmp         := >  |  <  |  >=  |  <=  |  ==
```

Cada instrucción consume exactamente un turno, incluida la que no produce
efecto porque su condición resultó falsa.

Las posiciones iniciales de los tanques se sortean, pero el orden de los
turnos es rotativo: gira una posición en cada ronda, de modo que nadie
conserva la ventaja de actuar primero y el escudo dura siempre lo mismo
(ver [`docs/DECISIONES.md`](docs/DECISIONES.md)).

| Instrucción | Efecto |
|---|---|
| `MOV(d)` | Avanza una casilla. Con pared sufre 5 puntos; con un tanque, choque de 15 a ambos |
| `AMT(d)` | Ametralladora: 10 puntos al primer enemigo de esa dirección. Munición ilimitada |
| `MISIL(x,y)` | 30 puntos al tanque de esa coordenada. Tres por partida |
| `MINA` | Mina en la casilla actual; se arma dos turnos después y causa 25 puntos. Tres por partida |
| `DAÑAR(d)` | Embiste al tanque contiguo: 15 puntos a ambos |
| `ESCUDO` | Inmunidad hasta el siguiente turno del tanque |
| `RADAR(d)` | Distancia al primer elemento: positiva si es enemigo, negativa si es pared |
| `REPARAR` | Recupera 20 puntos de vida. Un solo uso por partida |
| `ESPERAR` | No hace nada y cede el turno |
| `VIDA` | Vida restante; solo dentro de una condición |
| `IF ... THEN ...` | Ejecuta la acción si la condición se cumple |

Ejemplo (`tanques/defensivo.txt`):

```
# Defensivo — torreta: no se mueve, vigila los cuatro lados y se protege
IF RADAR(N) > 0 THEN AMT(N)
IF RADAR(E) > 0 THEN AMT(E)
IF RADAR(S) > 0 THEN AMT(S)
IF RADAR(O) > 0 THEN AMT(O)
IF VIDA < 50 THEN ESCUDO
IF VIDA < 40 THEN REPARAR
```

Dos consejos para escribir programas, que salen de medir cien partidas:

- **No hace falta un `RADAR` antes del `IF`.** El `IF RADAR(d)` explora por
  su cuenta si no hay lectura previa en esa dirección (D-01), y así la
  lectura es la del momento y no la de un turno antes.
- **Los recorridos deben volver a su punto de partida.** `MOV` no se admite
  dentro de un `IF`, así que un tanque no puede esquivar la pared al verla;
  si avanza siempre hacia el mismo lado, se pasa la partida chocando.
- **`AMT(d)` a secas rinde lo mismo que `IF RADAR(d) > 0 THEN AMT(d)`.** El
  `IF` también gasta el turno, así que si no hay blanco se pierde igual; sin
  `IF` al menos se ve la ráfaga.
- **Las minas y los recorridos cerrados no se llevan.** Un tanque que vuelve
  a su punto de partida acaba pisando la mina que dejó ahí. El `minador`
  avanza hacia el este y nunca regresa a una columna que ya dejó.

### Tolerancias del validador

El profesor evaluará el simulador cargando sus propios archivos, así que el
validador acepta variaciones razonables de escritura:

- Mayúsculas o minúsculas indistintamente (`mov(n)` = `MOV(N)`)
- Espacios de sobra (`MISIL ( 3 , 5 )`)
- `DAÑAR` y `DANAR`
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
