"""Pruebas del analizador sintáctico y del intérprete completo.

El profesor evaluará el simulador cargando sus propios archivos .txt, de modo
que la tolerancia a variaciones de escritura es un requisito y no una
comodidad. Esa es la razón de buena parte de estas pruebas.
"""
from pathlib import Path

import pytest

from tanques.lenguaje import Fuente, Interprete, Operador, Tipo, formato_errores
from tanques.modelo import Direccion

RAIZ = Path(__file__).resolve().parents[1]
I = Interprete()


def prog(texto, ancho=8, alto=8):
    """Analiza un texto y exige que no haya errores."""
    p, errores = Interprete(ancho, alto).analizar(texto)
    assert errores == [], formato_errores(errores)
    return p.instrucciones


def errores_de(texto, ancho=8, alto=8):
    return Interprete(ancho, alto).analizar(texto)[1]


# ---------------------------------------------------------------- básicos
def test_instruccion_con_direccion():
    i = prog("MOV(N)")[0]
    assert i.tipo is Tipo.MOV
    assert i.direccion is Direccion.N
    assert i.linea == 1


def test_las_cuatro_direcciones():
    for nombre in ("N", "S", "E", "O"):
        assert prog(f"MOV({nombre})")[0].direccion is Direccion[nombre]


def test_instrucciones_sin_parametros():
    for palabra, tipo in [("ESCUDO", Tipo.ESCUDO),
                          ("REPARAR", Tipo.REPARAR),
                          ("ESPERAR", Tipo.ESPERAR)]:
        assert prog(palabra)[0].tipo is tipo


def test_misil_en_linea_recta():
    i = prog("MISIL(E)")[0]
    assert (i.tipo, i.direccion) == (Tipo.MISIL, Direccion.E)


@pytest.mark.parametrize("texto, vertical, horizontal", [
    ("MINA(N,E)", Direccion.N, Direccion.E),
    ("MINA(N,O)", Direccion.N, Direccion.O),
    ("MINA(S,E)", Direccion.S, Direccion.E),
    ("MINA(S,O)", Direccion.S, Direccion.O),
    ("MINA(E,N)", Direccion.N, Direccion.E),     # en cualquier orden
])
def test_mina_a_una_esquina(texto, vertical, horizontal):
    i = prog(texto)[0]
    assert (i.tipo, i.direccion, i.direccion2) ==         (Tipo.MINA, vertical, horizontal)


@pytest.mark.parametrize("texto", ["MINA", "MINA(N)", "MINA(N,S)",
                                   "MINA(E,O)", "MINA(N,X)", "MINA(N,E"])
def test_mina_mal_formada(texto):
    assert errores_de(texto)


def test_misil_con_coordenadas_ya_no_existe():
    assert errores_de("MISIL(3,5)")


@pytest.mark.parametrize("texto", ["DAÑAR(N)", "DANAR(N)"])
def test_danar_ya_no_es_instruccion(texto):
    assert "no es una instrucción" in errores_de(texto)[0].mensaje


def test_radar_suelto_ya_no_es_instruccion():
    assert "condición de un IF" in errores_de("RADAR(N)")[0].mensaje


# ---------------------------------------------------------------- tolerancia
@pytest.mark.parametrize("texto", ["mov(n)", "Mov(N)", "MOV(n)",
                                   "if vida < 40 then reparar"])
def test_exige_mayusculas(texto):
    assert "mayúsculas" in errores_de(texto)[0].mensaje


def test_tolera_espacios_de_sobra():
    i = prog("  MINA (  N ,  E )  ")[0]
    assert (i.direccion, i.direccion2) == (Direccion.N, Direccion.E)
    assert prog("MOV ( N )")[0].direccion is Direccion.N


def test_ignora_comentarios_y_lineas_vacias():
    texto = "# encabezado\n\nMOV(N)   # avanza\n\n# final\nESPERAR\n"
    assert [i.tipo for i in prog(texto)] == [Tipo.MOV, Tipo.ESPERAR]


def test_conserva_el_numero_de_linea_real():
    assert [i.linea for i in prog("# uno\n# dos\nMOV(N)\n\nESPERAR\n")] == [3, 5]


def test_tolera_fin_de_linea_de_windows_y_bom():
    assert len(prog("﻿MOV(N)\r\nESPERAR\r\n")) == 2


# ---------------------------------------------------------------- IF
def test_if_con_radar():
    i = prog("IF RADAR(S) > 0 THEN AMT(S)")[0]
    assert i.tipo is Tipo.IF
    assert i.condicion.fuente is Fuente.RADAR
    assert i.condicion.direccion is Direccion.S
    assert i.condicion.operador is Operador.MAYOR
    assert i.condicion.valor == 0
    assert i.accion.tipo is Tipo.AMT


def test_if_con_vida():
    i = prog("IF VIDA < 40 THEN REPARAR")[0]
    assert i.condicion.fuente is Fuente.VIDA
    assert i.condicion.direccion is None
    assert i.accion.tipo is Tipo.REPARAR


@pytest.mark.parametrize("texto,op", [
    ("IF VIDA > 10 THEN ESCUDO", Operador.MAYOR),
    ("IF VIDA < 10 THEN ESCUDO", Operador.MENOR),
    ("IF VIDA >= 10 THEN ESCUDO", Operador.MAYOR_IGUAL),
    ("IF VIDA <= 10 THEN ESCUDO", Operador.MENOR_IGUAL),
    ("IF VIDA == 10 THEN ESCUDO", Operador.IGUAL),
])
def test_todos_los_operadores(texto, op):
    assert prog(texto)[0].condicion.operador is op


