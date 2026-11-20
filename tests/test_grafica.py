"""Pruebas de la interfaz gráfica.

Abren ventanas de verdad, así que se saltan si no hay pantalla (por ejemplo
en un servidor sin entorno gráfico). Los botones se pulsan con `senal()`
programada con `after`, que es lo mismo que hace el clic.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from tanques import config as cfg
from tanques.controlador import ejecutar
from tanques.lenguaje import Interprete
from tanques.modelo import Direccion, Motor

tk = pytest.importorskip("tkinter")
grafica = pytest.importorskip("tanques.vista.grafica")
from tanques.vista import sprites  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _hay_pantalla():
    try:
        tk.Tk().destroy()
        return True
    except tk.TclError:
        return False


requiere_pantalla = pytest.mark.skipif(not _hay_pantalla(),
                                       reason="no hay pantalla")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(grafica, "retardo_ms", lambda v: 1)
    a = grafica.AppGrafica(RAIZ)
    a.root.withdraw()
    yield a
    a.destruir()


def motor_de(*tanques, **cambios):
    config = replace(cfg.Configuracion(), **cambios)
    config = replace(config, tanques=tuple(
        cfg.TanqueConfig(n, f"{n}.txt") for n, _, _ in tanques))
    programas = [Interprete().analizar(t, nombre=n)[0]
                 for n, t, _ in tanques]
    return config, Motor(config, programas,
                         posiciones=[p for _, _, p in tanques])


def pulsar(app, *senales):
    """Entrega una secuencia de clics, uno cada vez que la ventana espera.

    No se usan temporizadores: si dos vencen juntos, Tk los atiende en el
    mismo ciclo y el primer clic se pierde, cosa que con un usuario real no
    ocurre. Agotado el guion, la ventana vuelve a esperar de verdad.
    """
    v = app._partida
    cola = list(senales)
    original = v._esperar_senal

    def siguiente():
        if not cola:
            return original()
        valor = cola.pop(0)
        v.senal(valor)
        return valor

    v._esperar_senal = siguiente


# ---------------------------------------------------------------- sin ventana
def test_retardo_segun_la_velocidad():
    valores = [grafica.retardo_ms(v) for v in range(1, 11)]
    assert valores == sorted(valores, reverse=True)
    assert valores[0] == 1200 and valores[-1] < 60
    assert grafica.retardo_ms(0) == grafica.retardo_ms(1)
    assert grafica.retardo_ms(99) == grafica.retardo_ms(10)


@pytest.mark.parametrize("direccion, punta", [
    (Direccion.N, (0, -1)), (Direccion.E, (1, 0)),
    (Direccion.S, (0, 1)), (Direccion.O, (-1, 0))])
def test_el_canon_apunta_a_la_direccion(direccion, punta):
    assert sprites.rotar(0, -1, direccion) == punta


def test_oscurecer_da_el_tono_de_la_torreta():
    assert sprites.oscurecer("#2E5E8C") == "#1E3E5D"


# ---------------------------------------------------------------- partida
@requiere_pantalla
def test_la_partida_no_empieza_hasta_pulsar(app):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    app.partida(config)
    pulsar(app, "salir")
    assert ejecutar(m, app._partida) is None
    assert m.estado().ronda == 0


@requiere_pantalla
def test_una_ronda_avanza_de_una_en_una(app):
    config, m = motor_de(("a", "MOV(S)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    app.partida(config)
    pulsar(app, "una", "una", "salir")
    ejecutar(m, app._partida)
    assert m.estado().ronda == 2
    assert app._partida.accion == "salir"


@requiere_pantalla
def test_partida_completa_en_automatico(app):
    config, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                         vida_inicial=30)
    app.partida(config)
    pulsar(app, "iniciar")
    resultado = ejecutar(m, app._partida)
    assert resultado.ganador == "a"
    v = app._partida
    assert v.botones["iniciar"]["state"] == "disabled"
    assert v.botones["reiniciar"]["state"] == "normal"
    assert v.canvas.find_withtag("cartel")
    pulsar(app, "reiniciar")
    assert v.despues() == "reiniciar"


@requiere_pantalla
def test_pausar_detiene_la_reproduccion(app):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    app.partida(config)
    v = app._partida
    app.root.after(10, lambda: v.senal("iniciar"))
    app.root.after(200, lambda: v.senal("pausar"))
    app.root.after(400, lambda: setattr(v, "ronda_en_pausa",
                                        m.estado().ronda))
    app.root.after(700, lambda: v.senal("salir"))
    ejecutar(m, v)
    assert 0 < v.ronda_en_pausa <= m.estado().ronda
    assert m.estado().ronda - v.ronda_en_pausa <= 1


@requiere_pantalla
def test_cerrar_la_ventana_termina_la_partida(app):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    app.partida(config)
    app.root.after(50, app._al_cerrar)
    assert ejecutar(m, app._partida) is None
    assert app.cerrada


@requiere_pantalla
def test_el_tablero_dibuja_lo_que_dice_el_estado(app):
    config, m = motor_de(("a", "MINA\nESCUDO", (1, 1)),
                         ("b", "ESPERAR", (3, 3)), ("c", "MISIL(3,3)",
                                                    (8, 8)), vida_inicial=30)
    app.partida(config)
    pulsar(app, "una", "una", "salir")
    ejecutar(m, app._partida)
    c = app._partida.canvas
    assert c.find_withtag("tanque1") and c.find_withtag("tanque3")
    assert not c.find_withtag("tanque2")          # destruido
    assert c.find_withtag("refaccion")            # lo que dejó b
    assert c.find_withtag("sin_armar")
    assert c.find_withtag("escudo")


@requiere_pantalla
def test_el_panel_muestra_vida_e_instruccion(app):
    config, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)))
    app.partida(config)
    pulsar(app, "una", "salir")
    ejecutar(m, app._partida)
    tarjeta = app._partida._tarjetas["b"]
    assert tarjeta["vida"]["text"] == "90"
    assert "ESPERAR" in app._partida._tarjetas["b"]["linea"]["text"]
    assert "AMT(E)" in app._partida._tarjetas["a"]["linea"]["text"]


# ---------------------------------------------------------------- configuración
@requiere_pantalla
def test_la_configuracion_lee_el_formulario(app):
    base = cfg.cargar(RAIZ / "config.json")
    pantalla = grafica.PantallaConfiguracion(app, base)
    pantalla.rutas[1].set("")                      # el tanque 2 no juega
    pantalla.rutas[3].set("tanques/cazador.txt")   # repite el archivo
    pantalla.semilla.set("7")
    nueva, problemas = pantalla.leer()
    assert problemas == []
    assert [t.nombre for t in nueva.tanques] == ["cazador", "explorador",
                                                 "cazador-2"]
    assert nueva.semilla == 7


@requiere_pantalla
def test_la_configuracion_rechaza_valores_invalidos(app):
    pantalla = grafica.PantallaConfiguracion(app,
                                             cfg.cargar(RAIZ / "config.json"))
    pantalla.semilla.set("abc")
    nueva, problemas = pantalla.leer()
    assert nueva is None and "Semilla" in problemas[0]

    for r in pantalla.rutas:
        r.set("")
    pantalla.semilla.set("1")
    _, problemas = pantalla.leer()
    assert "hace falta al menos un tanque" in problemas
