"""Componentes léxicos del lenguaje de instrucciones.

Un token es la unidad mínima con significado que produce el analizador
léxico. El analizador sintáctico trabaja sobre tokens, nunca sobre texto.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TipoToken(Enum):
    """Las categorías léxicas del lenguaje."""

    PALABRA = "palabra reservada"
    DIRECCION = "dirección"
    ENTERO = "entero"
    RELACIONAL = "operador relacional"
    PAR_IZQ = "paréntesis de apertura"
    PAR_DER = "paréntesis de cierre"
    COMA = "coma"
    FIN = "fin de línea"


#: Palabras reservadas del lenguaje. DANAR se admite como variante de DAÑAR
#: para que un teclado sin eñe no invalide el archivo.
PALABRAS_RESERVADAS = frozenset({
    "MOV", "AMT", "RADAR", "DAÑAR", "DANAR", "MISIL", "MINA", "ESCUDO",
    "RESTAURAR", "ESPERAR", "IF", "THEN", "VIDA",
})

#: Operadores relacionales admitidos en la condición de un IF.
RELACIONALES = frozenset({">", "<", ">=", "<=", "=="})

#: Los cuatro puntos cardinales.
DIRECCIONES = frozenset({"N", "S", "E", "O"})


@dataclass(frozen=True)
class Token:
    """Un componente léxico, con su posición para poder señalar errores."""

    tipo: TipoToken
    lexema: str
    linea: int
    columna: int

    def es(self, tipo: TipoToken, lexema: str | None = None) -> bool:
        """Comprueba el tipo y, opcionalmente, el lexema exacto."""
        if self.tipo is not tipo:
            return False
        return lexema is None or self.lexema == lexema

    def __str__(self) -> str:
        return f"{self.tipo.value} {self.lexema!r}"
