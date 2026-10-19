"""Escenario de referencia de la sección 7.2 del documento de arquitectura.

Tres tanques con posiciones fijas y programas conocidos. El resultado de
las diez primeras rondas se escribió a mano, turno por turno, ANTES de
correr el motor, y quedó en la tabla `ESPERADO`. Si el motor deja de
coincidir, algo cambió en las reglas: o es un error, o es una decisión
nueva que hay que registrar en docs/DECISIONES.md y reflejar aquí.

El escenario no usa azar: las posiciones están fijas, el orden es rotativo
y nadie recoge refacciones. Por eso no depende de la semilla.

Orden de los turnos (rotativo)
    R1 A B C   R2 B C A   R3 C A B   R4 A B C   R5 B C A
    R6 C A B   R7 A B C   R8 B C A   R9 C A B   R10 A B C

Desarrollo a mano
    R1  A: IF RADAR(E) explora → B a 4; AMT(E) a B (90)
        B: MINA en (6,2)
        C: IF RADAR(N) explora → B a 4; AMT(N) a B (80)
    R2  B: MOV(S) → (6,3); a la mina le falta 1 turno
        C: DAÑAR(O), no hay nadie en (5,6)
        A: MOV(S) → (2,3)
    R3  C: ESCUDO
        A: MISIL(6,6) contra C; el escudo lo absorbe (misiles 2)
        B: MOV(S) → (6,4); la mina queda armada
    R4  A: ESCUDO
        B: IF VIDA < 80 con vida 80: falso
        C: pierde el escudo al empezar su turno; MOV(O) → (5,6)
    R5  B: MOV(N) → (6,3)
        C: IF RADAR(N) desde (5,6) → pared a 6: falso
        A: pierde el escudo; IF RADAR(E) → B a 4; AMT(E) a B (70)
    R6  C: DAÑAR(O), no hay nadie en (4,6)
        A: MOV(S) → (2,4)
        B: MOV(N) → (6,2): pisa su propia mina armada (45),
           daño autoinfligido, no se acredita a nadie
    R7  A: MISIL(6,6), la casilla ya está vacía (misiles 1)
        B: MINA en (6,2), la segunda
        C: ESCUDO
    R8  B: MOV(S) → (6,3)
        C: pierde el escudo; MOV(O) → (4,6)
        A: ESCUDO
    R9  C: IF RADAR(N) desde (4,6) → pared a 6: falso
        A: pierde el escudo; IF RADAR(E) desde (2,4) → pared a 7: falso
        B: MOV(S) → (6,4); la segunda mina queda armada
    R10 A: MOV(S) → (2,5)
        B: IF VIDA < 80 con 45: REPARAR (65)
        C: DAÑAR(O), no hay nadie en (3,6)
"""
import pytest

from tanques import config as cfg
from tanques.lenguaje import Interprete, formato_errores
from tanques.modelo import Motor, TipoEvento

ARTILLERO = """
IF RADAR(E) > 0 THEN AMT(E)
MOV(S)
MISIL(6,6)
ESCUDO
"""

MINADOR = """
MINA
MOV(S)
MOV(S)
IF VIDA < 80 THEN REPARAR
MOV(N)
MOV(N)
"""

MURO = """
IF RADAR(N) > 0 THEN AMT(N)
DAÑAR(O)
ESCUDO
MOV(O)
"""

# ronda: {tanque: (posición, vida, escudo)}, minas [(posición, armada)]
ESPERADO = {
    1: ({"A": ((2, 2), 100, False), "B": ((6, 2), 80, False),
         "C": ((6, 6), 100, False)}, [((6, 2), False)]),
    2: ({"A": ((2, 3), 100, False), "B": ((6, 3), 80, False),
         "C": ((6, 6), 100, False)}, [((6, 2), False)]),
    3: ({"A": ((2, 3), 100, False), "B": ((6, 4), 80, False),
         "C": ((6, 6), 100, True)}, [((6, 2), True)]),
    4: ({"A": ((2, 3), 100, True), "B": ((6, 4), 80, False),
         "C": ((5, 6), 100, False)}, [((6, 2), True)]),
    5: ({"A": ((2, 3), 100, False), "B": ((6, 3), 70, False),
         "C": ((5, 6), 100, False)}, [((6, 2), True)]),
    6: ({"A": ((2, 4), 100, False), "B": ((6, 2), 45, False),
         "C": ((5, 6), 100, False)}, []),
    7: ({"A": ((2, 4), 100, False), "B": ((6, 2), 45, False),
         "C": ((5, 6), 100, True)}, [((6, 2), False)]),
    8: ({"A": ((2, 4), 100, True), "B": ((6, 3), 45, False),
         "C": ((4, 6), 100, False)}, [((6, 2), False)]),
    9: ({"A": ((2, 4), 100, False), "B": ((6, 4), 45, False),
         "C": ((4, 6), 100, False)}, [((6, 2), True)]),
    10: ({"A": ((2, 5), 100, False), "B": ((6, 4), 65, False),
          "C": ((4, 6), 100, False)}, [((6, 2), True)]),
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
        == (20, 0, 10)
    assert (a.misiles, a.minas) == (1, 3)
    assert (b.minas, b.reparaciones, b.dano_autoinfligido) == (1, 0, 25)
    assert (c.misiles, c.dano_recibido) == (3, 0)


@pytest.mark.parametrize("ronda, tipo, tanque", [
    (3, TipoEvento.BLOQUEO, "C"),          # el escudo absorbe el misil
    (3, TipoEvento.MINA_ARMADA, "B"),
    (4, TipoEvento.CONDICION_FALSA, "B"),  # 80 < 80 es falso
    (6, TipoEvento.MINA_EXPLOTA, "B"),     # su propia mina
    (10, TipoEvento.REPARACION, "B"),
])
def test_eventos_clave(ronda, tipo, tanque):
    m = escenario()
    eventos = []
    for _ in range(ronda):
        eventos = m.ronda()
    assert any(e.tipo is tipo and e.tanque == tanque for e in eventos)
