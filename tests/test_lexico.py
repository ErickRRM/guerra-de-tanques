"""Pruebas del analizador léxico, la primera fase del intérprete."""
import pytest

from tanques.lenguaje import AnalizadorLexico, TipoToken, tokenizar


def tipos(texto):
    """Tipos de los tokens, sin el token de fin."""
    return [t.tipo for t in tokenizar(texto)[:-1]]


def lexemas(texto):
    return [t.lexema for t in tokenizar(texto)[:-1]]


# ---------------------------------------------------------------- categorías
def test_reconoce_palabra_parentesis_y_direccion():
    assert tipos("MOV(N)") == [TipoToken.PALABRA, TipoToken.PAR_IZQ,
                               TipoToken.DIRECCION, TipoToken.PAR_DER]


def test_reconoce_la_coma_y_los_enteros():
    assert tipos("MISIL(3,5)") == [
        TipoToken.PALABRA, TipoToken.PAR_IZQ, TipoToken.ENTERO,
        TipoToken.COMA, TipoToken.ENTERO, TipoToken.PAR_DER]


@pytest.mark.parametrize("op", [">", "<", ">=", "<=", "=="])
def test_reconoce_los_operadores_relacionales(op):
    t = tokenizar(f"VIDA {op} 10")
    assert t[1].tipo is TipoToken.RELACIONAL
    assert t[1].lexema == op


def test_los_operadores_de_dos_caracteres_no_se_parten():
    assert lexemas("VIDA >= 10") == ["VIDA", ">=", "10"]
    assert lexemas("VIDA == 10") == ["VIDA", "==", "10"]


def test_reconoce_enteros_negativos():
    t = tokenizar("IF RADAR(O) < -3 THEN ESCUDO")
    negativo = [x for x in t if x.tipo is TipoToken.ENTERO][0]
    assert negativo.lexema == "-3"


def test_las_cuatro_direcciones_son_su_propia_categoria():
    for d in ("N", "S", "E", "O"):
        assert tokenizar(d)[0].tipo is TipoToken.DIRECCION


def test_una_palabra_desconocida_se_clasifica_como_palabra():
    # Que no pertenezca al lenguaje lo decide el analizador sintáctico.
    assert tokenizar("DISPARAR")[0].tipo is TipoToken.PALABRA


# ---------------------------------------------------------------- normalización
def test_normaliza_a_mayusculas():
    assert lexemas("mov(n)") == ["MOV", "(", "N", ")"]


def test_descarta_los_espacios():
    assert lexemas("  MISIL (  3 ,  5 )  ") == \
        ["MISIL", "(", "3", ",", "5", ")"]


def test_descarta_el_comentario():
    assert lexemas("MOV(N)   # avanza hacia el norte") == \
        ["MOV", "(", "N", ")"]


def test_una_linea_de_solo_comentario_no_produce_tokens():
    assert tipos("# nada que ver aquí") == []


def test_una_linea_vacia_solo_produce_el_token_de_fin():
    t = tokenizar("   ")
    assert len(t) == 1 and t[0].tipo is TipoToken.FIN


# ---------------------------------------------------------------- posición
def test_cada_token_conserva_su_linea_y_su_columna():
    t = tokenizar("MOV(N)", linea=7)
    assert all(x.linea == 7 for x in t)
    assert [x.columna for x in t[:-1]] == [1, 4, 5, 6]


# ---------------------------------------------------------------- errores
def test_un_caracter_invalido_se_reporta():
    _, errores = AnalizadorLexico("p.txt").analizar("MOV(N) $", 1)
    assert len(errores) == 1
    assert "no reconocido" in errores[0].mensaje


def test_el_analisis_continua_tras_un_caracter_invalido():
    tokens, errores = AnalizadorLexico().analizar("$ MOV(N)", 1)
    assert errores
    assert [t.lexema for t in tokens[:-1]] == ["MOV", "(", "N", ")"]
