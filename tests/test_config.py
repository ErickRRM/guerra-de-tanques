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
def test_las_cuatro_decisiones_tienen_el_valor_acordado():
    c = cfg.cargar(RAIZ / "config.json")
    assert c.modo_radar is cfg.ModoRadar.HIBRIDO
    assert c.orden_turnos is cfg.OrdenTurnos.ROTATIVO
    assert c.mina_turnos_armado == 2
    assert c.mina_medida_armado is cfg.MedidaArmado.TURNOS_PROPIETARIO
    assert c.acredita_choque is cfg.AcreditaChoque.EMBESTIDOR


def test_las_decisiones_se_pueden_cambiar_desde_el_json():
    c = cfg.desde_diccionario({
        "tanques": [{"nombre": "a", "programa": "a.txt"}],
        "reglas": {
            "modo_radar": "registro",
            "orden_turnos": "aleatorio",
            "acredita_choque": "ambos",
            "mina": {"turnos_armado": 3, "medida": "rondas"},
        },
    })
    assert c.modo_radar is cfg.ModoRadar.REGISTRO
    assert c.orden_turnos is cfg.OrdenTurnos.ALEATORIO
    assert c.acredita_choque is cfg.AcreditaChoque.AMBOS
    assert c.mina_turnos_armado == 3
    assert c.mina_medida_armado is cfg.MedidaArmado.RONDAS


def test_un_valor_mal_escrito_se_avisa_con_las_opciones():
    with pytest.raises(ValueError, match="hibrido"):
        cfg.desde_diccionario({"reglas": {"modo_radar": "mágico"}})


def test_no_distingue_mayusculas_ni_espacios():
    c = cfg.desde_diccionario({"reglas": {"orden_turnos": "  Rotativo "}})
    assert c.orden_turnos is cfg.OrdenTurnos.ROTATIVO


# ----------------------------------------------------------- por omisión
def test_un_json_minimo_toma_los_valores_por_omision():
    c = cfg.desde_diccionario({"tanques": [{"nombre": "a", "programa": "a.txt"}]})
    por_omision = cfg.Configuracion()
    assert c.tablero == por_omision.tablero
    assert c.modo_radar is por_omision.modo_radar
    assert c.dano.ametralladora == 10


def test_el_color_tiene_valor_por_omision():
    c = cfg.desde_diccionario({"tanques": [{"nombre": "a", "programa": "a.txt"}]})
    assert c.tanques[0].color.startswith("#")


# ------------------------------------------------------------ validación
@pytest.mark.parametrize("datos,aviso", [
    ({"tablero": {"ancho": 1, "alto": 8}}, "al menos 2"),
    ({"vida_inicial": 0}, "vida inicial"),
    ({"rondas_maximas": 0}, "máximo de rondas"),
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


def test_cargar_un_config_invalido_falla_con_el_detalle(tmp_path):
    ruta = tmp_path / "malo.json"
    ruta.write_text(json.dumps({"tablero": {"ancho": 1, "alto": 1},
                                "tanques": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="malo.json"):
        cfg.cargar(ruta)


# ------------------------------------------------- acoplamiento con el tablero
def test_el_tablero_configurado_llega_al_validador():
    """MISIL se valida contra el tamaño real del tablero, no contra 8 x 8."""
    from tanques.lenguaje import Interprete
    c = cfg.desde_diccionario({"tablero": {"ancho": 12, "alto": 12},
                               "tanques": [{"nombre": "a", "programa": "a.txt"}]})
    i = Interprete(c.tablero.ancho, c.tablero.alto)
    assert i.analizar("MISIL(10,10)")[1] == []
