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
    config, m = motor_de(("a", "MINA(SE)\nESCUDO", (1, 1)),
                         ("b", "ESPERAR", (3, 3)), ("c", "MISIL(O)",
                                                    (8, 3)), vida_inicial=10,
                         mina_rondas_armado=3)
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
    assert tarjeta["vida"]["text"] == "95"
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


# ---------------------------------------------------------------- usabilidad
@requiere_pantalla
def test_cada_fila_revisa_su_programa_al_momento(app):
    pantalla = grafica.PantallaConfiguracion(app,
                                             cfg.cargar(RAIZ / "config.json"))
    assert "instrucciones" in pantalla.avisos[0]["text"]
    assert "no juega" in pantalla.avisos[5]["text"]
    pantalla.rutas[5].set("tanques/no_existe.txt")
    assert "no existe" in pantalla.avisos[5]["text"]
    pantalla.rutas[5].set("tanques/con_errores.txt")
    assert "9 errores" in pantalla.avisos[5]["text"]
    assert pantalla.cuenta["text"] == "4 de 6 tanques"


@requiere_pantalla
def test_un_programa_con_algunas_lineas_malas_si_juega(app):
    pantalla = grafica.PantallaConfiguracion(app,
                                             cfg.cargar(RAIZ / "config.json"))
    pantalla.rutas[4].set("tanques/con_errores.txt")
    assert "se saltan" in pantalla.avisos[4]["text"]
    _, problemas = pantalla.leer()
    assert problemas == []


@requiere_pantalla
def test_no_se_inicia_si_un_programa_no_tiene_nada_valido(app, tmp_path):
    malo = tmp_path / "malo.txt"
    malo.write_text("DISPARAR\nmov(n)\n", encoding="utf-8")
    pantalla = grafica.PantallaConfiguracion(app,
                                             cfg.cargar(RAIZ / "config.json"))
    pantalla.rutas[4].set(str(malo))
    assert "ninguna instrucción válida" in pantalla.avisos[4]["text"]
    _, problemas = pantalla.leer()
    assert any("tanques 5" in p for p in problemas)


@requiere_pantalla
def test_el_visor_marca_las_lineas_con_error(app):
    v = grafica.VisorPrograma(app, RAIZ / "tanques" / "con_errores.txt", 1,
                              "#2E5E8C", cfg.Configuracion())
    try:
        texto = v.texto
        rojas = {n for n in range(1, 12)
                 if "error" in texto.tag_names(f"{n}.1")}
        assert 2 not in rojas              # MOV(N) es válida
        assert {3, 4, 7} <= rojas
        assert "avanza una casilla al norte" in texto.get("2.0", "2.end")
        assert v.validas >= 1 and v.con_error >= 5
        v.senalar(3, 0, 0)                 # el ratón sobre la línea 3
        assert v.globo.ventana is not None
        v.senalar(2, 0, 0)                 # sobre una línea válida
        assert v.globo.ventana is None
    finally:
        v.cerrar()


def test_explicar_dice_que_hace_cada_instruccion():
    from tanques.lenguaje import Interprete
    c = cfg.Configuracion()
    p, _ = Interprete().analizar("MISIL(N)\nIF V < 40 THEN REPARAR")
    assert grafica.explicar(p.instrucciones[0], c) == \
        "lanza un misil al norte (10 de daño)"
    assert grafica.explicar(p.instrucciones[1], c) == \
        "si su vida es menor que 40, se repara +20 (un solo uso)"


@requiere_pantalla
def test_el_formulario_muestra_el_dano_derivado(app):
    pantalla = grafica.PantallaConfiguracion(app, cfg.Configuracion())
    pantalla.amt.set("8")
    assert "misil 16 · mina 12" in pantalla.derivados["text"]


@requiere_pantalla
def test_valores_por_omision_y_los_campos_conservan_su_valor(app):
    base = replace(cfg.Configuracion(), escudo_puntos=35,
                   municion=cfg.Municion(minas=7, misiles=9))
    pantalla = grafica.PantallaConfiguracion(app, base)
    assert (pantalla.escudo.get(), pantalla.misiles.get()) == ("35", "9")
    pantalla._por_omision()
    assert (pantalla.escudo.get(), pantalla.misiles.get(),
            pantalla.minas.get()) == ("20", "3", "3")


@requiere_pantalla
def test_atajos_de_teclado(app):
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    app.partida(config)
    v = app._partida
    v._alternar()                      # espacio: iniciar
    assert v.modo == "auto"
    v._alternar()                      # espacio otra vez: pausar
    assert v.modo == "pausa"
    v.velocidad.set(5)
    v._acelerar(1)
    assert v.velocidad.get() == 6 and "6 ·" in v.vel_texto["text"]
    v._si_activo("configurar")         # Esc
    assert v.accion == "configurar"


