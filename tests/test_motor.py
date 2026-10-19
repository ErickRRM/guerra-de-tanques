"""Pruebas del motor de simulación.

Buena parte de estas pruebas corresponde a la tabla de casos borde de la
sección 7.3 del documento de arquitectura: son las situaciones que el
reglamento no resuelve de forma evidente y que hubo que decidir.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from tanques import config as cfg
from tanques.controlador import preparar
from tanques.lenguaje import Interprete, formato_errores
from tanques.modelo import Direccion, Motivo, Motor, TipoEvento

RAIZ = Path(__file__).resolve().parents[1]
BASE = cfg.Configuracion()


def programa(nombre, texto):
    p, errores = Interprete().analizar(texto, nombre=nombre)
    assert errores == [], formato_errores(errores)
    return p


def motor(*tanques, config=BASE, **cambios):
    """Crea un motor con tanques dados como (nombre, texto, (x, y))."""
    if cambios:
        config = replace(config, **cambios)
    programas = [programa(n, t) for n, t, _ in tanques]
    return Motor(config, programas, posiciones=[p for _, _, p in tanques])


def tanque(m, nombre):
    return next(t for t in m.registro.tanques if t.nombre == nombre)


def tipos(eventos):
    return [e.tipo for e in eventos]


# ---------------------------------------------------------------- arranque
def test_las_posiciones_iniciales_son_distintas_y_dentro():
    m = Motor(BASE, [programa(f"t{i}", "ESPERAR") for i in range(4)])
    posiciones = [t.posicion for t in m.estado().tanques]
    assert len(set(posiciones)) == 4
    assert all(1 <= x <= 8 and 1 <= y <= 8 for x, y in posiciones)


def test_misma_semilla_misma_partida():
    def partida(semilla):
        m, errores = preparar(cfg.cargar(RAIZ / "config.json"), RAIZ,
                              semilla)
        assert errores == []
        return [str(e) for e in m.jugar()], m.resultado()

    assert partida(7) == partida(7)
    assert partida(7)[0] != partida(8)[0]


def test_mas_tanques_que_casillas():
    c = replace(BASE, tablero=cfg.Tablero(2, 2))
    with pytest.raises(ValueError):
        Motor(c, [programa(f"t{i}", "ESPERAR") for i in range(5)])


def test_un_solo_tanque_juega_hasta_el_limite():
    m = motor(("solo", "ESPERAR", (1, 1)), rondas_maximas=5)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.rondas) == ("solo", 5)


def test_el_programa_se_reinicia_al_agotarse():
    m = motor(("a", "MOV(E)\nMOV(O)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    for _ in range(3):
        m.ronda()
    assert tanque(m, "a").posicion == (2, 1)


def test_la_configuracion_del_repositorio_arranca():
    m, errores = preparar(cfg.cargar(RAIZ / "config.json"), RAIZ)
    assert errores == []
    m.jugar()
    assert m.terminada()


def test_un_programa_con_errores_no_arranca(tmp_path):
    (tmp_path / "malo.txt").write_text("DISPARAR\n", encoding="utf-8")
    c = replace(BASE, tanques=(cfg.TanqueConfig("malo", "malo.txt"),))
    m, errores = preparar(c, tmp_path)
    assert m is None and len(errores) == 1


# ---------------------------------------------------------------- turnos
def test_orden_rotativo():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)),
              ("c", "ESPERAR", (5, 5)))
    ordenes = [next(e for e in m.ronda() if e.tipo is TipoEvento.RONDA)
               .datos["orden"] for _ in range(4)]
    assert ordenes == [["a", "b", "c"], ["b", "c", "a"],
                       ["c", "a", "b"], ["a", "b", "c"]]


def test_paso_ejecuta_un_solo_turno():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 3)))
    m.paso()
    assert (tanque(m, "a").turnos, tanque(m, "b").turnos) == (1, 0)


def test_un_tanque_destruido_pierde_sus_turnos():
    m = motor(("a", "MISIL(1,2)", (1, 1)), ("b", "ESPERAR", (1, 2)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=30)
    m.ronda()
    assert not tanque(m, "b").vivo
    assert tanque(m, "b").turnos == 0


# ---------------------------------------------------------------- movimiento
def test_mover_avanza_una_casilla():
    m = motor(("a", "MOV(S)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert tanque(m, "a").posicion == (1, 2)


def test_mover_contra_la_pared():
    m = motor(("a", "MOV(N)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    a = tanque(m, "a")
    assert (a.posicion, a.vida, a.dano_autoinfligido) == ((1, 1), 95, 5)


def test_mover_contra_un_tanque_es_un_choque():
    m = motor(("a", "MOV(E)", (1, 1)), ("b", "ESPERAR", (2, 1)))
    m.paso()
    a, b = tanque(m, "a"), tanque(m, "b")
    assert (a.posicion, a.vida, b.vida) == ((1, 1), 85, 85)
    assert (a.dano_infligido, b.dano_infligido) == (15, 0)


def test_la_pared_atraviesa_el_escudo():
    m = motor(("a", "ESCUDO\nMOV(N)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    tanque(m, "a").escudo = True
    m.ronda()
    assert tanque(m, "a").vida == 95


def test_muerte_contra_la_pared_deja_refaccion_sin_acreditar():
    m = motor(("a", "MOV(N)", (1, 1)), ("b", "ESPERAR", (8, 8)),
              ("c", "ESPERAR", (5, 5)), vida_inicial=5)
    m.paso()
    assert not tanque(m, "a").vivo
    assert m.estado().refacciones == ((1, 1),)
    assert all(t.dano_infligido == 0 for t in m.registro.tanques)


# ---------------------------------------------------------------- armas
def test_ametralladora_al_primer_tanque_de_la_linea():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (4, 1)),
              ("c", "ESPERAR", (6, 1)))
    m.paso()
    assert (tanque(m, "b").vida, tanque(m, "c").vida) == (90, 100)
    assert tanque(m, "a").dano_infligido == 10


def test_ametralladora_sin_objetivo():
    m = motor(("a", "AMT(N)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    assert TipoEvento.SIN_EFECTO in tipos(m.paso())


def test_los_eventos_dicen_hacia_donde_ocurren():
    # La interfaz los necesita para animar la ráfaga o el golpe en la pared.
    m = motor(("a", "AMT(N)\nMOV(N)\nAMT(E)", (1, 1)),
              ("b", "ESPERAR", (4, 1)))
    datos = []
    for _ in range(3):
        datos += [e.datos for e in m.ronda()
                  if e.tanque == "a" and e.tipo in (TipoEvento.SIN_EFECTO,
                                                    TipoEvento.MOVIMIENTO,
                                                    TipoEvento.DISPARO)]
    assert [d["direccion"] for d in datos] == ["N", "N", "E"]
    assert datos[0]["arma"] == "ametralladora"
    assert datos[2]["objetivo"] == "b"


def test_ronda_completa():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    assert m.ronda_completa
    m.paso()
    assert not m.ronda_completa
    m.paso()
    assert m.ronda_completa


def test_misil_gasta_municion_aunque_falle():
    m = motor(("a", "MISIL(5,5)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert tanque(m, "a").misiles == 2


def test_misil_se_agota():
    m = motor(("a", "MISIL(8,8)", (1, 1)), ("b", "ESPERAR", (8, 8)),
              vida_inicial=1000)
    for _ in range(5):
        m.ronda()
    assert tanque(m, "b").vida == 1000 - 3 * 30


def test_misil_a_la_propia_casilla_no_se_acredita():
    m = motor(("a", "MISIL(1,1)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    a = tanque(m, "a")
    assert (a.vida, a.dano_infligido, a.dano_autoinfligido) == (70, 0, 30)


def test_misil_no_destruye_la_mina_de_la_casilla():
    m = motor(("a", "MINA\nMOV(E)\nESPERAR", (1, 1)),
              ("b", "ESPERAR\nESPERAR\nMISIL(1,1)", (8, 8)))
    for _ in range(3):
        m.ronda()
    assert len(m.registro.minas) == 1


def test_danar_al_contiguo():
    m = motor(("a", "DAÑAR(S)", (1, 1)), ("b", "ESPERAR", (1, 2)))
    m.paso()
    assert (tanque(m, "a").vida, tanque(m, "b").vida) == (85, 85)


def test_danar_sin_nadie_al_lado():
    m = motor(("a", "DAÑAR(S)", (1, 1)), ("b", "ESPERAR", (1, 3)))
    m.paso()
    assert tanque(m, "a").vida == 100


def test_embestir_a_un_tanque_con_escudo():
    m = motor(("a", "ESPERAR\nDAÑAR(S)", (1, 1)),
              ("b", "ESCUDO", (1, 2)))
    m.ronda()                          # b activa el escudo
    m.ronda()                          # b lo renueva; después a embiste
    assert (tanque(m, "a").vida, tanque(m, "b").vida) == (85, 100)
    assert tanque(m, "a").dano_infligido == 0


def test_el_embestidor_no_ocupa_la_casilla_del_destruido():
    m = motor(("a", "MOV(S)", (1, 1)), ("b", "ESPERAR", (1, 2)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=15)
    m.paso()
    assert tanque(m, "a").posicion == (1, 1)


@pytest.mark.parametrize("modo, a, b", [
    (cfg.AcreditaChoque.EMBESTIDOR, 15, 0),
    (cfg.AcreditaChoque.AMBOS, 15, 15),
    (cfg.AcreditaChoque.NINGUNO, 0, 0),
])
def test_acreditacion_del_choque(modo, a, b):
    m = motor(("a", "DAÑAR(E)", (1, 1)), ("b", "ESPERAR", (2, 1)),
              acredita_choque=modo)
    m.paso()
    assert (tanque(m, "a").dano_infligido,
            tanque(m, "b").dano_infligido) == (a, b)


# ---------------------------------------------------------------- escudo
def test_el_escudo_bloquea_hasta_el_siguiente_turno():
    m = motor(("a", "ESCUDO\nESPERAR\nESPERAR", (1, 1)),
              ("b", "AMT(N)", (1, 5)))
    m.ronda()                           # a, b: bloqueado
    m.ronda()                           # b, a: a aún no juega, bloqueado
    assert tanque(m, "a").vida == 100
    m.ronda()                           # a, b: el escudo ya caducó
    assert tanque(m, "a").vida == 90


# ---------------------------------------------------------------- minas
def test_la_mina_se_arma_tras_dos_turnos_del_propietario():
    m = motor(("a", "MINA\nESPERAR\nESPERAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    assert not m.registro.minas[0].armada
    m.ronda()
    assert m.registro.minas[0].armada


def test_la_mina_se_puede_armar_por_rondas():
    m = motor(("a", "MINA\nESPERAR\nESPERAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)),
              mina_medida_armado=cfg.MedidaArmado.RONDAS)
    m.ronda()
    m.ronda()
    assert not m.registro.minas[0].armada
    m.ronda()
    assert m.registro.minas[0].armada


def test_pisar_una_mina_armada():
    m = motor(("a", "MINA\nMOV(E)\nESPERAR\nESPERAR", (2, 1)),
              ("b", "ESPERAR\nESPERAR\nESPERAR\nMOV(E)", (1, 1)))
    for _ in range(4):
        m.ronda()
    assert tanque(m, "b").vida == 75
    assert tanque(m, "a").dano_infligido == 25
    assert m.registro.minas == []


def test_pisar_una_mina_sin_armar_no_hace_nada():
    m = motor(("a", "MINA\nMOV(S)\nESPERAR", (2, 1)),
              ("b", "ESPERAR\nESPERAR\nMOV(E)", (1, 1)),
              mina_turnos_armado=3)
    for _ in range(3):
        m.ronda()
    assert tanque(m, "b").vida == 100
    assert len(m.registro.minas) == 1


def test_volver_a_la_propia_mina_armada():
    m = motor(("a", "MINA\nMOV(E)\nESPERAR\nMOV(O)", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    for _ in range(4):
        m.ronda()
    a = tanque(m, "a")
    assert (a.vida, a.dano_infligido, a.dano_autoinfligido) == (75, 0, 25)


def test_quedarse_sobre_la_propia_mina_no_la_detona():
    m = motor(("a", "MINA\nESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    for _ in range(5):
        m.ronda()
    assert tanque(m, "a").vida == 100
    assert m.registro.minas[0].armada


def test_el_escudo_nunca_cubre_al_pisar_una_mina():
    # Las minas se pisan en el turno propio, y el escudo caduca justo al
    # empezar ese turno: el caso «escudo activo al pisar» no puede darse.
    m = motor(("a", "MINA\nMOV(E)\nESPERAR\nESPERAR", (2, 1)),
              ("b", "ESPERAR\nESPERAR\nESCUDO\nMOV(E)", (1, 1)))
    for _ in range(4):
        m.ronda()
    assert tanque(m, "b").vida == 75
    assert m.registro.minas == []


def test_no_se_coloca_una_mina_sobre_otra():
    m = motor(("a", "MINA", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    assert (len(m.registro.minas), tanque(m, "a").minas) == (1, 2)


# ---------------------------------------------------------------- radar e IF
def test_radar_distancia_positiva_a_un_enemigo():
    m = motor(("a", "RADAR(E)", (1, 1)), ("b", "ESPERAR", (4, 1)))
    m.paso()
    assert tanque(m, "a").ultimo_radar == (Direccion.E, 3)


def test_radar_distancia_negativa_a_la_pared():
    m = motor(("a", "RADAR(N)", (1, 3)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert tanque(m, "a").ultimo_radar == (Direccion.N, -3)


def test_radar_no_ve_las_minas():
    m = motor(("a", "MINA\nMOV(S)\nRADAR(N)", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    for _ in range(3):
        m.ronda()
    assert tanque(m, "a").ultimo_radar == (Direccion.N, -2)


def test_if_falso_pierde_el_turno():
    m = motor(("a", "IF VIDA < 50 THEN ESCUDO", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    assert TipoEvento.CONDICION_FALSA in tipos(m.paso())
    assert not tanque(m, "a").escudo


def test_if_verdadero_ejecuta_la_accion():
    m = motor(("a", "IF RADAR(E) > 0 THEN AMT(E)", (1, 1)),
              ("b", "ESPERAR", (5, 1)))
    m.paso()
    assert tanque(m, "b").vida == 90


def test_if_hibrido_usa_la_lectura_previa():
    # La lectura previa dice que b está al este; b se aparta y el IF
    # sigue disparando con el dato viejo, al vacío.
    m = motor(("a", "RADAR(E)\nIF RADAR(E) > 0 THEN AMT(E)", (1, 1)),
              ("b", "MOV(S)", (5, 1)))
    m.ronda()
    eventos = m.ronda()
    assert TipoEvento.SIN_EFECTO in tipos(eventos)


@pytest.mark.parametrize("modo, dispara", [
    (cfg.ModoRadar.HIBRIDO, True),
    (cfg.ModoRadar.DIRECTO, True),
    (cfg.ModoRadar.REGISTRO, False),
])
def test_if_sin_lectura_previa_segun_el_modo(modo, dispara):
    m = motor(("a", "IF RADAR(E) > 0 THEN AMT(E)", (1, 1)),
              ("b", "ESPERAR", (5, 1)), modo_radar=modo)
    m.paso()
    assert (tanque(m, "b").vida == 90) is dispara


# ---------------------------------------------------------------- reparar
def test_reparar_no_pasa_del_maximo():
    m = motor(("a", "MOV(N)\nREPARAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    a = tanque(m, "a")
    assert (a.vida, a.reparaciones) == (100, 0)


def test_reparar_con_la_vida_completa_no_gasta_el_uso():
    m = motor(("a", "REPARAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert tanque(m, "a").reparaciones == 1


def test_reparar_una_sola_vez():
    m = motor(("a", "MISIL(1,1)\nREPARAR\nREPARAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    for _ in range(3):
        m.ronda()
    assert tanque(m, "a").vida == 90


# ---------------------------------------------------------------- refacciones
def test_recoger_una_refaccion():
    m = motor(("a", "MOV(N)\nMOV(E)\nESPERAR", (1, 1)),
              ("b", "MISIL(2,1)", (8, 8)), ("c", "ESPERAR", (2, 1)),
              vida_inicial=30)
    m.ronda()                          # c destruido en (2, 1)
    assert m.estado().refacciones == ((2, 1),)
    m.ronda()                          # a entra a (2, 1)
    a = tanque(m, "a")
    assert 25 + 15 >= a.vida >= 25     # 30 - 5 de la pared, hasta el tope
    assert m.estado().refacciones == ()


def test_refaccion_con_la_vida_al_maximo_se_consume():
    m = motor(("a", "ESPERAR\nMOV(E)", (1, 1)),
              ("b", "MISIL(2,1)\nESPERAR", (8, 8)), ("c", "ESPERAR", (2, 1)),
              vida_inicial=30)
    m.ronda()
    m.ronda()
    assert tanque(m, "a").vida == 30
    assert m.estado().refacciones == ()


# ---------------------------------------------------------------- término
def test_gana_el_ultimo_en_pie():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              vida_inicial=20)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo, r.rondas) == ("a", Motivo.DESTRUCCION, 2)


def test_desempate_por_dano_infligido():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              rondas_maximas=3)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo) == ("a", Motivo.DESEMPATE)
    assert r.dano_infligido == {"a": 30, "b": 0}


def test_empate_si_el_dano_coincide():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)),
              rondas_maximas=3)
    m.jugar()
    assert (m.resultado().ganador, m.resultado().motivo) \
        == (None, Motivo.EMPATE)


def test_todos_destruidos_en_el_mismo_turno():
    # El choque mata a los dos; desempatan ellos dos por daño infligido.
    m = motor(("a", "DAÑAR(E)", (1, 1)), ("b", "ESPERAR", (2, 1)),
              vida_inicial=15)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo) == ("a", Motivo.DESEMPATE)


def test_dos_destruidos_en_la_misma_ronda():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "MISIL(1,1)", (5, 5)),
              ("c", "MISIL(5,5)", (8, 8)), vida_inicial=30)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo, r.rondas) == ("c", Motivo.DESTRUCCION, 1)


def test_nada_ocurre_tras_el_final():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              vida_inicial=10)
    m.jugar()
    assert m.paso() == [] and m.terminada()


# ---------------------------------------------------------------- estado
def test_el_estado_es_de_solo_lectura():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    e = m.estado()
    with pytest.raises(AttributeError):
        e.tanques[0].vida = 0
    assert e.tanques[0].numero == 1
