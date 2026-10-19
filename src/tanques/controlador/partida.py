"""Arma una partida: lee los programas, los valida y crea el motor.

Es el único lugar que conoce a la vez el intérprete y el motor. Si algún
programa tiene errores la partida no se crea y se devuelven todos juntos.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Configuracion
from ..lenguaje import ErrorSintaxis, Interprete
from ..modelo import Motor


def preparar(config: Configuracion, raiz: str | Path = ".",
             semilla: Optional[int] = None,
             ) -> tuple[Optional[Motor], list[ErrorSintaxis]]:
    """Carga los programas de `config.tanques`, relativos a `raiz`."""
    interprete = Interprete(config.tablero.ancho, config.tablero.alto)
    programas, errores = [], []
    for t in config.tanques:
        programa, encontrados = interprete.cargar(Path(raiz) / t.programa)
        programa.nombre = t.nombre
        programas.append(programa)
        errores.extend(encontrados)
    if errores:
        return None, errores
    return Motor(config, programas, semilla), []
