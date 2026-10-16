"""Lectura y validación de los programas de los tanques.

El intérprete convierte un archivo de texto en una lista de instrucciones
validadas. No conoce el tablero ni las reglas del juego: su única tarea es
traducir y rechazar lo que no pertenezca al lenguaje.

Regla de oro: el archivo se valida COMPLETO antes de que empiece la partida y
se reportan todos los errores de una vez, con su número de línea. Nunca se
detiene en el primero.
"""
from __future__ import annotations

import re
from pathlib import Path

from .modelo import (ACCIONES_EN_IF, Condicion, Direccion, ErrorSintaxis,
                     Fuente, Instruccion, Operador, Programa, Tipo)

# --------------------------------------------------------------------------
# Expresiones regulares del lenguaje
#
# Se toleran mayúsculas o minúsculas y espacios de sobra porque los archivos
# los escribe una persona: 'mov( n )' debe funcionar igual que 'MOV(N)'.
# --------------------------------------------------------------------------
_DIR = r"[NSEOnseo]"
_OPS = r">=|<=|==|>|<"

RE_CON_DIR = re.compile(
    rf"^(MOV|AMT|RADAR|DAÑAR|DANAR)\s*\(\s*({_DIR})\s*\)$", re.IGNORECASE)
RE_MISIL = re.compile(
    r"^MISIL\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)$", re.IGNORECASE)
RE_SIN_PARAM = re.compile(
    r"^(MINA|ESCUDO|RESTAURAR|ESPERAR)$", re.IGNORECASE)
RE_IF = re.compile(r"^IF\s+(.+?)\s+THEN\s+(.+)$", re.IGNORECASE)
RE_COND_RADAR = re.compile(
    rf"^RADAR\s*\(\s*({_DIR})\s*\)\s*({_OPS})\s*(-?\d+)$", re.IGNORECASE)
RE_COND_VIDA = re.compile(
    rf"^VIDA\s*({_OPS})\s*(-?\d+)$", re.IGNORECASE)

#: Palabras que el lenguaje reconoce, para dar un mensaje de error más útil.
PALABRAS = {"MOV", "AMT", "RADAR", "DAÑAR", "DANAR", "MISIL", "MINA",
            "ESCUDO", "RESTAURAR", "ESPERAR", "IF", "THEN", "VIDA"}

AYUDA_IF = ("estructura IF inválida "
            "(use: IF RADAR(dir) > 0 THEN accion  |  IF VIDA < n THEN accion)")
AYUDA_ACCION = ("acción no permitida en IF: {!r} "
                "(admitidas: AMT, MISIL, ESCUDO, RESTAURAR)")
AYUDA_DIR = "dirección inválida: {!r} (admitidas: N, S, E, O)"


def _direccion(texto: str) -> Direccion:
    return Direccion[texto.strip().upper()]


def _operador(texto: str) -> Operador:
    return Operador(texto.strip())


def _normaliza(linea: str) -> str:
    """Quita el comentario, los espacios sobrantes y el BOM."""
    linea = linea.replace("﻿", "")
    if "#" in linea:
        linea = linea.split("#", 1)[0]
    return linea.strip()


def _tipo_con_dir(palabra: str) -> Tipo:
    """DAÑAR y DANAR designan la misma instrucción."""
    p = palabra.upper()
    return Tipo.DANAR if p in ("DAÑAR", "DANAR") else Tipo[p]


def _analiza_accion(texto: str, linea: int, archivo: str,
                    ancho: int, alto: int) -> tuple[Instruccion | None, str | None]:
    """Analiza la parte derecha de un IF. Devuelve (instrucción, error)."""
    instr, err = _analiza_simple(texto, linea, ancho, alto)
    if instr is None:
        return None, err
    if instr.tipo not in ACCIONES_EN_IF:
        return None, AYUDA_ACCION.format(texto.strip())
    return instr, None


def _analiza_simple(texto: str, linea: int, ancho: int,
                    alto: int) -> tuple[Instruccion | None, str | None]:
    """Analiza una instrucción que no es un IF. Devuelve (instrucción, error)."""
    t = texto.strip()

    m = RE_CON_DIR.match(t)
    if m:
        return Instruccion(tipo=_tipo_con_dir(m.group(1)),
                           direccion=_direccion(m.group(2)), linea=linea), None

    m = RE_MISIL.match(t)
    if m:
        x, y = int(m.group(1)), int(m.group(2))
        if not (1 <= x <= ancho and 1 <= y <= alto):
            return None, (f"coordenada fuera del tablero: ({x},{y}) "
                          f"— el tablero es de {ancho} x {alto}")
        return Instruccion(tipo=Tipo.MISIL, x=x, y=y, linea=linea), None

    m = RE_SIN_PARAM.match(t)
    if m:
        return Instruccion(tipo=Tipo[m.group(1).upper()], linea=linea), None

    # Mensaje más preciso cuando la palabra existe pero la dirección no.
    m = re.match(rf"^(MOV|AMT|RADAR|DAÑAR|DANAR)\s*\(\s*([^)]*)\s*\)$",
                 t, re.IGNORECASE)
    if m:
        return None, AYUDA_DIR.format(m.group(2).strip())

    return None, f"instrucción desconocida o mal formada: {t!r}"


