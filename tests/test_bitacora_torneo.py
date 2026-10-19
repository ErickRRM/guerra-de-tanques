"""Pruebas de la bitácora de partida y del torneo."""
import io
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from tanques import config as cfg
from tanques.controlador import (ejecutar, escribir_csv, formato_resumen,
                                 jugar_torneo, preparar)
from tanques.modelo import Motivo
from tanques.vista import Vista, VistaBitacora, VistaConsola, VistaMultiple
from tanques.vista.bitacora import ruta_por_omision

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = cfg.cargar(RAIZ / "config.json")


def partida_con_bitacora(semilla=5, salida=None):
    salida = salida or io.StringIO()
    motor, errores = preparar(CONFIG, RAIZ, semilla)
    assert errores == []
    bitacora = VistaBitacora(salida, CONFIG, semilla,
                             momento=datetime(2026, 10, 19, 12, 0, 0))
    resultado = ejecutar(motor, bitacora)
    return salida, resultado, motor


# ---------------------------------------------------------------- bitácora
def test_la_bitacora_lleva_lo_necesario_para_reproducir():
    salida, _, _ = partida_con_bitacora()
    texto = salida.getvalue()
    assert "Semilla        5" in texto
    assert "radar hibrido · turnos rotativo" in texto
    assert "tanques/cazador.txt" in texto


def test_la_bitacora_registra_cada_ronda_y_el_resultado():
    salida, resultado, _ = partida_con_bitacora()
    texto = salida.getvalue()
    assert texto.count("--- Ronda ") == resultado.rondas
    assert f"Ganador        {resultado.ganador}" in texto
    assert f"Rondas         {resultado.rondas}" in texto


def test_la_misma_semilla_da_la_misma_bitacora():
    assert (partida_con_bitacora(9)[0].getvalue()
            == partida_con_bitacora(9)[0].getvalue())


def test_la_bitacora_en_archivo(tmp_path):
    ruta = tmp_path / "sub" / "partida.txt"
    motor, _ = preparar(CONFIG, RAIZ)
    ejecutar(motor, VistaBitacora(ruta, CONFIG))
    assert ruta.read_text(encoding="utf-8").startswith("=" * 70)


def test_ruta_por_omision():
    ruta = ruta_por_omision("bitacoras", 42, datetime(2026, 10, 19, 14, 3, 12))
    assert ruta == Path("bitacoras/partida_20261019-140312_s42.txt")


def test_partida_interrumpida():
    class Corta(Vista):
        def inicio(self, estado, eventos):
            pass

        def ronda(self, estado, eventos):
            return estado.ronda < 3

        def fin(self, estado, resultado):
            pass

    salida = io.StringIO()
    motor, _ = preparar(CONFIG, RAIZ)
    resultado = ejecutar(motor, VistaMultiple(Corta(),
                                              VistaBitacora(salida, CONFIG)))
    assert resultado is None
    assert "Partida interrumpida en la ronda 3." in salida.getvalue()


def test_varias_vistas_reciben_la_misma_partida():
    consola, bitacora = io.StringIO(), io.StringIO()
    motor, _ = preparar(CONFIG, RAIZ)
    ejecutar(motor, VistaMultiple(
        VistaConsola(100, salida=consola, color=False),
        VistaBitacora(bitacora, CONFIG)))
    r = motor.resultado()
    assert f"Rondas jugadas: {r.rondas}." in consola.getvalue()
    assert f"Rondas         {r.rondas}" in bitacora.getvalue()


# ---------------------------------------------------------------- torneo
def test_el_torneo_juega_una_partida_por_semilla():
    torneo, errores = jugar_torneo(CONFIG, RAIZ, range(1, 11))
    assert errores == [] and torneo.partidas == 10
    assert [f.semilla for f in torneo.filas] == list(range(1, 11))
    victorias = sum(t.victorias for t in torneo.tanques.values())
    assert victorias + torneo.empates == 10


def test_el_torneo_coincide_con_partidas_sueltas():
    torneo, _ = jugar_torneo(CONFIG, RAIZ, [3])
    _, resultado, _ = partida_con_bitacora(3)
    fila = torneo.filas[0]
    assert (fila.ganador, fila.motivo, fila.rondas) \
        == (resultado.ganador, resultado.motivo, resultado.rondas)


def test_el_torneo_separa_destruccion_y_desempate():
    corto = replace(CONFIG, rondas_maximas=5)
    torneo, _ = jugar_torneo(corto, RAIZ, range(1, 6))
    assert all(f.motivo is not Motivo.DESTRUCCION for f in torneo.filas)
    assert sum(t.por_destruccion for t in torneo.tanques.values()) == 0


def test_el_csv_tiene_una_fila_por_partida():
    torneo, _ = jugar_torneo(CONFIG, RAIZ, range(1, 4))
    salida = io.StringIO()
    escribir_csv(torneo, salida)
    lineas = salida.getvalue().strip().splitlines()
    assert lineas[0].startswith("semilla,ganador,motivo,rondas,infligido_")
    assert len(lineas) == 4


def test_el_resumen():
    torneo, _ = jugar_torneo(CONFIG, RAIZ, range(1, 4))
    texto = formato_resumen(torneo)
    assert texto.startswith("3 partidas")
    assert "cazador" in texto and "autoinfligido" in texto


def test_el_torneo_no_juega_con_programas_invalidos(tmp_path):
    (tmp_path / "malo.txt").write_text("DISPARAR\n", encoding="utf-8")
    c = replace(CONFIG, tanques=(cfg.TanqueConfig("malo", "malo.txt"),))
    torneo, errores = jugar_torneo(c, tmp_path, range(3))
    assert torneo is None and errores
