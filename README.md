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
| Modelo de datos | Terminado |
| Intérprete y validador | Terminado |
| Motor de simulación | Por implementar |
| Interfaz gráfica | Por implementar |
| Bitácora de partida | Por implementar |

El avance detallado está en [`docs/BITACORA.md`](docs/BITACORA.md).

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

Ejecutar las pruebas:

```bash
python3 -m pytest tests/ -q
```

## El lenguaje de instrucciones

Cada tanque se programa en un archivo de texto, una instrucción por línea. Las
líneas vacías se ignoran y `#` marca un comentario.

```
instruccion := MOV(d) | AMT(d) | RADAR(d) | DAÑAR(d)
             | MISIL(x, y) | MINA | ESCUDO | RESTAURAR | ESPERAR
             | IF condicion THEN accion

condicion   := RADAR(d) cmp entero  |  VIDA cmp entero
accion      := AMT(d) | MISIL(x, y) | ESCUDO | RESTAURAR

d           := N | S | E | O
cmp         := >  |  <  |  >=  |  <=  |  ==
```

Cada instrucción consume exactamente un turno, incluida la que no produce
efecto porque su condición resultó falsa.

| Instrucción | Efecto |
|---|---|
| `MOV(d)` | Avanza una casilla. Con pared sufre 5 puntos; con un tanque, choque de 15 a ambos |
| `AMT(d)` | Ametralladora: 10 puntos al primer enemigo de esa dirección. Munición ilimitada |
| `MISIL(x,y)` | 30 puntos al tanque de esa coordenada. Tres por partida |
| `MINA` | Mina en la casilla actual; se arma dos turnos después y causa 25 puntos. Tres por partida |
| `DAÑAR(d)` | Embiste al tanque contiguo: 15 puntos a ambos |
| `ESCUDO` | Inmunidad hasta el siguiente turno del tanque |
| `RADAR(d)` | Distancia al primer elemento: positiva si es enemigo, negativa si es pared |
| `RESTAURAR` | Recupera 20 puntos de vida. Un solo uso por partida |
| `ESPERAR` | No hace nada y cede el turno |
| `VIDA` | Vida restante; solo dentro de una condición |
| `IF ... THEN ...` | Ejecuta la acción si la condición se cumple |

Ejemplo (`tanques/cazador.txt`):

```
# Cazador — agresivo: explora, dispara y se acerca
RADAR(S)
IF RADAR(S) > 0 THEN AMT(S)
MOV(S)
IF VIDA < 40 THEN RESTAURAR
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
├── main.py                 punto de entrada
├── config.json             parámetros de la partida
├── src/tanques/
│   ├── modelo.py           estructuras compartidas
│   ├── interprete.py       lectura y validación de programas
│   ├── motor.py            reglas del juego          (pendiente)
│   └── interfaz.py         ventana Tkinter           (pendiente)
├── tanques/                programas de ejemplo
├── tests/                  pruebas automáticas
└── docs/                   documento de arquitectura y bitácora
```

Los tres módulos se comunican por estructuras de datos fijadas de antemano: el
intérprete no conoce el tablero, el motor no conoce la interfaz y la interfaz
no contiene reglas.

## Configuración

Todos los parámetros ajustables viven en `config.json`, incluida la **semilla
aleatoria**: con la misma semilla, la partida se reproduce de forma idéntica.
Sin eso no es posible depurar ni comparar resultados entre versiones.

## Equipo

- García Urbina, Iván Daniel
- Méndez Reyes, Arturo Dante
- Romero Martínez, Erick Raúl
- Suárez Solares, Josué Abisaí