def _analiza_condicion(texto: str) -> tuple[Condicion | None, str | None]:
    """Analiza la condición de un IF. Devuelve (condición, error)."""
    t = texto.strip()

    m = RE_COND_RADAR.match(t)
    if m:
        return Condicion(fuente=Fuente.RADAR,
                         direccion=_direccion(m.group(1)),
                         operador=_operador(m.group(2)),
                         valor=int(m.group(3))), None

    m = RE_COND_VIDA.match(t)
    if m:
        return Condicion(fuente=Fuente.VIDA,
                         operador=_operador(m.group(1)),
                         valor=int(m.group(2))), None

    # La palabra es RADAR pero la dirección no sirve.
    m = re.match(rf"^RADAR\s*\(\s*([^)]*)\s*\)\s*({_OPS})\s*(-?\d+)$",
                 t, re.IGNORECASE)
    if m:
        return None, AYUDA_DIR.format(m.group(1).strip())

    return None, AYUDA_IF


def _analiza_linea(texto: str, linea: int, archivo: str, ancho: int,
                   alto: int) -> tuple[Instruccion | None, ErrorSintaxis | None]:
    """Analiza una línea ya normalizada (sin comentarios ni espacios)."""
    m = RE_IF.match(texto)
    if m:
        cond, err = _analiza_condicion(m.group(1))
        if cond is None:
            return None, ErrorSintaxis(archivo, linea, err, texto)
        accion, err = _analiza_accion(m.group(2), linea, archivo, ancho, alto)
        if accion is None:
            return None, ErrorSintaxis(archivo, linea, err, texto)
        return Instruccion(tipo=Tipo.IF, condicion=cond, accion=accion,
                           linea=linea), None

    # Un IF mal escrito no debe caer en "instrucción desconocida".
    if re.match(r"^IF\b", texto, re.IGNORECASE):
        return None, ErrorSintaxis(archivo, linea, AYUDA_IF, texto)

    instr, err = _analiza_simple(texto, linea, ancho, alto)
    if instr is None:
        return None, ErrorSintaxis(archivo, linea, err, texto)
    return instr, None


def analizar(contenido: str, nombre: str = "programa", archivo: str = "",
             ancho: int = 8, alto: int = 8) -> tuple[Programa, list[ErrorSintaxis]]:
    """Analiza el texto completo de un programa.

    Devuelve el programa y la lista de errores. Si la lista no está vacía, el
    programa no debe ejecutarse.
    """
    archivo = archivo or nombre
    instrucciones: list[Instruccion] = []
    errores: list[ErrorSintaxis] = []

    for n, cruda in enumerate(contenido.splitlines(), start=1):
        texto = _normaliza(cruda)
        if not texto:
            continue
        instr, err = _analiza_linea(texto, n, archivo, ancho, alto)
        if err is not None:
            errores.append(err)
        else:
            instrucciones.append(instr)

    if not instrucciones and not errores:
        errores.append(ErrorSintaxis(
            archivo, 0, "el archivo no contiene ninguna instrucción"))

    return Programa(nombre=nombre, instrucciones=instrucciones,
                    archivo=archivo), errores


def cargar(ruta: str | Path, ancho: int = 8,
           alto: int = 8) -> tuple[Programa, list[ErrorSintaxis]]:
    """Carga y valida el programa de un tanque desde un archivo de texto."""
    ruta = Path(ruta)
    nombre = ruta.stem
    try:
        contenido = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        vacio = Programa(nombre=nombre, instrucciones=[], archivo=ruta.name)
        return vacio, [ErrorSintaxis(ruta.name, 0, "el archivo no existe")]
    except UnicodeDecodeError:
        # Un archivo guardado desde el Bloc de notas de Windows puede venir
        # en Latin-1; se reintenta antes de darlo por inválido.
        contenido = ruta.read_text(encoding="latin-1")

    return analizar(contenido, nombre=nombre, archivo=ruta.name,
                    ancho=ancho, alto=alto)


def formato_errores(errores: list[ErrorSintaxis]) -> str:
    """Devuelve los errores con el formato acordado en la sección 4.4."""
    if not errores:
        return ""
    lineas = ["Errores de sintaxis, la partida no inicia:"]
    lineas += [f"  {e}" for e in errores]
    return "\n".join(lineas)
