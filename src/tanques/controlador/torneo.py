"""Lotes de partidas con semillas consecutivas, para medir el equilibrio.

Responde a la sección 8 del documento de arquitectura: para cada partida se
registra el ganador, la forma de término, las rondas y el daño de cada
tanque; y en el resumen se separan las victorias por destrucción de las
adjudicadas por desempate, porque mezclarlas puede hacer parecer dominante
a una estrategia que en combate directo no lo es. El daño autoinfligido se
cuenta aparte del causado a los rivales.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, TextIO

from ..config import Configuracion
from ..lenguaje import ErrorSintaxis
from ..modelo import Motivo
from .partida import preparar


@dataclass(frozen=True)
class FilaPartida:
    semilla: int
    ganador: Optional[str]
    motivo: Motivo
    rondas: int
    dano_infligido: dict[str, int]
    dano_autoinfligido: dict[str, int]


@dataclass
class ResumenTanque:
    nombre: str
    por_destruccion: int = 0
    por_desempate: int = 0
    dano_infligido: int = 0
    dano_autoinfligido: int = 0

    @property
    def victorias(self) -> int:
        return self.por_destruccion + self.por_desempate


@dataclass
class Torneo:
    filas: list[FilaPartida] = field(default_factory=list)
    tanques: dict[str, ResumenTanque] = field(default_factory=dict)

    @property
    def partidas(self) -> int:
        return len(self.filas)

    @property
    def empates(self) -> int:
        return sum(f.motivo is Motivo.EMPATE for f in self.filas)

    def rondas(self) -> tuple[float, int, int]:
        """Media, mínimo y máximo de rondas por partida."""
        r = [f.rondas for f in self.filas]
        return sum(r) / len(r), min(r), max(r)

    def agregar(self, fila: FilaPartida):
        self.filas.append(fila)
        for nombre in fila.dano_infligido:
            t = self.tanques.setdefault(nombre, ResumenTanque(nombre))
            t.dano_infligido += fila.dano_infligido[nombre]
            t.dano_autoinfligido += fila.dano_autoinfligido[nombre]
        if fila.ganador is not None:
            t = self.tanques[fila.ganador]
            if fila.motivo is Motivo.DESTRUCCION:
                t.por_destruccion += 1
            else:
                t.por_desempate += 1


def jugar_torneo(config: Configuracion, raiz: str | Path,
                 semillas: Iterable[int],
                 ) -> tuple[Optional[Torneo], list[ErrorSintaxis]]:
    """Juega una partida por semilla. Si un programa falla, no juega ninguna."""
    torneo = Torneo()
    for semilla in semillas:
        motor, errores = preparar(config, raiz, semilla)
        if errores:
            return None, errores
        motor.jugar()
        r = motor.resultado()
        tanques = motor.registro.tanques
        torneo.agregar(FilaPartida(
            semilla=semilla, ganador=r.ganador, motivo=r.motivo,
            rondas=r.rondas, dano_infligido=dict(r.dano_infligido),
            dano_autoinfligido={t.nombre: t.dano_autoinfligido
                                for t in tanques}))
    return torneo, []


def escribir_csv(torneo: Torneo, salida: TextIO):
    """Una fila por partida, con dos columnas de daño por tanque."""
    nombres = list(torneo.tanques)
    escritor = csv.writer(salida)
    escritor.writerow(["semilla", "ganador", "motivo", "rondas"]
                      + [f"infligido_{n}" for n in nombres]
                      + [f"autoinfligido_{n}" for n in nombres])
    for f in torneo.filas:
        escritor.writerow([f.semilla, f.ganador or "", f.motivo.value,
                           f.rondas]
                          + [f.dano_infligido[n] for n in nombres]
                          + [f.dano_autoinfligido[n] for n in nombres])


def formato_resumen(torneo: Torneo) -> str:
    media, minimo, maximo = torneo.rondas()
    ancho = max(len(n) for n in torneo.tanques)
    n = torneo.partidas
    lineas = [
        f"{n} partidas · rondas: media {media:.1f}, mínimo {minimo}, "
        f"máximo {maximo} · empates: {torneo.empates}",
        "",
        f"  {'tanque':<{ancho}}  victorias  destrucción  desempate"
        f"  daño infligido  autoinfligido",
    ]
    orden = sorted(torneo.tanques.values(), key=lambda t: -t.victorias)
    for t in orden:
        lineas.append(
            f"  {t.nombre:<{ancho}}  {t.victorias:>9}  "
            f"{t.por_destruccion:>11}  {t.por_desempate:>9}"
            f"  {t.dano_infligido / n:>14.1f}  "
            f"{t.dano_autoinfligido / n:>13.1f}")
    lineas += ["", "Daño: media por partida."]
    return "\n".join(lineas)
