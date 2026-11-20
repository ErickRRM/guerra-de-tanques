"""Pruebas de la partida de exhibición (config_dinamico.json).

Sus tanques están escritos para que la partida se vea: disparan siempre,
barren con el radar, siembran minas y lanzan misiles. Lo que se comprueba
es que la configuración sea válida y que cumplan lo que prometen sus
comentarios.
"""
from dataclasses import replace
from pathlib import Path

from tanques import config as cfg
from tanques.controlador import preparar
from tanques.lenguaje import Interprete
from tanques.modelo import Motor, TipoEvento

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = cfg.cargar(RAIZ / "config_dinamico.json")


def test_la_configuracion_de_exhibicion_es_valida():
    assert CONFIG.validar() == []
    assert len(CONFIG.tanques) == 4
    i = Interprete(CONFIG.tablero.ancho, CONFIG.tablero.alto)
    for t in CONFIG.tanques:
        _, errores = i.cargar(RAIZ / t.programa)
        assert errores == [], t.programa


def test_solo_cambia_el_tablero_y_las_rondas():
    """Las reglas son las mismas de config.json: la exhibición no es otro juego."""
    normal = cfg.cargar(RAIZ / "config.json")
    assert replace(CONFIG, tablero=normal.tablero,
                   rondas_maximas=normal.rondas_maximas,
                   tanques=normal.tanques) == normal


def test_hay_de_todo_en_una_partida():
    motor, _ = preparar(CONFIG, RAIZ, 42)
    tipos = {e.tipo for e in motor.jugar()}
    assert {TipoEvento.DISPARO, TipoEvento.RADAR, TipoEvento.MINA_COLOCADA,
            TipoEvento.ESCUDO, TipoEvento.DANO} <= tipos


def test_el_minador_no_pisa_sus_minas_si_empieza_lejos_de_la_pared():
    p, _ = Interprete(6, 6).cargar(RAIZ / "tanques/minador.txt")
    solo = replace(CONFIG, tanques=(), rondas_maximas=60)
    for inicio in [(1, 1), (2, 3), (3, 5), (4, 2)]:
        m = Motor(solo, [p], posiciones=[inicio])
        eventos = m.jugar()
        assert sum(e.tipo is TipoEvento.MINA_COLOCADA for e in eventos) == 3
        assert not any(e.tipo is TipoEvento.MINA_EXPLOTA for e in eventos), \
            inicio


def test_el_embestidor_y_la_patrulla_no_viven_en_la_pared():
    for archivo in ("embestidor.txt", "patrulla.txt"):
        p, _ = Interprete(6, 6).cargar(RAIZ / "tanques" / archivo)
        solo = replace(CONFIG, tanques=(), rondas_maximas=100)
        for inicio in [(1, 1), (6, 6), (3, 3), (6, 1)]:
            m = Motor(solo, [p], posiciones=[inicio])
            m.jugar()
            # Algún choque al arrancar junto a la pared, y ya no más.
            assert m.registro.tanques[0].dano_autoinfligido <= 15, \
                (archivo, inicio)
