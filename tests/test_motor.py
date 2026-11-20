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
    m = motor(("a", "MISIL(S)", (1, 1)), ("b", "ESPERAR", (1, 2)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=10)
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
    assert (a.posicion, a.vida, a.dano_autoinfligido) == ((1, 1), 88, 12)


def test_mover_contra_un_tanque_es_un_choque_y_se_danan_los_dos():
    m = motor(("a", "MOV(E)", (1, 1)), ("b", "ESPERAR", (2, 1)))
    m.paso()
    a, b = tanque(m, "a"), tanque(m, "b")
    assert (a.posicion, a.vida, b.vida) == ((1, 1), 88, 88)
    assert (a.dano_infligido, b.dano_infligido) == (12, 0)


def test_muerte_contra_la_pared_deja_refaccion_sin_acreditar():
    m = motor(("a", "MOV(N)", (1, 1)), ("b", "ESPERAR", (8, 8)),
              ("c", "ESPERAR", (5, 5)), vida_inicial=12)
    m.paso()
    assert not tanque(m, "a").vivo
    assert m.estado().refacciones == ((1, 1),)
    assert all(t.dano_infligido == 0 for t in m.registro.tanques)


def test_el_embestidor_no_ocupa_la_casilla_del_destruido():
    m = motor(("a", "MOV(S)", (1, 1)), ("b", "ESPERAR", (1, 2)),
              ("c", "ESPERAR", (8, 8)), vida_inicial=12)
    m.paso()
    assert tanque(m, "a").posicion == (1, 1)


@pytest.mark.parametrize("modo, a, b", [
    (cfg.AcreditaChoque.EMBESTIDOR, 12, 0),
    (cfg.AcreditaChoque.AMBOS, 12, 12),
    (cfg.AcreditaChoque.NINGUNO, 0, 0),
])
def test_acreditacion_del_choque(modo, a, b):
    m = motor(("a", "MOV(E)", (1, 1)), ("b", "ESPERAR", (2, 1)),
              acredita_choque=modo)
    m.paso()
    assert (tanque(m, "a").dano_infligido,
            tanque(m, "b").dano_infligido) == (a, b)


# ---------------------------------------------------------------- armas
def test_ametralladora_al_primer_tanque_de_la_linea():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (4, 1)),
              ("c", "ESPERAR", (6, 1)))
    m.paso()
    assert (tanque(m, "b").vida, tanque(m, "c").vida) == (95, 100)
    assert tanque(m, "a").dano_infligido == 5


def test_el_dano_de_la_ametralladora_es_configurable():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (4, 1)),
              dano=cfg.Dano(ametralladora=20))
    m.paso()
    assert tanque(m, "b").vida == 80


