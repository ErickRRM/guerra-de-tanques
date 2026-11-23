"""Terminar la partida tal como está y el menú de la partida."""
from dataclasses import replace
from pathlib import Path

import pytest

from tanques import config as cfg
from tanques.controlador import ejecutar
from tanques.lenguaje import Interprete
from tanques.modelo import Motivo, Motor, TipoEvento
from tanques.vista import Vista

RAIZ = Path(__file__).resolve().parents[1]


def motor_de(*tanques, **cambios):
    config = replace(cfg.Configuracion(), **cambios)
    config = replace(config, tanques=tuple(
        cfg.TanqueConfig(n, f"{n}.txt") for n, _, _ in tanques))
    programas = [Interprete().analizar(t, nombre=n)[0]
                 for n, t, _ in tanques]
    return config, Motor(config, programas,
                         posiciones=[p for _, _, p in tanques])


# ---------------------------------------------------------------- motor
def test_gana_el_vivo_con_mas_dano():
    _, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                    ("c", "ESPERAR", (5, 5)))
    m.ronda()
    m.ronda()
    eventos = m.terminar_ahora()
    assert m.terminada()
    r = m.resultado()
    assert (r.ganador, r.motivo, r.rondas) == ("a", Motivo.TERMINADA, 2)
    assert [e.tipo for e in eventos] == [TipoEvento.FIN]
    assert "terminada en la ronda 2" in eventos[0].texto


def test_sin_dano_es_empate_y_no_se_repite():
    _, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)))
    m.terminar_ahora()
    r = m.resultado()
    assert r.ganador is None and r.motivo is Motivo.TERMINADA
    assert m.terminar_ahora() == []
    assert m.resultado() == r


class Pide(Vista):
    """Una vista que, en la ronda 2, pide terminar."""

    def __init__(self):
        self.final = None

    def inicio(self, estado, eventos):
        return True

    def ronda(self, estado, eventos):
        return estado.ronda < 2

    def fin(self, estado, resultado):
        self.final = resultado

    def pide_terminar(self):
        return True


def test_ejecutar_termina_si_la_vista_lo_pide():
    _, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)))
    v = Pide()
    r = ejecutar(m, v)
    assert r.motivo is Motivo.TERMINADA and r.ganador == "a"
    assert v.final == r


# ---------------------------------------------------------------- ventana
tk = pytest.importorskip("tkinter")
grafica = pytest.importorskip("tanques.vista.grafica")
try:
    tk.Tk().destroy()
    HAY_PANTALLA = True
except tk.TclError:
    HAY_PANTALLA = False
requiere_pantalla = pytest.mark.skipif(not HAY_PANTALLA,
                                       reason="no hay pantalla")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(grafica, "retardo_ms", lambda v: 1)
    a = grafica.AppGrafica(RAIZ)
    a.root.withdraw()
    yield a
    a.destruir()


def guion(v, *pasos):
    """Cada vez que la ventana espera, hace el siguiente paso."""
    cola = list(pasos)
    original = v._esperar_senal

    def siguiente():
        if not cola:
            return original()
        paso = cola.pop(0)
        if callable(paso):
            paso()
            return v._senal.get()
        v.senal(paso)
        return paso
    v._esperar_senal = siguiente


@requiere_pantalla
def test_el_menu_no_pausa_la_partida(app):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    v = app.partida(config)
    v.senal("iniciar")
    v._abrir_menu()
    assert v._menu is not None and v.modo == "auto"
    assert not v.canvas.find_withtag("velo")
    assert "en curso" in app._subtitulo_menu["text"]
    v.opciones_menu["pausa"].invoke()       # Pausar desde el menú
    assert v.modo == "pausa" and v._menu is not None
    assert "en pausa" in app._subtitulo_menu["text"] or         "sin empezar" in app._subtitulo_menu["text"]
    assert v.opciones_menu["pausa"].texto == "Reanudar"
    v.opciones_menu["pausa"].invoke()       # y reanudar
    assert v.modo == "auto"
    v.opciones_menu["play"].invoke()        # Volver a la partida
    assert v._menu is None and v.modo == "auto"
    v.senal("salir")


@requiere_pantalla
def test_la_partida_avanza_con_el_menu_abierto(app):
    config, m = motor_de(("a", "MOV(E)", (1, 1)), ("b", "ESPERAR", (4, 4)))
    v = app.partida(config)
    v._abrir_menu()
    rondas = []
    original = v.ronda

    def ronda(estado, eventos):
        rondas.append(estado.ronda)
        if len(rondas) >= 3:
            v.senal("salir")
            return False
        return original(estado, eventos)
    v.ronda = ronda
    app.root.after(1, lambda: v.senal("iniciar"))
    ejecutar(m, v)
    assert rondas[:3] == [1, 2, 3]          # siguió sin cerrar el menú


@requiere_pantalla
def test_terminar_desde_el_menu_muestra_el_resultado(app):
    config, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)))
    v = app.partida(config)
    guion(v, "una", "una", v._abrir_menu,
          lambda: v.opciones_menu["bandera"].invoke(), "menu")
    r = ejecutar(m, v)
    assert r.motivo is Motivo.TERMINADA and r.ganador == "a"
    assert v.canvas.find_withtag("cartel")      # la clasificación
    assert v.despues() == "menu"


@requiere_pantalla
@pytest.mark.parametrize("simbolo, accion", [
    ("reiniciar", "reiniciar"), ("engrane", "configurar"),
    ("casa", "menu")])
def test_cada_opcion_del_menu(app, simbolo, accion):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    v = app.partida(config)
    guion(v, v._abrir_menu, lambda: v.opciones_menu[simbolo].invoke())
    assert ejecutar(m, v) is None
    assert v.accion == accion and v._menu is None


@requiere_pantalla
def test_el_menu_principal_vuelve_a_la_portada(app, monkeypatch):
    """En la aplicación, «Menú principal» sale de la configuración."""
    from tanques.controlador import aplicacion as ap
    llamadas = []
    monkeypatch.setattr(ap, "_validar", lambda *a: True)
    monkeypatch.setattr(ap, "_jugar",
                        lambda *a: (llamadas.append(1), ("menu", 5))[1])
    monkeypatch.setattr(app, "configurar", lambda c: c)
    ap._configurar_y_jugar(app, cfg.Configuracion(), RAIZ)
    assert llamadas == [1]
