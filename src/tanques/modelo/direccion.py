"""Las cuatro direcciones cardinales del tablero."""
from __future__ import annotations

from enum import Enum


class Direccion(Enum):
    """Dirección cardinal con su vector de desplazamiento.

    El tablero usa coordenadas (x, y) en base 1: x es la columna y crece hacia
    el este; y es la fila y crece hacia el sur. Por tanto la fila 1 es el norte
    y moverse al norte disminuye y.
    """

    N = (0, -1)
    S = (0, 1)
    E = (1, 0)
    O = (-1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    def opuesta(self) -> "Direccion":
        return _OPUESTAS[self]

    @classmethod
    def desde_texto(cls, texto: str) -> "Direccion":
        """Convierte 'n', 'N', ' s ' … en la dirección correspondiente."""
        return cls[texto.strip().upper()]

    @classmethod
    def es_valida(cls, texto: str) -> bool:
        return texto.strip().upper() in cls.__members__


_OPUESTAS = {Direccion.N: Direccion.S, Direccion.S: Direccion.N,
             Direccion.E: Direccion.O, Direccion.O: Direccion.E}
