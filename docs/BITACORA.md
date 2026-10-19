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
