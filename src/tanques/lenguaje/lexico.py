"""Analizador léxico.

Primera fase del intérprete. Recorre el texto de una línea carácter a
carácter y lo descompone en componentes léxicos, descartando los espacios y
los comentarios. No conoce la gramática: no le corresponde decidir si la
secuencia de tokens tiene sentido, solo reconocerlos.
"""
from __future__ import annotations

from .errores import ErrorSintaxis, caracter_invalido
from .tokens import (DIRECCIONES, PALABRAS_RESERVADAS, RELACIONALES, TipoToken,
                     Token)

COMENTARIO = "#"
_DOBLES = (">=", "<=", "==")


class AnalizadorLexico:
    """Convierte una línea de texto en una lista de tokens."""

    def __init__(self, archivo: str = "programa"):
        self.archivo = archivo

    # ------------------------------------------------------------------
    def analizar(self, texto: str,
                 linea: int = 1) -> tuple[list[Token], list[ErrorSintaxis]]:
        """Descompone una línea. Devuelve (tokens, errores)."""
        tokens: list[Token] = []
        errores: list[ErrorSintaxis] = []
        i, n = 0, len(texto)

        while i < n:
            c = texto[i]

            if c.isspace():
                i += 1
                continue

            if c == COMENTARIO:          # el comentario llega hasta el final
                break

            col = i + 1

            # operadores de dos caracteres antes que los de uno
            if texto[i:i + 2] in _DOBLES:
                tokens.append(Token(TipoToken.RELACIONAL, texto[i:i + 2],
                                    linea, col))
                i += 2
                continue

            if c in "<>":
                tokens.append(Token(TipoToken.RELACIONAL, c, linea, col))
                i += 1
                continue

            if c == "(":
                tokens.append(Token(TipoToken.PAR_IZQ, c, linea, col)); i += 1
                continue
            if c == ")":
                tokens.append(Token(TipoToken.PAR_DER, c, linea, col)); i += 1
                continue
            if c == ",":
                tokens.append(Token(TipoToken.COMA, c, linea, col)); i += 1
                continue

            # entero, con signo negativo opcional
            if c.isdigit() or (c == "-" and i + 1 < n and texto[i + 1].isdigit()):
                j = i + 1
                while j < n and texto[j].isdigit():
                    j += 1
                tokens.append(Token(TipoToken.ENTERO, texto[i:j], linea, col))
                i = j
                continue

            # identificador: letras, dígitos, guion bajo y eñe
            if c.isalpha() or c == "_":
                j = i
                while j < n and (texto[j].isalnum() or texto[j] == "_"):
                    j += 1
                lexema = texto[i:j].upper()
                tokens.append(Token(self._clasifica(lexema), lexema, linea, col))
                i = j
                continue

            errores.append(ErrorSintaxis(self.archivo, linea,
                                         caracter_invalido(c), texto.strip()))
            i += 1

        tokens.append(Token(TipoToken.FIN, "", linea, len(texto) + 1))
        return tokens, errores

    # ------------------------------------------------------------------
    @staticmethod
    def _clasifica(lexema: str) -> TipoToken:
        """Decide la categoría de un identificador ya normalizado.

        Una dirección y una palabra reservada se distinguen por su texto. Las
        letras N, S, E y O no colisionan con ninguna palabra reservada, de
        modo que la clasificación no es ambigua.
        """
        if lexema in DIRECCIONES:
            return TipoToken.DIRECCION
        if lexema in PALABRAS_RESERVADAS:
            return TipoToken.PALABRA
        return TipoToken.PALABRA      # palabra no reconocida: lo dirá el parser


def tokenizar(texto: str, linea: int = 1,
              archivo: str = "programa") -> list[Token]:
    """Atajo para las pruebas: devuelve solo los tokens."""
    return AnalizadorLexico(archivo).analizar(texto, linea)[0]
