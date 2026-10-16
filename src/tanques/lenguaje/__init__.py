"""Capa de lenguaje: análisis léxico y sintáctico de los programas de tanque.

El resto del sistema solo necesita `Interprete`; las fases internas quedan
disponibles para las pruebas y para la documentación.
"""
from .errores import ErrorSintaxis, formato_errores
from .instrucciones import (ACCIONES_EN_IF, Condicion, Fuente, Instruccion,
                            Operador, Programa, Tipo)
from .interprete import Interprete
from .lexico import AnalizadorLexico, tokenizar
from .sintactico import AnalizadorSintactico
from .tokens import TipoToken, Token

__all__ = ["Interprete", "AnalizadorLexico", "AnalizadorSintactico",
           "tokenizar", "Token", "TipoToken", "Instruccion", "Condicion",
           "Programa", "Tipo", "Fuente", "Operador", "ACCIONES_EN_IF",
           "ErrorSintaxis", "formato_errores"]
