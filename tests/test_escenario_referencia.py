"""Escenario de referencia de la sección 7.2 del documento de arquitectura.

Tres tanques con posiciones fijas y programas conocidos. El resultado de
las diez primeras rondas se escribió a mano, turno por turno, ANTES de
correr el motor, y quedó en la tabla `ESPERADO`. Si el motor deja de
coincidir, algo cambió en las reglas: o es un error, o es una decisión
nueva que hay que registrar en docs/DECISIONES.md y reflejar aquí.

Se rehízo con las correcciones del profesor: AMT 5, misil 10 en línea
recta, mina 7.5 lanzada a una esquina y activa de inmediato, choques de 12
a los dos tanques, escudo de 20 que dura hasta agotarse y sin RADAR suelto.

El escenario no usa azar: las posiciones están fijas, el orden es rotativo
y nadie pasa sobre un tanque destruido. Por eso no depende de la semilla.

Orden de los turnos (rotativo)
    R1 A B C   R2 B C A   R3 C A B   R4 A B C   R5 B C A
    R6 C A B   R7 A B C   R8 B C A   R9 C A B   R10 A B C

Desarrollo a mano  (vida, y entre corchetes el escudo)
    R1  A: IF RADAR(E) → B a 4; AMT(E) a B (95)
        B: MINA(SO) desde (6,2) cae en (5,3), armada; no hay nadie
        C: IF RADAR(N) → B a 4; AMT(N) a B (90)
    R2  B: MOV(S) → (6,3)
        C: MOV(N) → (6,5)
        A: MOV(S) → (2,3)
    R3  C: ESCUDO [20]
        A: MISIL(E) pasa sobre la mina de (5,3) y da a B en (6,3) (80)
        B: MOV(O) → (5,3): pisa su propia mina, 7.5 autoinfligidos (72.5)
    R4  A: ESCUDO [20]
        B: IF V < 90 con 72.5: REPARAR (92.5); ya no le quedan usos
        C: MOV(N) → (6,4)
    R5  B: MOV(E) → (6,3)
        C: IF RADAR(N) → B a 1; AMT(N) a B (87.5)
        A: IF RADAR(E) → B a 4; AMT(E) a B (82.5)
    R6  C: MOV(N) contra B: choque, B 70.5; C recibe 12 en el escudo [8]
        A: MOV(S) → (2,4)
        B: MOV(N) → (6,2)
    R7  A: MISIL(E) a C en (6,4): el escudo absorbe 8 [0], 2 a la vida (98)
        B: MINA(SO) a (5,3) otra vez, armada; no hay nadie
        C: ESCUDO, se recarga [20]
    R8  B: MOV(S) → (6,3)
        C: MOV(N) contra B: choque, B 58.5; C [8]
        A: ESCUDO con el escudo completo: no hace nada
    R9  C: IF RADAR(N) → B a 1; AMT(N) a B (53.5)
        A: IF RADAR(E) → C a 4; AMT(E), el escudo absorbe los 5 [3]
        B: MOV(O) → (5,3): pisa su segunda mina (46)
    R10 A: MOV(S) → (2,5)
        B: IF V < 90 con 46: REPARAR, pero ya lo usó
        C: MOV(N) → (6,3), vacía
"""
import pytest

from tanques import config as cfg
from tanques.lenguaje import Interprete, formato_errores
from tanques.modelo import Motor, TipoEvento

ARTILLERO = """
IF RADAR(E) > 0 THEN AMT(E)
MOV(S)
MISIL(E)
ESCUDO
"""

MINADOR = """
MINA(SO)
MOV(S)
MOV(O)
IF V < 90 THEN REPARAR
MOV(E)
MOV(N)
"""

MURO = """
IF RADAR(N) > 0 THEN AMT(N)
MOV(N)
ESCUDO
MOV(N)
"""

