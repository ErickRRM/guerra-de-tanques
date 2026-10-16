"""Estructuras de datos compartidas entre el intérprete, el motor y la interfaz.

Este módulo no contiene reglas del juego ni depende de los demás: solo define
el vocabulario común. Corresponde a los contratos de la sección 2.2 del
documento de arquitectura.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Direccion(Enum):
    """Las cuatro direcciones cardinales.

    El tablero usa coordenadas (x, y) en base 1: x es la columna y crece hacia
    el este; y es la fila y crece hacia el sur. La fila 1 es el norte.
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
        return {Direccion.N: Direccion.S, Direccion.S: Direccion.N,
                Direccion.E: Direccion.O, Direccion.O: Direccion.E}[self]


class Tipo(Enum):
    """Las once instrucciones del lenguaje definido en clase."""

    MOV = "MOV"
    AMT = "AMT"
    RADAR = "RADAR"
    DANAR = "DAÑAR"
    MISIL = "MISIL"
    MINA = "MINA"
    ESCUDO = "ESCUDO"
    RESTAURAR = "RESTAURAR"
    ESPERAR = "ESPERAR"
    IF = "IF"


#: Instrucciones que reciben una dirección como único parámetro.
CON_DIRECCION = {Tipo.MOV, Tipo.AMT, Tipo.RADAR, Tipo.DANAR}

#: Instrucciones sin parámetros.
SIN_PARAMETROS = {Tipo.MINA, Tipo.ESCUDO, Tipo.RESTAURAR, Tipo.ESPERAR}

#: Acciones admitidas dentro de un IF (sección 4.1 del documento).
ACCIONES_EN_IF = {Tipo.AMT, Tipo.MISIL, Tipo.ESCUDO, Tipo.RESTAURAR}


class Fuente(Enum):
    """Lo que puede evaluarse dentro de la condición de un IF."""

    RADAR = "RADAR"
    VIDA = "VIDA"


class Operador(Enum):
    MAYOR = ">"
    MENOR = "<"
    MAYOR_IGUAL = ">="
    MENOR_IGUAL = "<="
    IGUAL = "=="

    def compara(self, izq: int, der: int) -> bool:
        return {
            Operador.MAYOR: izq > der,
            Operador.MENOR: izq < der,
            Operador.MAYOR_IGUAL: izq >= der,
            Operador.MENOR_IGUAL: izq <= der,
            Operador.IGUAL: izq == der,
        }[self]


@dataclass(frozen=True)
class Condicion:
    """La condición de un IF: RADAR(dir) cmp n   o   VIDA cmp n."""

    fuente: Fuente
    operador: Operador
    valor: int
    direccion: Optional[Direccion] = None  # solo cuando fuente es RADAR

    def __str__(self) -> str:
        izq = (f"RADAR({self.direccion.name})" if self.fuente is Fuente.RADAR
               else "VIDA")
        return f"{izq} {self.operador.value} {self.valor}"


@dataclass(frozen=True)
class Instruccion:
    """Una instrucción ya validada y lista para ejecutarse."""

    tipo: Tipo
    direccion: Optional[Direccion] = None
    x: Optional[int] = None
    y: Optional[int] = None
    condicion: Optional[Condicion] = None
    accion: Optional["Instruccion"] = None  # solo cuando tipo es IF
    linea: int = 0                          # línea del archivo, para la bitácora

    def __str__(self) -> str:
        if self.tipo is Tipo.IF:
            return f"IF {self.condicion} THEN {self.accion}"
        if self.tipo is Tipo.MISIL:
            return f"MISIL({self.x},{self.y})"
        if self.direccion is not None:
            return f"{self.tipo.value}({self.direccion.name})"
        return self.tipo.value


@dataclass(frozen=True)
class ErrorSintaxis:
    """Un error detectado al validar un archivo de instrucciones."""

    archivo: str
    linea: int
    mensaje: str
    texto: str = ""

    def __str__(self) -> str:
        donde = f"{self.archivo}, línea {self.linea}" if self.linea else self.archivo
        return f"{donde}: {self.mensaje}"


@dataclass
class Programa:
    """El programa completo de un tanque."""

    nombre: str
    instrucciones: list[Instruccion]
    archivo: str = ""

    def __len__(self) -> int:
        return len(self.instrucciones)
