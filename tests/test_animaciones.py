"""Pruebas de las animaciones de la ventana de partida.

No se mira cómo se ven —eso se revisó con capturas— sino que cada acción
dispare su animación, que lo dibujado se borre y que la pausa a media
ronda funcione. Se saltan si no hay pantalla.
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
from tanques.vista import animaciones  # noqa: E402
from tanques.vista.animaciones import Animador, arco  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]

try:
    tk.Tk().destroy()
    HAY_PANTALLA = True
except tk.TclError:
    HAY_PANTALLA = False
pytestmark = pytest.mark.skipif(not HAY_PANTALLA, reason="no hay pantalla")

METODOS = ("rafaga", "misil", "explosion", "humo", "chispas", "deslizar",
           "embestida", "radar", "anillo", "texto", "mina_nueva", "golpe",
           "escudo", "bloqueo", "curar", "mina_armada")


@pytest.fixture
def app(monkeypatch):
    # Velocidad normal (sí anima), pero sin esperar entre cuadros.
    monkeypatch.setattr(grafica, "retardo_ms", lambda v: 256)
    a = grafica.AppGrafica(RAIZ)
    a.root.withdraw()
    yield a
    a.destruir()


@pytest.fixture
def lienzo(app):
    c = tk.Canvas(app.root, width=400, height=400)
    c.pack()
    return c


def partida(app, *tanques, **cambios):
    config = replace(cfg.Configuracion(), **cambios)
    config = replace(config, tanques=tuple(
        cfg.TanqueConfig(n, f"{n}.txt") for n, _, _ in tanques))
    programas = [Interprete().analizar(t, nombre=n)[0]
                 for n, t, _ in tanques]
    motor = Motor(config, programas, posiciones=[p for _, _, p in tanques])
    v = app.partida(config)
    v._esperar_ms = lambda ms: v.accion is None
    return motor, v


def espiar(v):
    """Registra qué animaciones pide la ventana, sin cambiar lo que hacen."""
    llamadas = []

    class Espia(Animador):
        pass

    for nombre in METODOS:
        original = getattr(Animador, nombre)

        def envuelto(self, *a, _n=nombre, _o=original, **k):
            llamadas.append(_n)
            return _o(self, *a, **k)
        setattr(Espia, nombre, envuelto)

    v._crear_animador = lambda f: Espia(v.canvas, v.celda, v._esperar_ms, f)
    return llamadas


def guion(v, *senales):
    cola = list(senales)
    original = v._esperar_senal

    def siguiente():
        if not cola:
            return original()
        valor = cola.pop(0)
        v.senal(valor)
        return valor
    v._esperar_senal = siguiente


# ---------------------------------------------------------------- animador
def test_el_misil_sube_en_arco():
    a, b = (0, 100), (200, 100)
    assert arco(a, b, 50, 0.5) == (100, 50)
    assert arco(a, b, 50, 0) == a and arco(a, b, 50, 1) == b


@pytest.mark.parametrize("metodo, args", [
    ("rafaga", ((50, 50), (250, 50), True)),
    ("misil", ((50, 50), (250, 250))),
    ("explosion", ((100, 100),)),
    ("humo", ((100, 100),)),
    ("radar", ((50, 50), Direccion.S, 3)),
    ("radar", ((50, 50), Direccion.E, -2)),
    ("anillo", ((100, 100), "#2E5E8C", 0.2, 0.5)),
    ("texto", ((100, 100), "−10", "#C62828")),
    ("mina_nueva", ((100, 100), (120, 120), 0.45)),
    ("escudo", ((100, 100),)),
    ("bloqueo", ((100, 100),)),
    ("curar", ((100, 100),)),
    ("mina_armada", ((100, 100),)),
])
def test_cada_efecto_borra_lo_que_dibuja(lienzo, metodo, args):
    cuadros = []
    a = Animador(lienzo, 50, lambda ms: cuadros.append(ms) or True)
    assert getattr(a, metodo)(*args) is True
    assert len(cuadros) >= 2
    assert lienzo.find_withtag("efecto") == ()


def test_deslizar_mueve_el_sprite_hasta_el_destino(lienzo):
    lienzo.create_rectangle(40, 40, 60, 60, tags="tanque1")
    Animador(lienzo, 50, lambda ms: True).deslizar("tanque1", (50, 50),
                                                   (150, 50))
    assert lienzo.coords("tanque1") == [140.0, 40.0, 160.0, 60.0]


def test_la_embestida_regresa_a_su_lugar(lienzo):
    lienzo.create_rectangle(40, 40, 60, 60, tags="tanque1")
    Animador(lienzo, 50, lambda ms: True).embestida("tanque1", (50, 50),
                                                    (100, 50))
    x0, y0, x1, y1 = lienzo.coords("tanque1")
    assert (round(x0), round(y0), round(x1), round(y1)) == (40, 40, 60, 60)


def test_la_animacion_se_corta_si_el_usuario_sale(lienzo):
    cuadros = []
    a = Animador(lienzo, 50, lambda ms: cuadros.append(ms) and False)
    assert a.explosion((100, 100)) is False
    assert len(cuadros) == 1
    assert lienzo.find_withtag("efecto") == ()


# ---------------------------------------------------------------- ventana
def test_cada_accion_tiene_su_animacion(app):
    motor, v = partida(
        app,
        ("a", "AMT(E)\nMISIL(E)\nIF RADAR(S) > 0 THEN AMT(S)\nESCUDO",
         (1, 1)),
        ("b", "MINA(SE)\nESPERAR", (4, 1)),
        ("c", "ESPERAR\nMOV(N)", (5, 2)), vida_inicial=12)
    llamadas = espiar(v)
    guion(v, "una", "una", "una", "una", "salir")
    ejecutar(motor, v)
    assert motor.estado().ronda == 4
    assert {"rafaga", "chispas", "texto", "mina_nueva", "misil",
            "explosion", "humo", "deslizar", "radar", "escudo",
            "golpe"} <= set(llamadas)


def test_el_choque_y_la_pared(app):
    motor, v = partida(app, ("a", "MOV(E)\nMOV(N)", (1, 1)),
                       ("b", "ESPERAR", (2, 1)))
    llamadas = espiar(v)
    guion(v, "una", "una", "salir")
    ejecutar(motor, v)
    assert llamadas.count("embestida") == 2          # al tanque y a la pared


def test_al_final_del_turno_solo_queda_el_estado(app):
    motor, v = partida(app, ("a", "AMT(E)", (1, 1)),
                       ("b", "ESPERAR", (3, 1)))
    guion(v, "una", "salir")
    ejecutar(motor, v)
    assert v.canvas.find_withtag("efecto") == ()
    assert v.canvas.find_withtag("tanque1") and v.canvas.find_withtag(
        "tanque2")


def test_a_velocidad_maxima_no_se_anima(app, monkeypatch):
    monkeypatch.setattr(grafica, "retardo_ms", lambda v: 30)
    motor, v = partida(app, ("a", "AMT(E)", (1, 1)),
                       ("b", "ESPERAR", (3, 1)))
    llamadas = espiar(v)
    guion(v, "una", "salir")
    ejecutar(motor, v)
    assert llamadas == []


def test_pausar_a_media_ronda_detiene_en_el_siguiente_turno(app):
    motor, v = partida(app, ("a", "ESPERAR", (1, 1)),
                       ("b", "ESPERAR", (3, 3)), ("c", "ESPERAR", (5, 5)))
    guion(v, "iniciar", "salir")
    original = v.turno
    llamados = []

    def turno(estado, eventos):
        if not llamados:
            v.senal("pausar")        # el usuario pausa durante el 1.er turno
        llamados.append(1)
        return original(estado, eventos)

    v.turno = turno
    ejecutar(motor, v)
    assert sum(t.turnos for t in motor.registro.tanques) == 1


def test_una_ronda_no_se_detiene_entre_turnos(app):
    motor, v = partida(app, ("a", "ESPERAR", (1, 1)),
                       ("b", "ESPERAR", (3, 3)), ("c", "ESPERAR", (5, 5)))
    guion(v, "una", "salir")
    ejecutar(motor, v)
    assert sum(t.turnos for t in motor.registro.tanques) == 3


def test_la_mina_bajo_un_tanque_se_ve(app):
    # b lanza la mina sobre a; sin armar, queda debajo de a.
    motor, v = partida(app, ("a", "ESPERAR", (3, 3)),
                       ("b", "MINA(NE)", (2, 4)), mina_rondas_armado=1)
    guion(v, "una", "salir")
    ejecutar(motor, v)
    assert v.canvas.find_withtag("en_3_3")


def test_el_retroceso_y_el_temblor_dejan_todo_en_su_lugar(lienzo):
    lienzo.create_rectangle(40, 40, 60, 60, tags="tanque1")
    lienzo.create_rectangle(0, 0, 10, 10, tags="casilla")
    a = Animador(lienzo, 50, lambda ms: True)
    assert a.rafaga((50, 50), (250, 50), True, etiqueta="tanque1")
    assert a.misil((50, 50), (250, 250), etiqueta="tanque1")
    assert a.explosion((100, 100), grande=True)
    assert a.embestida("tanque1", (50, 50), (100, 50))
    assert [round(v) for v in lienzo.coords("tanque1")] == [40, 40, 60, 60]
    assert [round(v) for v in lienzo.coords("casilla")] == [0, 0, 10, 10]


def test_el_temblor_se_deshace_aunque_se_corte(lienzo):
    lienzo.create_rectangle(0, 0, 10, 10, tags="casilla")
    a = Animador(lienzo, 50, lambda ms: False)
    assert a.explosion((100, 100), grande=True) is False
    assert [round(v) for v in lienzo.coords("casilla")] == [0, 0, 10, 10]


def test_el_golpe_devuelve_sus_colores(lienzo):
    pieza = lienzo.create_rectangle(40, 40, 60, 60, fill="#2E5E8C",
                                    tags="tanque1")
    Animador(lienzo, 50, lambda ms: True).golpe("tanque1", (50, 50))
    assert lienzo.itemcget(pieza, "fill") == "#2E5E8C"
    assert [round(v) for v in lienzo.coords(pieza)] == [40, 40, 60, 60]


def test_cada_arma_suena(lienzo):
    sonidos = []
    a = Animador(lienzo, 50, lambda ms: True, sonar=sonidos.append)
    a.rafaga((50, 50), (250, 50), True, blanco=True)
    a.misil((50, 50), (250, 250))
    a.explosion((100, 100))
    a.explosion((100, 100), grande=False)
    a.embestida("nada", (50, 50), (100, 50))
    a.radar((50, 50), Direccion.S, 3)
    a.escudo((50, 50))
    a.curar((50, 50))
    assert sonidos == ["ametralladora", "impacto", "misil", "explosion",
                       "explosion_chica", "motor", "choque", "radar",
                       "escudo", "reparar"]


def test_la_explosion_deja_quemadura(app):
    motor, v = partida(app, ("a", "MISIL(E)", (1, 1)),
                       ("b", "ESPERAR", (3, 1)))
    guion(v, "una", "salir")
    ejecutar(motor, v)
    assert (3, 1) in v._marcas
    assert v.canvas.find_withtag("quemadura")


def test_el_sonido_se_controla_desde_el_menu_de_la_partida(app):
    motor, v = partida(app, ("a", "ESPERAR", (1, 1)),
                       ("b", "ESPERAR", (3, 1)))
    app.sonido._reproductor = object()        # como si hubiera bocinas
    v._abrir_menu()
    musica = app._interruptores["musica"]
    efectos = app._interruptores["efectos"]
    musica.invoke()
    assert not app.sonido.musica_activa and app.sonido.efectos
    assert musica.texto == "Apagada" and efectos.texto == "Encendidos"
    efectos.invoke()
    assert not app.sonido.efectos and efectos.icono == "mudo"
    v.senal("salir")
