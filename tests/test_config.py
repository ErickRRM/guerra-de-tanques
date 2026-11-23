"""Pruebas de la configuración.

Importan sobre todo dos cosas: que `config.json` del repositorio sea válido
y que las cuatro decisiones de reglas lleguen al programa con el valor
acordado, porque de ellas depende el comportamiento del motor.
"""
import json
from pathlib import Path

import pytest

from tanques import config as cfg

RAIZ = Path(__file__).resolve().parents[1]


# -------------------------------------------------------- archivo del repo
def test_el_config_del_repositorio_es_valido():
    c = cfg.cargar(RAIZ / "config.json")
    assert c.validar() == []
    assert (c.tablero.ancho, c.tablero.alto) == (8, 8)
    assert len(c.tanques) == 3


def test_los_programas_declarados_existen():
    for t in cfg.cargar(RAIZ / "config.json").tanques:
        assert (RAIZ / t.programa).is_file(), t.programa


# ------------------------------------------------------- las decisiones
def test_las_decisiones_tienen_el_valor_acordado():
    c = cfg.cargar(RAIZ / "config.json")
    assert c.orden_turnos is cfg.OrdenTurnos.ROTATIVO
    assert c.mina_rondas_armado == 0          # la mina se activa de inmediato
    assert c.acredita_choque is cfg.AcreditaChoque.EMBESTIDOR


def test_las_decisiones_se_pueden_cambiar_desde_el_json():
    c = cfg.desde_diccionario({
        "tanques": [{"nombre": "a", "programa": "a.txt"}],
        "reglas": {
            "orden_turnos": "aleatorio",
            "acredita_choque": "ambos",
            "mina": {"rondas_armado": 1},
        },
    })
    assert c.orden_turnos is cfg.OrdenTurnos.ALEATORIO
    assert c.acredita_choque is cfg.AcreditaChoque.AMBOS
    assert c.mina_rondas_armado == 1


# ------------------------------------------------- valores del reglamento
def test_los_valores_por_omision_son_los_del_reglamento():
    c = cfg.Configuracion()
    assert c.vida_inicial == 100
    assert (c.municion.misiles, c.municion.minas) == (3, 3)
    assert c.dano.ametralladora == 5
    assert (c.dano.choque_pared, c.dano.choque_tanque) == (12, 12)
    assert c.reparar_puntos == 20
    assert (c.refaccion.minimo, c.refaccion.maximo) == (15, 35)
    assert cfg.REPARACIONES_POR_PARTIDA == 1
    assert cfg.MAX_TANQUES == 6


@pytest.mark.parametrize("amt, misil, mina", [(5, 10, 7.5), (8, 16, 12),
                                              (20, 40, 30)])
def test_misil_y_mina_se_derivan_de_la_ametralladora_sin_redondear(
        amt, misil, mina):
    d = cfg.Dano(ametralladora=amt)
    assert (d.misil, d.mina) == (misil, mina)


@pytest.mark.parametrize("datos, aviso", [
    ({"dano": {"ametralladora": 4}}, "ametralladora"),
    ({"dano": {"ametralladora": 21}}, "ametralladora"),
    ({"municion": {"misiles": 11}}, "misiles"),
    ({"municion": {"minas": 11}}, "minas"),
    ({"reparar_puntos": 14}, "REPARAR"),
    ({"reparar_puntos": 31}, "REPARAR"),
    ({"escudo_puntos": 0}, "escudo"),
    ({"reglas": {"mina": {"rondas_armado": -1}}}, "armado"),
])
def test_los_configurables_respetan_su_rango(datos, aviso):
    datos = {"tanques": [{"nombre": "a", "programa": "a.txt"}], **datos}
    problemas = cfg.desde_diccionario(datos).validar()
    assert any(aviso in p for p in problemas), problemas


@pytest.mark.parametrize("datos", [
    {"dano": {"ametralladora": 5}}, {"dano": {"ametralladora": 20}},
    {"municion": {"misiles": 10, "minas": 10}},
    {"reparar_puntos": 15}, {"reparar_puntos": 30},
])
def test_los_extremos_del_rango_son_validos(datos):
    datos = {"tanques": [{"nombre": "a", "programa": "a.txt"}], **datos}
    assert cfg.desde_diccionario(datos).validar() == []


