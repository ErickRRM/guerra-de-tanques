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
| Vista de consola | Por implementar |
| Interfaz gráfica | Por implementar |
| Bitácora de partida | Por implementar |

El avance detallado está en [`docs/BITACORA.md`](docs/BITACORA.md) y las
decisiones de diseño, con su motivo, en
[`docs/DECISIONES.md`](docs/DECISIONES.md).

```
$ python3 -m pytest tests/ -q
145 passed
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

Jugar una partida en la consola con los tanques de `config.json`:

```bash
python3 main.py jugar                  # todos los eventos, turno por turno
python3 main.py jugar --semilla 7      # otra semilla, otra partida
python3 main.py jugar --resumen        # solo el resultado
```

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

Ejemplo (`tanques/cazador.txt`):

```
# Cazador — agresivo: explora, dispara y se acerca
RADAR(S)
IF RADAR(S) > 0 THEN AMT(S)
MOV(S)
IF VIDA < 40 THEN REPARAR
```

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
│   ├── vista/                    presentación               (pendiente)
│   └── controlador/              coordinación de la partida
│       └── partida.py            carga los programas y crea el motor
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
