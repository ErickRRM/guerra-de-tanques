"""Analizador sintáctico.

Segunda fase del intérprete. Recibe los tokens de una línea y comprueba que
formen alguna producción de la gramática, construyendo la instrucción
correspondiente.

Ninguna producción es recursiva: la única anidación posible es la acción
situada dentro de un IF, que a su vez no admite otro IF. Por eso basta un
descenso recursivo de un solo nivel, sin tabla de análisis.

    instruccion  := simple | condicional
    simple       := con-direccion "(" direccion ")"
                  | "MISIL" "(" entero "," entero ")"
                  | sin-parametros
    condicional  := "IF" condicion "THEN" accion
    condicion    := "RADAR" "(" direccion ")" relacional entero
                  | "VIDA" relacional entero
    accion       := "AMT" "(" direccion ")"
                  | "MISIL" "(" entero "," entero ")"
                  | "ESCUDO" | "REPARAR"
"""
from __future__ import annotations

from ..modelo.direccion import Direccion
from . import errores as err
from .instrucciones import (ACCIONES_EN_IF, Condicion, Fuente, Instruccion,
                            Operador, Tipo)
from .tokens import TipoToken, Token

#: Palabras que introducen una instrucción con dirección.
_CON_DIRECCION = {"MOV": Tipo.MOV, "AMT": Tipo.AMT, "RADAR": Tipo.RADAR,
                  "DAÑAR": Tipo.DANAR, "DANAR": Tipo.DANAR}

#: Palabras que forman una instrucción por sí solas.
_SIN_PARAMETROS = {"MINA": Tipo.MINA, "ESCUDO": Tipo.ESCUDO,
                   "REPARAR": Tipo.REPARAR, "ESPERAR": Tipo.ESPERAR}


class ErrorAnalisis(Exception):
    """Interrumpe el análisis de una línea con un mensaje concreto."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class AnalizadorSintactico:
    """Construye una instrucción a partir de los tokens de una línea."""

    def __init__(self, ancho: int = 8, alto: int = 8,
                 archivo: str = "programa"):
        self.ancho = ancho
        self.alto = alto
        self.archivo = archivo
        self._tokens: list[Token] = []
        self._i = 0
        self._texto = ""

    # ------------------------------------------------------------ interfaz
    def analizar(self, tokens: list[Token], texto: str,
                 linea: int) -> tuple[Instruccion | None, err.ErrorSintaxis | None]:
        """Analiza una línea. Devuelve (instrucción, error); uno de los dos."""
        self._tokens, self._i, self._texto = tokens, 0, texto
        try:
            instr = self._instruccion(linea)
            self._esperar_fin()
            return instr, None
        except ErrorAnalisis as e:
            return None, err.ErrorSintaxis(self.archivo, linea, e.mensaje, texto)

    # ------------------------------------------------- recorrido de tokens
    @property
    def _actual(self) -> Token:
        return self._tokens[self._i]

    def _avanza(self) -> Token:
        token = self._tokens[self._i]
        if token.tipo is not TipoToken.FIN:
            self._i += 1
        return token

    def _acepta(self, tipo: TipoToken, lexema: str | None = None) -> bool:
        if self._actual.es(tipo, lexema):
            self._avanza()
            return True
        return False

    def _esperar_fin(self) -> None:
        if self._actual.tipo is not TipoToken.FIN:
            raise ErrorAnalisis(err.desconocida(self._texto))

    # ------------------------------------------------------- producciones
    def _instruccion(self, linea: int) -> Instruccion:
        if self._actual.es(TipoToken.PALABRA, "IF"):
            return self._condicional(linea)
        return self._simple(linea)

    def _simple(self, linea: int, solo_acciones: bool = False) -> Instruccion:
        token = self._actual
        if token.tipo is not TipoToken.PALABRA:
            raise ErrorAnalisis(err.desconocida(self._texto))

        if token.lexema in _SIN_PARAMETROS:
            self._avanza()
            return Instruccion(tipo=_SIN_PARAMETROS[token.lexema], linea=linea)

        if token.lexema in _CON_DIRECCION:
            self._avanza()
            direccion = self._parentesis_direccion()
            return Instruccion(tipo=_CON_DIRECCION[token.lexema],
                               direccion=direccion, linea=linea)

        if token.lexema == "MISIL":
            self._avanza()
            x, y = self._parentesis_coordenada()
            return Instruccion(tipo=Tipo.MISIL, x=x, y=y, linea=linea)

        raise ErrorAnalisis(err.desconocida(self._texto))

    def _condicional(self, linea: int) -> Instruccion:
        self._avanza()                              # IF
        condicion = self._condicion()
        if not self._acepta(TipoToken.PALABRA, "THEN"):
            raise ErrorAnalisis(err.if_invalido())
        accion = self._accion(linea)
        return Instruccion(tipo=Tipo.IF, condicion=condicion, accion=accion,
                           linea=linea)

    def _condicion(self) -> Condicion:
        token = self._actual
        if token.es(TipoToken.PALABRA, "VIDA"):
            self._avanza()
            operador = self._relacional()
            return Condicion(fuente=Fuente.VIDA, operador=operador,
                             valor=self._entero())

        if token.es(TipoToken.PALABRA, "RADAR"):
            self._avanza()
            direccion = self._parentesis_direccion()
            operador = self._relacional()
            return Condicion(fuente=Fuente.RADAR, direccion=direccion,
                             operador=operador, valor=self._entero())

        raise ErrorAnalisis(err.if_invalido())

    def _accion(self, linea: int) -> Instruccion:
        inicio = self._i
        instruccion = self._simple(linea)
        if instruccion.tipo not in ACCIONES_EN_IF:
            self._i = inicio
            raise ErrorAnalisis(err.accion_no_permitida(str(instruccion)))
        return instruccion

    # ------------------------------------------------------- terminales
    def _parentesis_direccion(self) -> Direccion:
        if not self._acepta(TipoToken.PAR_IZQ):
            raise ErrorAnalisis(err.desconocida(self._texto))
        token = self._avanza()
        if token.tipo is not TipoToken.DIRECCION:
            raise ErrorAnalisis(err.direccion_invalida(token.lexema))
        if not self._acepta(TipoToken.PAR_DER):
            raise ErrorAnalisis(err.desconocida(self._texto))
        return Direccion.desde_texto(token.lexema)

    def _parentesis_coordenada(self) -> tuple[int, int]:
        if not self._acepta(TipoToken.PAR_IZQ):
            raise ErrorAnalisis(err.desconocida(self._texto))
        x = self._entero()
        if not self._acepta(TipoToken.COMA):
            raise ErrorAnalisis(err.desconocida(self._texto))
        y = self._entero()
        if not self._acepta(TipoToken.PAR_DER):
            raise ErrorAnalisis(err.desconocida(self._texto))
        if not (1 <= x <= self.ancho and 1 <= y <= self.alto):
            raise ErrorAnalisis(
                err.fuera_del_tablero(x, y, self.ancho, self.alto))
        return x, y

    def _relacional(self) -> Operador:
        token = self._actual
        if token.tipo is not TipoToken.RELACIONAL:
            raise ErrorAnalisis(err.if_invalido())
        self._avanza()
        return Operador(token.lexema)

    def _entero(self) -> int:
        token = self._actual
        if token.tipo is not TipoToken.ENTERO:
            raise ErrorAnalisis(err.desconocida(self._texto))
        self._avanza()
        return int(token.lexema)
