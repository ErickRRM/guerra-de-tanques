"""Lo que ocupa el tablero: tanques, minas y refacciones.

Son objetos mutables que solo el motor modifica. La vista nunca los recibe
directamente; recibe la copia de solo lectura que arma `Motor.estado()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .direccion import Direccion
from .tablero import Posicion


@dataclass(eq=False)
class Tanque:
    """Un tanque con su programa y todos sus contadores.

    `eq=False` porque dos tanques son iguales solo si son el mismo objeto;
    comparar por valor confundiría a dos tanques con la misma vida.
    """

    nombre: str
    programa: Any                 # cualquier objeto con .en(i) -> instrucción
    posicion: Posicion
    vida: int
    vida_maxima: int
    minas: int
    misiles: int
    reparaciones: int
    color: str = "#2E5E8C"
    numero: int = 0               # el que se imprime sobre la torreta

    vivo: bool = True
    escudo: bool = False
    contador: int = 0             # índice de la siguiente instrucción
    turnos: int = 0               # turnos ya jugados
    ultima_direccion: Direccion = Direccion.N
    ultima_linea: int = 0
    #: Lectura del último RADAR suelto: (dirección, distancia). D-01.
    ultimo_radar: Optional[tuple[Direccion, int]] = None
    #: Si entró a una casilla en este turno; las minas se pisan al entrar.
    llego: bool = False

    dano_infligido: int = 0       # el criterio de desempate
    dano_recibido: int = 0
    dano_autoinfligido: int = 0   # pared, mina propia, misil propio

    def __repr__(self) -> str:
        return f"Tanque({self.nombre!r}, {self.posicion}, vida={self.vida})"


@dataclass(eq=False)
class Mina:
    """Una mina colocada. Se arma cuando `faltan` llega a cero."""

    posicion: Posicion
    dueno: Tanque
    faltan: int
    ronda_colocada: int
    turno_colocada: int           # turnos del dueño al colocarla

    @property
    def armada(self) -> bool:
        return self.faltan <= 0


@dataclass(frozen=True)
class Refaccion:
    """Lo que deja un tanque destruido; cura al tanque que la pisa."""

    posicion: Posicion


@dataclass
class Registro:
    """Contenedor de las entidades vivas del tablero."""

    tanques: list[Tanque] = field(default_factory=list)
    minas: list[Mina] = field(default_factory=list)
    refacciones: list[Refaccion] = field(default_factory=list)

    def tanque_en(self, pos: Posicion) -> Optional[Tanque]:
        return next((t for t in self.tanques
                     if t.vivo and t.posicion == pos), None)

    def mina_en(self, pos: Posicion) -> Optional[Mina]:
        return next((m for m in self.minas if m.posicion == pos), None)

    def refaccion_en(self, pos: Posicion) -> Optional[Refaccion]:
        return next((r for r in self.refacciones if r.posicion == pos), None)

    def vivos(self) -> list[Tanque]:
        return [t for t in self.tanques if t.vivo]