# ronda: {tanque: (posición, vida, escudo)}, minas [(posición, armada)]
ESPERADO = {
    1: ({"A": ((2, 2), 100, 0), "B": ((6, 2), 90, 0),
         "C": ((6, 6), 100, 0)}, [((5, 3), True)]),
    2: ({"A": ((2, 3), 100, 0), "B": ((6, 3), 90, 0),
         "C": ((6, 5), 100, 0)}, [((5, 3), True)]),
    3: ({"A": ((2, 3), 100, 0), "B": ((5, 3), 72.5, 0),
         "C": ((6, 5), 100, 20)}, []),
    4: ({"A": ((2, 3), 100, 20), "B": ((5, 3), 92.5, 0),
         "C": ((6, 4), 100, 20)}, []),
    5: ({"A": ((2, 3), 100, 20), "B": ((6, 3), 82.5, 0),
         "C": ((6, 4), 100, 20)}, []),
    6: ({"A": ((2, 4), 100, 20), "B": ((6, 2), 70.5, 0),
         "C": ((6, 4), 100, 8)}, []),
    7: ({"A": ((2, 4), 100, 20), "B": ((6, 2), 70.5, 0),
         "C": ((6, 4), 98, 20)}, [((5, 3), True)]),
    8: ({"A": ((2, 4), 100, 20), "B": ((6, 3), 58.5, 0),
         "C": ((6, 4), 98, 8)}, [((5, 3), True)]),
    9: ({"A": ((2, 4), 100, 20), "B": ((5, 3), 46, 0),
         "C": ((6, 4), 98, 3)}, []),
    10: ({"A": ((2, 5), 100, 20), "B": ((5, 3), 46, 0),
          "C": ((6, 3), 98, 3)}, []),
}


def escenario():
    config = cfg.Configuracion()
    programas = []
    for nombre, texto in (("A", ARTILLERO), ("B", MINADOR), ("C", MURO)):
        p, errores = Interprete().analizar(texto, nombre=nombre)
        assert errores == [], formato_errores(errores)
        programas.append(p)
    return Motor(config, programas, posiciones=[(2, 2), (6, 2), (6, 6)])


def test_las_diez_rondas_coinciden_con_el_calculo_a_mano():
    m = escenario()
    for ronda in range(1, 11):
        m.ronda()
        e = m.estado()
        tanques, minas = ESPERADO[ronda]
        obtenido = {t.nombre: (t.posicion, t.vida, t.escudo)
                    for t in e.tanques}
        assert obtenido == tanques, f"ronda {ronda}"
        assert [(mi.posicion, mi.armada) for mi in e.minas] == minas, \
            f"ronda {ronda}"
    assert not m.terminada()


def test_contadores_al_final_de_la_ronda_diez():
    m = escenario()
    for _ in range(10):
        m.ronda()
    a, b, c = m.registro.tanques
    assert (a.dano_infligido, b.dano_infligido, c.dano_infligido) \
        == (22, 0, 39)
    assert (a.misiles, a.minas) == (1, 3)
    assert (b.minas, b.reparaciones, b.dano_autoinfligido) == (1, 0, 15)
    assert (b.dano_recibido, c.misiles, c.dano_recibido) == (74, 3, 2)


@pytest.mark.parametrize("ronda, tipo, tanque", [
    (3, TipoEvento.MINA_EXPLOTA, "B"),     # su propia mina
    (4, TipoEvento.REPARACION, "B"),
    (5, TipoEvento.RADAR, "C"),            # el IF explora en el momento
    (6, TipoEvento.BLOQUEO, "C"),          # el escudo absorbe el choque
    (7, TipoEvento.BLOQUEO, "C"),          # y parte del misil
    (7, TipoEvento.DANO, "C"),             # el resto llega a la vida
    (7, TipoEvento.MINA_COLOCADA, "B"),
    (8, TipoEvento.SIN_EFECTO, "A"),       # escudo ya completo
    (9, TipoEvento.MINA_EXPLOTA, "B"),
    (10, TipoEvento.SIN_EFECTO, "B"),      # REPARAR ya usado
])
def test_eventos_clave(ronda, tipo, tanque):
    m = escenario()
    eventos = []
    for _ in range(ronda):
        eventos = m.ronda()
    assert any(e.tipo is tipo and e.tanque == tanque for e in eventos)
