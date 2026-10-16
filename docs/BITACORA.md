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
análisis sintáctico. El intérprete del paso 1 valida con expresiones regulares
por línea, lo que cumple la misma función pero no exhibe las dos fases por
separado. Queda pendiente reestructurarlo en `lexico.py` y `sintactico.py`
para que el código corresponda a lo documentado.
