"""El editor de programas dentro del juego y el generador aleatorio."""
from pathlib import Path

import pytest

from tanques import config as cfg
from tanques.lenguaje import CATALOGO, Interprete, generar_programa

RAIZ = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- generador
@pytest.mark.parametrize("semilla", range(60))
def test_el_programa_aleatorio_siempre_es_valido(semilla):
    programa, errores = Interprete().analizar(generar_programa(semilla=semilla))
    assert errores == []
    assert 6 <= len(programa) <= 12


def test_misma_semilla_mismo_programa_y_largo_pedido():
    assert generar_programa(semilla=7) == generar_programa(semilla=7)
    assert len(Interprete().analizar(generar_programa(4, 1))[0]) == 4


def test_cada_instruccion_del_catalogo_es_valida():
    for plantilla, descripcion in CATALOGO:
        _, errores = Interprete().analizar(plantilla)
        assert errores == [], plantilla
        assert descripcion


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
def app(tmp_path):
    (tmp_path / "tanques").mkdir()
    a = grafica.AppGrafica(tmp_path)
    a.root.withdraw()
    yield a
    a.destruir()


def editor(app, ruta=None, **kw):
    e = grafica.EditorPrograma(app, ruta, 1, "#2E5E8C", cfg.Configuracion(),
                               **kw)
    e._confirmar = lambda *_a, **_k: True          # sin cuadros de diálogo
    return e


def escribir(e, texto):
    e.texto.delete("1.0", "end")
    e.texto.insert("1.0", texto)
    e.revisar()


@requiere_pantalla
def test_avisa_si_esta_bien_escrito(app):
    e = editor(app)
    try:
        assert e.contenido() == "" and "Escribe" in e.estado["text"]
        escribir(e, "MOV(N)\nIF V < 40 THEN REPARAR")
        assert e.validas == 2 and e.con_error == 0
        assert "Bien escrito" in e.estado["text"]
        assert not e.texto.tag_ranges("error")
    finally:
        e.cerrar()


@requiere_pantalla
def test_avisa_las_lineas_con_error(app):
    e = editor(app)
    try:
        escribir(e, "MOV(N)\nDISPARAR\nAMT(X)")
        assert e.validas == 1 and e.con_error == 2
        assert set(e._errores) == {2, 3}
        assert "error" in e.texto.tag_names("2.1")
        assert "error" not in e.texto.tag_names("1.1")
        assert "Línea 2" in e.lista.get("1.0", "end")
        assert "2 líneas con errores" in e.estado["text"]
        escribir(e, "disparar")
        assert e.validas == 0 and "Ninguna" in e.estado["text"]
    finally:
        e.cerrar()


@requiere_pantalla
def test_insertar_desde_la_lista_de_instrucciones(app):
    e = editor(app)
    try:
        e.insertar("MOV(N)")
        e.insertar("ESCUDO")
        assert e.contenido() == "MOV(N)\nESCUDO"
        assert e.validas == 2
        assert len(e.fichas) == len(CATALOGO)
    finally:
        e.cerrar()


@requiere_pantalla
def test_aleatorio_se_puede_modificar(app):
    e = editor(app)
    try:
        e.aleatorio()
        assert e.validas >= 6 and e.con_error == 0
        e.texto.insert("end", "\nESPERAR")
        e.revisar()
        assert e.contenido().endswith("ESPERAR")
    finally:
        e.cerrar()


@requiere_pantalla
def test_guardar_un_programa_nuevo(app):
    guardados = []
    e = editor(app, al_guardar=guardados.append)
    e.nombre.set("mi_tanque")
    escribir(e, "MOV(E)\nAMT(E)")
    assert e.guardar()
    ruta = app.raiz / "tanques" / "mi_tanque.txt"
    assert guardados == [ruta]
    assert ruta.read_text(encoding="utf-8") == "MOV(E)\nAMT(E)\n"


@requiere_pantalla
def test_no_guarda_sin_nombre_valido(app):
    e = editor(app)
    try:
        e.nombre.set("mal/nombre")
        escribir(e, "MOV(E)")
        assert not e.guardar()
        assert "✗" in e.donde["text"]
    finally:
        e.cerrar()


@requiere_pantalla
def test_editar_un_programa_existente(app):
    ruta = app.raiz / "tanques" / "viejo.txt"
    ruta.write_text("MOV(N)\n", encoding="utf-8")
    e = editor(app, ruta)
    assert e.contenido() == "MOV(N)\n" and e.nombre.get() == "viejo"
    assert not e.hay_cambios()
    e.texto.insert("end", "AMT(S)")
    assert e.hay_cambios()
    assert e.guardar()
    assert ruta.read_text(encoding="utf-8") == "MOV(N)\nAMT(S)\n"


@requiere_pantalla
def test_programar_desde_la_configuracion_asigna_el_tanque(app):
    pantalla = grafica.PantallaConfiguracion(app, cfg.Configuracion())
    e = pantalla.programar(2)
    e._confirmar = lambda *_a, **_k: True
    e.nombre.set("nuevo")
    escribir(e, "IF RADAR(N) > 0 THEN AMT(N)\nMOV(N)")
    assert e.guardar()
    assert pantalla.rutas[2].get() == "tanques/nuevo.txt"
    assert "2 instrucciones" in pantalla.avisos[2]["text"]


@requiere_pantalla
def test_el_boton_editar_del_visor_abre_el_editor(app):
    ruta = app.raiz / "tanques" / "malo.txt"
    ruta.write_text("MOV(N)\nDISPARAR\n", encoding="utf-8")
    visor = grafica.VisorPrograma(app, ruta, 1, "#2E5E8C",
                                  cfg.Configuracion())
    try:
        assert visor.con_error == 1
        e = visor.editar()
        e._confirmar = lambda *_a, **_k: True
        assert isinstance(e, grafica.EditorPrograma)
        assert e.con_error == 1
        escribir(e, "MOV(N)\nESPERAR")
        assert e.guardar()
        assert visor.con_error == 0 and visor.validas == 2
    finally:
        visor.cerrar()
