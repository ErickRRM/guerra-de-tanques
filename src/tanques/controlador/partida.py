"""Arma una partida y la conduce hasta el final.

Es el único lugar que conoce a la vez el intérprete, el motor y la vista.
Si algún programa tiene errores la partida no se crea y se devuelven todos
juntos.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Configuracion
from ..lenguaje import ErrorSintaxis, Interprete
from ..modelo import Motor, Resultado
from ..vista import Vista


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


def ejecutar(motor: Motor, vista: Vista) -> Optional[Resultado]:
    """Juega la partida ronda por ronda y se la va entregando a la vista.

    Devuelve el resultado, o None si el usuario salió antes del final.
    """
    vista.inicio(motor.estado(), motor.eventos_iniciales())
    while not motor.terminada():
        eventos = motor.ronda()
        if not vista.ronda(motor.estado(), eventos):
            break
    vista.fin(motor.estado(), motor.resultado())
    return motor.resultado()
