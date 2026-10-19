"""Eventos que publica el motor.

El motor no escribe en pantalla: devuelve una lista de eventos por turno.
La bitácora, la vista de consola y la interfaz gráfica consumen la misma
lista, de modo que las tres cuentan siempre la misma partida.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TipoEvento(Enum):
    INICIO = "inicio"
    RONDA = "ronda"
    INSTRUCCION = "instruccion"     # qué línea ejecuta el tanque
    MOVIMIENTO = "movimiento"
    RADAR = "radar"
    DISPARO = "disparo"
    DANO = "dano"
    BLOQUEO = "bloqueo"             # el escudo absorbió un daño
    ESCUDO = "escudo"
    REPARACION = "reparacion"
    REFACCION = "refaccion"
    MINA_COLOCADA = "mina_colocada"
    MINA_ARMADA = "mina_armada"
    MINA_EXPLOTA = "mina_explota"
    CONDICION_FALSA = "condicion_falsa"
    SIN_EFECTO = "sin_efecto"
    DESTRUCCION = "destruccion"
    FIN = "fin"


@dataclass(frozen=True)
class Evento:
    """Algo que ocurrió en la partida, con su texto ya redactado."""

    ronda: int
    tipo: TipoEvento
    texto: str
    tanque: Optional[str] = None
    datos: dict[str, Any] = field(default_factory=dict, compare=False)

    def __str__(self) -> str:
        return f"[R{self.ronda:>3}] {self.texto}"
