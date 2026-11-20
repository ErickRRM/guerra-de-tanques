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


def direcciones_mina(texto: str) -> str:
    return (f"MINA necesita una esquina: {texto!r} "
            "(use MINA(NE), MINA(NO), MINA(SE) o MINA(SO))")


def mina_con_coma(esquina: str) -> str:
    return (f"MINA ya no lleva coma: escriba la esquina junta, "
            f"MINA({esquina})")


def radar_suelto() -> str:
    return ("RADAR solo se usa como condición de un IF: "
            "IF RADAR(d) > 0 THEN accion")


def danar_no_es_instruccion() -> str:
    return ("DAÑAR no es una instrucción: el daño lo causan AMT, MISIL, "
            "MINA y los choques al moverse")


def en_minusculas(lexemas: list[str]) -> str:
    malas = ", ".join(repr(x) for x in lexemas)
    buenas = ", ".join(repr(x.upper()) for x in lexemas)
    return (f"las instrucciones y direcciones van en mayúsculas: "
            f"{malas} (escriba {buenas})")


def accion_no_permitida(texto: str) -> str:
    return f"acción no permitida en IF: {texto!r}"


def if_anidado() -> str:
    return "no se admite un IF dentro de otro IF"


def if_invalido() -> str:
    return ("estructura IF inválida "
            "(use: IF RADAR(dir) > 0 THEN accion  |  IF V < n THEN accion)")


def vida_es_v() -> str:
    return ("VIDA ya no existe: la vida se guarda en la variable V "
            "(escriba: IF V < 50 THEN accion)")


def caracter_invalido(c: str) -> str:
    return f"carácter no reconocido: {c!r}"


def archivo_vacio() -> str:
    return "el archivo no contiene ninguna instrucción"


def archivo_inexistente() -> str:
    return "el archivo no existe"