def test_como_maximo_seis_tanques():
    def con(n):
        return cfg.desde_diccionario({"tanques": [
            {"nombre": f"t{i}", "programa": "x.txt"} for i in range(n)]})
    assert con(6).validar() == []
    assert any("6 tanques" in p for p in con(7).validar())


def test_un_valor_mal_escrito_se_avisa_con_las_opciones():
    with pytest.raises(ValueError, match="rotativo"):
        cfg.desde_diccionario({"reglas": {"orden_turnos": "mágico"}})


def test_no_distingue_mayusculas_ni_espacios():
    c = cfg.desde_diccionario({"reglas": {"orden_turnos": "  Rotativo "}})
    assert c.orden_turnos is cfg.OrdenTurnos.ROTATIVO


# ----------------------------------------------------------- por omisión
def test_un_json_minimo_toma_los_valores_por_omision():
    c = cfg.desde_diccionario({"tanques": [{"nombre": "a", "programa": "a.txt"}]})
    por_omision = cfg.Configuracion()
    assert c.tablero == por_omision.tablero
    assert c.orden_turnos is por_omision.orden_turnos
    assert c.dano == por_omision.dano


def test_el_color_tiene_valor_por_omision():
    c = cfg.desde_diccionario({"tanques": [{"nombre": "a", "programa": "a.txt"}]})
    assert c.tanques[0].color.startswith("#")


# ------------------------------------------------------------ validación
@pytest.mark.parametrize("datos,aviso", [
    ({"tablero": {"ancho": 3, "alto": 8}}, "al menos 4 x 4"),
    ({"vida_inicial": 0}, "vida inicial"),
    ({"rondas_maximas": -1}, "máximo de rondas"),
    ({"refaccion": {"minimo": 30, "maximo": 10}}, "mínimo de la refacción"),
])
def test_la_validacion_detecta_los_valores_imposibles(datos, aviso):
    datos = {"tanques": [{"nombre": "a", "programa": "a.txt"}], **datos}
    problemas = cfg.desde_diccionario(datos).validar()
    assert any(aviso in p for p in problemas), problemas


def test_la_validacion_exige_al_menos_un_tanque():
    assert any("al menos un tanque" in p
               for p in cfg.desde_diccionario({}).validar())


def test_la_validacion_rechaza_nombres_repetidos():
    datos = {"tanques": [{"nombre": "a", "programa": "a.txt"},
                         {"nombre": "a", "programa": "b.txt"}]}
    assert any("repetidos" in p for p in cfg.desde_diccionario(datos).validar())


def test_no_caben_mas_tanques_que_casillas():
    datos = {"tablero": {"ancho": 2, "alto": 2},
             "tanques": [{"nombre": f"t{i}", "programa": "x.txt"}
                         for i in range(5)]}
    assert any("más tanques que casillas" in p
               for p in cfg.desde_diccionario(datos).validar())


@pytest.mark.parametrize("tanques, lado, valido", [
    (2, 4, True), (4, 4, True), (5, 4, False), (5, 5, True),
    (6, 5, False), (6, 6, True)])
def test_el_tablero_crece_con_los_tanques(tanques, lado, valido):
    datos = {"tablero": {"ancho": lado, "alto": lado + 3},
             "tanques": [{"nombre": f"t{i}", "programa": "x.txt"}
                         for i in range(tanques)]}
    problemas = cfg.desde_diccionario(datos).validar()
    assert (not any("al menos" in p for p in problemas)) is valido, problemas
    assert cfg.lado_minimo(tanques) == max(4, tanques)


def test_cargar_un_config_invalido_falla_con_el_detalle(tmp_path):
    ruta = tmp_path / "malo.json"
    ruta.write_text(json.dumps({"tablero": {"ancho": 1, "alto": 1},
                                "tanques": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="malo.json"):
        cfg.cargar(ruta)