def test_ametralladora_sin_objetivo():
    m = motor(("a", "AMT(N)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    assert TipoEvento.SIN_EFECTO in tipos(m.paso())


def test_los_eventos_dicen_hacia_donde_ocurren():
    # La interfaz los necesita para animar la ráfaga o el golpe en la pared.
    m = motor(("a", "AMT(N)\nMOV(N)\nAMT(E)", (1, 1)),
              ("b", "ESPERAR", (4, 1)), vida_inicial=1000)
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


def test_misil_en_linea_recta_al_primer_tanque():
    m = motor(("a", "MISIL(E)", (1, 1)), ("b", "ESPERAR", (4, 1)),
              ("c", "ESPERAR", (6, 1)))
    m.paso()
    assert (tanque(m, "b").vida, tanque(m, "c").vida) == (90, 100)
    assert tanque(m, "a").dano_infligido == 10


def test_misil_hace_el_doble_que_la_ametralladora():
    m = motor(("a", "MISIL(E)", (1, 1)), ("b", "ESPERAR", (4, 1)),
              dano=cfg.Dano(ametralladora=8))
    m.paso()
    assert tanque(m, "b").vida == 84


def test_misil_gasta_municion_aunque_falle():
    m = motor(("a", "MISIL(N)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    eventos = m.paso()
    assert tanque(m, "a").misiles == 2
    assert any(e.datos.get("arma") == "misil" for e in eventos)


def test_misil_se_agota():
    m = motor(("a", "MISIL(E)", (1, 1)), ("b", "ESPERAR", (8, 1)),
              vida_inicial=1000)
    for _ in range(5):
        m.ronda()
    assert tanque(m, "b").vida == 1000 - 3 * 10


def test_la_cantidad_de_misiles_es_configurable():
    m = motor(("a", "MISIL(E)", (1, 1)), ("b", "ESPERAR", (8, 1)),
              vida_inicial=1000, municion=cfg.Municion(minas=3, misiles=5))
    for _ in range(8):
        m.ronda()
    assert tanque(m, "b").vida == 1000 - 5 * 10


def test_misil_pasa_sobre_las_minas_sin_tocarlas():
    m = motor(("a", "MINA(S,E)\nESPERAR", (1, 1)),
              ("b", "ESPERAR\nMISIL(N)", (2, 5)))
    m.ronda()
    m.ronda()
    assert len(m.registro.minas) == 1
    assert tanque(m, "a").vida == 100


# ---------------------------------------------------------------- escudo
def test_el_escudo_es_vida_extra_que_dura_hasta_agotarse():
    m = motor(("a", "ESCUDO" + "\nESPERAR" * 5, (1, 1)),
              ("b", "AMT(N)", (1, 5)))
    for _ in range(4):                  # cuatro disparos de 5: 20 absorbidos
        m.ronda()
    a = tanque(m, "a")
    assert (a.vida, a.escudo) == (100, 0)
    m.ronda()
    assert tanque(m, "a").vida == 95


def test_el_escudo_absorbe_parte_y_el_resto_llega_a_la_vida():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    a, b = tanque(m, "a"), tanque(m, "b")
    a.escudo = 3
    assert m.aplicar_dano(a, 10, autor=b, origen="prueba") == 7
    assert (a.vida, a.escudo, b.dano_infligido) == (93, 0, 7)


def test_el_escudo_no_se_acumula():
    m = motor(("a", "ESCUDO", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    assert tanque(m, "a").escudo == 20


def test_el_escudo_se_recarga():
    m = motor(("a", "ESCUDO\nESPERAR\nESCUDO", (1, 1)),
              ("b", "AMT(N)", (1, 5)))
    m.ronda()                           # 20, b deja 15
    m.ronda()                           # b deja 10
    m.ronda()                           # a recarga a 20, b deja 15
    assert tanque(m, "a").escudo == 15


def test_el_valor_del_escudo_es_configurable():
    m = motor(("a", "ESCUDO", (1, 1)), ("b", "ESPERAR", (8, 8)),
              escudo_puntos=35)
    m.paso()
    assert tanque(m, "a").escudo == 35


def test_el_escudo_absorbe_la_pared_y_el_choque():
    m = motor(("a", "ESCUDO\nMOV(N)\nMOV(E)", (1, 1)),
              ("b", "ESPERAR", (2, 1)))
    for _ in range(3):
        m.ronda()
    a, b = tanque(m, "a"), tanque(m, "b")
    assert (a.vida, a.escudo) == (96, 0)        # 12 + 8 absorbidos, 4 a vida
    assert b.vida == 88


def test_embestir_a_un_tanque_con_escudo():
    m = motor(("a", "ESPERAR\nMOV(S)", (1, 1)), ("b", "ESCUDO", (1, 2)))
    m.ronda()                           # b activa el escudo
    m.ronda()                           # b ya lo tiene completo; a embiste
    a, b = tanque(m, "a"), tanque(m, "b")
    assert (a.vida, b.vida, b.escudo) == (88, 100, 8)
    assert a.dano_infligido == 0


# ---------------------------------------------------------------- minas
@pytest.mark.parametrize("texto, destino", [
    ("MINA(N,E)", (4, 2)), ("MINA(N,O)", (2, 2)),
    ("MINA(S,E)", (4, 4)), ("MINA(S,O)", (2, 4)),
])
def test_la_mina_se_lanza_a_la_esquina(texto, destino):
    m = motor(("a", texto, (3, 3)), ("b", "ESPERAR", (8, 8)))
    m.paso()
    assert [mi.posicion for mi in m.registro.minas] == [destino]
    assert tanque(m, "a").minas == 2


def test_la_mina_se_activa_de_inmediato():
    m = motor(("a", "MINA(S,E)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    eventos = m.paso()
    assert m.registro.minas[0].armada
    assert TipoEvento.MINA_ARMADA in tipos(eventos)


def test_la_mina_puede_armarse_en_n_rondas():
    m = motor(("a", "MINA(S,E)\nESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)),
              mina_rondas_armado=2)
    m.ronda()
    m.ronda()
    assert not m.registro.minas[0].armada
    eventos = m.ronda()
    assert m.registro.minas[0].armada
    assert TipoEvento.MINA_ARMADA in tipos(eventos)


def test_mina_fuera_del_tablero_no_gasta_municion():
    m = motor(("a", "MINA(N,O)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    assert TipoEvento.SIN_EFECTO in tipos(m.paso())
    assert (m.registro.minas, tanque(m, "a").minas) == ([], 3)


def test_no_se_lanza_una_mina_sobre_otra():
    m = motor(("a", "MINA(S,E)", (1, 1)), ("b", "ESPERAR", (8, 8)))
    m.ronda()
    m.ronda()
    assert (len(m.registro.minas), tanque(m, "a").minas) == (1, 2)


def test_la_mina_estalla_si_cae_sobre_un_tanque():
    m = motor(("a", "MINA(S,E)", (1, 1)), ("b", "ESPERAR", (2, 2)))
    eventos = m.paso()
    assert TipoEvento.MINA_EXPLOTA in tipos(eventos)
    assert tanque(m, "b").vida == 92.5          # 1.5 x 5, sin redondear
    assert tanque(m, "a").dano_infligido == 7.5
    assert m.registro.minas == []


def test_la_mina_sin_armar_no_estalla_bajo_un_tanque_quieto():
    m = motor(("a", "MINA(S,E)\nESPERAR", (1, 1)),
              ("b", "ESPERAR", (2, 2)), mina_rondas_armado=1)
    for _ in range(3):
        m.ronda()
    assert tanque(m, "b").vida == 100
    assert m.registro.minas[0].armada


def test_pisar_una_mina_armada():
    m = motor(("a", "MINA(S,E)", (1, 1)), ("b", "MOV(O)", (3, 2)))
    m.ronda()
    b = tanque(m, "b")
    assert (b.posicion, b.vida) == ((2, 2), 92.5)
    assert m.registro.minas == []


def test_volver_a_la_propia_mina():
    m = motor(("a", "MINA(S,E)\nMOV(E)\nMOV(S)", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    for _ in range(3):
        m.ronda()
    a = tanque(m, "a")
    assert (a.vida, a.dano_infligido, a.dano_autoinfligido) == (92.5, 0, 7.5)


def test_el_escudo_absorbe_la_mina():
    m = motor(("a", "ESPERAR\nMINA(S,E)", (1, 1)),
              ("b", "ESCUDO\nMOV(O)", (3, 2)))
    m.ronda()                           # a espera; b activa el escudo
    m.ronda()                           # b entra a (2, 2); a le lanza la mina
    b = tanque(m, "b")
    assert (b.vida, b.escudo) == (100, 12.5)


# ---------------------------------------------------------------- radar e IF
def test_radar_distancia_positiva_a_un_enemigo():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (4, 1)))
    assert m.explorar(tanque(m, "a"), Direccion.E) == 3


def test_radar_distancia_negativa_a_la_pared():
    m = motor(("a", "ESPERAR", (1, 3)), ("b", "ESPERAR", (8, 8)))
    assert m.explorar(tanque(m, "a"), Direccion.N) == -3


def test_radar_no_ve_las_minas():
    m = motor(("a", "ESPERAR", (2, 3)), ("b", "MINA(N,O)", (3, 3)))
    m.ronda()                           # b lanza la mina a (2, 2)
    assert m.explorar(tanque(m, "a"), Direccion.N) == -3


def test_if_falso_pierde_el_turno():
    m = motor(("a", "IF VIDA < 50 THEN ESCUDO", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    assert TipoEvento.CONDICION_FALSA in tipos(m.paso())
    assert not tanque(m, "a").escudo


def test_if_verdadero_ejecuta_la_accion():
    m = motor(("a", "IF RADAR(E) > 0 THEN AMT(E)", (1, 1)),
              ("b", "ESPERAR", (5, 1)))
    eventos = m.paso()
    assert tanque(m, "b").vida == 95
    radar = next(e for e in eventos if e.tipo is TipoEvento.RADAR)
    assert radar.datos["lectura"] == 4


def test_if_radar_explora_en_el_momento():
    # No hay lecturas guardadas: si b se aparta, el IF ya no lo ve.
    m = motor(("a", "IF RADAR(E) > 0 THEN AMT(E)", (1, 1)),
              ("b", "MOV(S)", (5, 1)))
    m.ronda()                           # a dispara; b se aparta
    eventos = m.ronda()                 # b se mueve otra vez; a no ve nada
    assert TipoEvento.CONDICION_FALSA in tipos(eventos)
    assert tanque(m, "b").vida == 95


def test_if_con_misil():
    m = motor(("a", "IF RADAR(S) > 0 THEN MISIL(S)", (1, 1)),
              ("b", "ESPERAR", (1, 6)))
    m.paso()
    assert (tanque(m, "b").vida, tanque(m, "a").misiles) == (90, 2)


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
    m = motor(("a", "MOV(N)\nMOV(N)\nREPARAR\nREPARAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)))
    for _ in range(4):
        m.ronda()
    assert tanque(m, "a").vida == 76 + 20


def test_lo_que_cura_reparar_es_configurable():
    m = motor(("a", "MOV(N)\nMOV(N)\nMOV(N)\nREPARAR", (1, 1)),
              ("b", "ESPERAR", (8, 8)), reparar_puntos=30)
    for _ in range(4):
        m.ronda()
    assert tanque(m, "a").vida == 64 + 30


# ---------------------------------------------------------------- refacciones
def refaccion_en_2_1(programa_a, vida_inicial):
    """c cae en (2, 1) en la primera ronda; a juega `programa_a`."""
    m = motor(("a", programa_a, (1, 1)),
              ("b", "MISIL(O)\nESPERAR", (8, 1)), ("c", "ESPERAR", (2, 1)),
              vida_inicial=vida_inicial)
    m.ronda()
    assert m.estado().refacciones == ((2, 1),)
    return m


def test_pasar_sobre_un_tanque_destruido_repara():
    m = refaccion_en_2_1("ESPERAR\nMOV(E)", 10)
    a = tanque(m, "a")
    a.vida_maxima, a.vida = 100, 40
    m.ronda()                          # a entra a (2, 1)
    assert 40 + 15 <= a.vida <= 40 + 35
    assert m.estado().refacciones == ()


def test_refaccion_con_la_vida_al_maximo_se_consume():
    m = refaccion_en_2_1("ESPERAR\nMOV(E)", 10)
    m.ronda()
    assert tanque(m, "a").vida == 10
    assert m.estado().refacciones == ()


# ---------------------------------------------------------------- término
def test_gana_el_ultimo_en_pie():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              vida_inicial=10)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo, r.rondas) == ("a", Motivo.DESTRUCCION, 2)


def test_desempate_por_dano_infligido():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              rondas_maximas=3)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo) == ("a", Motivo.DESEMPATE)
    assert r.dano_infligido == {"a": 15, "b": 0}


def test_empate_si_el_dano_coincide():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (3, 1)),
              rondas_maximas=3)
    m.jugar()
    assert (m.resultado().ganador, m.resultado().motivo) \
        == (None, Motivo.EMPATE)


def test_todos_destruidos_en_el_mismo_turno():
    # El choque mata a los dos; desempatan ellos dos por daño infligido.
    m = motor(("a", "MOV(E)", (1, 1)), ("b", "ESPERAR", (2, 1)),
              vida_inicial=12)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo) == ("a", Motivo.DESEMPATE)


def test_dos_destruidos_en_la_misma_ronda():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "MISIL(N)", (1, 5)),
              ("c", "MISIL(O)", (8, 5)), vida_inicial=10)
    m.jugar()
    r = m.resultado()
    assert (r.ganador, r.motivo, r.rondas) == ("c", Motivo.DESTRUCCION, 1)


def test_nada_ocurre_tras_el_final():
    m = motor(("a", "AMT(E)", (1, 1)), ("b", "ESPERAR", (3, 1)),
              vida_inicial=5)
    m.jugar()
    assert m.paso() == [] and m.terminada()


# ---------------------------------------------------------------- estado
def test_el_estado_es_de_solo_lectura():
    m = motor(("a", "ESPERAR", (1, 1)), ("b", "ESPERAR", (8, 8)))
    e = m.estado()
    with pytest.raises(AttributeError):
        e.tanques[0].vida = 0
    assert e.tanques[0].numero == 1
