"""Pruebas de la vista de consola.

La vista escribe en cualquier objeto de texto, así que se prueba contra un
`StringIO` sin abrir una terminal. Lo que más importa comprobar es que cada
cosa aparezca en la casilla correcta y que el color sea solo un
acompañamiento: sin color la partida se tiene que poder seguir igual.
"""
import io
from dataclasses import replace

import pytest

from tanques import config as cfg
from tanques.controlador import ejecutar
from tanques.lenguaje import Interprete
from tanques.modelo import Motor
from tanques.vista import Vista, VistaConsola
from tanques.vista.consola import barra_vida, dibujar_panel, dibujar_tablero

BASE = cfg.Configuracion()


def motor(*tanques, **cambios):
    config = replace(BASE, **cambios) if cambios else BASE
    programas = [Interprete().analizar(t, nombre=n)[0] for n, t, _ in tanques]
    return Motor(config, programas, posiciones=[p for _, _, p in tanques])


def vista(**opciones):
    salida = io.StringIO()
    opciones.setdefault("color", False)
    return VistaConsola(100, salida=salida, **opciones), salida


def casilla(tablero: str, x: int, y: int) -> str:
    """El texto de la casilla (x, y) en un tablero ya dibujado."""
    fila = tablero.splitlines()[y]
    inicio = 4 + 4 * (x - 1)
    return fila[inicio:inicio + 4]


# ---------------------------------------------------------------- tablero
def test_el_tanque_aparece_en_su_casilla_con_el_canon():
    m = motor(("a", "MOV(E)", (2, 3)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    t = dibujar_tablero(m.estado())
    assert casilla(t, 3, 3) == " 1> "
    assert casilla(t, 8, 8) == " 2^ "
    assert casilla(t, 2, 3) == "  . "


def test_el_escudo_se_marca_con_corchetes():
    m = motor(("a", "ESCUDO", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert casilla(dibujar_tablero(m.estado()), 1, 1) == "[1^]"


def test_mina_sin_armar_y_armada():
    m = motor(("a", "MINA\nMOV(S)\nESPERAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    assert casilla(dibujar_tablero(m.estado()), 1, 1) == "  o "
    m.ronda()
    assert casilla(dibujar_tablero(m.estado()), 1, 1) == "  * "


def test_la_refaccion_y_el_tanque_destruido():
    m = motor(("a", "MISIL(5,5)", (1, 1)), ("b", "ESPERAR", (5, 5)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=30)
    m.paso()
    t = dibujar_tablero(m.estado())
    assert casilla(t, 5, 5) == "  + "


def test_el_tablero_respeta_las_dimensiones():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (5, 3)),
              tablero=cfg.Tablero(5, 3))
    lineas = dibujar_tablero(m.estado()).splitlines()
    assert len(lineas) == 1 + 3
    assert lineas[0].split() == ["1", "2", "3", "4", "5"]


# ---------------------------------------------------------------- panel
@pytest.mark.parametrize("vida, barra", [
    (100, "[##########]"), (55, "[######....]"), (0, "[..........]"),
    (-5, "[..........]")])
def test_barra_de_vida(vida, barra):
    assert barra_vida(vida, 100) == barra


def test_el_panel_muestra_el_estado_de_cada_tanque():
    m = motor(("a", "MISIL(8,8)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    panel = dibujar_panel(m.estado(), {"a": "MISIL(8,8)"},
                          100).splitlines()
    assert panel[0].startswith("#1 a")
    assert "misiles 2" in panel[0] and "daño   30" in panel[0]
    assert panel[0].endswith("L1 MISIL(8,8)")
    assert " 70 " in panel[1]


def test_la_columna_de_dano_se_alinea_con_los_destruidos():
    m = motor(("a", "MISIL(5,5)", (1, 1)), ("b", "ESPERAR", (5, 5)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=30)
    m.paso()
    panel = dibujar_panel(m.estado(), {}, 30).splitlines()
    assert "destruido" in panel[1]
    assert len({linea.index("daño") for linea in panel}) == 1


# ---------------------------------------------------------------- vista
def test_la_vista_es_una_vista():
    assert isinstance(vista()[0], Vista)
    with pytest.raises(TypeError):
        Vista()


def test_una_partida_completa():
    v, salida = vista()
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              vida_inicial=20)
    resultado = ejecutar(m, v)
    texto = salida.getvalue()
    assert resultado.ganador == "a"
    assert "=== Inicio de la partida" in texto
    assert "=== Ronda 1 " in texto and "=== Ronda 2 " in texto
    assert "#1 a  L1: AMT(E)" in texto
    assert "Gana #1 a." in texto
    assert "1. #1 a" in texto


def test_sin_color_no_hay_secuencias_ansi():
    v, salida = vista(color=False)
    ejecutar(motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                   vida_inicial=10), v)
    assert "\033[" not in salida.getvalue()


def test_con_color_se_pinta_cada_tanque_con_el_suyo():
    v, salida = vista(color=True)
    ejecutar(motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                   vida_inicial=10), v)
    assert "\033[1;38;2;46;94;140m" in salida.getvalue()   # #2E5E8C


def test_el_resumen_omite_las_rondas():
    v, salida = vista(resumen=True)
    ejecutar(motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                   vida_inicial=20), v)
    texto = salida.getvalue()
    assert "=== Ronda" not in texto
    assert "Gana #1 a." in texto


def test_paso_a_paso_y_salir():
    v, salida = vista(paso=True, entrada=io.StringIO("\nq\n"))
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)))
    assert ejecutar(m, v) is None
    texto = salida.getvalue()
    assert "=== Ronda 2 " in texto and "=== Ronda 3 " not in texto
    assert "Partida interrumpida en la ronda 2." in texto


def test_paso_a_paso_sin_entrada_sale():
    v, _ = vista(paso=True, entrada=io.StringIO(""))
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)))
    assert ejecutar(m, v) is None and m.estado().ronda == 1


def test_empate():
    v, salida = vista()
    ejecutar(motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)),
                   rondas_maximas=2), v)
    assert "Empate." in salida.getvalue()
