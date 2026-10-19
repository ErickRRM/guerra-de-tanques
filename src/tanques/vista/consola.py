"""Vista de consola: tablero en texto, panel de estado y registro de eventos.

Sigue los criterios de la sección 6.1 del documento de arquitectura:

- Codificación redundante: cada tanque se dibuja con su número, y el color
  solo lo acompaña. Sin color la partida se sigue igual.
- Estado siempre visible: vida, munición, daño infligido y la línea en
  ejecución aparecen en el panel después de cada ronda.
- Correspondencia directa: el número del tablero es el mismo del panel y
  del registro.

Todo se dibuja en ASCII porque la consola de Windows no garantiza los
caracteres de caja ni los bloques.

    Tablero               Panel
     .   vacía            #1 cazador   [#######...]  70  ...
     1>  tanque 1, cañón al este
    [1>] tanque 1 con escudo
     *   mina armada
     o   mina sin armar
     +   refacción
"""
from __future__ import annotations

import os
import sys
import time
from typing import Callable, Optional, Sequence, TextIO

from ..modelo import (Direccion, EstadoJuego, Evento, Motivo, Resultado,
                      TipoEvento)
from ..modelo.motor import EstadoTanque
from .base import Vista

_FLECHAS = {Direccion.N: "^", Direccion.S: "v", Direccion.E: ">",
            Direccion.O: "<"}
_BARRA = 10                     # ancho de la barra de vida
_MOTIVOS = {Motivo.DESTRUCCION: "último tanque en pie",
            Motivo.DESEMPATE: "límite de rondas; decide el daño infligido",
            Motivo.EMPATE: "límite de rondas; el daño infligido coincide"}


