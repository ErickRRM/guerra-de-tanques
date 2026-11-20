# Registro de decisiones

Este archivo recoge las decisiones de diseño que no estaban fijadas por el
profesor y que hubo que resolver para poder programar. Cada una indica qué se
eligió, por qué, qué alternativa se descartó y con qué clave de `config.json`
se puede cambiar sin tocar el código.

Se registran por una razón práctica: dentro de dos semanas nadie recuerda por
qué una regla quedó así, y sin el motivo escrito la discusión se repite. Si
alguna resulta equivocada al probar el juego, se cambia el valor en
`config.json` y se anota aquí el motivo del cambio.

---

## D-00 · Correcciones del profesor (noviembre de 2026)

El profesor revisó las reglas y cambió varias. Las que eran decisiones
nuestras quedan **reemplazadas** y se marcan abajo; las demás siguen
vigentes. Lo que dijo:

| Corrección | Cómo quedó en el código |
|---|---|
| Todo en mayúsculas, incluso las direcciones | `mov(n)` es un error léxico; se avisa una vez por línea |
| `MISIL(dir)` en línea recta como `AMT`, sin `x,y` | Al primer tanque de la línea; gasta munición aunque falle |
| `DAÑAR` es consecuencia, no instrucción | Se quitó. El choque ocurre al moverse hacia un tanque |
| `IF RADAR` no necesita un `RADAR` antes | `RADAR` solo existe en la condición y explora al evaluarse. Reemplaza **D-01** |
| `ESCUDO` es configurable, como vida extra | Reserva de puntos que absorbe daño hasta agotarse. Reemplaza la inmunidad de un turno |
| `MINA(esq)` (sin coma: `MINA(NE)`) se lanza a la esquina contigua y se activa de inmediato | `rondas_armado = 0`; se puede configurar. Reemplaza **D-03** |
| Pasar sobre un tanque destruido repara de 15 a 35 | Es la «refacción» de antes con otro rango |
| `REPARAR`: 20, configurable de 15 a 30, un uso | Se mantiene como instrucción además del cadáver |
| Máximo 6 tanques | Se valida en `config.py` |
| `AMT` 5 (5 a 20); misil `AMT`×2; mina `AMT`×1.5 | Sin redondear: la vida puede quedar en 92.5 |
| Choque: pared 12, enemigo 12 | Los dos tanques reciben los 12 |
| Misiles y minas: 3, máximo 10 | Rango 0 a 10 |

### Lo que el profesor no fijó y decidimos nosotros

- **Valor del escudo: 20, configurable de 5 a 50.** Es el mismo valor que
  `REPARAR`, para que «vida extra» valga lo mismo que una reparación.
- **El escudo no se acumula.** Activarlo lo recarga hasta su valor; si ya
  está completo no hace nada. Acumularlo haría invencible a un programa que
  solo escribe `ESCUDO`.
- **El escudo absorbe cualquier daño**, incluida la pared y la mina. Antes
  la pared lo atravesaba; con el escudo como vida extra esa excepción ya no
  tiene sentido.
- **Lo absorbido por el escudo no se acredita** para el desempate: solo el
  daño que llega a la vida.
- **Mina fuera del tablero o sobre otra mina:** no pasa nada y no se gasta,
  igual que `REPARAR` con la vida completa.
- **Mina que cae sobre un tanque:** como se activa de inmediato, estalla en
  ese momento. Se acredita a quien la lanzó.
- **El rango de las rondas de armado es 0 a 10**, por si se quiere volver a
  una mina diferida.

---

## D-01 · Qué lectura usa `IF RADAR(dir) ...`  — *reemplazada por D-00*

Ya no existe el `RADAR` suelto: el `IF RADAR(dir)` explora siempre en el
momento de evaluarse, y la clave `reglas.modo_radar` desapareció. Se
conserva el razonamiento original como historia.

**Decisión original: modo híbrido.** La condición usa la lectura guardada de esa
dirección si el tanque ya exploró ahí antes; si no hay ninguna, explora en ese
mismo momento para evaluar la condición.

*Clave:* `reglas.modo_radar = "hibrido"`

### El problema

`RADAR(dir)` es una instrucción que consume un turno, pero también aparece
dentro de la condición de un `IF`. No está dicho si el `IF` consulta un valor
guardado por un `RADAR` anterior o si explora por su cuenta. Un programa
escrito así:

```
RADAR(S)
IF RADAR(S) > 0 THEN AMT(S)
```

gasta un turno explorando y otro decidiendo. Pero el profesor puede cargar un
archivo que solo tenga la segunda línea, sin el `RADAR(S)` previo.

### Por qué el modo híbrido

Porque funciona en los dos casos. Con cualquiera de los otros dos modos, una
de las dos formas de escribir el programa deja de tener sentido:

