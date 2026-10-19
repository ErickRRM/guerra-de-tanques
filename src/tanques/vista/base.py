"""Contrato común de las vistas.

El controlador solo conoce esta clase: le entrega el estado y los eventos de
cada ronda y no le importa si los dibuja la consola o Tkinter. Ninguna vista
contiene reglas; todo lo que muestra sale de `Motor.estado()` y de los
eventos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..modelo import EstadoJuego, Evento, Resultado


class Vista(ABC):

    @abstractmethod
    def inicio(self, estado: EstadoJuego,
               eventos: Sequence[Evento]) -> Optional[bool]:
        """La partida está colocada y aún no empieza.

        Devolver False cancela la partida antes de la primera ronda; None
        o True la dejan seguir.
        """

    def turno(self, estado: EstadoJuego, eventos: Sequence[Evento]) -> bool:
        """Terminó el turno de un tanque. False si el usuario quiere salir.

        Opcional: la consola dibuja por rondas y no lo necesita; la ventana
        lo usa para animar cada disparo, movimiento o explosión.
        """
        return True

    @abstractmethod
    def ronda(self, estado: EstadoJuego, eventos: Sequence[Evento]) -> bool:
        """Terminó una ronda. Devuelve False si el usuario quiere salir."""

    @abstractmethod
    def fin(self, estado: EstadoJuego, resultado: Resultado) -> None:
        """La partida terminó."""


class VistaMultiple(Vista):
    """Reparte la partida entre varias vistas, p. ej. consola y bitácora.

    El usuario sale si cualquiera de ellas lo pide.
    """

    def __init__(self, *vistas: Vista):
        self.vistas = vistas

    def inicio(self, estado, eventos):
        seguir = True
        for v in self.vistas:
            seguir = v.inicio(estado, eventos) is not False and seguir
        return seguir

    def turno(self, estado, eventos):
        seguir = True
        for v in self.vistas:
            seguir = v.turno(estado, eventos) is not False and seguir
        return seguir

    def ronda(self, estado, eventos):
        seguir = True
        for v in self.vistas:
            seguir = v.ronda(estado, eventos) and seguir
        return seguir

    def fin(self, estado, resultado):
        for v in self.vistas:
            v.fin(estado, resultado)