# ------------------------------------------------------------------ color
def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _activar_ansi() -> bool:
    """Habilita las secuencias ANSI en la consola de Windows si hace falta."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        modo = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(modo)):
            return False
        return bool(k.SetConsoleMode(h, modo.value | 0x0004))
    except (AttributeError, OSError):
        return False


def color_por_omision(salida: TextIO) -> bool:
    """Color solo en una terminal real y si NO_COLOR no está definido."""
    return (hasattr(salida, "isatty") and salida.isatty()
            and "NO_COLOR" not in os.environ and _activar_ansi())


# ------------------------------------------------------------- dibujo puro
def dibujar_tablero(estado: EstadoJuego,
                    pintar: Callable[[str, str], str] = lambda t, c: t
                    ) -> str:
    """El tablero con coordenadas en base 1, fila 1 al norte."""
    celdas: dict[tuple[int, int], str] = {}
    for pos in estado.refacciones:
        celdas[pos] = "  + "
    for m in estado.minas:
        celdas[m.posicion] = "  * " if m.armada else "  o "
    for t in estado.tanques:
        if t.vivo:
            flecha = _FLECHAS[t.direccion]
            texto = (f"[{t.numero}{flecha}]" if t.escudo
                     else f" {t.numero}{flecha} ")
            celdas[t.posicion] = pintar(texto, t.color)

    lineas = ["    " + "".join(f"{x:^4}" for x in range(1, estado.ancho + 1))]
    for y in range(1, estado.alto + 1):
        fila = "".join(celdas.get((x, y), "  . ")
                       for x in range(1, estado.ancho + 1))
        lineas.append(f"{y:>3} {fila}")
    return "\n".join(lineas)


def barra_vida(vida: int, maxima: int) -> str:
    llenas = 0 if maxima <= 0 else round(_BARRA * max(vida, 0) / maxima)
    llenas = min(_BARRA, llenas)
    return "[" + "#" * llenas + "." * (_BARRA - llenas) + "]"


def dibujar_panel(estado: EstadoJuego, instrucciones: dict[str, str],
                  vida_maxima: int,
                  pintar: Callable[[str, str], str] = lambda t, c: t
                  ) -> str:
    """Una línea por tanque con todo su estado."""
    ancho = max(len(t.nombre) for t in estado.tanques)
    lineas = []
    for t in estado.tanques:
        nombre = pintar(f"#{t.numero} {t.nombre:<{ancho}}", t.color)
        escudo = "escudo" if t.escudo else "      "
        medio = (f"{barra_vida(t.vida, vida_maxima)} {t.vida:>3}  "
                 f"{escudo}  minas {t.minas} misiles {t.misiles} "
                 f"rep {t.reparaciones}")
        linea = (f"L{t.linea} {instrucciones[t.nombre]}"
                 if t.nombre in instrucciones else "")
        if not t.vivo:
            medio, linea = "destruido".ljust(len(medio)), ""
        lineas.append(f"{nombre}  {medio}  daño {t.dano_infligido:>4}  "
                      f"{linea}".rstrip())
    return "\n".join(lineas)


def dibujar_eventos(eventos: Sequence[Evento], numeros: dict[str, int],
                    colores: dict[str, str],
                    pintar: Callable[[str, str], str] = lambda t, c: t
                    ) -> str:
    """El registro de la ronda: cada turno encabezado por su instrucción."""
    lineas = []
    for e in eventos:
        if e.tipo is TipoEvento.RONDA:
            continue
        if e.tipo is TipoEvento.INSTRUCCION:
            cabeza = pintar(f"#{numeros[e.tanque]} {e.tanque}",
                            colores[e.tanque])
            lineas.append(f"  {cabeza}  L{e.datos['linea']}: "
                          f"{e.datos['instruccion']}")
        elif e.tipo is TipoEvento.FIN:
            continue
        else:
            lineas.append(f"      {e.texto}")
    return "\n".join(lineas)


# ------------------------------------------------------------------ vista
class VistaConsola(Vista):
    """Muestra la partida ronda por ronda en una salida de texto.

    resumen   solo el tablero inicial y el resultado
    paso      espera Enter después de cada ronda; 'q' sale
    pausa     segundos de espera entre rondas
    limpiar   borra la pantalla antes de cada ronda (animación)
    """

    def __init__(self, vida_maxima: int, salida: Optional[TextIO] = None,
                 entrada: Optional[TextIO] = None,
                 color: Optional[bool] = None, resumen: bool = False,
                 paso: bool = False, pausa: float = 0.0,
                 limpiar: bool = False):
        self.salida = salida or sys.stdout
        self.entrada = entrada or sys.stdin
        self.color = (color_por_omision(self.salida) if color is None
                      else color)
        self.vida_maxima = vida_maxima
        self.resumen = resumen
        self.paso = paso
        self.pausa = pausa
        self.limpiar = limpiar and self.color
        self._instrucciones: dict[str, str] = {}
        self._numeros: dict[str, int] = {}
        self._colores: dict[str, str] = {}

    # ---------------------------------------------------------- contrato
    def inicio(self, estado, eventos):
        self._numeros = {t.nombre: t.numero for t in estado.tanques}
        self._colores = {t.nombre: t.color for t in estado.tanques}
        self._escribir(self._titulo("Inicio de la partida"))
        self._escribir(dibujar_tablero(estado, self._pintar))
        self._escribir("")
        self._escribir(self._panel(estado))
        self._escribir("")

    def ronda(self, estado, eventos):
        for e in eventos:
            if e.tipo is TipoEvento.INSTRUCCION:
                self._instrucciones[e.tanque] = e.datos["instruccion"]
        if self.resumen:
            return True

        if self.limpiar:
            self._escribir("\033[2J\033[H", fin="")
        self._escribir(self._titulo(f"Ronda {estado.ronda}"))
        registro = dibujar_eventos(eventos, self._numeros, self._colores,
                                   self._pintar)
        if registro:
            self._escribir(registro)
            self._escribir("")
        self._escribir(dibujar_tablero(estado, self._pintar))
        self._escribir("")
        self._escribir(self._panel(estado))
        self._escribir("")

        if self.paso:
            self._escribir("Enter: siguiente ronda   q: salir  ", fin="")
            self.salida.flush()
            respuesta = self.entrada.readline()
            if respuesta == "" or respuesta.strip().lower() == "q":
                return False
        elif self.pausa > 0:
            self.salida.flush()
            time.sleep(self.pausa)
        return True

    def fin(self, estado, resultado):
        if self.resumen:
            self._escribir(dibujar_tablero(estado, self._pintar))
            self._escribir("")
        self._escribir(self._titulo("Fin de la partida"))
        if resultado is None:
            self._escribir(f"Partida interrumpida en la ronda "
                           f"{estado.ronda}.")
            self._escribir("")
            self._escribir(self._panel(estado))
            return
        if resultado.ganador is None:
            self._escribir("Empate.")
        else:
            numero = self._numeros[resultado.ganador]
            ganador = self._pintar(f"#{numero} {resultado.ganador}",
                                   self._colores[resultado.ganador])
            self._escribir(f"Gana {ganador}.")
        self._escribir(f"Motivo: {_MOTIVOS[resultado.motivo]}.")
        self._escribir(f"Rondas jugadas: {resultado.rondas}.")
        self._escribir("")
        self._escribir(self._clasificacion(estado, resultado))

    # ---------------------------------------------------------- partes
    def _panel(self, estado):
        return dibujar_panel(estado, self._instrucciones, self.vida_maxima,
                             self._pintar)

    def _clasificacion(self, estado, resultado) -> str:
        def orden(t: EstadoTanque):
            return (t.nombre != resultado.ganador, not t.vivo,
                    -t.dano_infligido, t.numero)

        ancho = max(len(t.nombre) for t in estado.tanques)
        lineas = [f"     {'tanque':<{ancho + 3}}  vida  daño infligido"]
        for lugar, t in enumerate(sorted(estado.tanques, key=orden), 1):
            nombre = self._pintar(f"#{t.numero} {t.nombre:<{ancho}}",
                                  t.color)
            lineas.append(f"  {lugar}. {nombre}  {t.vida:>4}  "
                          f"{t.dano_infligido:>14}")
        return "\n".join(lineas)

    def _titulo(self, texto: str) -> str:
        return f"=== {texto} " + "=" * max(0, 40 - len(texto))

    def _pintar(self, texto: str, color: str) -> str:
        if not self.color:
            return texto
        r, g, b = _rgb(color)
        return f"\033[1;38;2;{r};{g};{b}m{texto}\033[0m"

    def _escribir(self, texto: str, fin: str = "\n"):
        self.salida.write(texto + fin)