| Modo | Con `RADAR` previo | Sin `RADAR` previo |
|---|---|---|
| Solo registro | correcto | la condición nunca se cumple |
| Solo directo | el `RADAR` suelto no sirve de nada | correcto |
| **Híbrido** | correcto | correcto |

El criterio es que el simulador no debe fallar por la forma en que esté
escrito un archivo ajeno, y el profesor evaluará cargando los suyos.

### Lo que hay que vigilar

El modo híbrido tiene una asimetría incómoda: escribir `RADAR(S)` antes del
`IF` da una lectura de un turno antes, es decir **más vieja**, que omitirlo.
Explorar primero puede resultar peor que no explorar. Es un efecto raro y se
deja anotado aquí para revisarlo cuando el motor esté armado y se pueda medir
si de verdad cambia el resultado de las partidas.

---

## D-02 · Orden de los turnos dentro de la ronda

**Decisión: orden rotativo.** El orden gira una posición en cada ronda: si en
la ronda 1 actúan A, B, C, en la 2 actúan B, C, A, en la 3 C, A, B.

*Clave:* `reglas.orden_turnos = "rotativo"`

### El problema

El `ESCUDO` da inmunidad «hasta el siguiente turno del tanque». Con un orden
sorteado en cada ronda, el tiempo real que dura esa inmunidad cambia de una
vez a otra: si un tanque actúa último en una ronda y primero en la siguiente,
su escudo apenas cubre dos turnos ajenos; si actúa primero y luego último,
cubre hasta cuatro. La misma instrucción vale el doble o la mitad según el
sorteo, y eso no se puede compensar al programar.

### Por qué rotativo

Con el orden rotativo, entre dos turnos consecutivos de un mismo tanque pasan
siempre exactamente tantos turnos como tanques haya. El escudo pasa a durar
siempre lo mismo y deja de depender del azar.

Además resuelve de paso un problema distinto: con un orden fijo, el primer
tanque tiene ventaja permanente, porque siempre golpea antes. Rotando, cada
tanque pasa por todas las posiciones el mismo número de veces.

Las posiciones iniciales **siguen siendo aleatorias**, según lo que pidió el
profesor; lo que deja de sortearse es el orden de los turnos.

### Alternativa descartada

Sortear el orden en cada ronda (`"aleatorio"`). Da más variedad entre
partidas, pero introduce ruido justo en la regla que define cuánto vale el
escudo. La variedad ya la aporta el sorteo de posiciones iniciales.

---

## D-03 · En qué se cuentan los dos turnos de armado de la mina — *reemplazada por D-00*

Ahora la mina se activa de inmediato (`reglas.mina.rondas_armado = 0`) y,
si se configura un retraso, se cuenta en rondas. La clave `medida`
desapareció. Se conserva el razonamiento original como historia.

**Decisión: dos turnos del propietario.** La mina queda armada cuando el
tanque que la puso ha jugado dos turnos más.

*Claves:* `reglas.mina.turnos_armado = 2`,
`reglas.mina.medida = "turnos_propietario"`

### El problema

«La mina se activa después de dos turnos» admite dos lecturas: dos turnos
del tanque que la colocó, o dos rondas completas de la partida.

### Por qué turnos del propietario

Es la lectura literal de lo acordado y la que el dueño de la mina puede
contar mirando su propio programa: pone la mina, y dos instrucciones después
ya está armada. Con la medida en rondas tendría que saber cuántos tanques
quedan vivos para calcularlo.

Conviene notar que, **con el orden rotativo de D-02, las dos lecturas
coinciden**: dos turnos del propietario son exactamente dos rondas. La
ambigüedad se disuelve sola. La clave se conserva porque si alguna vez se
volviera al orden aleatorio volvería a importar.

---

## D-04 · A quién se acredita el daño de un choque

**Decisión: al embestidor, y solo el daño que causó al otro.** Un choque
(`MOV` hacia un tanque) reparte 12 puntos a cada tanque —15 antes de D-00—;
los que recibe el enemigo cuentan para el desempate a favor de quien
embistió, y los que se hace a sí mismo no se le acreditan a nadie. Los
números de abajo son los de la regla original.

*Clave:* `reglas.acredita_choque = "embestidor"`

### El problema

El daño hecho es el criterio de desempate. En un choque los dos tanques
reciben 15 puntos, así que hay que decidir si esos 30 puntos se reparten, se
acreditan a uno o no cuentan.

### Por qué al embestidor

Porque el desempate pretende medir quién jugó mejor, y el choque fue una
decisión de uno solo de los dos tanques: el otro estaba quieto. Acreditarle
también los 15 que el embestido «le hizo» premiaría a quien no hizo nada.