@requiere_pantalla
def test_la_tarjeta_del_que_juega_se_resalta(app):
    from tanques.modelo import Evento, TipoEvento
    config, m = motor_de(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    app.partida(config)
    v = app._partida
    pulsar(app, "salir")
    ejecutar(m, v)                     # arma las tarjetas
    v._anotar([Evento(1, TipoEvento.INSTRUCCION, "", "b",
                      {"instruccion": "ESPERAR", "linea": 1})])
    t = v._tarjetas
    assert str(t["b"]["marco"]["highlightbackground"]).upper() == \
        t["b"]["color"].upper()
    assert t["a"]["marco"]["highlightbackground"] == grafica.BORDE_SUAVE


@requiere_pantalla
def test_la_casilla_bajo_el_raton_se_describe(app):
    config, m = motor_de(("a", "ESCUDO", (2, 2)), ("b", "ESPERAR", (5, 5)))
    app.partida(config)
    pulsar(app, "una", "salir")
    ejecutar(m, app._partida)
    v = app._partida
    v._raton = v._centro((2, 2))
    v._describir(v._estado)
    assert "tanque 1 a" in v.leyenda["text"]
    assert "escudo 20" in v.leyenda["text"]
    v._raton = v._centro((4, 4))
    v._describir(v._estado)
    assert v.leyenda["text"].endswith("vacía")


@requiere_pantalla
def test_el_cartel_final_trae_la_clasificacion(app):
    config, m = motor_de(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
                         vida_inicial=10)
    app.partida(config)
    pulsar(app, "iniciar")
    ejecutar(m, app._partida)
    c = app._partida.canvas
    textos = [c.itemcget(i, "text") for i in c.find_withtag("cartel")
              if c.type(i) == "text"]
    assert any(t.startswith("1.  Tanque 1 · a") for t in textos)
    assert any("destruido" in t for t in textos)


@requiere_pantalla
def test_el_tablero_minimo_crece_con_los_tanques(app):
    base = replace(cfg.Configuracion(), tablero=cfg.Tablero(4, 4),
                   tanques=())
    pantalla = grafica.PantallaConfiguracion(app, base)
    for i in range(4):
        pantalla.rutas[i].set("tanques/cazador.txt")
    assert (pantalla.ancho.get(), pantalla.alto.get()) == ("4", "4")
    assert "hasta 4 tanques" in pantalla.pista_tablero["text"]
    pantalla.rutas[4].set("tanques/cazador.txt")      # el quinto
    assert (pantalla.ancho.get(), pantalla.alto.get()) == ("5", "5")
    assert "5 × 5 con 5 tanques" in pantalla.pista_tablero["text"]
    pantalla.ancho.set("4")
    _, problemas = pantalla.leer()
    assert any("al menos 5 x 5" in p for p in problemas)


@requiere_pantalla
def test_el_ajuste_respeta_rango_y_paso(app):
    var = tk.StringVar(app.root, "5")
    marco = tk.Frame(app.root)
    ajuste = grafica.Ajuste(marco, app, var, 5, 20, etiqueta="Daño")
    ajuste.mover(-1)
    assert var.get() == "5"                     # no baja del mínimo
    ajuste.mover(3)
    assert var.get() == "8"
    ajuste.poner(99)
    assert var.get() == "20"
    var.set("abc")                               # escrito a mano, inválido
    assert ajuste.caja["highlightbackground"] == grafica.ROJO_UI
    rondas = tk.StringVar(app.root, "15")
    paso = grafica.Ajuste(marco, app, rondas, 10, 1000, paso=10, pista=False)
    paso.mover(1)
    assert rondas.get() == "20"                 # se alinea de 10 en 10
    paso.mover(-1)
    assert rondas.get() == "10"


@requiere_pantalla
def test_tablero_cuadrado_y_medidas_rapidas(app):
    base = replace(cfg.Configuracion(), tablero=cfg.Tablero(8, 8))
    pantalla = grafica.PantallaConfiguracion(app, base)
    assert pantalla.cuadrado.get()
    pantalla.ancho.set("10")
    assert pantalla.alto.get() == "10"          # el alto sigue al ancho
    pantalla._alternar_cuadrado()                # se suelta el eslabón
    pantalla.alto.set("6")
    assert pantalla.ancho.get() == "10"
    pantalla.medidas[12].invoke()
    assert (pantalla.ancho.get(), pantalla.alto.get()) == ("12", "12")
    for i in range(5):
        pantalla.rutas[i].set("tanques/cazador.txt")
    assert pantalla.medidas[4]["state"] == "disabled"   # no caben 5
    assert pantalla.medidas[6]["state"] == "normal"