def test_el_radar_negativo_es_una_condicion_valida():
    assert prog("IF RADAR(O) < -1 THEN ESCUDO")[0].condicion.valor == -1


@pytest.mark.parametrize("accion", ["AMT(N)", "MISIL(N)", "ESCUDO",
                                    "REPARAR"])
def test_acciones_admitidas_en_if(accion):
    assert prog(f"IF VIDA > 0 THEN {accion}")[0].accion is not None


@pytest.mark.parametrize("accion", ["MOV(N)", "MINA(N,E)", "ESPERAR"])
def test_acciones_no_admitidas_en_if(accion):
    errs = errores_de(f"IF VIDA > 0 THEN {accion}")
    assert len(errs) == 1
    assert "no permitida en IF" in errs[0].mensaje


def test_la_condicion_evalua_correctamente():
    c = prog("IF VIDA < 40 THEN REPARAR")[0].condicion
    assert c.evalua(30) is True
    assert c.evalua(40) is False


# ---------------------------------------------------------------- errores
def test_direccion_invalida():
    errs = errores_de("MOV(X)")
    assert len(errs) == 1 and "dirección inválida" in errs[0].mensaje


def test_instruccion_desconocida():
    assert "desconocida o mal formada" in errores_de("DISPARAR")[0].mensaje


def test_misil_mal_formado():
    assert errores_de("MISIL(3)")


def test_falta_el_parentesis():
    assert errores_de("MOV N)")
    assert errores_de("MOV(N")


def test_sobra_texto_al_final_de_la_linea():
    assert "desconocida o mal formada" in errores_de("MOV(N) ESPERAR")[0].mensaje


def test_if_sin_operador():
    assert "IF inválida" in errores_de("IF RADAR(S) 0 THEN AMT(S)")[0].mensaje


def test_if_sin_then():
    assert "IF inválida" in errores_de("IF VIDA < 40 REPARAR")[0].mensaje


def test_condicion_con_fuente_invalida():
    assert "IF inválida" in errores_de("IF MINAS > 0 THEN ESCUDO")[0].mensaje


def test_reporta_todos_los_errores_no_solo_el_primero():
    assert [e.linea for e in errores_de("MOV(X)\nDISPARAR\nMISIL(3)\n")] == \
        [1, 2, 3]


def test_las_lineas_validas_no_se_pierden_cuando_hay_errores():
    p, errs = I.analizar("MOV(N)\nDISPARAR\nESPERAR\n")
    assert len(errs) == 1
    assert [i.tipo for i in p.instrucciones] == [Tipo.MOV, Tipo.ESPERAR]


def test_archivo_vacio():
    assert "ninguna instrucción" in errores_de("")[0].mensaje
    assert "ninguna instrucción" in errores_de("# solo comentarios\n\n")[0].mensaje


def test_archivo_inexistente():
    assert "no existe" in I.cargar(RAIZ / "tanques" / "no_existe.txt")[1][0].mensaje


# ---------------------------------------------------------------- archivos
@pytest.mark.parametrize("nombre", ["cazador", "defensivo", "explorador",
                                    "artillero", "embestidor", "minador",
                                    "patrulla"])
def test_los_programas_de_ejemplo_son_validos(nombre):
    p, errs = I.cargar(RAIZ / "tanques" / f"{nombre}.txt")
    assert errs == [], formato_errores(errs)
    assert len(p) > 0


def test_el_archivo_con_errores_los_reporta_todos():
    _, errs = I.cargar(RAIZ / "tanques" / "con_errores.txt")
    assert [e.linea for e in errs] == [3, 4, 5, 6, 7, 8, 9, 10, 11]


def test_formato_de_los_errores():
    _, errs = I.cargar(RAIZ / "tanques" / "con_errores.txt")
    salida = formato_errores(errs)
    assert salida.startswith("Errores de sintaxis, la partida no inicia:")
    assert "con_errores.txt, línea 3" in salida


# ---------------------------------------------------------------- utilidades
def test_representacion_legible():
    assert str(prog("MOV(N)")[0]) == "MOV(N)"
    assert str(prog("MISIL(E)")[0]) == "MISIL(E)"
    assert str(prog("MINA(E,S)")[0]) == "MINA(S,E)"
    assert str(prog("IF VIDA < 40 THEN REPARAR")[0]) == \
        "IF VIDA < 40 THEN REPARAR"


def test_el_programa_se_reinicia_al_agotarse():
    p, _ = I.analizar("MOV(N)\nESPERAR\n")
    assert str(p.en(0)) == "MOV(N)"
    assert str(p.en(2)) == "MOV(N)"      # vuelve a la primera línea
    assert str(p.en(3)) == "ESPERAR"


def test_direcciones_opuestas():
    assert Direccion.N.opuesta() is Direccion.S
    assert Direccion.E.opuesta() is Direccion.O


def test_vectores_de_direccion():
    # La fila 1 es el norte: N disminuye y, S aumenta y.
    assert (Direccion.N.dx, Direccion.N.dy) == (0, -1)
    assert (Direccion.S.dx, Direccion.S.dy) == (0, 1)
    assert (Direccion.E.dx, Direccion.E.dy) == (1, 0)
    assert (Direccion.O.dx, Direccion.O.dy) == (-1, 0)
