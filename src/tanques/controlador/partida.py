"""Arma una partida y la conduce hasta el final.

Es el único lugar que conoce a la vez el intérprete, el motor y la vista.

Una línea con errores no detiene la partida: se salta, y el tanque juega
con las demás. Solo es fatal un programa que no tiene ninguna instrucción
válida (o cuyo archivo no existe), porque ese tanque no tendría nada que
ejecutar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Configuracion
from ..lenguaje import ErrorSintaxis, Interprete, Programa
from ..modelo import Motor, Resultado
from ..vista import Vista


def cargar_programas(config: Configuracion, raiz: str | Path = "."
                     ) -> tuple[list[Programa], list[ErrorSintaxis],
                                list[ErrorSintaxis]]:
    """Carga los programas de `config.tanques`, relativos a `raiz`.

    Devuelve (programas, fatales, saltadas): `fatales` son los errores de
    los programas que no pueden jugar; `saltadas`, los de las líneas que se
    omiten en programas que sí juegan.
    """
    interprete = Interprete(config.tablero.ancho, config.tablero.alto)
    programas: list[Programa] = []
    fatales: list[ErrorSintaxis] = []
    saltadas: list[ErrorSintaxis] = []
    for t in config.tanques:
        programa, encontrados = interprete.cargar(Path(raiz) / t.programa)
        programa.nombre = t.nombre
        programas.append(programa)
        if not programa.instrucciones:
            fatales.extend(encontrados or [ErrorSintaxis(
                programa.archivo or t.programa, 0,
                "no tiene ninguna instrucción válida")])
            if encontrados and all(e.linea for e in encontrados):
                fatales.append(ErrorSintaxis(
                    programa.archivo or t.programa, 0,
                    "todas sus líneas tienen errores: el tanque no tendría "
                    "nada que ejecutar"))
        else:
            saltadas.extend(encontrados)
    return programas, fatales, saltadas


def preparar(config: Configuracion, raiz: str | Path = ".",
             semilla: Optional[int] = None,
             ) -> tuple[Optional[Motor], list[ErrorSintaxis]]:
    """Crea el motor. Devuelve (motor, fatales); sin motor si hay fatales.

    Las líneas con errores de los programas que sí juegan se saltan; para
    saber cuáles, `cargar_programas` o `lineas_saltadas`.
    """
    programas, fatales, _ = cargar_programas(config, raiz)
    if fatales:
        return None, fatales
    return Motor(config, programas, semilla), []


def lineas_saltadas(config: Configuracion, raiz: str | Path = "."
                    ) -> list[ErrorSintaxis]:
    """Los errores de las líneas que se omitirán al jugar."""
    return cargar_programas(config, raiz)[2]


def ejecutar(motor: Motor, vista: Vista) -> Optional[Resultado]:
    """Juega la partida ronda por ronda y se la va entregando a la vista.

    Devuelve el resultado, o None si el usuario salió antes del final.
    """
    seguir = vista.inicio(motor.estado(), motor.eventos_iniciales())
    seguir = seguir is not False
    while seguir and not motor.terminada():
        eventos = []
        while seguir:                     # los turnos de una ronda
            del_turno = motor.paso()
            eventos += del_turno
            seguir = vista.turno(motor.estado(), del_turno) is not False
            if motor.ronda_completa:
                break
        if seguir:
            seguir = vista.ronda(motor.estado(), eventos)
    vista.fin(motor.estado(), motor.resultado())
    return motor.resultado()
