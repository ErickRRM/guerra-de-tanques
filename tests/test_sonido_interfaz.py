"""Sonidos de la interfaz: portada, botones, selector de velocidad y teclas.

No se escucha nada: un reproductor falso anota qué se pidió tocar. Se
saltan si no hay pantalla.
"""
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
grafica = pytest.importorskip("tanques.vista.grafica")
from tanques.vista import sonido  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]

try:
    tk.Tk().destroy()
    HAY_PANTALLA = True
except tk.TclError:
    HAY_PANTALLA = False
pytestmark = pytest.mark.skipif(not HAY_PANTALLA, reason="no hay pantalla")


class Falso:
    def __init__(self):
        self.tocados, self.detenidos, self.volumenes = [], [], []
        self.musicas = []

    def tocar(self, nombre, ruta):
        self.tocados.append(nombre)
        return True

    def detener(self, nombre):
        self.detenidos.append(nombre)

    def musica(self, ruta, volumen):
        self.musicas.append(volumen)
        return True

    def volumen_musica(self, volumen):
        self.volumenes.append(volumen)

    def parar_musica(self):
        self.detenidos.append("musica")

    def cerrar(self):
        pass


@pytest.fixture
def app():
    a = grafica.AppGrafica(RAIZ)
    a.root.withdraw()
    falso = Falso()
    a.sonido._reproductor = falso
    a.sonido._rutas = {n: Path(f"{n}.wav") for n in sonido.NOMBRES}
    a.falso = falso
    yield a
    a.destruir()


def test_cada_boton_suena_segun_su_estilo(app):
    marco = tk.Frame(app.root)
    primario = app.boton(marco, "Iniciar", lambda: None, primario=True)
    normal = app.boton(marco, "Una ronda", lambda: None)
    volver = app.boton(marco, "Volver", lambda: None, icono="atras")
    for b in (primario, normal, volver):
        b.invoke()
    assert app.falso.tocados == ["confirmar", "clic", "atras"]


def test_pasar_el_raton_y_el_boton_apagado(app):
    b = app.boton(tk.Frame(app.root), "Pausar", lambda: None)
    b._sobre(True)
    app.activar(b, False)
    b._sobre(True)                          # apagado: no suena al pasar
    b._presionar(None)
    b.invoke()                              # apagado: no hace nada
    assert app.falso.tocados == ["hover", "apagado"]


def test_el_selector_de_velocidad_hace_tic(app):
    marco = tk.Frame(app.root)
    seg = grafica.Segmentos(marco, app, valor=5)
    seg.pack()
    app.root.update_idletasks()

    class Evento:
        x = seg.winfo_width() - 2
        type = tk.EventType.ButtonPress
    seg._clic(Evento())
    seg._clic(Evento())                     # mismo valor: no repite
    assert app.falso.tocados == ["tic"]


def test_la_portada_toca_el_arranque_y_luego_la_musica(app):
    app.sonido._musica = Path("musica.wav")
    app.root.after(50, lambda: app._elegir("salir"))
    app.menu()
    assert app.falso.tocados[0] == "intro"
    app._arrancar_musica()
    assert app.falso.musicas == [0.5 ** 1.7]
    app._nueva_pantalla("otra")             # la música sigue sonando
    assert app.sonido._sonando


def test_el_volumen_de_la_musica_se_sube_y_se_baja(app):
    app.sonido._musica = Path("musica.wav")
    marco = tk.Frame(app.root)
    uno = grafica.ControlMusica(marco, app)
    otro = grafica.ControlMusica(marco, app)
    uno._paso(1)
    assert app.sonido.volumen_musica == 6
    assert otro.barras.get() == 6 and otro.cifra["text"] == "6"
    app.cambiar_volumen_musica(0)               # en cero se calla
    assert not app.sonido._sonando and otro.cifra["text"] == "—"
    app.cambiar_volumen_musica(15)
    assert app.sonido.volumen_musica == 10 and app.sonido._sonando
    assert app.falso.musicas[-1] == 1.0


def test_musica_y_efectos_se_apagan_por_separado(app):
    app.sonido._musica = Path("musica.wav")
    app.sonido.musica()
    app.alternar_musica()
    assert not app.sonido._sonando and app.sonido.efectos
    app.boton(tk.Frame(app.root), "Iniciar", lambda: None).invoke()
    assert app.falso.tocados[-1] == "clic"        # los efectos siguen
    app.cambiar_volumen_musica(3)                  # subirla la enciende
    assert app.sonido.musica_activa and app.sonido._sonando
    app.alternar_efectos()
    n = len(app.falso.tocados)
    app.boton(tk.Frame(app.root), "Iniciar", lambda: None).invoke()
    assert len(app.falso.tocados) == n            # efectos callados
    assert app.sonido._sonando                    # la música sigue


def test_el_menu_esta_arriba_a_la_derecha_en_cada_pantalla(app):
    app._nueva_pantalla("Configuración")
    app.root.update_idletasks()
    info = app.boton_menu.place_info()
    assert (info["relx"], info["anchor"]) == ("1", "ne")
    app.abrir_menu()                    # sin partida: solo el sonido
    assert app._desplegable is not None and app.opciones_menu == {}
    assert set(app._interruptores) == {"musica", "efectos"}
    assert app._desplegable.place_info()["anchor"] == "ne"
    app.alternar_menu()
    assert app._desplegable is None


def test_las_teclas_suenan_como_su_boton(app):
    config = grafica.Configuracion()
    v = app.partida(config)
    v._si_activo("iniciar")                       # activo: confirma
    v._si_activo("pausar")                        # aún no, va de nuevo
    assert app.falso.tocados[:1] == ["confirmar"]
    v.senal("salir")


def test_la_primera_barra_apaga_la_musica(app):
    marco = tk.Frame(app.root)
    marco.pack()
    seg = grafica.Segmentos(marco, app, valor=1, minimo=0)
    seg.pack()
    app.root.update_idletasks()

    class Evento:
        x, type = 1, tk.EventType.ButtonPress
    seg._clic(Evento())
    assert seg.get() == 0
