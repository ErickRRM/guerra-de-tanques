"""Representación interna de las instrucciones ya validadas.

Es la salida del analizador sintáctico y la entrada del motor. No contiene
lógica de juego: describe qué pide la instrucción, no qué ocurre al
ejecutarla.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..modelo.direccion import Direccion


class Tipo(Enum):
    """Las once instrucciones del lenguaje definido en clase."""

    MOV = "MOV"
    AMT = "AMT"
    RADAR = "RADAR"
    DANAR = "DAÑAR"
    MISIL = "MISIL"
    MINA = "MINA"
    ESCUDO = "ESCUDO"
    REPARAR = "REPARAR"
    ESPERAR = "ESPERAR"
    IF = "IF"


#: Instrucciones cuyo único parámetro es una dirección.
CON_DIRECCION = frozenset({Tipo.MOV, Tipo.AMT, Tipo.RADAR, Tipo.DANAR})

#: Instrucciones sin parámetros.
SIN_PARAMETROS = frozenset({Tipo.MINA, Tipo.ESCUDO, Tipo.REPARAR,
                            Tipo.ESPERAR})

#: Acciones admitidas dentro de un IF.
ACCIONES_EN_IF = frozenset({Tipo.AMT, Tipo.MISIL, Tipo.ESCUDO, Tipo.REPARAR})


class Fuente(Enum):
    """Lo que puede evaluarse en la condición de un IF."""

    RADAR = "RADAR"
    VIDA = "VIDA"


class Operador(Enum):
    MAYOR = ">"
    MENOR = "<"
    MAYOR_IGUAL = ">="
    MENOR_IGUAL = "<="
    IGUAL = "=="

    def compara(self, izquierda: int, derecha: int) -> bool:
        return _COMPARACIONES[self](izquierda, derecha)


_COMPARACIONES = {
    Operador.MAYOR: lambda a, b: a > b,
    Operador.MENOR: lambda a, b: a < b,
    Operador.MAYOR_IGUAL: lambda a, b: a >= b,
    Operador.MENOR_IGUAL: lambda a, b: a <= b,
    Operador.IGUAL: lambda a, b: a == b,
}


@dataclass(frozen=True)
class Condicion:
    """La condición de un IF: RADAR(dir) cmp n  o  VIDA cmp n."""

    fuente: Fuente
    operador: Operador
    valor: int
    direccion: Optional[Direccion] = None   # solo cuando la fuente es RADAR

    def evalua(self, lectura: int) -> bool:
        """Compara el valor leído contra el de la condición."""
        return self.operador.compara(lectura, self.valor)

    def __str__(self) -> str:
        izq = (f"RADAR({self.direccion.name})" if self.fuente is Fuente.RADAR
               else "VIDA")
        return f"{izq} {self.operador.value} {self.valor}"


@dataclass(frozen=True)
class Instruccion:
    """Una instrucción validada, lista para que el motor la ejecute."""

    tipo: Tipo
    direccion: Optional[Direccion] = None
    x: Optional[int] = None
    y: Optional[int] = None
    condicion: Optional[Condicion] = None
    accion: Optional["Instruccion"] = None   # solo cuando el tipo es IF
    linea: int = 0

    def __str__(self) -> str:
        if self.tipo is Tipo.IF:
            return f"IF {self.condicion} THEN {self.accion}"
        if self.tipo is Tipo.MISIL:
            return f"MISIL({self.x},{self.y})"
        if self.direccion is not None:
            return f"{self.tipo.value}({self.direccion.name})"
        return self.tipo.value


@dataclass
class Programa:
    """El programa completo de un tanque."""

    nombre: str
    instrucciones: list[Instruccion]
    archivo: str = ""

    def __len__(self) -> int:
        return len(self.instrucciones)

    def __iter__(self):
        return iter(self.instrucciones)

    def en(self, indice: int) -> Instruccion:
        """Devuelve la instrucción en esa posición, reiniciando al final.

        Al agotarse el programa vuelve a la primera línea, según la decisión
        registrada en docs/DECISIONES.md.
        """
        if not self.instrucciones:
            raise IndexError("el programa no tiene instrucciones")
        return self.instrucciones[indice % len(self.instrucciones)]