Y el daño propio no se acredita a nadie por la misma razón que el golpe
contra la pared no cuenta: si se lo acreditáramos al embestido, embestir a un
rival sería una forma de regalarle puntos de desempate, y un tanque podría
perder por haber atacado mucho.

Esto encaja con lo ya acordado para los otros casos:

| Caso | A quién se acredita |
|---|---|
| Ametralladora, misil | A quien dispara |
| Mina | A quien la puso |
| Choque entre tanques | Al embestidor, solo los 15 del otro |
| Choque contra la pared | A nadie |
| Curación o refacción | No descuenta daño ya hecho a nadie |

### Alternativa descartada

`"ambos"`: cada tanque se anota los 15 que causó. Es defendible —el daño
existió— pero vuelve el desempate sensible a ser embestido, que no es mérito.

---

## D-05 · Cuándo se pisa una mina

*Con D-00 la mina se lanza a otra casilla y no a la propia, así que el
problema de abajo ya no se da; la regla sigue vigente y además una mina
activa que cae sobre un tanque estalla en ese momento. El escudo ahora sí
puede cubrir una mina.*

**Decisión: al entrar a la casilla.** Una mina armada estalla cuando un
tanque llega a su casilla con `MOV`. Quedarse encima no la detona.

*Sin clave en `config.json`.*

### El problema

La mina se coloca en la casilla del propio tanque. Si la revisión de minas
de la Figura 4 detonara cualquier mina armada bajo un tanque, el dueño que se
queda quieto —por ejemplo, porque su `MOV` choca con la pared— volaría con su
propia mina dos turnos después de ponerla.

### Consecuencias

- La revisión de minas sigue ocurriendo después de cada turno, como en la
  figura; solo dispara si el tanque llegó a la casilla en ese turno.
- La mina estalla y se retira aunque el daño no llegue a aplicarse.
- **El escudo nunca cubre al pisar una mina.** Las minas solo se pisan en el
  turno propio y el escudo caduca justo al empezar ese turno, así que el caso
  «el escudo está activo cuando el tanque pisa una mina» de la sección 7.3
  no puede darse. Queda una prueba que lo demuestra.

---

## D-06 · Casos borde de la sección 7.3, resueltos en el motor

| Caso | Resolución |
|---|---|
| Un misil pasa sobre una casilla con mina | La mina no se ve afectada: el misil solo daña tanques |
| Mina sobre otra mina, o fuera del tablero | No se lanza y no gasta munición; el turno se pierde |
| `REPARAR` con la vida al máximo | No hace nada y **no gasta** el uso |
| Refacción con la vida al máximo | Se recoge y se pierde |
| Destruido sobre una refacción | No puede darse: entrar a la casilla ya la recoge. El motor igual deja una sola |
| Muerte contra la pared | Deja refacción; el daño no se acredita a nadie |
| El choque destruye al embestido | El embestidor no ocupa la casilla; ambos se quedan donde estaban |
| Todos destruidos en el mismo turno | Desempatan por daño infligido los que cayeron en ese turno |
| Partida con un solo tanque | Juega hasta el límite de rondas y gana por desempate |
| Muere el dueño de una mina sin armar | Se arma igual al llegar su ronda |

El orden rotativo gira sobre la lista completa de tanques, vivos o no, y
después descarta a los destruidos; así la rotación no se descoloca cuando
alguno cae.

---

## Pendiente de confirmar con el profesor

Las cuatro decisiones de arriba son provisionales en el sentido de que
resuelven huecos del reglamento con el criterio de que el simulador no falle.
Conviene preguntarlas en clase, sobre todo **D-01**, porque si los demás
equipos la resolvieron de otra forma, un mismo archivo `.txt` puede dar
partidas distintas en cada simulador.

## Decisiones menores ya tomadas en el código

| Decisión | Dónde está | Motivo |
|---|---|---|
| El programa se reinicia al agotarse | `Programa.en()` | Un tanque sin instrucciones que ejecutar quedaría inerte el resto de la partida |
| Las coordenadas son base 1, `(x, y)` = (columna, fila), fila 1 al norte | `modelo/direccion.py` | Coincide con lo visto en clase; el ejemplo de `MINA` del profesor usa (2,2) como centro de 3 x 3 |
| `DAÑAR`/`DANAR` y `RADAR` suelto dan un error que explica el cambio | `lenguaje/sintactico.py` | Los archivos escritos con las reglas anteriores dicen qué corregir |
| Se reportan todos los errores de sintaxis, no solo el primero | `lenguaje/interprete.py` | Corregir un archivo error por error es inviable |
| El léxico y la sintaxis son dos fases separadas | `lenguaje/` | Responde a la pregunta del profesor sobre el intérprete lexicográfico |
