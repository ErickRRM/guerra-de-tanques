"""Errores que puede reportar el intérprete."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorSintaxis:
    """Un error detectado al analizar un archivo de instrucciones.

    Se reporta con el número de línea para que el autor del programa pueda
    localizarlo sin tener que adivinar.
    """

    archivo: str
    linea: int
    mensaje: str
    texto: str = ""

    def __str__(self) -> str:
        donde = f"{self.archivo}, línea {self.linea}" if self.linea else self.archivo
        return f"{donde}: {self.mensaje}"


def formato_errores(errores: list[ErrorSintaxis]) -> str:
    """Devuelve los errores con el formato acordado en el reporte."""
    if not errores:
        return ""
    lineas = ["Errores de sintaxis, la partida no inicia:"]
    lineas += [f"  {e}" for e in errores]
    return "\n".join(lineas)


# ---------------------------------------------------------------- mensajes
def desconocida(texto: str) -> str:
    return f"instrucción desconocida o mal formada: {texto!r}"


def direccion_invalida(texto: str) -> str:
    return f"dirección inválida: {texto!r} (admitidas: N, S, E, O)"


def accion_no_permitida(texto: str) -> str:
    return (f"acción no permitida en IF: {texto!r} "
            "(admitidas: AMT, MISIL, ESCUDO, RESTAURAR)")


def if_invalido() -> str:
    return ("estructura IF inválida "
            "(use: IF RADAR(dir) > 0 THEN accion  |  IF VIDA < n THEN accion)")


def fuera_del_tablero(x: int, y: int, ancho: int, alto: int) -> str:
    return (f"coordenada fuera del tablero: ({x},{y}) "
            f"— el tablero es de {ancho} x {alto}")


def caracter_invalido(c: str) -> str:
    return f"carácter no reconocido: {c!r}"


def archivo_vacio() -> str:
    return "el archivo no contiene ninguna instrucción"


def archivo_inexistente() -> str:
    return "el archivo no existe"
