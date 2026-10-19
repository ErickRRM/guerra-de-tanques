"""Contrato común de las vistas.

El controlador solo conoce esta clase: le entrega el estado y los eventos de
cada ronda y no le importa si los dibuja la consola o Tkinter. Ninguna vista
contiene reglas; todo lo que muestra sale de `Motor.estado()` y de los
eventos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from ..modelo import EstadoJuego, Evento, Resultado


class Vista(ABC):

    @abstractmethod
    def inicio(self, estado: EstadoJuego, eventos: Sequence[Evento]) -> None:
        """La partida está colocada y aún no empieza."""

    @abstractmethod
    def ronda(self, estado: EstadoJuego, eventos: Sequence[Evento]) -> bool:
        """Terminó una ronda. Devuelve False si el usuario quiere salir."""

    @abstractmethod
    def fin(self, estado: EstadoJuego, resultado: Resultado) -> None:
        """La partida terminó."""
