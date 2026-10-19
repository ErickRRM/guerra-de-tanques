"""Bitácora de partida: el registro completo en un archivo de texto.

Es una vista más: recibe los mismos eventos que la consola o la ventana, de
modo que la bitácora cuenta siempre la misma partida que se vio. Lleva
además la semilla y las reglas vigentes, que son lo necesario para
reproducirla.

    ======================================================================
    GUERRA DE TANQUES · BITÁCORA DE PARTIDA
    ...
    --- Ronda 1 · cazador, defensivo, explorador
    [R  1] cazador L2: RADAR(S)
    [R  1] cazador explora al S: pared a 7
    ...
    RESULTADO
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from ..config import Configuracion
from ..modelo import Motivo, TipoEvento
from .base import Vista

_MOTIVOS = {Motivo.DESTRUCCION: "último tanque en pie",
            Motivo.DESEMPATE: "límite de rondas; decide el daño infligido",
            Motivo.EMPATE: "límite de rondas; el daño infligido coincide"}


def ruta_por_omision(carpeta: str | Path, semilla: int,
                     momento: Optional[datetime] = None) -> Path:
    """bitacoras/partida_20261019-140312_s42.txt"""
    momento = momento or datetime.now()
    return (Path(carpeta)
            / f"partida_{momento:%Y%m%d-%H%M%S}_s{semilla}.txt")


class VistaBitacora(Vista):
    """Escribe la partida en `salida`, que puede ser una ruta o un archivo.

    Si recibe una ruta, abre el archivo al empezar y lo cierra al terminar.
    """

    def __init__(self, salida: str | Path | TextIO, config: Configuracion,
                 semilla: Optional[int] = None,
                 momento: Optional[datetime] = None):
        self._ruta = None if hasattr(salida, "write") else Path(salida)
        self._salida: Optional[TextIO] = (None if self._ruta
                                          else salida)
        self.config = config
        self.semilla = config.semilla if semilla is None else semilla
        self.momento = momento or datetime.now()

    @property
    def ruta(self) -> Optional[Path]:
        return self._ruta

    # ---------------------------------------------------------- contrato
    def inicio(self, estado, eventos):
        if self._ruta is not None:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            self._salida = self._ruta.open("w", encoding="utf-8")
        c = self.config
        programas = {t.nombre: t.programa for t in c.tanques}
        self._linea("=" * 70)
        self._linea("GUERRA DE TANQUES · BITÁCORA DE PARTIDA")
        self._linea("=" * 70)
        self._linea(f"Fecha          {self.momento:%Y-%m-%d %H:%M:%S}")
        self._linea(f"Semilla        {self.semilla}")
        self._linea(f"Tablero        {estado.ancho} x {estado.alto}")
        self._linea(f"Rondas máximas {c.rondas_maximas}")
        self._linea(f"Vida inicial   {c.vida_inicial}")
        self._linea(f"Reglas         radar {c.modo_radar.value} · turnos "
                    f"{c.orden_turnos.value} · mina "
                    f"{c.mina_turnos_armado} {c.mina_medida_armado.value} "
                    f"· choque {c.acredita_choque.value}")
        self._linea("")
        self._linea("Tanques")
        for t in estado.tanques:
            programa = programas.get(t.nombre, "")
            self._linea(f"  #{t.numero} {t.nombre:<14} {str(t.posicion):<9}"
                        f"{programa}")
        self._linea("")
        self._flush()

    def turno(self, estado, eventos):
        # Turno por turno: si el usuario sale a media ronda, lo jugado
        # hasta ahí queda escrito.
        for e in eventos:
            if e.tipo is TipoEvento.RONDA:
                self._linea("")
                self._linea(f"--- Ronda {e.ronda} · "
                            + ", ".join(e.datos["orden"]))
            elif e.tipo is not TipoEvento.FIN:
                self._linea(str(e))
        self._flush()
        return True

    def ronda(self, estado, eventos):
        return True

    def fin(self, estado, resultado):
        self._linea("")
        self._linea("=" * 70)
        self._linea("RESULTADO")
        if resultado is None:
            self._linea(f"Partida interrumpida en la ronda {estado.ronda}.")
        else:
            ganador = resultado.ganador or "ninguno (empate)"
            self._linea(f"Ganador        {ganador}")
            self._linea(f"Motivo         {_MOTIVOS[resultado.motivo]}")
            self._linea(f"Rondas         {resultado.rondas}")
        self._linea("")
        self._linea(f"  {'tanque':<17} {'vida':>4}  {'daño infligido':>14}")
        for t in estado.tanques:
            self._linea(f"  #{t.numero} {t.nombre:<14} {t.vida:>4}  "
                        f"{t.dano_infligido:>14}")
        self._flush()
        if self._ruta is not None and self._salida is not None:
            self._salida.close()
            self._salida = None

    # ---------------------------------------------------------- escritura
    def _linea(self, texto: str):
        self._salida.write(texto + "\n")

    def _flush(self):
        # La bitácora debe sobrevivir a un cierre a media partida.
        self._salida.flush()
