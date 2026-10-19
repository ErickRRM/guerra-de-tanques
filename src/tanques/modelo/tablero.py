"""Geometría del tablero: límites y recorrido en línea recta.

El tablero no guarda qué hay en cada casilla; eso lo sabe el motor. Aquí
solo vive lo que depende de las dimensiones, para que el radar, la
ametralladora y el movimiento compartan una sola definición de «pared».
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .direccion import Direccion

Posicion = tuple[int, int]


@dataclass(frozen=True)
class Tablero:
    """Rejilla de `ancho` x `alto` casillas en coordenadas base 1."""

    ancho: int
    alto: int

    def dentro(self, x: int, y: int) -> bool:
        return 1 <= x <= self.ancho and 1 <= y <= self.alto

    def casillas(self) -> list[Posicion]:
        """Todas las casillas, fila por fila de norte a sur."""
        return [(x, y) for y in range(1, self.alto + 1)
                for x in range(1, self.ancho + 1)]

    @staticmethod
    def vecina(pos: Posicion, direccion: Direccion) -> Posicion:
        return pos[0] + direccion.dx, pos[1] + direccion.dy

    def linea(self, desde: Posicion,
              direccion: Direccion) -> Iterator[tuple[int, Posicion]]:
        """Recorre las casillas en esa dirección, sin incluir la de partida.

        Entrega pares (distancia, casilla) y se detiene en la primera casilla
        fuera del tablero, que también entrega: es la pared. Quien recorre
        la línea decide qué hacer al encontrarla.
        """
        distancia, pos = 0, desde
        while True:
            distancia += 1
            pos = self.vecina(pos, direccion)
            yield distancia, pos
            if not self.dentro(*pos):
                return
