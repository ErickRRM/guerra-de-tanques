"""Intérprete: une el análisis léxico y el sintáctico.

Es la única clase que el resto del sistema necesita conocer de esta capa.
Su contrato es sencillo: recibe un archivo de texto y devuelve un programa
validado más la lista de errores. Si la lista no está vacía, el programa no
debe ejecutarse.

El intérprete no ejecuta nada: eso corresponde al motor.
"""
from __future__ import annotations

from pathlib import Path

from . import errores as err
from .errores import ErrorSintaxis
from .instrucciones import Instruccion, Programa
from .lexico import AnalizadorLexico
from .sintactico import AnalizadorSintactico


class Interprete:
    """Convierte texto en un programa de tanque validado."""

    def __init__(self, ancho: int = 8, alto: int = 8):
        self.ancho = ancho
        self.alto = alto

    # ------------------------------------------------------------------
    def analizar(self, contenido: str, nombre: str = "programa",
                 archivo: str = "") -> tuple[Programa, list[ErrorSintaxis]]:
        """Analiza el texto completo de un programa."""
        archivo = archivo or nombre
        lexico = AnalizadorLexico(archivo)
        sintactico = AnalizadorSintactico(self.ancho, self.alto, archivo)

        instrucciones: list[Instruccion] = []
        errores: list[ErrorSintaxis] = []

        for numero, cruda in enumerate(self._lineas(contenido), start=1):
            texto = cruda.strip()
            tokens, errores_lexicos = lexico.analizar(texto, numero)
            if errores_lexicos:
                errores.extend(errores_lexicos)
                continue
            if len(tokens) == 1:          # solo el token de fin: línea vacía
                continue
            instruccion, error = sintactico.analizar(tokens, texto, numero)
            if error is not None:
                errores.append(error)
            else:
                instrucciones.append(instruccion)

        if not instrucciones and not errores:
            errores.append(ErrorSintaxis(archivo, 0, err.archivo_vacio()))

        return Programa(nombre=nombre, instrucciones=instrucciones,
                        archivo=archivo), errores

    # ------------------------------------------------------------------
    def cargar(self, ruta: str | Path) -> tuple[Programa, list[ErrorSintaxis]]:
        """Carga y valida el programa de un tanque desde un archivo."""
        ruta = Path(ruta)
        nombre = ruta.stem
        try:
            contenido = ruta.read_text(encoding="utf-8")
        except FileNotFoundError:
            vacio = Programa(nombre=nombre, instrucciones=[],
                             archivo=ruta.name)
            return vacio, [ErrorSintaxis(ruta.name, 0, err.archivo_inexistente())]
        except UnicodeDecodeError:
            # El Bloc de notas de Windows puede guardar en Latin-1.
            contenido = ruta.read_text(encoding="latin-1")
        return self.analizar(contenido, nombre=nombre, archivo=ruta.name)

    # ------------------------------------------------------------------
    @staticmethod
    def _lineas(contenido: str) -> list[str]:
        """Separa en líneas quitando la marca BOM si la hubiera."""
        return contenido.replace("﻿", "").splitlines()
