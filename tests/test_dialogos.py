"""Las ventanas emergentes con el diseño del juego.

Cada prueba programa el clic con `after` y luego abre la ventana, que
espera la respuesta como lo haría con el usuario.
"""
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
grafica = pytest.importorskip("tanques.vista.grafica")

try:
    tk.Tk().destroy()
    HAY_PANTALLA = True
except tk.TclError:
    HAY_PANTALLA = False
pytestmark = pytest.mark.skipif(not HAY_PANTALLA, reason="no hay pantalla")


@pytest.fixture
def app(tmp_path):
    (tmp_path / "tanques").mkdir()
    a = grafica.AppGrafica(tmp_path)
    a.root.withdraw()
    yield a
    a.destruir()


def con(monkeypatch, app, clase, accion):
    original = clase.mostrar

    def mostrar(self):
        app.root.after(30, lambda: accion(self))
        return original(self)
    monkeypatch.setattr(clase, "mostrar", mostrar)


def botones(v):
    return {b.texto: b for b in v.pie.winfo_children()}


def test_preguntar_si_y_no(app, monkeypatch):
    vistas = []

    def pulsar_si(v):
        vistas.append((v.color, botones(v)["Borrar"].estilo))
        botones(v)["Borrar"].invoke()
    con(monkeypatch, app, grafica.Dialogo, pulsar_si)
    assert app.preguntar(app.root, "Borrar todo", "¿Seguro?", si="Borrar",
                         peligro=True) is True
    assert vistas == [(grafica.ROJO_UI, "peligro")]


def test_preguntar_cancelar_y_escape_dan_no(app, monkeypatch):
    con(monkeypatch, app, grafica.Dialogo,
        lambda v: botones(v)["Cancelar"].invoke())
    assert app.preguntar(app.root, "¿Algo?", "texto") is False
    con(monkeypatch, app, grafica.Dialogo, lambda v: v.cancelar())
    assert app.preguntar(app.root, "¿Algo?", "texto") is False


def test_avisar_muestra_el_detalle(app, monkeypatch):
    vistos = []

    def leer(v):
        vistos.append(v.detalle.get("1.0", "end"))
        botones(v)["Entendido"].invoke()
    con(monkeypatch, app, grafica.Dialogo, leer)
    app.mostrar_errores("Errores de sintaxis, la partida no inicia:\n"
                        "  a.txt, línea 2: instrucción desconocida")
    assert "a.txt, línea 2" in vistos[0]


def test_selector_de_color(app, monkeypatch):
    def elegir(v):
        v.elegir("#DC2626")
        botones(v)["Usar color"].invoke()
    con(monkeypatch, app, grafica.SelectorColor, elegir)
    assert app.elegir_color(app.root, 1, "#2E5E8C") == "#DC2626"


def test_selector_de_color_valida_el_codigo(app, monkeypatch):
    estados = []

    def escribir(v):
        v.codigo.set("verde")
        estados.append((v.actual, str(v.usar["state"])))
        v.codigo.set("12ab34")
        estados.append((v.actual, str(v.usar["state"])))
        v.cancelar()
    con(monkeypatch, app, grafica.SelectorColor, escribir)
    assert app.elegir_color(app.root, 2, "#2E5E8C") is None
    assert estados == [(None, "disabled"), ("#12AB34", "normal")]


def test_selector_de_programa(app, monkeypatch):
    carpeta = app.raiz / "tanques"
    (carpeta / "bueno.txt").write_text("MOV(N)\nAMT(N)\n", encoding="utf-8")
    (carpeta / "malo.txt").write_text("DISPARAR\n", encoding="utf-8")
    (carpeta / "extra").mkdir()
    (carpeta / "extra" / "otro.txt").write_text("ESPERAR\n",
                                                encoding="utf-8")
    vistos = {}

    def elegir(v):
        nombres = [r.name for r in v._filas]
        vistos["lista"] = nombres
        v.activar_entrada(carpeta / "extra")       # entrar a la carpeta
        vistos["dentro"] = [r.name for r in v._filas]
        v.subir()
        v.seleccionar(carpeta / "bueno.txt")
        vistos["estado"] = v.estado["text"]
        botones(v)["Elegir"].invoke()
    con(monkeypatch, app, grafica.SelectorPrograma, elegir)
    assert app.elegir_programa(app.root, 1) == carpeta / "bueno.txt"
    assert vistos["lista"] == ["extra", "bueno.txt", "malo.txt"]
    assert vistos["dentro"] == ["otro.txt"]
    assert "2 instrucciones" in vistos["estado"]


def test_examinar_asigna_el_programa_elegido(app, monkeypatch):
    from tanques import config as cfg
    (app.raiz / "tanques" / "p.txt").write_text("MOV(N)\n", encoding="utf-8")
    pantalla = grafica.PantallaConfiguracion(app, cfg.Configuracion())
    monkeypatch.setattr(app, "elegir_programa",
                        lambda *_a: app.raiz / "tanques" / "p.txt")
    pantalla._examinar(3)
    assert pantalla.rutas[3].get() == "tanques/p.txt"
    monkeypatch.setattr(app, "elegir_color", lambda *_a: "#abcdef")
    pantalla._color(3)
    assert pantalla.colores[3] == "#ABCDEF"


def test_no_quedan_ventanas_nativas():
    fuente = Path(grafica.__file__).read_text(encoding="utf-8")
    for nativa in ("messagebox", "colorchooser", "filedialog"):
        assert nativa not in fuente
