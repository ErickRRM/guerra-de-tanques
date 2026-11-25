"""Interfaz gráfica con Tkinter: portada, configuración y ventana de partida.

Sigue los bosquejos de las figuras 10, 11 y 12 del documento de
arquitectura. Todo ocurre en una sola ventana que cambia de pantalla.

La ventana de partida implementa el mismo contrato `Vista` que la consola,
así que el controlador la conduce con el mismo `ejecutar()`. Para eso cada
método espera la orden del usuario con `wait_variable`, que sigue
atendiendo los eventos de Tk mientras espera: los botones, la velocidad y
el cierre de la ventana responden en todo momento.

Ninguna clase de aquí contiene reglas del juego: dibujan `EstadoJuego` y
los eventos, y devuelven lo que el usuario eligió.

Aspecto: tema oscuro de videojuego. Los botones, los paneles y el control
de velocidad son componentes propios dibujados en un Canvas (`Boton`,
`Panel`, `Segmentos`), porque los de Tk no permiten esquinas redondeadas,
cortes en diagonal ni brillos. Toda la paleta está en las constantes de
abajo.
"""
from __future__ import annotations

import ctypes
import math
import random
import re
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import font as tkfont
from typing import Callable, Optional

from ..config import (MAX_TANQUES, RANGOS, TABLERO_MINIMO, Configuracion,
                      Dano, Municion, Tablero, TanqueConfig, lado_minimo)
from ..lenguaje import (CATALOGO, NOTAS, Interprete, formato_errores,
                        generar_programa)
from ..modelo import Direccion, Motivo, TipoEvento
from . import sprites
from .animaciones import AZUL, ROJO, VERDE, Animador
from .sonido import Sonido
from .base import Vista

TABLERO_PX = 520                 # lado máximo del tablero en pantalla
MARGEN_PANTALLA = 90             # barra de tareas y marco de la ventana

# ------------------------------------------------------------------ paleta
FONDO_VENTANA = "#0A1018"        # fondo de las pantallas
NOCHE = "#060A10"                # lo más oscuro: portada, carteles
NOCHE_CLARA = "#13233A"
PANEL = "#111B28"                # paneles
PANEL_ALTO = "#192638"           # campos, chips, segmentos apagados
PANEL_HOVER = "#22344A"
BORDE = "#26384E"
BORDE_SUAVE = BORDE
TINTA = "#E8EEF5"                # texto principal
GRIS = "#8A9BB0"                 # texto secundario
GRIS_CLARO = "#4E6077"           # texto apagado
ACENTO = "#F5B342"               # oro: la acción principal
ACENTO_CLARO = "#FFD27A"
ACENTO_OSCURO = "#B9822A"
TINTA_ACENTO = "#1E1404"         # texto sobre el oro
CIAN = "#4CC9F0"                 # escudo e información
VERDE_OK = "#4ADE80"
ROJO_UI = "#F87171"
FONDO_BARRA = "#0D1622"
GRIS_NOCHE = GRIS
TEXTO_NOCHE = TINTA
_MOTIVOS = {Motivo.DESTRUCCION: "último tanque en pie",
            Motivo.DESEMPATE: "límite de rondas; decide el daño infligido",
            Motivo.EMPATE: "límite de rondas; el daño infligido coincide",
            Motivo.TERMINADA: "terminada antes de tiempo; decide el daño "
                              "infligido"}


def activar_dpi():
    """En Windows con escalado (125 %, 150 %) el texto se ve nítido.

    Sin esto Windows dibuja la ventana a 96 ppp y la estira, y todo queda
    borroso. Tk ajusta solo el tamaño de las fuentes; las medidas en
    píxeles se escalan con `AppGrafica.px`.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def retardo_ms(velocidad: int) -> int:
    """Velocidad 1 (lenta) a 10 (rápida) → milisegundos entre rondas."""
    velocidad = min(10, max(1, int(velocidad)))
    return round(1200 * 0.68 ** (velocidad - 1))


#: Por debajo de este retardo (velocidades 9 y 10) no se anima: avance rápido.
RETARDO_MIN_ANIMAR = 60


def factor_animacion(retardo: int) -> float:
    """Cuánto se estiran o encogen las animaciones según la velocidad."""
    return min(2.2, max(0.45, retardo / 256))


# ------------------------------------------------------------ dibujo común
def claro(color: str, t: float = 0.35) -> str:
    """El color aclarado: para texto de color sobre el fondo oscuro."""
    return sprites.mezclar(color, "#FFFFFF", t)


def espaciado(texto: str) -> str:
    """Letras separadas por un espacio fino, para rótulos en mayúsculas."""
    return " ".join(texto)


def rect_redondeado(canvas, x0, y0, x1, y1, r, **opciones):
    """Rectángulo de esquinas redondeadas (un polígono suavizado)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    puntos = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
              x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
              x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(puntos, smooth=True, **opciones)


def chaflan(canvas, x0, y0, x1, y1, c, **opciones):
    """Rectángulo con dos esquinas cortadas en diagonal, estilo HUD."""
    c = max(0, min(c, (x1 - x0) / 3, (y1 - y0) / 3))
    puntos = [x0 + c, y0, x1, y0, x1, y1 - c, x1 - c, y1, x0, y1, x0, y0 + c]
    return canvas.create_polygon(puntos, **opciones)


def pildora(canvas, x0, y0, x1, y1, color, tags=()):
    """Barra de extremos redondeados; no dibuja nada si no tiene largo."""
    if x1 - x0 < 1:
        return
    alto = y1 - y0
    r = alto / 2
    if x1 - x0 < alto:
        canvas.create_oval(x0, y0, x0 + alto, y1, fill=color, width=0,
                           tags=tags)
        return
    canvas.create_oval(x0, y0, x0 + alto, y1, fill=color, width=0, tags=tags)
    canvas.create_oval(x1 - alto, y0, x1, y1, fill=color, width=0, tags=tags)
    canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, width=0,
                            tags=tags)


def degradado(canvas, ancho, alto, arriba, abajo, tags="fondo", pasos=48,
              horizontal=False):
    """Degradado hecho con franjas, vertical u horizontal."""
    for k in range(pasos):
        color = sprites.mezclar(arriba, abajo, k / max(1, pasos - 1))
        if horizontal:
            x0, x1 = ancho * k / pasos, ancho * (k + 1) / pasos + 1
            canvas.create_rectangle(x0, 0, x1, alto, width=0, fill=color,
                                    tags=tags)
        else:
            y0, y1 = alto * k / pasos, alto * (k + 1) / pasos + 1
            canvas.create_rectangle(0, y0, ancho, y1, width=0, fill=color,
                                    tags=tags)


def estrella(canvas, cx, cy, r, **opciones):
    puntos = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        puntos += [cx + rr * math.cos(a), cy + rr * math.sin(a)]
    return canvas.create_polygon(puntos, **opciones)


def icono(canvas, nombre, cx, cy, s, color, tags=()):
    """Íconos vectoriales: nítidos a cualquier escala y del color pedido."""
    k = s / 2
    o = dict(fill=color, width=0, tags=tags)
    linea = dict(fill=color, width=max(1.5, s / 9), tags=tags,
                 capstyle="round")
    if nombre == "play":
        canvas.create_polygon(cx - k * 0.6, cy - k * 0.8, cx + k * 0.85, cy,
                              cx - k * 0.6, cy + k * 0.8, **o)
    elif nombre == "pausa":
        for dx in (-0.45, 0.2):
            canvas.create_rectangle(cx + k * dx, cy - k * 0.75,
                                    cx + k * (dx + 0.28), cy + k * 0.75, **o)
    elif nombre == "paso":
        canvas.create_polygon(cx - k * 0.75, cy - k * 0.75, cx + k * 0.35, cy,
                              cx - k * 0.75, cy + k * 0.75, **o)
        canvas.create_rectangle(cx + k * 0.45, cy - k * 0.75, cx + k * 0.75,
                                cy + k * 0.75, **o)
    elif nombre == "reiniciar":
        canvas.create_arc(cx - k * 0.8, cy - k * 0.8, cx + k * 0.8,
                          cy + k * 0.8, start=60, extent=280, style="arc",
                          outline=color, width=max(1.5, s / 9), tags=tags)
        canvas.create_polygon(cx + k * 0.15, cy - k * 1.05, cx + k * 0.75,
                              cy - k * 0.72, cx + k * 0.2, cy - k * 0.3, **o)
    elif nombre == "engrane":
        for a in range(0, 360, 45):
            r = math.radians(a)
            canvas.create_line(cx + k * 0.45 * math.cos(r),
                               cy + k * 0.45 * math.sin(r),
                               cx + k * 0.95 * math.cos(r),
                               cy + k * 0.95 * math.sin(r),
                               fill=color, width=max(2, s / 5), tags=tags)
        canvas.create_oval(cx - k * 0.62, cy - k * 0.62, cx + k * 0.62,
                           cy + k * 0.62, outline=color,
                           width=max(1.5, s / 8), tags=tags)
    elif nombre == "x":
        canvas.create_line(cx - k * 0.6, cy - k * 0.6, cx + k * 0.6,
                           cy + k * 0.6, **linea)
        canvas.create_line(cx - k * 0.6, cy + k * 0.6, cx + k * 0.6,
                           cy - k * 0.6, **linea)
    elif nombre == "carpeta":
        canvas.create_polygon(cx - k * 0.85, cy - k * 0.55, cx - k * 0.25,
                              cy - k * 0.55, cx - k * 0.05, cy - k * 0.3,
                              cx + k * 0.85, cy - k * 0.3, cx + k * 0.85,
                              cy + k * 0.65, cx - k * 0.85, cy + k * 0.65,
                              **o)
    elif nombre == "paleta":
        canvas.create_oval(cx - k * 0.8, cy - k * 0.8, cx + k * 0.8,
                           cy + k * 0.8, outline=color,
                           width=max(1.5, s / 9), tags=tags)
        for dx, dy in ((-0.3, -0.3), (0.3, -0.3), (0, 0.35)):
            canvas.create_oval(cx + k * dx - k * 0.17, cy + k * dy - k * 0.17,
                               cx + k * dx + k * 0.17, cy + k * dy + k * 0.17,
                               **o)
    elif nombre == "lapiz":
        canvas.create_polygon(cx + k * 0.55, cy - k * 0.85, cx + k * 0.85,
                              cy - k * 0.55, cx - k * 0.45, cy + k * 0.75,
                              cx - k * 0.75, cy + k * 0.45, **o)
        canvas.create_polygon(cx - k * 0.75, cy + k * 0.45, cx - k * 0.45,
                              cy + k * 0.75, cx - k * 0.9, cy + k * 0.9, **o)
    elif nombre == "dado":
        rect_redondeado(canvas, cx - k * 0.8, cy - k * 0.8, cx + k * 0.8,
                        cy + k * 0.8, k * 0.3, outline=color, fill="",
                        width=max(1.5, s / 10), tags=tags)
        for d in (-0.4, 0, 0.4):
            canvas.create_oval(cx + k * d - k * 0.13, cy + k * d - k * 0.13,
                               cx + k * d + k * 0.13, cy + k * d + k * 0.13,
                               **o)
    elif nombre == "atras":
        canvas.create_line(cx + k * 0.7, cy, cx - k * 0.7, cy, arrow="last",
                           arrowshape=(k * 0.7, k * 0.7, k * 0.45), **linea)
    elif nombre == "salir":
        canvas.create_line(cx - k * 0.7, cy, cx + k * 0.75, cy, arrow="last",
                           arrowshape=(k * 0.6, k * 0.6, k * 0.4), **linea)
        canvas.create_line(cx - k * 0.2, cy - k * 0.85, cx - k * 0.85,
                           cy - k * 0.85, cx - k * 0.85, cy + k * 0.85,
                           cx - k * 0.2, cy + k * 0.85, **linea)
    elif nombre == "ayuda":
        canvas.create_oval(cx - k * 0.85, cy - k * 0.85, cx + k * 0.85,
                           cy + k * 0.85, outline=color,
                           width=max(1.5, s / 9), tags=tags)
        canvas.create_text(cx, cy, text="?", fill=color, tags=tags,
                           font=("Segoe UI", max(6, int(s * 0.42)), "bold"))
    elif nombre == "estrella":
        estrella(canvas, cx, cy, k, **o)
    elif nombre == "misil":
        canvas.create_polygon(cx - k * 0.32, cy + k * 0.8, cx - k * 0.32,
                              cy - k * 0.3, cx, cy - k * 0.9, cx + k * 0.32,
                              cy - k * 0.3, cx + k * 0.32, cy + k * 0.8, **o)
    elif nombre == "mina":
        r = k * 0.5
        for a in range(0, 360, 90):
            ra = math.radians(a + 45)
            canvas.create_line(cx, cy, cx + k * 0.9 * math.cos(ra),
                               cy + k * 0.9 * math.sin(ra), fill=color,
                               width=max(1, s / 8), tags=tags)
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, **o)
    elif nombre == "ojo":
        canvas.create_oval(cx - k * 0.95, cy - k * 0.55, cx + k * 0.95,
                           cy + k * 0.55, outline=color,
                           width=max(1.5, s / 9), tags=tags)
        canvas.create_oval(cx - k * 0.3, cy - k * 0.3, cx + k * 0.3,
                           cy + k * 0.3, fill=color, width=0, tags=tags)
    elif nombre == "bala":
        for dx in (-0.55, 0, 0.55):
            x = cx + k * dx
            canvas.create_polygon(x - k * 0.17, cy + k * 0.8, x - k * 0.17,
                                  cy - k * 0.25, x, cy - k * 0.75,
                                  x + k * 0.17, cy - k * 0.25, x + k * 0.17,
                                  cy + k * 0.8, **o)
    elif nombre == "escudo":
        puntos = []
        for a in range(6):
            r = math.radians(60 * a + 30)
            puntos += [cx + k * 0.9 * math.cos(r), cy + k * 0.9 * math.sin(r)]
        canvas.create_polygon(puntos, fill="", outline=color,
                              width=max(1.5, s / 8), tags=tags)
        canvas.create_oval(cx - k * 0.25, cy - k * 0.25, cx + k * 0.25,
                           cy + k * 0.25, **o)
    elif nombre == "reloj":
        canvas.create_oval(cx - k * 0.85, cy - k * 0.85, cx + k * 0.85,
                           cy + k * 0.85, outline=color,
                           width=max(1.5, s / 9), tags=tags)
        canvas.create_line(cx, cy - k * 0.55, cx, cy, cx + k * 0.4,
                           cy + k * 0.2, **linea)
    elif nombre == "tablero":
        for d in (-0.85, -0.28, 0.28, 0.85):
            canvas.create_line(cx + k * d, cy - k * 0.85, cx + k * d,
                               cy + k * 0.85, fill=color,
                               width=max(1, s / 12), tags=tags)
            canvas.create_line(cx - k * 0.85, cy + k * d, cx + k * 0.85,
                               cy + k * d, fill=color,
                               width=max(1, s / 12), tags=tags)
    elif nombre == "enlace":
        for dx in (-0.35, 0.35):
            rect_redondeado(canvas, cx + k * dx - k * 0.45, cy - k * 0.3,
                            cx + k * dx + k * 0.45, cy + k * 0.3, k * 0.28,
                            outline=color, fill="", width=max(1.5, s / 9),
                            tags=tags)
    elif nombre == "nota":
        r = k * 0.32
        canvas.create_oval(cx - k * 0.7 - r, cy + k * 0.5 - r * 0.8,
                           cx - k * 0.7 + r, cy + k * 0.5 + r * 0.8, **o)
        canvas.create_oval(cx + k * 0.35 - r, cy + k * 0.3 - r * 0.8,
                           cx + k * 0.35 + r, cy + k * 0.3 + r * 0.8, **o)
        canvas.create_line(cx - k * 0.4, cy + k * 0.5, cx - k * 0.4,
                           cy - k * 0.8, cx + k * 0.65, cy - k * 1.0,
                           cx + k * 0.65, cy + k * 0.3, **linea)
    elif nombre in ("menos", "mas"):
        canvas.create_line(cx - k * 0.6, cy, cx + k * 0.6, cy, **linea)
        if nombre == "mas":
            canvas.create_line(cx, cy - k * 0.6, cx, cy + k * 0.6, **linea)
    elif nombre == "menu":
        for dy in (-0.55, 0, 0.55):
            canvas.create_line(cx - k * 0.7, cy + k * dy, cx + k * 0.7,
                               cy + k * dy, **linea)
    elif nombre == "bandera":
        canvas.create_line(cx - k * 0.6, cy + k * 0.9, cx - k * 0.6,
                           cy - k * 0.85, **linea)
        canvas.create_polygon(cx - k * 0.55, cy - k * 0.85, cx + k * 0.8,
                              cy - k * 0.45, cx - k * 0.55, cy - k * 0.05,
                              **o)
    elif nombre == "casa":
        canvas.create_polygon(cx, cy - k * 0.9, cx + k * 0.9, cy - k * 0.05,
                              cx + k * 0.6, cy - k * 0.05, cx + k * 0.6,
                              cy + k * 0.8, cx - k * 0.6, cy + k * 0.8,
                              cx - k * 0.6, cy - k * 0.05, cx - k * 0.9,
                              cy - k * 0.05, **o)
    elif nombre in ("sonido", "mudo"):
        canvas.create_polygon(cx - k * 0.85, cy - k * 0.3, cx - k * 0.45,
                              cy - k * 0.3, cx + k * 0.05, cy - k * 0.75,
                              cx + k * 0.05, cy + k * 0.75, cx - k * 0.45,
                              cy + k * 0.3, cx - k * 0.85, cy + k * 0.3, **o)
        if nombre == "sonido":
            for r in (0.45, 0.8):
                canvas.create_arc(cx - k * r + k * 0.1, cy - k * r,
                                  cx + k * r + k * 0.1, cy + k * r,
                                  start=-45, extent=90, style="arc",
                                  outline=color, width=max(1.5, s / 10),
                                  tags=tags)
        else:
            for a, b in ((0.35, 0.95), (0.95, 0.35)):
                canvas.create_line(cx + k * 0.35, cy - k * (a - 0.65),
                                   cx + k * 0.95, cy - k * (b - 0.65),
                                   **linea)
    elif nombre == "cruz":
        canvas.create_rectangle(cx - k * 0.25, cy - k * 0.8, cx + k * 0.25,
                                cy + k * 0.8, **o)
        canvas.create_rectangle(cx - k * 0.8, cy - k * 0.25, cx + k * 0.8,
                                cy + k * 0.25, **o)


def _fondo_de(widget) -> str:
    try:
        return widget.cget("bg")
    except (tk.TclError, AttributeError):
        return FONDO_VENTANA


# ======================================================================
class Boton(tk.Canvas):
    """Botón dibujado: forma redondeada, ícono, brillo al pasar el ratón.

    Se comporta como un `tk.Button` en lo que usa el resto del código:
    `boton["state"]`, `configure(state=...)` e `invoke()`.
    """

    #: estilo → (relleno, relleno al pasar, borde, texto,
    #:           relleno apagado, texto apagado)
    ESTILOS = {
        "primario": (ACENTO, ACENTO_CLARO, ACENTO, TINTA_ACENTO,
                     "#3A3122", "#7D6E4E"),
        "secundario": (PANEL_ALTO, PANEL_HOVER, BORDE, TINTA,
                       "#141E2B", GRIS_CLARO),
        "fantasma": (None, "#16263A", "#36506F", TINTA,
                     None, GRIS_CLARO),
        "peligro": ("#C2353B", "#DC4A4F", "#E05A5F", "#FFFFFF",
                    "#3A1E22", "#7D4E52"),
    }

    def __init__(self, padre, app: "AppGrafica", texto: str,
                 orden: Callable, estilo: str = "secundario",
                 icono_: Optional[str] = None, minimo: int = 0,
                 alto: int = 36, ayuda: str = "",
                 sonido: Optional[str] = "auto"):
        self._listo = False
        # El sonido del clic sigue a la jerarquía visual: el botón dorado
        # confirma, regresar o salir baja de tono y el resto hace clic.
        if sonido == "auto":
            sonido = ("confirmar" if estilo == "primario"
                      else "atras" if icono_ in ("atras", "salir")
                      else "clic")
        self.sonido = sonido
        self.app, self.texto, self.orden = app, texto, orden
        self.ayuda, self._globo, self._espera = ayuda, None, None
        self.estilo, self.icono = estilo, icono_
        px = app.px
        ancho = app.fuente_boton.measure(texto) + px(32)
        if icono_:
            ancho += px(22) if texto else px(4)
        super().__init__(padre, width=max(ancho, px(minimo)),
                         height=px(alto), bg=_fondo_de(padre),
                         highlightthickness=0, bd=0, takefocus=0,
                         cursor="hand2")
        self._encima = self._presionado = False
        self.bind("<Enter>", lambda _e: self._sobre(True))
        self.bind("<Leave>", lambda _e: self._sobre(False))
        self.bind("<ButtonPress-1>", self._presionar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self._listo = True
        self._dibujar()

    # --------------------------------------------------------- comportamiento
    def configure(self, cnf=None, **kw):
        resultado = super().configure(cnf, **kw)
        claves = set(kw) | (set(cnf) if isinstance(cnf, dict) else set())
        if self._listo and claves & {"state", "bg", "background"}:
            self._dibujar()
        return resultado

    config = configure

    def activo(self) -> bool:
        return str(self["state"]) != "disabled"

    def invoke(self):
        self._ocultar_globo()
        if self.activo():
            if self.sonido:
                self.app.sonido.tocar(self.sonido)
            self.orden()

    def _sobre(self, encima):
        self._encima = encima
        if encima and self.activo():
            self.app.sonido.tocar("hover")
        if not encima:
            self._presionado = False
        self._dibujar()
        if self.ayuda:
            if encima:
                self._espera = self.after(450, self._mostrar_globo)
            else:
                if self._espera:
                    self.after_cancel(self._espera)
                    self._espera = None
                self._ocultar_globo()

    def _mostrar_globo(self):
        """Etiqueta flotante con lo que hace un botón de solo ícono."""
        self._espera = None
        self._ocultar_globo()
        globo = tk.Toplevel(self)
        globo.overrideredirect(True)
        globo.attributes("-topmost", True)
        tk.Label(globo, text=self.ayuda, font=self.app.f_chico, fg=TINTA,
                 bg=PANEL_HOVER, padx=self.app.px(8), pady=self.app.px(3),
                 highlightthickness=1, highlightbackground=BORDE).pack()
        globo.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width()
                                  - globo.winfo_reqwidth()) // 2
        y = self.winfo_rooty() - globo.winfo_reqheight() - self.app.px(6)
        globo.geometry(f"+{x}+{y}")
        self._globo = globo

    def _ocultar_globo(self):
        if self._globo is not None:
            self._globo.destroy()
            self._globo = None

    def _presionar(self, _e):
        if self.activo():
            self._presionado = True
            self._dibujar()
        else:
            self.app.sonido.tocar("apagado")

    def _soltar(self, e):
        dentro = 0 <= e.x <= self.winfo_width() and \
            0 <= e.y <= self.winfo_height()
        presionado, self._presionado = self._presionado, False
        self._dibujar()
        if presionado and dentro:
            self.invoke()

    # --------------------------------------------------------- dibujo
    def _dibujar(self):
        if not self._listo:
            return
        px = self.app.px
        w = max(self.winfo_width(), int(self["width"]))
        h = max(self.winfo_height(), int(self["height"]))
        if self.winfo_width() > 1:
            w, h = self.winfo_width(), self.winfo_height()
        fondo = _fondo_de(self)
        relleno, encima, borde, texto, apagado, texto_apagado = \
            self.ESTILOS[self.estilo]
        activo = self.activo()
        super().configure(cursor="hand2" if activo else "")
        self.delete("all")
        if not activo:
            color, contorno, tinta = apagado, borde if apagado is None \
                else apagado, texto_apagado
            if self.estilo == "secundario":
                contorno = "#1C2939"
        elif self._encima:
            color, contorno, tinta = encima, borde, texto
            if self.estilo == "primario":
                color = ACENTO_OSCURO if self._presionado else ACENTO_CLARO
            elif self.estilo == "fantasma":
                contorno = ACENTO
            elif self.estilo == "peligro":
                contorno = "#FCA5A5"
            else:
                contorno = sprites.mezclar(CIAN, BORDE, 0.45)
        else:
            color, contorno, tinta = relleno, borde, texto
        m = px(2)
        if activo and self._encima and self.estilo == "primario":
            rect_redondeado(self, 0, 0, w, h, px(10),
                            fill=sprites.mezclar(ACENTO, fondo, 0.65))
        rect_redondeado(self, m, m, w - m, h - m, px(8),
                        fill=color or fondo, outline=contorno, width=1.5)
        if activo and self.estilo == "primario":       # brillo superior
            self.create_line(m + px(10), m + px(2), w - m - px(10),
                             m + px(2), fill=sprites.mezclar(color, "#FFFFFF",
                                                             0.35))
        desplazar = px(1) if self._presionado else 0
        tam = px(14)
        ancho_texto = self.app.fuente_boton.measure(self.texto)
        total = ancho_texto + ((tam + px(8)) if self.icono and self.texto
                               else tam if self.icono else 0)
        x = (w - total) / 2
        cy = h / 2 + desplazar
        if self.icono:
            icono(self, self.icono, x + tam / 2, cy, tam, tinta)
            x += tam + px(8)
        if self.texto:
            self.create_text(x, cy, text=self.texto, anchor="w", fill=tinta,
                             font=self.app.f_boton)


class Panel(tk.Canvas):
    """Panel con esquinas cortadas, borde fino y una línea de acento.

    El contenido va en `panel.cuerpo` (un Frame). `modo` dice de dónde sale
    el tamaño: "ajustar" (del contenido), "x" (ancho del contenedor, alto
    del contenido) o "ambos" (del contenedor).
    """

    def __init__(self, padre, app: "AppGrafica", modo: str = "ajustar",
                 relleno: int = 14, color: str = PANEL,
                 acento: Optional[str] = None, corte: int = 12):
        super().__init__(padre, bg=_fondo_de(padre), highlightthickness=0,
                         bd=0, width=1, height=1)
        self.app, self.modo, self.color, self.acento = app, modo, color, acento
        self.p = app.px(relleno)
        self.corte = app.px(corte)
        self._resalte: Optional[str] = None
        # El contenido va con `place` y no como ventana del Canvas: una
        # ventana fuera del área visible no se muestra ni avisa su tamaño,
        # y el panel nace de 1 x 1.
        self.cuerpo = tk.Frame(self, bg=color)
        lugar = dict(x=self.p, y=self.p)
        if modo in ("x", "ambos"):
            lugar.update(relwidth=1, width=-2 * self.p)
        if modo == "ambos":
            lugar.update(relheight=1, height=-2 * self.p)
        self.cuerpo.place(**lugar)
        self.cuerpo.bind("<Configure>", self._por_cuerpo)
        self.bind("<Configure>", self._por_lienzo)

    def _por_cuerpo(self, _e=None):
        ancho = self.cuerpo.winfo_reqwidth() + 2 * self.p
        alto = self.cuerpo.winfo_reqheight() + 2 * self.p
        if self.modo == "ajustar":
            if (int(self["width"]), int(self["height"])) != (ancho, alto):
                super().configure(width=ancho, height=alto)
        elif self.modo == "x" and int(self["height"]) != alto:
            super().configure(height=alto)

    def _por_lienzo(self, e):
        self._forma(e.width, e.height)

    def resaltar(self, color: Optional[str]):
        """Borde brillante del color dado; None lo quita."""
        self._resalte = color
        self._forma(self.winfo_width(), self.winfo_height())

    def _forma(self, w, h):
        if w < 4 or h < 4:
            return
        px = self.app.px
        self.delete("forma")
        c = self.corte
        if self._resalte:
            chaflan(self, 0, 0, w - 1, h - 1, c + px(1), fill="",
                    outline=sprites.mezclar(self._resalte, _fondo_de(self),
                                            0.55), width=px(4), tags="forma")
        chaflan(self, px(2), px(2), w - px(3), h - px(3), c, fill=self.color,
                outline=self._resalte or BORDE, width=2 if self._resalte
                else 1, tags="forma")
        if self.acento:
            self.create_line(c + px(4), px(3), c + px(54), px(3),
                             fill=self.acento, width=px(3), tags="forma")
            self.create_line(px(3), c + px(2), c + px(1), px(4),
                             fill=self.acento, width=px(2), tags="forma")
        self.tag_lower("forma")


class Segmentos(tk.Canvas):
    """Selector de 1 a 10 en barras crecientes, como un nivel de señal.

    Tiene la interfaz de `tk.Scale` que usa la ventana: `get()`, `set(v)` y
    una función `command` que se llama al cambiar.
    """

    def __init__(self, padre, app, valor=5, command=None, n=10, minimo=1,
                 barra=16, alto=26):
        self.app, self.n, self.command = app, n, command
        self.minimo = minimo
        self._valor = valor
        super().__init__(padre, width=app.px(barra) * n, height=app.px(alto),
                         bg=_fondo_de(padre), highlightthickness=0,
                         cursor="hand2")
        self.bind("<Button-1>", self._clic)
        self.bind("<B1-Motion>", self._clic)
        self.bind("<MouseWheel>", lambda e: self._cambiar(
            self._valor + (1 if e.delta > 0 else -1)))
        self.bind("<Configure>", lambda _e: self._dibujar())
        self._dibujar()

    def get(self) -> int:
        return self._valor

    def set(self, valor):
        self._valor = min(self.n, max(self.minimo, int(round(float(valor)))))
        self._dibujar()

    def _clic(self, e):
        paso = max(self.winfo_width(), int(self["width"])) / self.n
        nuevo = min(self.n, max(1, int(e.x // paso) + 1))
        # Con mínimo 0, un clic en la primera barra encendida la apaga.
        if self.minimo == 0 and nuevo == 1 and self._valor == 1 \
                and e.type == tk.EventType.ButtonPress:
            nuevo = 0
        self._cambiar(nuevo)

    def _cambiar(self, nuevo):
        nuevo = min(self.n, max(self.minimo, nuevo))
        if nuevo != self._valor:
            self.set(nuevo)
            self.app.sonido.tocar("tic")
            if self.command:
                self.command(nuevo)

    def _dibujar(self):
        self.delete("all")
        px = self.app.px
        w = max(self.winfo_width(), int(self["width"]))
        h = int(self["height"])
        paso = w / self.n
        for k in range(self.n):
            alto = h * (0.35 + 0.65 * (k + 1) / self.n)
            lleno = k < self._valor
            color = (sprites.mezclar(ACENTO_OSCURO, ACENTO_CLARO,
                                     k / (self.n - 1)) if lleno
                     else PANEL_ALTO)
            rect_redondeado(self, k * paso + px(2), h - alto,
                            (k + 1) * paso - px(2), h, px(2), fill=color,
                            outline="")


class Ajuste(tk.Frame):
    """Un valor numérico con su rango, a la vista y a la mano.

    Arriba: el ícono del color del ajuste, el nombre, el rango y el valor
    en una caja que se puede escribir. Abajo: −, una pista que se llena
    con una perilla que se arrastra, y +. La rueda del ratón también lo
    mueve. Si lo escrito no es un número del rango, la caja se pone roja.
    Con `pista=False` queda compacto: − valor +.
    """

    def __init__(self, padre, app: "AppGrafica", variable: tk.StringVar,
                 minimo: int, maximo: int, etiqueta: str = "",
                 color: str = ACENTO, simbolo: Optional[str] = None,
                 paso: int = 1, pista: bool = True, nota: str = "",
                 ancho: int = 200):
        fondo = _fondo_de(padre)
        super().__init__(padre, bg=fondo)
        self.app, self.var = app, variable
        self.minimo, self.maximo, self.paso = minimo, maximo, paso
        self.color = color
        px = app.px
        self.caja = tk.Entry(
            self, textvariable=variable, width=4, justify="center",
            font=app.f_boton, relief="flat", bd=0, bg=PANEL_ALTO,
            fg=color if pista else TINTA, highlightthickness=1,
            highlightbackground=BORDE, highlightcolor=color,
            insertbackground=color, selectbackground=color,
            selectforeground=TINTA_ACENTO)
        self.texto_rango: Optional[tk.Label] = None
        self.pista: Optional[tk.Canvas] = None
        if pista:
            # Cabeza: ícono y nombre a la izquierda, el valor a la derecha
            cabeza = tk.Frame(self, bg=fondo)
            cabeza.pack(fill="x")
            if simbolo:
                dibujo = tk.Canvas(cabeza, width=px(18), height=px(18),
                                   bg=fondo, highlightthickness=0)
                icono(dibujo, simbolo, px(9), px(9), px(14), color)
                dibujo.pack(side="left", padx=(0, px(6)))
            tk.Label(cabeza, text=etiqueta, font=app.f_boton, fg=TINTA,
                     bg=fondo).pack(side="left")
            self.texto_rango = tk.Label(cabeza, text="", font=app.f_chico,
                                        fg=GRIS_CLARO, bg=fondo)
            self.texto_rango.pack(side="left", padx=(px(6), 0))
            self.caja.lift(cabeza)
            self.caja.pack(in_=cabeza, side="right", ipady=px(2))
        fila = tk.Frame(self, bg=fondo)
        fila.pack(fill="x", pady=(px(3) if pista else 0, 0))
        boton = 26 if pista else 28
        app.boton(fila, "", lambda: self.mover(-1), icono="menos",
                  estilo="fantasma", alto=boton, ancho=boton, sonido=None
                  ).pack(side="left")
        mas = app.boton(fila, "", lambda: self.mover(1), icono="mas",
                        estilo="fantasma", alto=boton, ancho=boton,
                        sonido=None)
        if pista:
            # El + se acomoda antes que la pista: si falta espacio, cede la
            # pista y no el botón.
            mas.pack(side="right")
            self.pista = tk.Canvas(fila, height=px(24), width=px(60),
                                   bg=fondo, highlightthickness=0,
                                   cursor="hand2")
            self.pista.pack(side="left", fill="x", expand=True,
                            padx=px(4))
            self.pista.bind("<Button-1>", self._clic)
            self.pista.bind("<B1-Motion>", self._clic)
            self.pista.bind("<Configure>", lambda _e: self._dibujar())
        else:
            self.caja.lift(fila)
            self.caja.pack(in_=fila, side="left", padx=px(4), ipady=px(3))
            mas.pack(side="left")
        for w in (self.caja, self.pista):
            if w is not None:
                w.bind("<MouseWheel>", lambda e: self.mover(
                    1 if e.delta > 0 else -1))
        # Pie: qué significa el valor
        self.nota = tk.Label(self, text=nota, font=app.f_chico, fg=GRIS,
                             bg=fondo, anchor="w", justify="left")
        if pista:
            self.nota.pack(fill="x", padx=(px(2), 0))
            # El texto se acomoda al ancho que le dé la columna
            self.nota.bind("<Configure>", lambda e: self.nota.configure(
                wraplength=max(1, e.width)))
        variable.trace_add("write", lambda *_a: self._dibujar())
        self.rango(minimo, maximo)

    # --------------------------------------------------------- valor
    def valor(self) -> Optional[int]:
        try:
            return int(self.var.get().strip())
        except ValueError:
            return None

    def poner(self, valor: float):
        """Lleva el valor al paso y al rango más cercanos."""
        if self.paso > 1:
            valor = round(valor / self.paso) * self.paso
        nuevo = int(min(self.maximo, max(self.minimo, round(valor))))
        if str(nuevo) != self.var.get().strip():
            self.var.set(str(nuevo))
            self.app.sonido.tocar("tic")

    def mover(self, pasos: int):
        actual = self.valor()
        if actual is None:
            actual = self.minimo
        if self.paso > 1 and actual % self.paso:
            # fuera del paso (p. ej. 15 de 10 en 10): primero se alinea
            abajo = actual // self.paso * self.paso
            self.poner(abajo + (self.paso if pasos > 0 else 0))
            return
        self.poner(actual + pasos * self.paso)

    def rango(self, minimo: int, maximo: Optional[int] = None):
        """Cambia el rango (el tablero mínimo crece con el escuadrón)."""
        self.minimo = minimo
        if maximo is not None:
            self.maximo = maximo
        if self.texto_rango is not None:
            self.texto_rango.configure(
                text=f"{self.minimo}–{self.maximo}")
        self._dibujar()

    # --------------------------------------------------------- dibujo
    def _clic(self, e):
        px = self.app.px
        w = max(self.pista.winfo_width(), int(self.pista["width"]))
        x0, x1 = px(9), w - px(9)
        t = min(1.0, max(0.0, (e.x - x0) / max(1, x1 - x0)))
        self.poner(self.minimo + t * (self.maximo - self.minimo))

    def _dibujar(self):
        v = self.valor()
        valido = v is not None and self.minimo <= v <= self.maximo
        try:
            self.caja.configure(highlightbackground=BORDE if valido
                                else ROJO_UI)
        except tk.TclError:
            return
        c = self.pista
        if c is None:
            return
        px = self.app.px
        c.delete("all")
        w = max(c.winfo_width(), int(c["width"]))
        h = int(c["height"])
        x0, x1, y = px(9), w - px(9), h / 2
        pildora(c, x0, y - px(3), x1, y + px(3), PANEL_ALTO)
        pasos = (self.maximo - self.minimo) // self.paso
        if 0 < pasos <= 20:                       # marcas de cada valor
            for k in range(pasos + 1):
                x = x0 + (x1 - x0) * k / pasos
                c.create_line(x, y + px(6), x, y + px(9), fill=BORDE)
        if v is None:
            return
        t = min(1.0, max(0.0, (v - self.minimo)
                         / max(1, self.maximo - self.minimo)))
        xf = x0 + (x1 - x0) * t
        if xf > x0 + px(6):
            pildora(c, x0, y - px(3), xf, y + px(3),
                    sprites.mezclar(self.color, PANEL, 0.25))
        r = px(7)
        c.create_oval(xf - r - px(2), y - r - px(2), xf + r + px(2),
                      y + r + px(2), fill=sprites.mezclar(self.color, PANEL,
                                                          0.7), outline="")
        c.create_oval(xf - r, y - r, xf + r, y + r, fill=self.color,
                      outline=sprites.mezclar(self.color, "#FFFFFF", 0.45),
                      width=1.5)


class VistaTablero(tk.Canvas):
    """Miniatura del tablero con el tamaño elegido, para verlo antes de
    jugar: el damero, las esquinas doradas y la medida."""

    def __init__(self, padre, app: "AppGrafica", lado: int = 108):
        self.app = app
        super().__init__(padre, width=app.px(lado), height=app.px(lado + 18),
                         bg=_fondo_de(padre), highlightthickness=0)
        self.lado = app.px(lado)

    def dibujar(self, ancho: Optional[int], alto: Optional[int],
                minimo: int):
        self.delete("all")
        px = self.app.px
        if not ancho or not alto or ancho < 1 or alto < 1:
            self.create_text(self.lado / 2, self.lado / 2, text="?",
                             font=self.app.f_grande, fill=ROJO_UI)
            return
        caja = self.lado - px(10)
        celda = caja / max(ancho, alto)
        w, h = celda * ancho, celda * alto
        x0 = (self.lado - w) / 2
        y0 = (self.lado - h) / 2
        valido = ancho >= minimo and alto >= minimo
        for y in range(alto):
            for x in range(ancho):
                color = sprites.mezclar(
                    sprites.FONDO if (x + y) % 2 == 0
                    else sprites.CASILLA_ALTERNA, sprites.LUZ, 0.6)
                self.create_rectangle(x0 + x * celda, y0 + y * celda,
                                      x0 + (x + 1) * celda,
                                      y0 + (y + 1) * celda, fill=color,
                                      outline=sprites.MARCA
                                      if celda > 5 else "")
        borde = ACENTO if valido else ROJO_UI
        largo, g = px(10), px(3)
        for cx, cy, dx, dy in ((x0, y0, 1, 1), (x0 + w, y0, -1, 1),
                               (x0, y0 + h, 1, -1), (x0 + w, y0 + h, -1, -1)):
            ex, ey = cx - dx * g, cy - dy * g
            self.create_line(ex, ey + dy * largo, ex, ey, ex + dx * largo,
                             ey, fill=borde, width=px(2))
        self.create_text(self.lado / 2, self.lado + px(8),
                         text=f"{ancho} × {alto}  ·  {ancho * alto} casillas",
                         font=self.app.f_chico,
                         fill=GRIS if valido else ROJO_UI)


class ControlMusica(tk.Frame):
    """Volumen de la música: nota, −, diez barras y +.

    Todos los controles de la aplicación muestran el mismo volumen: cambiar
    uno actualiza los demás.
    """

    def __init__(self, padre, app: "AppGrafica", fondo: Optional[str] = None):
        fondo = fondo or _fondo_de(padre)
        super().__init__(padre, bg=fondo)
        self.app = app
        px = app.px
        nota = tk.Canvas(self, width=px(20), height=px(26), bg=fondo,
                         highlightthickness=0)
        icono(nota, "nota", px(10), px(13), px(14), ACENTO)
        nota.pack(side="left", padx=(0, px(4)))
        app.boton(self, "", lambda: self._paso(-1), icono="menos",
                  estilo="fantasma", alto=30, ancho=30, sonido=None,
                  ayuda="Bajar la música").pack(side="left")
        self.barras = Segmentos(self, app, valor=app.sonido.volumen_musica,
                                command=app.cambiar_volumen_musica,
                                minimo=0, barra=9, alto=22)
        self.barras.pack(side="left", padx=px(6))
        app.boton(self, "", lambda: self._paso(1), icono="mas",
                  estilo="fantasma", alto=30, ancho=30, sonido=None,
                  ayuda="Subir la música").pack(side="left")
        self.cifra = tk.Label(self, text="", font=app.f_boton, fg=ACENTO,
                              bg=fondo, width=3, anchor="e")
        self.cifra.pack(side="left")
        app._controles_musica = [c for c in app._controles_musica
                                 if c.winfo_exists()] + [self]
        self.refrescar()

    def _paso(self, d: int):
        self.app.sonido.tocar("tic")
        self.app.cambiar_volumen_musica(self.app.sonido.volumen_musica + d)

    def refrescar(self):
        v = self.app.sonido.volumen_musica
        self.barras.set(v)
        self.cifra.configure(text=str(v) if v else "—")


class _Interruptor:
    """Un «botón» sin dibujo: guarda si una acción está disponible.

    Volver a la configuración ya no tiene botón propio (vive en el menú de
    arriba a la derecha), pero el menú y las teclas siguen preguntando si
    está activa, igual que con un botón.
    """

    def __init__(self, sonido: Optional[str] = "clic"):
        self._estado = "normal"
        self.sonido = sonido

    def configure(self, cnf=None, **kw):
        if "state" in kw:
            self._estado = kw["state"]

    config = configure

    def __getitem__(self, clave):
        return self._estado


class _Rotulo:
    """Un texto del Canvas con la interfaz de un Label (configure, [])."""

    def __init__(self, canvas, item):
        self.canvas, self.item = canvas, item

    def configure(self, **kw):
        if "text" in kw:
            self.canvas.itemconfigure(self.item, text=kw["text"])

    config = configure

    def __getitem__(self, clave):
        return self.canvas.itemcget(self.item, clave)


class Globo:
    """Etiqueta flotante con título y explicación, junto al ratón.

    Se usa para los errores: el título dice dónde y la explicación qué pasa
    y cómo corregirlo, con una franja del color del aviso.
    """

    def __init__(self, app: "AppGrafica"):
        self.app = app
        self.ventana: Optional[tk.Toplevel] = None

    def mostrar(self, padre, x: int, y: int, titulo: str, texto: str,
                color: str = ROJO_UI):
        self.ocultar()
        app, px = self.app, self.app.px
        g = tk.Toplevel(padre)
        g.overrideredirect(True)
        g.attributes("-topmost", True)
        marco = tk.Frame(g, bg=PANEL_ALTO, highlightthickness=1,
                         highlightbackground=color)
        marco.pack()
        tk.Frame(marco, bg=color, width=px(4)).pack(side="left", fill="y")
        dentro = tk.Frame(marco, bg=PANEL_ALTO)
        dentro.pack(side="left", padx=px(10), pady=px(8))
        tk.Label(dentro, text=titulo, font=app.f_boton, fg=color,
                 bg=PANEL_ALTO, anchor="w", justify="left").pack(fill="x")
        tk.Label(dentro, text=texto, font=app.f_chico, fg=TINTA,
                 bg=PANEL_ALTO, anchor="w", justify="left",
                 wraplength=px(380)).pack(fill="x", pady=(px(3), 0))
        g.update_idletasks()
        ancho, alto = g.winfo_reqwidth(), g.winfo_reqheight()
        x = min(x, g.winfo_screenwidth() - ancho - px(8))
        if y + alto > g.winfo_screenheight() - px(40):
            y = y - alto - px(28)
        g.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.ventana = g

    def ocultar(self):
        if self.ventana is not None:
            try:
                self.ventana.destroy()
            except tk.TclError:
                pass
            self.ventana = None


# ------------------------------------------------- explicación de un programa
_DIRECCIONES = {"N": "norte", "S": "sur", "E": "este", "O": "oeste"}
_ESQUINAS = {"NE": "noreste", "NO": "noroeste", "SE": "sureste",
             "SO": "suroeste"}
_COMPARA = {">": "mayor que", "<": "menor que", ">=": "al menos",
            "<=": "a lo más", "==": "igual a"}


def explicar(instruccion, config: Configuracion) -> str:
    """Qué hace una instrucción, en palabras, con los valores vigentes."""
    tipo = instruccion.tipo.name
    d = (_DIRECCIONES.get(instruccion.direccion.name, "")
         if instruccion.direccion is not None else "")
    if tipo == "MOV":
        return f"avanza una casilla al {d}"
    if tipo == "AMT":
        return (f"dispara la ametralladora al {d} "
                f"({config.dano.ametralladora:g} de daño)")
    if tipo == "MISIL":
        return f"lanza un misil al {d} ({config.dano.misil:g} de daño)"
    if tipo == "MINA":
        esquina = (instruccion.direccion.name
                   + (instruccion.direccion2.name
                      if instruccion.direccion2 is not None else ""))
        return (f"lanza una mina a la esquina "
                f"{_ESQUINAS.get(esquina, esquina)} "
                f"({config.dano.mina:g} de daño)")
    if tipo == "ESCUDO":
        return f"activa el escudo ({config.escudo_puntos} puntos)"
    if tipo == "REPARAR":
        return f"se repara +{config.reparar_puntos} (un solo uso)"
    if tipo == "ESPERAR":
        return "no hace nada este turno"
    if tipo == "IF":
        c = instruccion.condicion
        compara = _COMPARA.get(c.operador.value, c.operador.value)
        if c.fuente.name == "RADAR":
            dc = _DIRECCIONES.get(c.direccion.name, "")
            if c.operador.value == ">" and c.valor == 0:
                si = f"si el radar ve un tanque al {dc}"
            elif c.operador.value == "<" and c.valor == 0:
                si = f"si al {dc} solo hay pared"
            else:
                si = f"si el radar al {dc} da {compara} {c.valor}"
        else:
            si = f"si su vida es {compara} {c.valor}"
        return f"{si}, {explicar(instruccion.accion, config)}"
    return ""


#: Color de cada palabra del lenguaje en el visor.
_COLOR_PALABRA = {
    "MOV": "#7DD3FC",
    "AMT": "#FCA5A5", "MISIL": "#FCA5A5", "MINA": "#FCA5A5",
    "ESCUDO": "#86EFAC", "REPARAR": "#86EFAC",
    "ESPERAR": "#94A3B8",
    "IF": "#C4B5FD", "THEN": "#C4B5FD",
    "RADAR": "#FDE68A", "V": "#FDE68A",
}
_COLOR_DIRECCION = "#67E8F9"
_COLOR_NUMERO = "#FDBA74"
_LEYENDA = (("Movimiento", "#7DD3FC"), ("Armas", "#FCA5A5"),
            ("Defensa", "#86EFAC"), ("Condición", "#C4B5FD"),
            ("Radar y vida", "#FDE68A"), ("Dirección", _COLOR_DIRECCION))


_FICHA = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ_]+|-?\d+|\s+|.")


def _etiqueta_de(parte: str) -> Optional[str]:
    """La etiqueta de color de una palabra del programa, si lleva."""
    if parte.isspace():
        return None
    if parte in _COLOR_PALABRA:
        return f"p_{parte}"
    if parte in ("N", "S", "E", "O") or parte in _ESQUINAS:
        return "direccion"
    if re.fullmatch(r"-?\d+", parte):
        return "entero"
    if parte in "(),<>=":
        return "signo"
    return None


def etiquetas_de_codigo(texto: tk.Text, app: "AppGrafica"):
    """Los colores del código, compartidos por el visor y el editor."""
    mono = app.f_mono[0]
    texto.tag_configure("comentario", foreground=GRIS_CLARO,
                        font=(mono, 10, "italic"))
    for palabra, tono in _COLOR_PALABRA.items():
        texto.tag_configure(f"p_{palabra}", foreground=tono,
                            font=(mono, 10, "bold"))
    texto.tag_configure("direccion", foreground=_COLOR_DIRECCION)
    texto.tag_configure("entero", foreground=_COLOR_NUMERO)
    texto.tag_configure("signo", foreground=GRIS)


def cabeza_programa(app: "AppGrafica", c: tk.Canvas, numero: int,
                    color: str, rotulo: str, titulo: str, pildoras):
    """Encabezado del visor y del editor: el tanque, el archivo y un
    resumen en píldoras [(texto, color)] de derecha a izquierda."""
    px = app.px
    w = max(c.winfo_width(), px(600))
    h = int(c["height"])
    c.delete("all")
    degradado(c, w, h, "#132235", FONDO_BARRA, horizontal=True, pasos=32)
    c.create_line(0, h - 2, w, h - 2, fill=color, width=2)
    sprites.tanque(c, px(42), h / 2, px(52), numero, color, Direccion.E,
                   etiqueta="visor")
    c.create_text(px(80), h / 2 - px(12), text=espaciado(rotulo),
                  anchor="w", font=app.f_mini, fill=claro(color, 0.3))
    c.create_text(px(80), h / 2 + px(10), text=titulo, anchor="w",
                  font=app.f_barra, fill=TINTA)
    x = w - px(18)
    for texto, tono in pildoras:
        ancho = app.fuente_boton.measure(texto) + px(24)
        rect_redondeado(c, x - ancho, h / 2 - px(13), x, h / 2 + px(13),
                        px(13), fill=PANEL_ALTO, outline=tono)
        c.create_text(x - ancho / 2, h / 2, text=texto, fill=tono,
                      font=app.f_boton)
        x -= ancho + px(8)


def leer_programa(ruta: Path) -> Optional[str]:
    """El texto del archivo, con la misma tolerancia que el intérprete."""
    try:
        return ruta.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ruta.read_text(encoding="latin-1")
    except OSError:
        return None


class VisorPrograma:
    """Ventana que muestra un programa mejor que un .txt.

    Cada línea lleva su número, la sintaxis en colores y, a la derecha, lo
    que hace en palabras. Las líneas con errores van en rojo; al pasar el
    ratón encima, un globo explica el error. Esas líneas se saltan al jugar.
    """

    def __init__(self, app: "AppGrafica", ruta: Path, numero: int,
                 color: str, config: Configuracion,
                 al_cerrar: Optional[Callable[[], None]] = None,
                 al_guardar: Optional[Callable[[Path], None]] = None):
        self.app, self.ruta, self.numero = app, Path(ruta), numero
        self.color, self.config, self.al_cerrar = color, config, al_cerrar
        self.al_guardar = al_guardar
        self.editor: Optional[EditorPrograma] = None
        self.globo = Globo(app)
        self._errores: dict[int, list] = {}
        px = app.px
        v = tk.Toplevel(app.root, bg=FONDO_VENTANA)
        v.title(f"Programa del tanque {numero} · {self.ruta.name}")
        v.geometry(f"{px(900)}x{px(660)}")
        v.minsize(px(640), px(420))
        v.protocol("WM_DELETE_WINDOW", self.cerrar)
        v.bind("<Escape>", lambda _e: self.cerrar())
        self.ventana = v

        # --- encabezado: el tanque, el archivo y el resumen
        self.cabeza = tk.Canvas(v, height=px(76), bg=FONDO_BARRA,
                                highlightthickness=0)
        self.cabeza.pack(fill="x")
        self.cabeza.bind("<Configure>", lambda _e: self._dibujar_cabeza())

        cuerpo = tk.Frame(v, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=px(16), pady=px(12))
        self.aviso = tk.Label(cuerpo, text="", font=app.f_chico, fg=GRIS,
                              bg=FONDO_VENTANA, anchor="w", justify="left")
        self.aviso.pack(fill="x", pady=(0, px(8)))

        caja = Panel(cuerpo, app, modo="ambos", relleno=10, acento=color)
        caja.configure(height=px(360))
        caja.pack(fill="both", expand=True)
        cab = tk.Canvas(caja.cuerpo, height=px(18), bg=PANEL,
                        highlightthickness=0)
        cab.pack(fill="x", pady=(0, px(4)))
        for texto, x in (("LÍNEA", px(8)), ("INSTRUCCIÓN", px(68)),
                         ("QUÉ HACE", px(404))):
            cab.create_text(x, px(9), text=espaciado(texto), anchor="w",
                            font=app.f_mini, fill=GRIS)
        self.texto = tk.Text(caja.cuerpo, font=(app.f_mono[0], 10),
                             bg=PANEL, fg=TINTA, relief="flat",
                             highlightthickness=0, wrap="none",
                             padx=px(4), pady=px(2), cursor="arrow",
                             spacing1=px(3), spacing3=px(3),
                             tabs=(px(64), px(400)),
                             insertbackground=PANEL)
        self.texto.pack(fill="both", expand=True)
        self._etiquetas()
        self.texto.bind("<Motion>", self._sobre)
        self.texto.bind("<Leave>", lambda _e: self._fuera())

        # --- pie: leyenda de colores y acciones
        pie = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        pie.pack(fill="x", pady=(px(10), 0))
        leyenda = tk.Frame(pie, bg=FONDO_VENTANA)
        leyenda.pack(side="left")
        for nombre, tono in _LEYENDA:
            tk.Label(leyenda, text="■", fg=tono, bg=FONDO_VENTANA,
                     font=app.f_chico).pack(side="left")
            tk.Label(leyenda, text=nombre, fg=GRIS, bg=FONDO_VENTANA,
                     font=app.f_chico).pack(side="left", padx=(px(2), px(10)))
        app.boton(pie, "Cerrar", self.cerrar, primario=True,
                  ancho=100).pack(side="right")
        app.boton(pie, "Revisar", self.recargar, icono="reiniciar",
                  ayuda="Volver a leer el archivo"
                  ).pack(side="right", padx=px(8))
        app.boton(pie, "Editar", self.editar, icono="lapiz",
                  ayuda="Corregir el programa aquí mismo, con la revisión "
                        "al momento").pack(side="right")
        self.recargar()
        v.transient(app.root)
        v.focus_set()

    # ------------------------------------------------------------ contenido
    def _etiquetas(self):
        t, app = self.texto, self.app
        mono = app.f_mono[0]
        t.tag_configure("numero", foreground=GRIS_CLARO)
        t.tag_configure("numero_error", foreground=ROJO_UI,
                        font=(mono, 10, "bold"))
        etiquetas_de_codigo(t, app)
        t.tag_configure("explica", foreground=GRIS,
                        font=(app.f_texto[0], 9))
        t.tag_configure("explica_error", foreground=ROJO_UI,
                        font=(app.f_texto[0], 9))
        t.tag_configure("error", background="#3A161C")
        t.tag_configure("codigo_error", foreground="#FFB4B4",
                        underline=True)
        t.tag_configure("encima", background=PANEL_HOVER)
        t.tag_raise("encima")

    def recargar(self):
        """Lee el archivo otra vez y lo vuelve a revisar."""
        contenido = leer_programa(self.ruta)
        t = self.texto
        t.configure(state="normal")
        t.delete("1.0", "end")
        self._errores = {}
        if contenido is None:
            t.insert("end", "\n   El archivo no existe o no se puede leer.",
                     "explica_error")
            t.configure(state="disabled")
            self.validas = 0
            self._dibujar_cabeza()
            return
        programa, errores = Interprete().analizar(contenido,
                                                  nombre=self.ruta.stem,
                                                  archivo=self.ruta.name)
        instrucciones = {i.linea: i for i in programa.instrucciones}
        for e in errores:
            self._errores.setdefault(e.linea, []).append(e)
        lineas = contenido.replace("﻿", "").splitlines()
        for n, cruda in enumerate(lineas, start=1):
            con_error = n in self._errores
            inicio = t.index("end-1c")
            t.insert("end", f"{n:>4}", "numero_error" if con_error
                     else "numero")
            t.insert("end", "  ✗\t" if con_error else "\t",
                     "numero_error" if con_error else "numero")
            self._colorear(cruda, con_error)
            if n in instrucciones:
                t.insert("end", "\t" + explicar(instrucciones[n],
                                                self.config), "explica")
            elif con_error:
                t.insert("end", "\t✗ " + self._errores[n][0].mensaje,
                         "explica_error")
            t.insert("end", "\n")
            if con_error:
                t.tag_add("error", inicio, t.index("end-1c"))
        sin_linea = self._errores.get(0, [])
        if sin_linea:
            t.insert("end", "\n   " + sin_linea[0].mensaje, "explica_error")
        t.configure(state="disabled")
        self.validas = len(programa.instrucciones)
        self.con_error = len([n for n in self._errores if n])
        if not self.validas:
            texto = ("Este programa no tiene ninguna instrucción válida: el "
                     "tanque no puede jugar hasta corregirlo.")
            color = ROJO_UI
        elif self.con_error:
            texto = (f"Las {self.con_error} líneas en rojo tienen errores y "
                     f"se saltan al jugar: el tanque ejecuta las demás. Pasa "
                     f"el ratón sobre una para ver qué está mal.")
            color = ACENTO
        else:
            texto = "Todas las líneas son válidas."
            color = VERDE_OK
        self.aviso.configure(text=texto, fg=color)
        self._dibujar_cabeza()

    def _colorear(self, cruda: str, con_error: bool):
        """Inserta una línea de código con cada palabra en su color."""
        t = self.texto
        extra = ("codigo_error",) if con_error else ()
        codigo, _, comentario = cruda.partition("#")
        for parte in _FICHA.findall(codigo):
            etiqueta = _etiqueta_de(parte)
            t.insert("end", parte, ((etiqueta,) if etiqueta else ()) + extra)
        if comentario or cruda.lstrip().startswith("#"):
            t.insert("end", "#" + comentario, "comentario")

    # ------------------------------------------------------------ globo
    def _sobre(self, e):
        t = self.texto
        n = int(t.index(f"@{e.x},{e.y}").split(".")[0])
        self.senalar(n, e.x_root, e.y_root)

    def senalar(self, n: int, x: int, y: int):
        """Resalta la línea n y, si tiene error, lo explica en un globo."""
        t = self.texto
        t.tag_remove("encima", "1.0", "end")
        t.tag_add("encima", f"{n}.0", f"{n}.end+1c")
        if n in self._errores:
            mensajes = "\n".join(f"• {err.mensaje}"
                                 for err in self._errores[n])
            self.globo.mostrar(
                self.ventana, x + self.app.px(18),
                y + self.app.px(14), f"Línea {n}: error",
                f"{mensajes}\n\nEsta línea se salta al jugar; el tanque "
                f"sigue con la siguiente.")
        else:
            self.globo.ocultar()

    def _fuera(self):
        self.texto.tag_remove("encima", "1.0", "end")
        self.globo.ocultar()

    # ------------------------------------------------------------ cabeza
    def _dibujar_cabeza(self):
        validas = getattr(self, "validas", 0)
        con_error = getattr(self, "con_error", 0)
        cabeza_programa(
            self.app, self.cabeza, self.numero, self.color,
            f"TANQUE {self.numero}", self.ruta.name,
            ((f"{con_error} con error", ROJO_UI if con_error else GRIS_CLARO),
             (f"{validas} válidas", VERDE_OK if validas else GRIS_CLARO)))

    # ------------------------------------------------------------ acciones
    def editar(self) -> "EditorPrograma":
        """Abre el editor del juego con este programa; al guardar, el visor
        se pone al día."""
        if self.editor is not None and self.editor.ventana.winfo_exists():
            self.editor.ventana.lift()
            return self.editor
        self.globo.ocultar()
        self.editor = EditorPrograma(
            self.app, self.ruta, self.numero, self.color, self.config,
            al_guardar=self._guardado)
        return self.editor

    def _guardado(self, ruta: Path):
        self.ruta = Path(ruta)
        try:
            self.ventana.title(f"Programa del tanque {self.numero} · "
                               f"{self.ruta.name}")
            self.recargar()
        except tk.TclError:
            pass
        if self.al_guardar:
            self.al_guardar(self.ruta)

    def cerrar(self):
        self.globo.ocultar()
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass
        if self.al_cerrar:
            self.al_cerrar()


# ======================================================================
# ------------------------------------------------------- ventanas emergentes
def lista_desplazable(padre, fondo: str = PANEL):
    """Un marco dentro de un lienzo que se recorre con la rueda del ratón
    (la barra de desplazamiento de Windows no admite colores).

    Devuelve (lienzo, marco, enlazar): `enlazar()` activa la rueda sobre
    todo lo que se haya puesto en el marco; se llama al terminar de llenarlo.
    """
    lienzo = tk.Canvas(padre, bg=fondo, highlightthickness=0, bd=0)
    marco = tk.Frame(lienzo, bg=fondo)
    dentro = lienzo.create_window(0, 0, window=marco, anchor="nw")
    marco.bind("<Configure>", lambda _e: lienzo.configure(
        scrollregion=lienzo.bbox("all")))
    lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(
        dentro, width=e.width))

    def rueda(e):
        caja = lienzo.bbox("all")
        if caja and caja[3] > lienzo.winfo_height():
            lienzo.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def enlazar():
        pendientes = [lienzo]
        while pendientes:
            w = pendientes.pop()
            w.bind("<MouseWheel>", rueda, add="+")
            pendientes.extend(w.winfo_children())
    return lienzo, marco, enlazar


def _centrar(ventana: tk.Toplevel, padre):
    """Pone la ventana en el centro de la que la abrió."""
    ventana.update_idletasks()
    w, h = ventana.winfo_reqwidth(), ventana.winfo_reqheight()
    try:
        x = padre.winfo_rootx() + (padre.winfo_width() - w) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - h) // 3
    except tk.TclError:
        x = y = 100
    if padre.winfo_width() <= 1:              # el padre aún no se muestra
        x = (ventana.winfo_screenwidth() - w) // 2
        y = (ventana.winfo_screenheight() - h) // 3
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")


class VentanaEmergente:
    """Base de las ventanas emergentes con el diseño del juego.

    Es modal: `mostrar()` bloquea las demás ventanas, espera la respuesta y
    la devuelve. Tiene la franja de color arriba, el encabezado oscuro con
    su ícono y un pie con los botones a la derecha.
    """

    def __init__(self, app: "AppGrafica", padre, titulo: str,
                 color: str = ACENTO, simbolo: str = "?",
                 subtitulo: str = ""):
        self.app, self.color = app, color
        self.padre = padre or app.root
        self.valor = None
        px = app.px
        v = tk.Toplevel(self.padre, bg=PANEL)
        v.withdraw()
        v.title(titulo)
        v.resizable(False, False)
        v.protocol("WM_DELETE_WINDOW", self.cancelar)
        v.bind("<Escape>", lambda _e: self.cancelar())
        self.ventana = v
        tk.Frame(v, bg=color, height=px(4)).pack(fill="x")
        cabeza = tk.Frame(v, bg=FONDO_BARRA)
        cabeza.pack(fill="x")
        dibujo = tk.Canvas(cabeza, width=px(46), height=px(46),
                           bg=FONDO_BARRA, highlightthickness=0)
        dibujo.pack(side="left", padx=(px(18), px(12)), pady=px(12))
        dibujo.create_oval(px(3), px(3), px(43), px(43), width=2,
                           outline=color,
                           fill=sprites.mezclar(color, FONDO_BARRA, 0.8))
        dibujo.create_text(px(23), px(23), text=simbolo, fill=color,
                           font=(app.f_vida[0], 17))
        textos = tk.Frame(cabeza, bg=FONDO_BARRA)
        textos.pack(side="left", fill="x", expand=True, padx=(0, px(22)))
        tk.Label(textos, text=titulo, font=app.f_grande, fg=TINTA,
                 bg=FONDO_BARRA, anchor="w").pack(fill="x")
        if subtitulo:
            tk.Label(textos, text=subtitulo, font=app.f_chico, fg=GRIS,
                     bg=FONDO_BARRA, anchor="w").pack(fill="x")
        tk.Frame(v, bg=BORDE, height=1).pack(fill="x")
        self.pie = tk.Frame(v, bg=PANEL)
        self.pie.pack(side="bottom", fill="x", padx=px(18),
                      pady=(px(6), px(16)))
        self.cuerpo = tk.Frame(v, bg=PANEL)
        self.cuerpo.pack(fill="both", expand=True, padx=px(22),
                         pady=(px(16), px(10)))

    def boton(self, texto, accion: Callable, estilo="secundario",
              icono=None, ancho=110) -> Boton:
        """Un botón del pie; se agregan de derecha a izquierda."""
        b = self.app.boton(self.pie, texto, accion, estilo=estilo,
                           icono=icono, ancho=ancho)
        b.pack(side="right", padx=(self.app.px(8), 0))
        return b

    def responder(self, valor):
        self.valor = valor
        try:
            self.ventana.grab_release()
            self.ventana.destroy()
        except tk.TclError:
            pass

    def cancelar(self):
        self.responder(None)

    def mostrar(self):
        v = self.ventana
        v.transient(self.padre)
        _centrar(v, self.padre)
        v.deiconify()
        v.lift()
        try:
            v.grab_set()
        except tk.TclError:
            pass
        v.focus_set()
        self.padre.wait_window(v)
        return self.valor


class Dialogo(VentanaEmergente):
    """Pregunta, aviso o error: un texto, un detalle opcional en un cuadro
    y los botones. `botones` va de izquierda a derecha como
    [(texto, valor, estilo)]; Enter elige el último y Esc cancela."""

    TIPOS = {"pregunta": (ACENTO, "?"), "peligro": (ROJO_UI, "!"),
             "error": (ROJO_UI, "✕"), "aviso": (ACENTO, "!"),
             "info": (CIAN, "i"), "listo": (VERDE_OK, "✓")}

    def __init__(self, app, padre, titulo: str, texto: str,
                 tipo: str = "pregunta", botones=(("Aceptar", True,
                                                    "primario"),),
                 detalle: str = "", cancelar=None):
        color, simbolo = self.TIPOS[tipo]
        super().__init__(app, padre, titulo, color, simbolo)
        px = app.px
        self._cancelar = cancelar
        tk.Label(self.cuerpo, text=texto, font=app.f_texto, fg=TINTA,
                 bg=PANEL, anchor="w", justify="left",
                 wraplength=px(430)).pack(fill="x")
        if detalle:
            caja = tk.Frame(self.cuerpo, bg=PANEL_ALTO,
                            highlightthickness=1, highlightbackground=BORDE)
            caja.pack(fill="both", expand=True, pady=(px(12), 0))
            tk.Frame(caja, bg=color, width=px(3)).pack(side="left",
                                                       fill="y")
            lineas = detalle.splitlines() or [""]
            cuadro = tk.Text(caja, font=app.f_mono, bg=PANEL_ALTO, fg=TINTA,
                             relief="flat", highlightthickness=0,
                             wrap="word", width=58, padx=px(10),
                             pady=px(8), height=min(14, sum(
                                 1 + len(l) // 56 for l in lineas)),
                             cursor="arrow")
            cuadro.insert("1.0", detalle)
            cuadro.configure(state="disabled")
            cuadro.pack(side="left", fill="both", expand=True)
            self.detalle = cuadro
        for texto_b, valor, estilo in reversed(list(botones)):
            self.boton(texto_b, lambda v=valor: self.responder(v), estilo)
        ultimo = list(botones)[-1][1]
        self.ventana.bind("<Return>", lambda _e: self.responder(ultimo))

    def cancelar(self):
        self.responder(self._cancelar)


#: Colores para elegir en el selector: los seis del escuadrón primero.
PALETA_TANQUES = sprites.COLORES_TANQUE + (
    "#1D4ED8", "#EA580C", "#059669", "#7C3AED", "#DB2777", "#65A30D",
    "#0891B2", "#CA8A04", "#DC2626", "#9333EA", "#475569", "#92400E",
    "#38BDF8", "#FACC15", "#F87171", "#A3E635", "#CBD5E1", "#1F2937")


class SelectorColor(VentanaEmergente):
    """Elige el color de un tanque: una paleta, el tanque de muestra y un
    campo para escribir el color en hexadecimal (#RRGGBB)."""

    def __init__(self, app, padre, numero: int, color: str):
        super().__init__(app, padre, f"Color del tanque {numero}",
                         color, "●", "Elige uno de la paleta o escribe "
                                     "su código")
        px = app.px
        self.numero, self.actual = numero, color.upper()
        self.muestra = tk.Canvas(self.cuerpo, width=px(130),
                                 height=px(130), bg=PANEL_ALTO,
                                 highlightthickness=0)
        self.muestra.grid(row=0, column=0, rowspan=2, sticky="n",
                          padx=(0, px(18)))
        rejilla = tk.Frame(self.cuerpo, bg=PANEL)
        rejilla.grid(row=0, column=1, sticky="nw")
        self.celdas: dict[str, tk.Canvas] = {}
        lado = px(34)
        for k, tono in enumerate(PALETA_TANQUES):
            c = tk.Canvas(rejilla, width=lado, height=lado, bg=PANEL,
                          highlightthickness=0, cursor="hand2")
            c.grid(row=k // 6, column=k % 6, padx=px(3), pady=px(3))
            c.bind("<Button-1>", lambda _e, t=tono: self.elegir(t))
            c.bind("<Double-Button-1>", lambda _e, t=tono: (
                self.elegir(t), self.responder(t)))
            self.celdas[tono] = c
        fila = tk.Frame(self.cuerpo, bg=PANEL)
        fila.grid(row=1, column=1, sticky="w", pady=(px(10), 0))
        tk.Label(fila, text="Código", font=app.f_chico, fg=GRIS,
                 bg=PANEL).pack(side="left")
        self.codigo = tk.StringVar(app.root, self.actual)
        campo = app.campo_texto(fila, self.codigo, ancho=10)
        campo.configure(font=app.f_mono)
        campo.pack(side="left", padx=px(8), ipady=px(3))
        self.aviso = tk.Label(fila, text="", font=app.f_chico, fg=ROJO_UI,
                              bg=PANEL)
        self.aviso.pack(side="left")
        self.codigo.trace_add("write", lambda *_a: self._escrito())
        self.usar = self.boton("Usar color",
                               lambda: self.responder(self.actual),
                               "primario", "play", ancho=130)
        self.boton("Cancelar", self.cancelar, "fantasma")
        self.ventana.bind("<Return>", lambda _e: self.responder(
            self.actual) if self.actual else None)
        self._pintar()

    def elegir(self, color: str):
        self.app.sonido.tocar("clic")
        self.codigo.set(color)

    def _escrito(self):
        texto = self.codigo.get().strip().upper()
        if not texto.startswith("#"):
            texto = "#" + texto
        if re.fullmatch(r"#[0-9A-F]{6}", texto):
            self.actual = texto
            self.aviso.configure(text="")
        else:
            self.actual = None
            self.aviso.configure(text="✗ usa #RRGGBB")
        self.app.activar(self.usar, self.actual is not None)
        self._pintar()

    def _pintar(self):
        px = self.app.px
        lado = px(34)
        for tono, c in self.celdas.items():
            c.delete("all")
            elegido = tono == self.actual
            if elegido:
                rect_redondeado(c, 1, 1, lado - 1, lado - 1, px(8),
                                fill="", outline=ACENTO, width=2)
            rect_redondeado(c, px(5), px(5), lado - px(5), lado - px(5),
                            px(6), fill=tono, outline=claro(tono, 0.3))
        m = self.muestra
        m.delete("all")
        w = px(130)
        if self.actual:
            m.create_oval(w * 0.15, w * 0.78, w * 0.85, w * 0.95,
                          fill="#070C12", width=0)
            sprites.tanque(m, w / 2, w / 2, w * 0.85, self.numero,
                           self.actual, Direccion.N, etiqueta="muestra")
        else:
            m.create_text(w / 2, w / 2, text="?", fill=GRIS_CLARO,
                          font=self.app.f_titulo)


class SelectorPrograma(VentanaEmergente):
    """Elige el archivo .txt de un tanque sin salir del juego.

    A la izquierda, las carpetas y los programas de la carpeta actual (cada
    programa dice si es válido); a la derecha, el programa seleccionado con
    sus colores. Doble clic entra a una carpeta o elige el programa.
    """

    def __init__(self, app, padre, numero: int,
                 inicial: Optional[Path] = None):
        super().__init__(app, padre, f"Programa del tanque {numero}",
                         ACENTO, "≡", "Elige un archivo .txt")
        px = app.px
        carpeta = app.raiz / "tanques"
        self.carpeta = (inicial if inicial and inicial.is_dir()
                        else carpeta if carpeta.is_dir() else app.raiz)
        self.elegido: Optional[Path] = None
        self._filas: dict[Path, tuple] = {}

        barra = tk.Frame(self.cuerpo, bg=PANEL)
        barra.pack(fill="x", pady=(0, px(8)))
        app.boton(barra, "", self.subir, icono="atras", alto=30, ancho=34,
                  ayuda="Subir a la carpeta de arriba").pack(side="left")
        app.boton(barra, "", lambda: self.abrir(carpeta if carpeta.is_dir()
                                                else app.raiz),
                  icono="casa", alto=30, ancho=34,
                  ayuda="Los programas del juego (tanques/)").pack(
                      side="left", padx=(px(6), px(10)))
        self.ruta = tk.Label(barra, text="", font=app.f_chico, fg=GRIS,
                             bg=PANEL, anchor="w")
        self.ruta.pack(side="left", fill="x", expand=True)

        zona = tk.Frame(self.cuerpo, bg=PANEL)
        zona.pack(fill="both", expand=True)
        izq = tk.Frame(zona, bg=PANEL_ALTO, highlightthickness=1,
                       highlightbackground=BORDE, width=px(300),
                       height=px(360))
        izq.pack(side="left", fill="y")
        izq.pack_propagate(False)
        self.lienzo, self.lista, self._enlazar = lista_desplazable(
            izq, PANEL_ALTO)
        self.lienzo.pack(fill="both", expand=True, padx=px(4), pady=px(4))
        der = tk.Frame(zona, bg=PANEL_ALTO, highlightthickness=1,
                       highlightbackground=BORDE)
        der.pack(side="left", fill="both", expand=True, padx=(px(10), 0))
        self.estado = tk.Label(der, text="Selecciona un programa para "
                               "verlo.", font=app.f_boton, fg=GRIS,
                               bg=PANEL_ALTO, anchor="w")
        self.estado.pack(fill="x", padx=px(10), pady=(px(8), px(4)))
        self.vista = tk.Text(der, font=app.f_mono, bg=PANEL_ALTO, fg=TINTA,
                             relief="flat", highlightthickness=0,
                             wrap="none", width=40, height=18,
                             padx=px(10), cursor="arrow")
        self.vista.pack(fill="both", expand=True, pady=(0, px(8)))
        etiquetas_de_codigo(self.vista, app)
        self.vista.tag_configure("error", background="#3A161C")
        self.vista.tag_configure("numero", foreground=GRIS_CLARO)

        self.elegir_btn = self.boton("Elegir", self.confirmar, "primario",
                                     "play", ancho=120)
        self.boton("Cancelar", self.cancelar, "fantasma")
        self.ventana.bind("<Return>", lambda _e: self.confirmar())
        self.abrir(self.carpeta)

    # ------------------------------------------------------------ carpetas
    def entradas(self, carpeta: Path) -> list[Path]:
        """Subcarpetas y archivos .txt, primero las carpetas."""
        try:
            todo = list(carpeta.iterdir())
        except OSError:
            return []
        carpetas = sorted((p for p in todo if p.is_dir()
                           and not p.name.startswith((".", "__"))),
                          key=lambda p: p.name.lower())
        archivos = sorted((p for p in todo if p.is_file()
                           and p.suffix.lower() == ".txt"),
                          key=lambda p: p.name.lower())
        return (carpetas + archivos)[:300]

    def abrir(self, carpeta: Path):
        app, px = self.app, self.app.px
        self.carpeta = Path(carpeta)
        self.elegido = None
        self.app.activar(self.elegir_btn, False)
        try:
            texto = self.carpeta.resolve().relative_to(
                app.raiz.resolve()).as_posix() or "."
        except ValueError:
            texto = str(self.carpeta)
        self.ruta.configure(text=texto)
        for w in self.lista.winfo_children():
            w.destroy()
        self._filas = {}
        entradas = self.entradas(self.carpeta)
        if not entradas:
            tk.Label(self.lista, text="No hay programas .txt aquí.",
                     font=app.f_chico, fg=GRIS_CLARO, bg=PANEL_ALTO
                     ).pack(anchor="w", padx=px(8), pady=px(8))
        for ruta in entradas:
            fila = tk.Frame(self.lista, bg=PANEL_ALTO, cursor="hand2")
            fila.pack(fill="x")
            dibujo = tk.Canvas(fila, width=px(22), height=px(22),
                               bg=PANEL_ALTO, highlightthickness=0)
            dibujo.pack(side="left", padx=(px(6), px(6)), pady=px(4))
            textos = tk.Frame(fila, bg=PANEL_ALTO)
            textos.pack(side="left", fill="x", expand=True)
            nombre = tk.Label(textos, text=ruta.name, font=app.f_texto,
                              fg=TINTA, bg=PANEL_ALTO, anchor="w")
            nombre.pack(fill="x")
            partes = [fila, dibujo, textos, nombre]
            if ruta.is_dir():
                icono(dibujo, "carpeta", px(11), px(11), px(16), ACENTO)
            else:
                resumen, tono = self._resumen(ruta)
                icono(dibujo, "lapiz", px(11), px(11), px(14), tono)
                nota = tk.Label(textos, text=resumen, font=app.f_chico,
                                fg=tono, bg=PANEL_ALTO, anchor="w")
                nota.pack(fill="x")
                partes.append(nota)
            for w in partes:
                w.bind("<Button-1>", lambda _e, r=ruta: self.seleccionar(r))
                w.bind("<Double-Button-1>",
                       lambda _e, r=ruta: self.activar_entrada(r))
            self._filas[ruta] = tuple(partes)
        self.lienzo.yview_moveto(0)
        self._enlazar()
        self.vista.configure(state="normal")
        self.vista.delete("1.0", "end")
        self.vista.configure(state="disabled")
        self.estado.configure(text="Selecciona un programa para verlo.",
                              fg=GRIS)

    def subir(self):
        if self.carpeta.parent != self.carpeta:
            self.abrir(self.carpeta.parent)

    @staticmethod
    def _resumen(ruta: Path) -> tuple[str, str]:
        programa, errores = Interprete().cargar(ruta)
        if not programa.instrucciones:
            return "✗ ninguna instrucción válida", ROJO_UI
        if errores:
            n = len(errores)
            return f"▲ {n} error{'es' if n > 1 else ''}", ACENTO
        return f"✓ {len(programa)} instrucciones", VERDE_OK

    # ------------------------------------------------------------ selección
    def seleccionar(self, ruta: Path):
        for r, partes in self._filas.items():
            tono = PANEL_HOVER if r == ruta else PANEL_ALTO
            for w in partes:
                try:
                    w.configure(bg=tono)
                except tk.TclError:
                    pass
        if ruta.is_dir():
            self.elegido = None
            self.app.activar(self.elegir_btn, False)
            self.estado.configure(text="Carpeta: doble clic para entrar.",
                                  fg=GRIS)
            return
        self.elegido = ruta
        self.app.activar(self.elegir_btn, True)
        self._previa(ruta)

    def activar_entrada(self, ruta: Path):
        if ruta.is_dir():
            self.abrir(ruta)
        else:
            self.seleccionar(ruta)
            self.confirmar()

    def _previa(self, ruta: Path):
        contenido = leer_programa(ruta) or ""
        _, errores = Interprete().analizar(contenido, nombre=ruta.stem)
        malas = {e.linea for e in errores}
        t = self.vista
        t.configure(state="normal")
        t.delete("1.0", "end")
        for n, cruda in enumerate(contenido.replace("﻿", "")
                                  .splitlines(), start=1):
            inicio = t.index("end-1c")
            t.insert("end", f"{n:>3}  ", "numero")
            codigo, hay, comentario = cruda.partition("#")
            for parte in _FICHA.findall(codigo):
                etiqueta = _etiqueta_de(parte)
                t.insert("end", parte, (etiqueta,) if etiqueta else ())
            if hay:
                t.insert("end", "#" + comentario, "comentario")
            t.insert("end", "\n")
            if n in malas:
                t.tag_add("error", inicio, t.index("end-1c"))
        t.configure(state="disabled")
        resumen, tono = self._resumen(ruta)
        self.estado.configure(text=f"{ruta.name}  ·  {resumen}", fg=tono)

    def confirmar(self):
        if self.elegido is not None:
            self.responder(self.elegido)


#: Nombre de archivo admitido para un programa: letras, números, guiones,
#: guiones bajos y espacios.
_NOMBRE_VALIDO = re.compile(r"^[\w\- ]+$")

_ETIQUETAS_CODIGO = tuple(f"p_{p}" for p in _COLOR_PALABRA) + (
    "direccion", "entero", "signo", "comentario")


class EditorPrograma:
    """Escribe o modifica el programa de un tanque sin salir del juego.

    Mientras se escribe, cada línea se revisa: el margen marca ✓ o ✗, las
    líneas con error se pintan en rojo (el globo y la lista de abajo dicen
    por qué) y un aviso resume si el programa está bien escrito. A la
    derecha están las instrucciones disponibles: un clic las inserta.
    «Aleatorio» escribe un programa válido que luego se puede modificar.
    """

    def __init__(self, app: "AppGrafica", ruta: Optional[Path],
                 numero: int, color: str, config: Configuracion,
                 al_guardar: Optional[Callable[[Path], None]] = None,
                 al_cerrar: Optional[Callable[[], None]] = None):
        self.app, self.numero, self.color = app, numero, color
        self.config = config
        self.ruta = Path(ruta) if ruta else None
        self.al_guardar, self.al_cerrar = al_guardar, al_cerrar
        self.globo = Globo(app)
        self._errores: dict[int, list] = {}
        self._buenas: set[int] = set()
        self._tarea: Optional[str] = None
        self.validas = self.con_error = 0
        self.guardado: Optional[Path] = None
        px = app.px

        v = tk.Toplevel(app.root, bg=FONDO_VENTANA)
        v.title(f"Programar el tanque {numero}")
        v.geometry(f"{px(1060)}x{px(720)}")
        v.minsize(px(840), px(540))
        v.protocol("WM_DELETE_WINDOW", self.cancelar)
        v.bind("<Escape>", lambda _e: self.cancelar())
        v.bind("<Control-s>", lambda _e: (self.guardar(), "break")[1])
        self.ventana = v

        self.cabeza = tk.Canvas(v, height=px(76), bg=FONDO_BARRA,
                                highlightthickness=0)
        self.cabeza.pack(fill="x")
        self.cabeza.bind("<Configure>", lambda _e: self._dibujar_cabeza())

        cuerpo = tk.Frame(v, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=px(16), pady=px(12))

        # --- el nombre del archivo
        fila = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        fila.pack(fill="x")
        app.rotulo(fila, "Nombre").pack(side="left")
        self.nombre = tk.StringVar(app.root, self.ruta.stem if self.ruta
                                   else self._nombre_libre())
        self.campo_nombre = app.campo_texto(fila, self.nombre, ancho=26)
        self.campo_nombre.pack(side="left", padx=(px(10), px(4)),
                               ipady=px(4))
        tk.Label(fila, text=".txt", font=app.f_texto, fg=GRIS,
                 bg=FONDO_VENTANA).pack(side="left")
        self.donde = tk.Label(fila, text="", font=app.f_chico,
                              fg=GRIS_CLARO, bg=FONDO_VENTANA, anchor="w")
        self.donde.pack(side="left", padx=(px(12), 0))

        # --- pie: acciones (se empaca antes que el centro para que nunca
        # quede fuera de la ventana)
        pie = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        pie.pack(side="bottom", fill="x", pady=(px(10), 0))
        app.boton(pie, "Aleatorio", self.aleatorio, icono="dado",
                  ayuda="Escribir un programa válido al azar; luego puedes "
                        "modificarlo").pack(side="left")
        app.boton(pie, "Borrar todo", self.limpiar, icono="x",
                  estilo="fantasma").pack(side="left", padx=px(8))
        app.boton(pie, "Guardar", self.guardar, primario=True,
                  icono="play", ancho=140,
                  ayuda="Guardar el programa  (Ctrl+S)").pack(side="right")
        app.boton(pie, "Cancelar", self.cancelar, estilo="fantasma",
                  icono="atras").pack(side="right", padx=px(8))

        centro = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        centro.pack(fill="both", expand=True, pady=(px(10), 0))

        # --- derecha: las instrucciones disponibles
        ayuda = Panel(centro, app, modo="ambos", relleno=12, acento=CIAN)
        ayuda.configure(width=px(330))
        ayuda.pack(side="right", fill="y", padx=(px(12), 0))
        self._catalogo(ayuda.cuerpo)

        # --- izquierda: el código con su margen y el resultado
        izq = tk.Frame(centro, bg=FONDO_VENTANA)
        izq.pack(side="left", fill="both", expand=True)
        self.estado = tk.Label(izq, text="", font=app.f_boton, fg=GRIS,
                               bg=FONDO_VENTANA, anchor="w",
                               justify="left")
        self.estado.pack(side="bottom", fill="x", pady=(px(8), 0))
        caja_err = Panel(izq, app, modo="x", relleno=8)
        caja_err.pack(side="bottom", fill="x", pady=(px(8), 0))
        self.lista = tk.Text(caja_err.cuerpo, height=4, font=app.f_chico,
                             bg=PANEL, fg=TINTA, relief="flat",
                             highlightthickness=0, wrap="word",
                             cursor="arrow", padx=px(4))
        self.lista.pack(fill="x")
        self.lista.tag_configure("linea", foreground=ROJO_UI,
                                 font=app.f_boton)
        self.lista.tag_configure("ok", foreground=VERDE_OK)
        self.lista.tag_configure("gris", foreground=GRIS)
        self.lista.tag_bind("ir", "<Button-1>", self._ir_a_error)
        self.lista.tag_bind("ir", "<Enter>",
                            lambda _e: self.lista.configure(cursor="hand2"))
        self.lista.tag_bind("ir", "<Leave>",
                            lambda _e: self.lista.configure(cursor="arrow"))

        caja = Panel(izq, app, modo="ambos", relleno=10, acento=color)
        caja.pack(fill="both", expand=True)
        self.margen = tk.Canvas(caja.cuerpo, width=px(52), bg=PANEL,
                                highlightthickness=0)
        self.margen.pack(side="left", fill="y")
        tk.Frame(caja.cuerpo, bg=BORDE, width=1).pack(side="left", fill="y")
        self.texto = tk.Text(caja.cuerpo, font=(app.f_mono[0], 11),
                             bg=PANEL, fg=TINTA, relief="flat",
                             highlightthickness=0, wrap="none",
                             undo=True, padx=px(8), pady=px(4),
                             spacing1=px(3), spacing3=px(3),
                             insertbackground=ACENTO, insertwidth=2,
                             selectbackground=ACENTO_OSCURO,
                             selectforeground=TINTA,
                             yscrollcommand=lambda *_a: self._pintar_margen())
        self.texto.pack(side="left", fill="both", expand=True)
        etiquetas_de_codigo(self.texto, app)
        for palabra in _COLOR_PALABRA:
            self.texto.tag_configure(f"p_{palabra}",
                                     font=(app.f_mono[0], 11, "bold"))
        self.texto.tag_configure("error", background="#3A161C",
                                 underline=True)
        self.texto.bind("<<Modified>>", self._modificado)
        self.texto.bind("<Motion>", self._sobre)
        self.texto.bind("<Leave>", lambda _e: self.globo.ocultar())
        self.texto.bind("<KeyRelease>", lambda _e: self._pintar_margen())

        contenido = leer_programa(self.ruta) if self.ruta else None
        if contenido:
            self.texto.insert("1.0", contenido.replace("﻿", ""))
        self.texto.edit_reset()
        self._original = (self.contenido(), self.nombre.get())
        self.nombre.trace_add("write", lambda *_a: self._pintar_donde())
        self._pintar_donde()
        self.revisar()
        v.transient(app.root)
        self.texto.focus_set()
        self.texto.mark_set("insert", "end-1c")

    # ------------------------------------------------------------ catálogo
    def _catalogo(self, padre):
        """La lista de instrucciones disponibles; un clic inserta una."""
        app, px = self.app, self.app.px
        app.rotulo(padre, "Instrucciones disponibles", color=CIAN
                   ).pack(anchor="w")
        tk.Label(padre, text="Clic para insertarla en el programa; luego "
                 "cambia la dirección o el número. La rueda del ratón "
                 "recorre la lista.", font=app.f_chico,
                 fg=GRIS, bg=PANEL, anchor="w", justify="left",
                 wraplength=px(300)).pack(fill="x", pady=(px(2), px(6)))
        # La lista va en un lienzo que se recorre con la rueda: así cabe
        # en ventanas bajas sin cortar nada.
        lienzo = tk.Canvas(padre, bg=PANEL, highlightthickness=0, bd=0)
        lienzo.pack(fill="both", expand=True)
        padre = tk.Frame(lienzo, bg=PANEL)
        dentro_id = lienzo.create_window(0, 0, window=padre, anchor="nw")
        padre.bind("<Configure>", lambda _e: lienzo.configure(
            scrollregion=lienzo.bbox("all")))
        lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(
            dentro_id, width=e.width))
        self.lista_instrucciones = lienzo

        def rueda(e):
            if lienzo.bbox("all") and                     lienzo.bbox("all")[3] > lienzo.winfo_height():
                lienzo.yview_scroll(-1 if e.delta > 0 else 1, "units")
        self._rueda = rueda
        self.fichas: dict[str, tk.Frame] = {}
        for plantilla, descripcion in CATALOGO:
            palabra = plantilla.split("(")[0].split()[0]
            if palabra == "IF":
                palabra = plantilla.split()[1].split("(")[0]
            tono = _COLOR_PALABRA.get(palabra, TINTA)
            ficha = tk.Frame(padre, bg=PANEL_ALTO, cursor="hand2")
            ficha.pack(fill="x", pady=px(2))
            tk.Frame(ficha, bg=tono, width=px(3)).pack(side="left",
                                                        fill="y")
            dentro = tk.Frame(ficha, bg=PANEL_ALTO)
            dentro.pack(side="left", fill="x", expand=True, padx=px(8),
                        pady=px(4))
            codigo = tk.Label(dentro, text=plantilla, bg=PANEL_ALTO,
                              fg=tono, font=(app.f_mono[0], 10, "bold"),
                              anchor="w")
            codigo.pack(fill="x")
            texto = tk.Label(dentro, text=descripcion, bg=PANEL_ALTO,
                             fg=GRIS, font=app.f_chico, anchor="w",
                             justify="left", wraplength=px(270))
            texto.pack(fill="x")
            partes = (ficha, dentro, codigo, texto)
            for w in partes:
                w.bind("<Button-1>",
                       lambda _e, p=plantilla: self._clic_ficha(p))
                w.bind("<Enter>", lambda _e, ws=partes: self._tenir(
                    ws, PANEL_HOVER))
                w.bind("<Leave>", lambda _e, ws=partes: self._tenir(
                    ws, PANEL_ALTO))
            self.fichas[plantilla] = ficha
        tk.Frame(padre, bg=BORDE, height=1).pack(fill="x",
                                                 pady=(px(8), px(6)))
        for nota in NOTAS:
            tk.Label(padre, text="•  " + nota, font=app.f_chico,
                     fg=GRIS, bg=PANEL, anchor="w", justify="left",
                     wraplength=px(290)).pack(fill="x", pady=px(1))
        pendientes = [lienzo]
        while pendientes:                 # la rueda funciona sobre todo
            w = pendientes.pop()
            w.bind("<MouseWheel>", rueda, add="+")
            pendientes.extend(w.winfo_children())

    @staticmethod
    def _tenir(widgets, color):
        for w in widgets:
            try:
                w.configure(bg=color)
            except tk.TclError:
                pass

    def _clic_ficha(self, plantilla: str):
        self.app.sonido.tocar("clic")
        self.insertar(plantilla)

    def insertar(self, plantilla: str):
        """Pone la instrucción en la línea del cursor, o en una nueva
        debajo si esa línea ya tiene algo."""
        t = self.texto
        if t.get("insert linestart", "insert lineend").strip():
            t.mark_set("insert", "insert lineend")
            t.insert("insert", "\n" + plantilla)
        else:
            t.delete("insert linestart", "insert lineend")
            t.insert("insert", plantilla)
        t.see("insert")
        t.focus_set()
        self.revisar()

    # ------------------------------------------------------------ revisión
    def contenido(self) -> str:
        return self.texto.get("1.0", "end-1c")

    def _modificado(self, _e=None):
        if not self.texto.edit_modified():
            return
        self.texto.edit_modified(False)
        if self._tarea is not None:
            self.texto.after_cancel(self._tarea)
        self._tarea = self.texto.after(150, self.revisar)

    def revisar(self):
        """Analiza el programa como lo hará el juego y lo dice al momento."""
        if self._tarea is not None:
            try:
                self.texto.after_cancel(self._tarea)
            except tk.TclError:
                pass
            self._tarea = None
        contenido = self.contenido()
        vacio = not contenido.strip()
        programa, errores = Interprete().analizar(
            contenido, nombre=self.nombre.get() or "programa")
        self._errores = {}
        for e in errores:
            if e.linea:
                self._errores.setdefault(e.linea, []).append(e)
        self._buenas = {i.linea for i in programa.instrucciones}
        self.validas = len(programa.instrucciones)
        self.con_error = len(self._errores)
        self._colorear(contenido)
        self._pintar_margen()
        self._pintar_lista(vacio)
        if vacio:
            texto, color = ("Escribe una instrucción por línea, elige una "
                            "de la derecha o pulsa «Aleatorio».", GRIS)
        elif not self.validas:
            texto, color = ("✗ Ninguna instrucción es válida: el tanque no "
                            "podría jugar. Revisa los avisos en rojo.",
                            ROJO_UI)
        elif self.con_error:
            n = self.con_error
            texto, color = (f"▲ {n} línea{'s' if n > 1 else ''} con "
                            f"error{'es' if n > 1 else ''}: se saltarán al "
                            f"jugar. Las otras {self.validas} están bien.",
                            ACENTO)
        else:
            n = self.validas
            texto, color = (f"✓ ¡Bien escrito! {n} instrucci"
                            f"{'ones' if n > 1 else 'ón'} válida"
                            f"{'s' if n > 1 else ''}.", VERDE_OK)
        self.estado.configure(text=texto, fg=color)
        self._dibujar_cabeza()

    def _colorear(self, contenido: str):
        t = self.texto
        for etiqueta in _ETIQUETAS_CODIGO + ("error",):
            t.tag_remove(etiqueta, "1.0", "end")
        for n, linea in enumerate(contenido.split("\n"), start=1):
            codigo, hay, _ = linea.partition("#")
            col = 0
            for parte in _FICHA.findall(codigo):
                etiqueta = _etiqueta_de(parte)
                if etiqueta:
                    t.tag_add(etiqueta, f"{n}.{col}",
                              f"{n}.{col + len(parte)}")
                col += len(parte)
            if hay:
                t.tag_add("comentario", f"{n}.{len(codigo)}", f"{n}.end")
            if n in self._errores:
                t.tag_add("error", f"{n}.0", f"{n}.end")

    def _pintar_margen(self):
        """Número de cada línea visible y si está bien (✓) o mal (✗)."""
        c, t, px = self.margen, self.texto, self.app.px
        try:
            c.delete("all")
            i = t.index("@0,0")
            while True:
                d = t.dlineinfo(i)
                if d is None:
                    break
                n = int(i.split(".")[0])
                y = d[1] + d[3] / 2
                mal = n in self._errores
                c.create_text(px(28), y, text=str(n), anchor="e",
                              fill=ROJO_UI if mal else GRIS_CLARO,
                              font=self.app.f_mono)
                if mal or n in self._buenas:
                    c.create_text(px(42), y, text="✗" if mal else "✓",
                                  fill=ROJO_UI if mal else VERDE_OK,
                                  font=self.app.f_boton)
                siguiente = t.index(f"{i}+1line")
                if siguiente == i:
                    break
                i = siguiente
        except tk.TclError:
            pass

    def _pintar_lista(self, vacio: bool):
        """Debajo del código: qué está mal en cada línea, o que todo va
        bien. Un clic en un error lleva a su línea."""
        lista = self.lista
        lista.configure(state="normal")
        lista.delete("1.0", "end")
        if vacio:
            lista.insert("end", "Aún no hay nada que revisar.", "gris")
        elif not self._errores:
            lista.insert("end", "Sin errores: cada línea es una "
                         "instrucción que el tanque entiende.", "ok")
        else:
            for n in sorted(self._errores):
                inicio = lista.index("end-1c")
                lista.insert("end", f"Línea {n}:  ", ("linea", f"l{n}"))
                lista.insert("end", self._errores[n][0].mensaje + "\n",
                             f"l{n}")
                lista.tag_add("ir", inicio, lista.index("end-1c"))
        lista.configure(state="disabled")

    def _ir_a_error(self, e):
        for etiqueta in self.lista.tag_names(f"@{e.x},{e.y}"):
            if re.fullmatch(r"l\d+", etiqueta):
                self.ir_a_linea(int(etiqueta[1:]))
                return

    def ir_a_linea(self, n: int):
        self.texto.mark_set("insert", f"{n}.end")
        self.texto.see("insert")
        self.texto.focus_set()

    def _sobre(self, e):
        t = self.texto
        n = int(t.index(f"@{e.x},{e.y}").split(".")[0])
        if n in self._errores:
            mensajes = "\n".join(f"• {err.mensaje}"
                                 for err in self._errores[n])
            self.globo.mostrar(self.ventana, e.x_root + self.app.px(18),
                               e.y_root + self.app.px(14),
                               f"Línea {n}: error",
                               f"{mensajes}\n\nSi la dejas así, se salta "
                               f"al jugar.")
        else:
            self.globo.ocultar()

    def _dibujar_cabeza(self):
        try:
            cabeza_programa(
                self.app, self.cabeza, self.numero, self.color,
                f"TANQUE {self.numero}  ·  EDITOR",
                f"{self._limpio() or 'sin nombre'}.txt",
                ((f"{self.con_error} con error",
                  ROJO_UI if self.con_error else GRIS_CLARO),
                 (f"{self.validas} válidas",
                  VERDE_OK if self.validas else GRIS_CLARO)))
        except tk.TclError:
            pass

    # ------------------------------------------------------------ archivo
    def _nombre_libre(self) -> str:
        carpeta = self.app.raiz / "tanques"
        nombre, k = f"mi_tanque{self.numero}", 2
        while (carpeta / f"{nombre}.txt").exists():
            nombre, k = f"mi_tanque{self.numero}-{k}", k + 1
        return nombre

    def _limpio(self) -> str:
        nombre = self.nombre.get().strip()
        return nombre[:-4] if nombre.lower().endswith(".txt") else nombre

    def destino(self) -> Path:
        """Dónde se guarda: junto al archivo original o en tanques/."""
        nombre = self._limpio()
        if self.ruta is not None:
            return self.ruta.with_name(f"{nombre}.txt")
        return self.app.raiz / "tanques" / f"{nombre}.txt"

    def _pintar_donde(self):
        nombre = self._limpio()
        if not nombre:
            self.donde.configure(text="✗ escribe un nombre", fg=ROJO_UI)
        elif not _NOMBRE_VALIDO.match(nombre):
            self.donde.configure(text="✗ usa letras, números, - o _",
                                 fg=ROJO_UI)
        else:
            destino = self.destino()
            try:
                texto = destino.resolve().relative_to(
                    self.app.raiz.resolve()).as_posix()
            except ValueError:
                texto = str(destino)
            nuevo = self.ruta is None or destino != self.ruta
            aviso = (" · ya existe: se reemplazará" if nuevo
                     and destino.exists() else "")
            self.donde.configure(text=f"se guarda en {texto}{aviso}",
                                 fg=ACENTO if aviso else GRIS_CLARO)
        self._dibujar_cabeza()

    def hay_cambios(self) -> bool:
        return (self.contenido(), self.nombre.get()) != self._original

    def _confirmar(self, titulo: str, texto: str, si: str = "Sí",
                   no: str = "Cancelar", peligro: bool = False) -> bool:
        return self.app.preguntar(self.ventana, titulo, texto, si, no,
                                  peligro)

    # ------------------------------------------------------------ acciones
    def aleatorio(self):
        """Escribe un programa válido al azar; se puede modificar luego."""
        if self.contenido().strip() and not self._confirmar(
                "Programa aleatorio", "¿Reemplazar lo que está escrito por "
                "un programa al azar? Después podrás modificarlo.",
                si="Reemplazar", peligro=True):
            return
        t = self.texto
        t.delete("1.0", "end")
        t.insert("1.0", generar_programa())
        t.mark_set("insert", "1.0")
        t.see("1.0")
        self.revisar()

    def limpiar(self):
        if self.contenido().strip() and self._confirmar(
                "Borrar todo", "¿Seguro que quieres borrar todo el "
                "programa?", si="Borrar", peligro=True):
            self.texto.delete("1.0", "end")
            self.revisar()

    def guardar(self) -> bool:
        """Revisa, avisa si algo no está bien y guarda el archivo."""
        nombre = self._limpio()
        if not nombre or not _NOMBRE_VALIDO.match(nombre):
            self.app.sonido.tocar("apagado")
            self._pintar_donde()
            self.campo_nombre.focus_set()
            return False
        self.revisar()
        if not self.validas:
            if not self._confirmar(
                    "Programa sin instrucciones válidas",
                    "Ninguna línea es una instrucción válida: el tanque no "
                    "podrá jugar con este programa.\n\n¿Guardarlo de todos "
                    "modos?", si="Guardar así", no="Seguir editando"):
                return False
        elif self.con_error:
            if not self._confirmar(
                    "Hay líneas con errores",
                    f"{self.con_error} líneas tienen errores y se saltarán "
                    f"al jugar.\n\n¿Guardar así?", si="Guardar así",
                    no="Seguir editando"):
                return False
        destino = self.destino()
        if destino.exists() and destino != self.ruta and not self._confirmar(
                "El archivo ya existe",
                f"Ya hay un programa llamado {destino.name}.\n\n"
                f"¿Reemplazarlo?", si="Reemplazar", peligro=True):
            return False
        contenido = self.contenido()
        if contenido and not contenido.endswith("\n"):
            contenido += "\n"
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8")
        except OSError as e:
            self.app.avisar(self.ventana, "No se pudo guardar",
                            f"No se pudo escribir {destino.name}.", str(e))
            return False
        self.guardado = self.ruta = destino
        self._original = (self.contenido(), self.nombre.get())
        if self.al_guardar:
            self.al_guardar(destino)
        self.cerrar()
        return True

    def cancelar(self):
        if self.hay_cambios() and not self._confirmar(
                "Salir sin guardar", "Hay cambios sin guardar. ¿Salir y "
                "perderlos?", si="Salir sin guardar", no="Seguir editando",
                peligro=True):
            return
        self.cerrar()

    def cerrar(self):
        self.globo.ocultar()
        if self._tarea is not None:
            try:
                self.texto.after_cancel(self._tarea)
            except tk.TclError:
                pass
            self._tarea = None
        try:
            self.ventana.destroy()
        except tk.TclError:
            pass
        if self.al_cerrar:
            self.al_cerrar()


# ======================================================================
class AppGrafica:
    """La ventana principal y la navegación entre pantallas."""

    def __init__(self, raiz: str | Path = "."):
        self.raiz = Path(raiz)
        activar_dpi()
        self.root = tk.Tk()
        self.escala = max(1.0, self.root.winfo_fpixels("1i") / 96)
        self.root.title("Guerra de tanques")
        self.root.configure(bg=FONDO_VENTANA)
        self.root.minsize(self.px(900), self.px(620))
        self._atajos: list[str] = []
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.cerrada = False
        self._eleccion = tk.StringVar(self.root)
        self._pantalla: Optional[tk.Frame] = None
        self._partida: Optional["VentanaPartida"] = None
        self._portada: dict = {}
        self.sonido = Sonido()
        self._intro_tocada = False
        self._controles_musica: list = []
        self._desplegable: Optional[Panel] = None
        self._proveedor = None
        self._interruptores: dict[str, Boton] = {}
        self.opciones_menu: dict[str, Boton] = {}
        self._subtitulo_menu: Optional[tk.Label] = None
        self._fuentes()

    # ---------------------------------------------------------- utilidades
    def _fuentes(self):
        familias = set(tkfont.families(self.root))
        texto = next((f for f in ("Segoe UI", "Inter", "Helvetica",
                                  "DejaVu Sans") if f in familias),
                     "TkDefaultFont")
        negra = next((f for f in ("Segoe UI Black", "Segoe UI Semibold",
                                  texto) if f in familias), texto)
        semi = next((f for f in ("Segoe UI Semibold", texto)
                     if f in familias), texto)
        mono = next((f for f in ("Cascadia Mono", "Consolas", "Menlo",
                                 "DejaVu Sans Mono") if f in familias),
                    "TkFixedFont")
        self.f_portada = (negra, 40)
        self.f_titulo = (negra, 26)
        self.f_vida = (negra, 20)
        self.f_barra = (semi, 14)
        self.f_seccion = (semi, 12)
        self.f_grande = (semi, 17)
        self.f_texto = (texto, 10)
        self.f_chico = (texto, 9)
        self.f_mini = (semi, 8)
        self.f_mono = (mono, 9)
        self.f_boton = (semi, 10)
        self.fuente_boton = tkfont.Font(root=self.root, font=self.f_boton)

    def px(self, medida: float) -> int:
        """Píxeles a 96 ppp → píxeles de esta pantalla."""
        return int(round(medida * self.escala))

    def boton(self, padre, texto, orden, ancho=0, primario=False,
              estilo: Optional[str] = None, icono: Optional[str] = None,
              alto: int = 36, ayuda: str = "",
              sonido: Optional[str] = "auto") -> Boton:
        """Botón de la aplicación; `ancho` es el mínimo en píxeles a 96 ppp.

        No toma el foco: así la barra espaciadora es siempre el atajo de
        la pantalla y no «pulsa» el último botón usado.
        """
        return Boton(padre, self, texto, orden,
                     estilo or ("primario" if primario else "secundario"),
                     icono, minimo=ancho, alto=alto, ayuda=ayuda,
                     sonido=sonido)

    # ---------------------------------------------------------- sonido
    def _pintar_interruptores(self):
        """Los interruptores del menú muestran lo que está encendido."""
        musica = self._interruptores.get("musica")
        efectos = self._interruptores.get("efectos")
        try:
            if musica is not None:
                musica.texto = ("Encendida" if self.sonido.musica_activa
                                else "Apagada")
                musica.icono = "nota" if self.sonido.musica_activa else "mudo"
                musica._dibujar()
            if efectos is not None:
                efectos.texto = ("Encendidos" if self.sonido.efectos
                                 else "Apagados")
                efectos.icono = "sonido" if self.sonido.efectos else "mudo"
                efectos._dibujar()
        except tk.TclError:
            pass

    def alternar_musica(self):
        """Música sí / no, sin tocar los efectos."""
        if not self.sonido.disponible:
            return
        self.sonido.alternar_musica()
        self.sonido.tocar("clic")
        self._pintar_interruptores()

    def alternar_efectos(self):
        """Efectos sí / no (disparos, botones…), sin tocar la música."""
        if not self.sonido.disponible:
            return
        if self.sonido.alternar_efectos():
            self.sonido.tocar("clic")
        self._pintar_interruptores()

    # ---------------------------------------------------------- menú ☰
    def poner_menu(self, proveedor):
        """La pantalla agrega sus opciones al menú de arriba a la derecha.

        `proveedor` tiene `opciones_del_menu()` → (título, subtítulo,
        [(clave, texto, ícono, orden, estilo, activo)]), `al_abrir_menu()`
        (False lo impide) y `al_cerrar_menu(continuar)`.
        """
        self._proveedor = proveedor

    def alternar_menu(self):
        if self._desplegable is not None:
            self.cerrar_menu(continuar=True)
        else:
            self.abrir_menu()

    def abrir_menu(self):
        """Despliega el menú bajo el botón ☰: las opciones de la pantalla
        (en la partida: continuar, reiniciar, volver a los tanques,
        terminar, menú principal) y el sonido, música y efectos por
        separado."""
        if self._desplegable is not None or self._pantalla is None:
            return
        prov = self._proveedor
        if prov is not None and prov.al_abrir_menu() is False:
            return
        px = self.px
        menu = Panel(self._pantalla, self, modo="ajustar", relleno=16,
                     acento=ACENTO)
        cuerpo = menu.cuerpo
        self.opciones_menu = {}
        if prov is not None:
            titulo, subtitulo, opciones = prov.opciones_del_menu()
            self.rotulo(cuerpo, titulo).pack(anchor="w")
            self._subtitulo_menu = tk.Label(cuerpo, text=subtitulo,
                                            font=self.f_chico, fg=GRIS,
                                            bg=PANEL, anchor="w")
            self._subtitulo_menu.pack(fill="x", pady=(px(2), px(10)))
            for clave, texto, simbolo, orden, estilo, activo in opciones:
                b = self.boton(cuerpo, texto, orden, ancho=290, alto=38,
                               icono=simbolo, estilo=estilo,
                               sonido="atras" if simbolo == "casa"
                               else "auto")
                b.pack(fill="x", pady=px(3))
                if not activo:
                    self.activar(b, False)
                self.opciones_menu[clave] = b
            tk.Frame(cuerpo, bg=BORDE, height=1).pack(
                fill="x", pady=(px(12), px(10)))
        self.rotulo(cuerpo, "Sonido", color=CIAN).pack(anchor="w")
        rejilla = tk.Frame(cuerpo, bg=PANEL)
        rejilla.pack(fill="x", pady=(px(6), 0))
        rejilla.columnconfigure(1, weight=1)
        self._interruptores = {}
        for fila, (clave, texto, orden) in enumerate((
                ("musica", "Música", self.alternar_musica),
                ("efectos", "Efectos", self.alternar_efectos))):
            tk.Label(rejilla, text=texto, font=self.f_texto, fg=TINTA,
                     bg=PANEL, anchor="w").grid(row=2 * fila, column=0,
                                                sticky="w", pady=px(3))
            b = self.boton(rejilla, "Encendidos", orden, ancho=140, alto=32,
                           icono="sonido", estilo="secundario", sonido=None)
            b.grid(row=2 * fila, column=1, sticky="e", pady=px(3))
            if not self.sonido.disponible:
                self.activar(b, False)
            self._interruptores[clave] = b
            if clave == "musica":
                ControlMusica(rejilla, self).grid(
                    row=1, column=0, columnspan=2, sticky="e",
                    pady=(0, px(6)))
        self._pintar_interruptores()
        tk.Label(cuerpo, text="Esc cerrar", font=self.f_chico,
                 fg=GRIS_CLARO, bg=PANEL).pack(pady=(px(10), 0))
        menu.place(relx=1, x=-px(14), y=px(54), anchor="ne")
        tk.Misc.tkraise(menu)              # Panel es Canvas: su lift() es otro
        self._desplegable = menu

    def refrescar_menu(self):
        """Pone al día el menú abierto (la partida sigue mientras tanto):
        la ronda, el estado y qué opciones se pueden usar."""
        prov = self._proveedor
        if self._desplegable is None or prov is None:
            return
        try:
            _, subtitulo, opciones = prov.opciones_del_menu()
            if self._subtitulo_menu is not None:
                self._subtitulo_menu.configure(text=subtitulo)
            for clave, texto, simbolo, _o, _e, activo in opciones:
                b = self.opciones_menu.get(clave)
                if b is None:
                    continue
                if (b.texto, b.icono) != (texto, simbolo):
                    b.texto, b.icono = texto, simbolo
                    b._dibujar()
                if (str(b["state"]) == "normal") != activo:
                    self.activar(b, activo)
        except tk.TclError:
            pass

    def cerrar_menu(self, continuar: bool = False):
        if self._desplegable is None:
            return
        try:
            self._desplegable.destroy()
        except tk.TclError:
            pass
        self._desplegable = None
        self._subtitulo_menu = None
        self._interruptores = {}
        if self._proveedor is not None:
            self._proveedor.al_cerrar_menu(continuar)

    def _intro(self, intentos=40):
        """El sonido de arranque, en cuanto los WAV estén listos; luego
        entra la música, que ya no se detiene al cambiar de pantalla."""
        if self._intro_tocada or not self.sonido.disponible:
            return
        if not self.sonido.listo:
            if intentos:
                self.root.after(100, lambda: self._intro(intentos - 1))
            return
        self._intro_tocada = True
        self.sonido.tocar("intro")
        self.root.after(1600, self._arrancar_musica)

    def _arrancar_musica(self, intentos=75):
        """La canción se sintetiza después de los efectos: se espera."""
        if self.sonido.hay_musica:
            self.sonido.musica()
        elif intentos and self.sonido.disponible:
            self.root.after(200, lambda: self._arrancar_musica(intentos - 1))

    def cambiar_volumen_musica(self, volumen: int):
        """Sube o baja la música (0 a 10). Subirla con la música apagada
        la enciende; los efectos no cambian."""
        if volumen > 0 and not self.sonido.musica_activa:
            self.sonido.alternar_musica()
        self.sonido.cambiar_volumen_musica(volumen)
        self._pintar_interruptores()
        for c in self._controles_musica:
            try:
                c.refrescar()
            except tk.TclError:
                pass

    def activar(self, boton, activo: bool):
        boton.configure(state="normal" if activo else "disabled")

    def atajo(self, secuencia: str, orden, sonido: Optional[str] = "clic"):
        """Tecla de la pantalla actual; se olvida al cambiar de pantalla.

        Suena como el botón que reemplaza.
        """
        def accion(_e):
            if sonido:
                self.sonido.tocar(sonido)
            orden()
            return "break"
        self.root.bind(secuencia, accion)
        self._atajos.append(secuencia)

    def rotulo(self, padre, texto, color=ACENTO, fondo=None):
        """Rótulo de sección: mayúsculas espaciadas en color."""
        return tk.Label(padre, text=espaciado(texto.upper()),
                        font=self.f_mini, fg=color,
                        bg=fondo or _fondo_de(padre))

    def bloque_centrado(self, padre, ancho_maximo: int, margen: int = 24,
                        con_pie: bool = False):
        """El marco del contenido de una pantalla. En la ventana normal
        ocupa lo de siempre; en una grande (pantalla completa) queda
        centrado y con un ancho máximo, en vez de estirarse a lo ancho y
        quedarse pegado arriba.

        Nunca pide más alto que el de la pantalla: si el contenido no cabe
        (pantalla chica o con escala alta), se recorre con la rueda del
        ratón. Con `con_pie` devuelve también un pie fijo abajo, siempre
        visible, para los botones de la pantalla: `(bloque, pie)`.
        """
        px = self.px
        mx, my = px(margen), px(12)
        pie = None
        if con_pie:
            tira = tk.Frame(padre, bg=FONDO_VENTANA)
            tira.pack(side="bottom", fill="x")
            tira.pack_propagate(False)      # su alto lo fija `acomodar`
            tk.Frame(tira, bg=BORDE, height=1).pack(fill="x")
            pie = tk.Frame(tira, bg=FONDO_VENTANA)
        zona = tk.Frame(padre, bg=FONDO_VENTANA)
        zona.pack(fill="both", expand=True)
        bloque = tk.Frame(zona, bg=FONDO_VENTANA)
        barra = tk.Frame(zona, bg=BORDE, width=px(4))
        estado = {"bajado": 0, "exceso": 0}

        def acomodar(_e=None):
            try:
                req_w = bloque.winfo_reqwidth()
                req_h = bloque.winfo_reqheight()
                # Lo que pide la zona es lo natural del contenido (así no
                # cambia el tamaño de la ventana normal), con el alto de la
                # pantalla como tope.
                otros = self.root.winfo_reqheight() - int(zona["height"])
                tope = max(px(240), self.root.winfo_screenheight()
                           - px(MARGEN_PANTALLA) - otros)
                pedido = (req_w + 2 * mx, min(req_h + 2 * my, tope))
                if (int(zona["width"]), int(zona["height"])) != pedido:
                    zona.configure(width=pedido[0], height=pedido[1])
                    self.root.after_idle(self._dentro_de_pantalla)
                if pie is not None:
                    alto_pie = pie.winfo_reqheight() + px(10) + my
                    if int(tira["height"]) != alto_pie:
                        tira.configure(height=alto_pie)
                W, H = zona.winfo_width(), zona.winfo_height()
                if W <= 1:
                    return
                ancho = min(W - 2 * mx, max(px(ancho_maximo), req_w))
                x = (W - ancho) // 2
                exceso = req_h + 2 * my - H
                estado["exceso"] = max(0, exceso)
                if exceso > 0:
                    bajado = min(max(0, estado["bajado"]), exceso)
                    estado["bajado"] = bajado
                    y = my - bajado
                    total = req_h + 2 * my
                    alto_barra = max(px(30), H * H // total)
                    barra.place(x=W - px(6),
                                y=(H - alto_barra) * bajado // exceso,
                                width=px(4), height=alto_barra)
                    barra.lift()
                else:
                    estado["bajado"] = 0
                    y = max(my, (H - req_h) // 2)
                    barra.place_forget()
                bloque.place(x=x, y=y, width=ancho)
                if pie is not None:
                    pie.place(x=x, y=px(10), width=ancho)
            except tk.TclError:
                pass

        def rueda(e):
            if estado["exceso"] <= 0:
                return None
            try:
                w = e.widget
                if not str(w).startswith(str(zona)) or \
                        w.bind("<MouseWheel>"):
                    return None             # el control usa su rueda
            except (tk.TclError, AttributeError):
                return None
            estado["bajado"] -= (1 if e.delta > 0 else -1) * px(60)
            acomodar()
            return "break"

        self.root.bind("<MouseWheel>", rueda)
        self._atajos.append("<MouseWheel>")
        zona.bind("<Configure>", acomodar)
        bloque.bind("<Configure>", acomodar)
        if pie is not None:
            pie.bind("<Configure>", acomodar)
        zona.after_idle(acomodar)
        return (bloque, pie) if con_pie else bloque

    def _dentro_de_pantalla(self):
        """Si la ventana (normal, no maximizada) se sale por abajo o por
        la derecha de la pantalla, la sube para que se vea completa."""
        root = self.root
        try:
            if root.state() != "normal":
                return
            root.update_idletasks()
            x, y = root.winfo_x(), root.winfo_y()
            w = max(root.winfo_width(), root.winfo_reqwidth())
            h = max(root.winfo_height(), root.winfo_reqheight())
            # El marco y la barra de título de Windows más la barra de
            # tareas: lo que MARGEN_PANTALLA ya reserva.
            limite_y = root.winfo_screenheight() - self.px(MARGEN_PANTALLA)
            limite_x = root.winfo_screenwidth() - self.px(16)
            nx = max(0, min(x, limite_x - w))
            ny = max(0, min(y, limite_y - h))
            if (nx, ny) != (x, y):
                root.geometry(f"+{nx}+{ny}")
        except tk.TclError:
            pass

    def campo_texto(self, padre, variable, ancho=None) -> tk.Entry:
        e = tk.Entry(padre, textvariable=variable, font=self.f_texto,
                     relief="flat", bd=0, bg=PANEL_ALTO, fg=TINTA,
                     highlightthickness=1, highlightbackground=BORDE,
                     highlightcolor=ACENTO, insertbackground=ACENTO,
                     selectbackground=ACENTO, selectforeground=TINTA_ACENTO)
        if ancho:
            e.configure(width=ancho)
        return e

    def _nueva_pantalla(self, titulo: str, encabezado=True) -> tk.Frame:
        self._portada = {}
        self._desplegable = None
        self._subtitulo_menu = None
        self._proveedor = None
        self._interruptores = {}
        self.opciones_menu = {}
        for secuencia in self._atajos:
            self.root.unbind(secuencia)
        self._atajos = []
        if self._pantalla is not None:
            self._pantalla.destroy()
        self._pantalla = tk.Frame(self.root, bg=FONDO_VENTANA)
        self._pantalla.pack(fill="both", expand=True)
        barra = tk.Canvas(self._pantalla, height=self.px(58),
                          bg=FONDO_BARRA, highlightthickness=0)
        if encabezado:
            barra.pack(fill="x")
        px = self.px
        sprites.tanque(barra, px(32), px(29), px(34), 1, ACENTO,
                       Direccion.E, etiqueta="icono")
        self.titulo_barra = _Rotulo(barra, barra.create_text(
            px(62), px(29), text=titulo, anchor="w", fill=TINTA,
            font=self.f_barra))
        sub = barra.create_text(0, px(29), text="", anchor="e", fill=GRIS,
                                font=self.f_chico)
        self.subtitulo_barra = _Rotulo(barra, sub)

        def redibujar(e):
            barra.delete("fondo")
            degradado(barra, e.width, e.height, "#132235", FONDO_BARRA,
                      horizontal=True, pasos=32)
            for k in range(40):                    # filo dorado que se apaga
                barra.create_line(e.width * k / 40, e.height - 2,
                                  e.width * (k + 1) / 40 + 1, e.height - 2,
                                  width=2, tags="fondo",
                                  fill=sprites.mezclar(ACENTO, FONDO_BARRA,
                                                       k / 40))
            barra.tag_lower("fondo")
            barra.coords(sub, e.width - px(66), px(29))

        barra.bind("<Configure>", redibujar)
        # El menú ☰, siempre arriba a la derecha (encima del encabezado o
        # de la portada); se sube cuando la pantalla ya tiene su contenido.
        boton = self.boton(self._pantalla, "", self.alternar_menu,
                           icono="menu", estilo="fantasma", alto=38,
                           ancho=38, ayuda="Menú  (Esc)")
        boton.configure(bg=FONDO_BARRA if encabezado else "#0B1626")
        boton.place(relx=1, x=-px(14), y=px(10), anchor="ne")
        self.boton_menu = boton
        self.root.after_idle(lambda: self._subir(boton))
        return self._pantalla

    @staticmethod
    def _subir(widget):
        try:
            tk.Misc.tkraise(widget)
        except tk.TclError:
            pass

    def _esperar(self) -> str:
        """Atiende eventos hasta que el usuario elige algo."""
        if self.cerrada:
            return "salir"
        self._eleccion.set("")
        self.root.wait_variable(self._eleccion)
        return "salir" if self.cerrada else self._eleccion.get()

    def _elegir(self, valor: str):
        self._eleccion.set(valor)

    def _al_cerrar(self):
        self.cerrada = True
        if self._partida is not None:
            self._partida.cerrar()
        self._eleccion.set("salir")

    def destruir(self):
        self.sonido.cerrar()
        try:
            # Los temporizadores pendientes (animación de la portada, luces
            # del tablero…) se cancelan: si no, Tk los corre ya sin ventana.
            for tarea in self.root.tk.splitlist(
                    self.root.tk.call("after", "info")):
                self.root.after_cancel(tarea)
            self.root.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------- portada
    def menu(self) -> str:
        """Figura 10, como portada animada. Devuelve 'iniciar', 'ayuda' o
        'salir'."""
        p = self._nueva_pantalla("Guerra de tanques", encabezado=False)
        lienzo = tk.Canvas(p, bg=NOCHE, highlightthickness=0,
                           width=self.px(1000), height=self.px(680))
        lienzo.pack(fill="both", expand=True)
        botones = [
            self.boton(lienzo, "INICIAR PARTIDA",
                       lambda: self._elegir("iniciar"), ancho=290,
                       primario=True, icono="play", alto=50),
            self.boton(lienzo, "Cómo jugar", lambda: self._elegir("ayuda"),
                       ancho=290, estilo="fantasma", icono="ayuda", alto=42),
            self.boton(lienzo, "Salir", lambda: self._elegir("salir"),
                       ancho=290, estilo="fantasma", icono="salir", alto=42)]
        self._portada = {"c": lienzo, "botones": botones, "tanques": [],
                         "angulo": 0, "listo": False}
        lienzo.bind("<Configure>", lambda e: self._dibujar_portada(
            e.width, e.height))
        self.atajo("<Return>", lambda: self._elegir("iniciar"), "confirmar")
        self.atajo("<F1>", lambda: self._elegir("ayuda"))
        self.atajo("<Escape>", self.alternar_menu)
        self.root.after(40, self._animar_portada)
        self._intro()
        return self._esperar()

    def _dibujar_portada(self, w, h):
        est = self._portada
        c = est["c"]
        # En una pantalla grande el título, el radar y el desfile crecen
        # con ella (hasta 1.3 veces) y no se quedan chicos en el centro.
        # Los botones conservan su tamaño y su separación.
        k = max(1.0, min(w / self.px(1000), h / self.px(680), 1.3))

        def px(medida):
            return self.px(medida * k)
        c.delete("all")
        cielo_arriba, cielo_abajo = "#0B1626", "#152A44"
        horizonte = h * 0.66
        degradado(c, w, horizonte, cielo_arriba, cielo_abajo)
        c.create_rectangle(0, horizonte, w, h, fill="#070D15", width=0)
        for k in range(14):                       # resplandor del horizonte
            c.create_line(0, horizonte + k, w, horizonte + k,
                          fill=sprites.mezclar("#3B5E86", "#070D15", k / 14))
        # Piso en perspectiva, como el tablero que se aleja.
        fuga = w / 2
        for k in range(-14, 15):
            c.create_line(fuga + k * px(18), horizonte, fuga + k * px(150), h,
                          fill="#14263B")
        for k in range(1, 9):
            y = horizonte + (h - horizonte) * (k / 8) ** 1.8
            c.create_line(0, y, w, y, fill="#14263B")

        # Radar detrás del título.
        cx, cy = w / 2, h * 0.25
        for r in (px(80), px(150), px(220), px(290)):
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#13253A")
        c.create_line(cx - px(300), cy, cx + px(300), cy, fill="#112135")
        c.create_line(cx, cy - px(300), cx, cy + px(300), fill="#112135")
        r = px(290)
        for k, color in enumerate(("#183552", "#15304A", "#132A41")):
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=est["angulo"]
                         + k * 14, extent=14, fill=color, outline="",
                         tags=("barrido", f"barrido{k}"))
        c.tag_lower("barrido")
        c.tag_lower("fondo")

        # Título con sombra y resplandor dorado.
        ty = h * 0.2
        titulo = (self.f_portada[0], round(self.f_portada[1] * k))
        c.create_text(w / 2 + px(4), ty + px(5), text="GUERRA DE TANQUES",
                      font=titulo, fill="#000000")
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            c.create_text(w / 2 + dx * k, ty + dy * k,
                          text="GUERRA DE TANQUES", font=titulo,
                          fill=ACENTO_OSCURO)
        c.create_text(w / 2, ty, text="GUERRA DE TANQUES",
                      font=titulo, fill=ACENTO)
        c.create_text(w / 2, ty + px(48),
                      text=espaciado("SIMULADOR DE COMBATE AUTÓNOMO"),
                      font=(self.f_mini[0], round(self.f_mini[1] * k)),
                      fill=CIAN)
        c.create_text(w / 2, ty + px(76),
                      text="Programa tu tanque. Míralo pelear.",
                      font=(self.f_texto[0], round(12 * k)), fill=GRIS)

        y = ty + px(110) + self.px(30)
        for b in est["botones"]:
            fondo = sprites.mezclar(cielo_arriba, cielo_abajo,
                                    min(1, y / horizonte))
            b.configure(bg=fondo)
            c.create_window(w / 2, y, window=b)
            y += self.px(56)
        c.create_text(w / 2, y - self.px(8),
                      text="Enter  iniciar   ·   F1  ayuda   ·   ☰ / Esc  menú",
                      font=self.f_chico, fill=GRIS_CLARO)


        # Desfile de tanques sobre el piso: tres carriles, dos sentidos.
        est["tanques"] = []
        carriles = ((horizonte + (h - horizonte) * 0.22, px(38), 1.2),
                    (horizonte + (h - horizonte) * 0.5, px(52), -1.7),
                    (horizonte + (h - horizonte) * 0.8, px(66), 2.3))
        for i, color in enumerate(sprites.COLORES_TANQUE):
            cy_, s, v = carriles[i % 3]
            x = (w * (0.15 + 0.55 * (i // 3))) % w
            sentido = Direccion.E if v > 0 else Direccion.O
            etiqueta = f"desfile{i}"
            c.create_oval(x - s * 0.45, cy_ + s * 0.32, x + s * 0.45,
                          cy_ + s * 0.46, fill="#03070C", width=0,
                          tags=(etiqueta,))
            sprites.tanque(c, x, cy_, s, i + 1, color, sentido,
                           etiqueta=etiqueta)
            est["tanques"].append({"tag": etiqueta, "x": x, "v": px(v),
                                   "s": s})
        est["w"], est["listo"] = w, True

    def _animar_portada(self):
        est = self._portada
        c = est.get("c")
        try:
            if c is None or not c.winfo_exists():
                return
        except tk.TclError:
            return
        if est.get("listo"):
            est["angulo"] = (est["angulo"] - 3) % 360
            if est["angulo"] == 90:          # el barrido pasa por arriba
                self.sonido.tocar("barrido")
            for k in range(3):
                c.itemconfigure(f"barrido{k}", start=est["angulo"] + k * 14)
            w = est["w"]
            for t in est["tanques"]:
                t["x"] += t["v"]
                salto = 0
                if t["v"] > 0 and t["x"] > w + t["s"]:
                    salto = -(w + 2 * t["s"])
                elif t["v"] < 0 and t["x"] < -t["s"]:
                    salto = w + 2 * t["s"]
                t["x"] += salto
                c.move(t["tag"], t["v"] + salto, 0)
        self.root.after(33, self._animar_portada)

    # ---------------------------------------------------------- ayuda
    def ayuda(self):
        px = self.px
        ventana = tk.Toplevel(self.root, bg=PANEL)
        ventana.title("Cómo jugar")
        ventana.geometry(f"{px(700)}x{px(660)}")
        cabeza = tk.Canvas(ventana, height=px(54), bg=FONDO_BARRA,
                           highlightthickness=0)
        cabeza.pack(fill="x")
        icono(cabeza, "ayuda", px(30), px(27), px(22), ACENTO)
        cabeza.create_text(px(52), px(27), text="Cómo jugar", anchor="w",
                           fill=TINTA, font=self.f_barra)
        pie = tk.Frame(ventana, bg=PANEL)
        pie.pack(side="bottom", fill="x")
        self.boton(pie, "Entendido", ventana.destroy, ancho=130,
                   primario=True).pack(side="right", padx=px(16),
                                       pady=px(10))
        texto = tk.Text(ventana, wrap="word", font=self.f_texto,
                        padx=px(24), pady=px(10), relief="flat", bg=PANEL,
                        fg=TINTA, spacing1=2, spacing3=2,
                        highlightthickness=0, insertbackground=TINTA)
        # Sin barra de desplazamiento: la de Windows no admite colores.
        texto.pack(fill="both", expand=True)
        texto.focus_set()                  # la rueda del ratón lo recorre
        texto.tag_configure("h", font=self.f_seccion, foreground=ACENTO,
                            spacing1=px(16), spacing3=px(4))
        texto.tag_configure("m", font=self.f_mono, foreground="#BFE9F7",
                            background=PANEL_ALTO, lmargin1=px(10),
                            lmargin2=px(10))
        for estilo, linea in AYUDA:
            texto.insert("end", linea + "\n", estilo)
        texto.configure(state="disabled")
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind("<Escape>", lambda _e: ventana.destroy())
        self.root.wait_window(ventana)

    # ---------------------------------------------------- ventanas emergentes
    def dialogo(self, padre, titulo: str, texto: str, tipo: str = "pregunta",
                botones=(("Aceptar", True, "primario"),), detalle: str = "",
                cancelar=None):
        """Toda pregunta o aviso pasa por aquí, con el diseño del juego (las
        pruebas lo sustituyen para no esperar a nadie)."""
        return Dialogo(self, padre, titulo, texto, tipo, botones, detalle,
                       cancelar).mostrar()

    def preguntar(self, padre, titulo: str, texto: str, si: str = "Sí",
                  no: str = "Cancelar", peligro: bool = False) -> bool:
        """Sí o no. Con `peligro` (borrar, reemplazar, perder cambios) la
        ventana y el botón van en rojo."""
        return bool(self.dialogo(
            padre, titulo, texto, "peligro" if peligro else "pregunta",
            ((no, False, "fantasma"),
             (si, True, "peligro" if peligro else "primario")),
            cancelar=False))

    def avisar(self, padre, titulo: str, texto: str, detalle: str = "",
               tipo: str = "error"):
        self.dialogo(padre, titulo, texto, tipo,
                     (("Entendido", True, "primario"),), detalle)

    def elegir_color(self, padre, numero: int,
                     color: str) -> Optional[str]:
        return SelectorColor(self, padre, numero, color).mostrar()

    def elegir_programa(self, padre, numero: int,
                        inicial: Optional[Path] = None) -> Optional[Path]:
        return SelectorPrograma(self, padre, numero, inicial).mostrar()

    # ---------------------------------------------------------- configuración
    def configurar(self, config: Configuracion) -> Optional[Configuracion]:
        """Figura 11. Devuelve la configuración elegida, o None para volver."""
        pantalla = PantallaConfiguracion(self, config)
        while True:
            eleccion = self._esperar()
            if eleccion != "iniciar":
                return None
            nueva, problemas = pantalla.leer()
            if not problemas:
                return nueva
            self.avisar(self.root, "Configuración incompleta",
                        "Corrige esto antes de iniciar la batalla:",
                        "\n".join(f"• {p}" for p in problemas), "aviso")

    def mostrar_errores(self, texto: str):
        lineas = texto.splitlines()
        if lineas and lineas[0].endswith(":"):
            titular, detalle = lineas[0], "\n".join(l.strip()
                                                   for l in lineas[1:])
        else:
            titular, detalle = "Revisa los programas de los tanques.", texto
        self.avisar(self.root, "Errores en los programas", titular, detalle)

    # ---------------------------------------------------------- partida
    def partida(self, config: Configuracion, velocidad: int = 5,
                saltadas=()) -> "VentanaPartida":
        self._partida = VentanaPartida(self, config, velocidad, saltadas)
        return self._partida


# ======================================================================
class PantallaConfiguracion:
    """Arma el escuadrón (un programa y un color por tanque) y las reglas.

    Cada programa se revisa en cuanto se escribe o se elige: la tarjeta dice
    si es válido o cuántos errores tiene, y un clic en el aviso los muestra.
    Así los errores aparecen antes de pulsar «Iniciar partida».
    """

    def __init__(self, app: AppGrafica, config: Configuracion):
        self.app = app
        self.config = config
        self._errores: dict[int, list] = {}
        self._fatales: set[int] = set()
        self.globo = Globo(app)
        self.ver: list[Boton] = []
        px = app.px
        p = app._nueva_pantalla("Preparar la batalla")
        app.subtitulo_barra.configure(
            text=espaciado("PASO 1  ·  ESCUADRÓN Y REGLAS"))
        cuerpo, pie = app.bloque_centrado(p, ancho_maximo=1440,
                                          con_pie=True)
        self.cuerpo = cuerpo

        # --- el escuadrón
        cabeza = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        cabeza.pack(fill="x")
        app.rotulo(cabeza, "Escuadrón").pack(side="left")
        self.cuenta = tk.Label(cabeza, text="", font=app.f_boton, fg=ACENTO,
                               bg=FONDO_VENTANA)
        self.cuenta.pack(side="right")
        tk.Label(cuerpo, text="Asigna un programa .txt a cada tanque o "
                 "escríbelo con «Programar». Se revisa al momento: «Ver» lo "
                 "muestra línea por línea y las líneas con errores se "
                 "saltan al jugar. Clic en el tanque para cambiar su color.",
                 font=app.f_chico, fg=GRIS, bg=FONDO_VENTANA, anchor="w"
                 ).pack(fill="x", pady=(px(2), px(8)))

        self.rutas: list[tk.StringVar] = []
        self.colores: list[str] = []
        self.muestras: list[tk.Canvas] = []
        self.avisos: list[tk.Label] = []
        self.nombres: list[tk.Label] = []
        self._paneles: list[Panel] = []
        rejilla = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        rejilla.pack(fill="x")
        for col in range(3):
            rejilla.columnconfigure(col, weight=1, uniform="ranura")
        for i in range(MAX_TANQUES):
            self._ranura(rejilla, i, config)

        # --- reglas: el campo de batalla y el arsenal
        grupos = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        grupos.pack(fill="x", pady=(px(12), 0))
        campo = self._grupo(grupos, "Campo de batalla", "ajustar")
        campo.master.master.pack(side="left", anchor="n", fill="y",
                                 padx=(0, px(10)))
        armas = self._grupo(grupos, "Arsenal y defensa", "x")
        armas.master.master.pack(side="left", fill="both", expand=True,
                                 anchor="n")

        def var(valor):
            return tk.StringVar(app.root, str(valor))

        self.ancho = var(config.tablero.ancho)
        self.alto = var(config.tablero.alto)
        self.semilla = var(config.semilla)
        self.rondas = var(config.rondas_maximas)
        self.amt = var(config.dano.ametralladora)
        self.misiles = var(config.municion.misiles)
        self.minas = var(config.municion.minas)
        self.reparar = var(config.reparar_puntos)
        self.escudo = var(config.escudo_puntos)
        self.armado = var(config.mina_rondas_armado)

        # Tablero: la miniatura a la izquierda; ancho, alto, «cuadrado» y
        # medidas rápidas a la derecha.
        self.vista_tablero = VistaTablero(campo, app)
        self.vista_tablero.grid(row=0, column=0, rowspan=4, sticky="nw",
                                padx=(0, px(14)))
        self.lados = {}
        medidas = tk.Frame(campo, bg=PANEL)
        medidas.grid(row=0, column=1, sticky="w")
        for k, (nombre, variable) in enumerate((("Ancho", self.ancho),
                                                ("Alto", self.alto))):
            caja = tk.Frame(medidas, bg=PANEL)
            caja.pack(side="left", padx=(0 if k == 0 else px(10), 0))
            tk.Label(caja, text=nombre, font=app.f_chico, fg=GRIS,
                     bg=PANEL).pack(anchor="w")
            ajuste = Ajuste(caja, app, variable, TABLERO_MINIMO, 30,
                            pista=False)
            ajuste.pack(anchor="w")
            self.lados[nombre] = ajuste
        self.cuadrado = tk.BooleanVar(app.root, self.ancho.get()
                                      == self.alto.get())
        # El eslabón entre ancho y alto: encendido, el tablero es cuadrado
        self.boton_cuadrado = app.boton(
            medidas, "", self._alternar_cuadrado, icono="enlace", alto=28,
            ancho=28, ayuda="Cuadrado: ancho y alto iguales")
        self.boton_cuadrado.pack(side="left", anchor="s",
                                 padx=(px(10), 0))
        rapidas = tk.Frame(campo, bg=PANEL)
        rapidas.grid(row=1, column=1, sticky="w", pady=(px(8), 0))
        self.medidas = {}
        for lado in (4, 6, 8, 10, 12):
            b = app.boton(rapidas, f"{lado}", lambda n=lado: self._medida(n),
                          estilo="fantasma", alto=26, ancho=28,
                          ayuda=f"Tablero de {lado} × {lado}")
            b.pack(side="left", padx=(0, px(3)))
            self.medidas[lado] = b
        self.pista_tablero = tk.Label(campo, text="", font=app.f_chico,
                                      fg=GRIS_CLARO, bg=PANEL, anchor="w")
        self.pista_tablero.grid(row=2, column=1, sticky="w",
                                pady=(px(4), 0))
        # Rondas y semilla
        abajo = tk.Frame(campo, bg=PANEL)
        abajo.grid(row=3, column=1, sticky="w", pady=(px(8), 0))
        izquierda = tk.Frame(abajo, bg=PANEL)
        izquierda.pack(side="left", anchor="n")
        tk.Label(izquierda, text="Límite de rondas", font=app.f_chico,
                 fg=GRIS, bg=PANEL).pack(anchor="w")
        # Por omisión no hay límite: se juega hasta el último en pie, y en
        # la partida «Terminar la partida aquí» la corta cuando se quiera.
        linea_rondas = tk.Frame(izquierda, bg=PANEL)
        linea_rondas.pack(anchor="w")
        self.sin_limite = tk.BooleanVar(app.root,
                                        config.rondas_maximas == 0)
        self._rondas_guardadas = str(config.rondas_maximas or 200)
        self.boton_limite = app.boton(
            linea_rondas, "∞", self._alternar_limite, alto=28, ancho=34,
            ayuda="Sin límite: hasta el último tanque en pie")
        self.boton_limite.pack(side="left", padx=(0, px(6)))
        self.contador_rondas = Ajuste(linea_rondas, app, self.rondas, 10,
                                      1000, paso=10, pista=False)
        self.texto_sin_limite = tk.Label(
            linea_rondas, text="hasta el último en pie", font=app.f_chico,
            fg=ACENTO, bg=PANEL)
        self._pintar_limite()
        derecha = tk.Frame(abajo, bg=PANEL)
        derecha.pack(side="left", anchor="n", padx=(px(14), 0))
        tk.Label(derecha, text="Semilla", font=app.f_chico, fg=GRIS,
                 bg=PANEL).pack(anchor="w")
        linea = tk.Frame(derecha, bg=PANEL)
        linea.pack(anchor="w")
        semilla = app.campo_texto(linea, self.semilla, ancho=7)
        semilla.configure(justify="center", font=app.f_boton)
        semilla.pack(side="left", ipady=px(4))
        app.boton(linea, "", self._sortear, icono="dado", alto=30,
                  ayuda="Otra semilla al azar").pack(side="left",
                                                     padx=(px(6), 0))
        self.ancho.trace_add("write", lambda *_a: self._cambio_lado(
            self.ancho, self.alto))
        self.alto.trace_add("write", lambda *_a: self._cambio_lado(
            self.alto, self.ancho))
        self._ajustar_lado()

        # Arsenal: tres por fila, cada uno con su color e ícono
        # Izquierda el ataque, derecha la defensa y la mina.
        ajustes = (
            ("Daño AMT", self.amt, "ametralladora", CIAN, "bala", ""),
            ("REPARAR cura", self.reparar, "reparar", VERDE_OK, "cruz",
             "vida que recupera · 1 uso"),
            ("Misiles", self.misiles, "misiles", ACENTO, "misil",
             "por tanque"),
            ("Escudo absorbe", self.escudo, "escudo", CIAN, "escudo",
             "daño que detiene"),
            ("Minas", self.minas, "minas", ROJO_UI, "mina",
             "por tanque"),
            ("Armado de mina", self.armado, "rondas_armado", "#C084FC",
             "reloj", "rondas · 0 = al caer"))
        self.ajustes = {}
        for k, (etiqueta, variable, clave, color, simbolo, nota) in \
                enumerate(ajustes):
            minimo, maximo = RANGOS[clave]
            ajuste = Ajuste(armas, app, variable, minimo, maximo,
                            etiqueta=etiqueta, color=color, simbolo=simbolo,
                            nota=nota, ancho=210)
            ajuste.grid(row=k // 2, column=k % 2, sticky="new",
                        padx=(0 if k % 2 == 0 else px(22), 0),
                        pady=(0, px(4)))
            armas.columnconfigure(k % 2, weight=1, uniform="ajuste")
            self.ajustes[clave] = ajuste
        # El daño de las demás armas sale del de la ametralladora: va
        # escrito bajo su ajuste.
        self.derivados = self.ajustes["ametralladora"].nota
        self.amt.trace_add("write", lambda *_a: self._derivar())

        # Los botones van en el pie fijo: siempre a la vista, aunque la
        # pantalla sea chica y el formulario tenga que recorrerse.
        botones = tk.Frame(pie, bg=FONDO_VENTANA)
        botones.pack(fill="x")
        app.boton(botones, "Valores por omisión", self._por_omision,
                  icono="reiniciar").pack(side="left")
        app.boton(botones, "INICIAR BATALLA", lambda: app._elegir("iniciar"),
                  ancho=220, primario=True, icono="play", alto=44
                  ).pack(side="right")
        app.boton(botones, "Volver", lambda: app._elegir("volver"),
                  estilo="fantasma", icono="atras", alto=44
                  ).pack(side="right", padx=px(10))
        app.atajo("<Return>", lambda: app._elegir("iniciar"), "confirmar")
        app.atajo("<Escape>", lambda: app._elegir("volver"), "atras")

        for i in range(MAX_TANQUES):
            self._revisar(i)
        self._derivar()
        self._pintar_tablero()

    # ------------------------------------------------------------ armado
    def _ranura(self, rejilla, i, config):
        """La tarjeta de un tanque: su dibujo, su programa y sus botones."""
        app, px = self.app, self.app.px
        t = config.tanques[i] if i < len(config.tanques) else None
        var = tk.StringVar(app.root, t.programa if t else "")
        self.rutas.append(var)
        self.colores.append(t.color if t else sprites.COLORES_TANQUE[i])

        panel = Panel(rejilla, app, modo="x", relleno=12,
                      acento=self.colores[i])
        panel.grid(row=i // 3, column=i % 3, sticky="ew",
                   padx=(0 if i % 3 == 0 else px(5), 0 if i % 3 == 2
                         else px(5)), pady=px(5))
        self._paneles.append(panel)
        c = panel.cuerpo
        arriba = tk.Frame(c, bg=PANEL)
        arriba.pack(fill="x")
        muestra = tk.Canvas(arriba, width=px(54), height=px(54), bg=PANEL,
                            highlightthickness=0, cursor="hand2")
        muestra.pack(side="left")
        muestra.bind("<Button-1>", lambda _e, k=i: self._color(k))
        self.muestras.append(muestra)
        info = tk.Frame(arriba, bg=PANEL)
        info.pack(side="left", fill="x", expand=True, padx=(px(10), 0))
        tk.Label(info, text=espaciado(f"TANQUE {i + 1}"), font=app.f_mini,
                 fg=GRIS, bg=PANEL, anchor="w").pack(fill="x")
        nombre = tk.Label(info, text="", font=app.f_seccion, fg=TINTA,
                          bg=PANEL, anchor="w")
        nombre.pack(fill="x")
        self.nombres.append(nombre)
        aviso = tk.Label(info, text="", font=app.f_chico, bg=PANEL,
                         anchor="w")
        aviso.pack(fill="x")
        aviso.bind("<Button-1>", lambda _e, k=i: self._ver_errores(k))
        aviso.bind("<Enter>", lambda e, k=i: self._globo_aviso(k, e))
        aviso.bind("<Leave>", lambda _e: self.globo.ocultar())
        self.avisos.append(aviso)

        app.campo_texto(c, var).pack(fill="x", pady=(px(8), px(6)),
                                     ipady=px(4))
        acciones = tk.Frame(c, bg=PANEL)
        acciones.pack(fill="x")
        app.boton(acciones, "", lambda k=i: self._examinar(k),
                  icono="carpeta", alto=30,
                  ayuda="Examinar: elegir un archivo .txt").pack(side="left")
        ver = app.boton(acciones, "Ver", lambda k=i: self._ver(k),
                        icono="ojo", alto=30,
                        ayuda="Ver el programa línea por línea")
        ver.pack(side="left", padx=(px(6), 0))
        self.ver.append(ver)
        app.boton(acciones, "Programar", lambda k=i: self.programar(k),
                  icono="lapiz", alto=30,
                  ayuda="Escribir o modificar el programa aquí, con la "
                        "lista de instrucciones y un programa aleatorio"
                  ).pack(side="left", padx=(px(6), 0))
        app.boton(acciones, "", lambda k=i: self.rutas[k].set(""),
                  icono="x", alto=30, ayuda="Quitar este tanque"
                  ).pack(side="right")
        app.boton(acciones, "", lambda k=i: self._color(k), icono="paleta",
                  alto=30, ayuda="Cambiar el color"
                  ).pack(side="right", padx=px(6))
        var.trace_add("write", lambda *_a, k=i: self._revisar(k))
        var.trace_add("write", lambda *_a: self._ajustar_lado())

    def _grupo(self, padre, titulo, modo):
        """Panel con rótulo; devuelve el marco interior para los campos."""
        app = self.app
        panel = Panel(padre, app, modo=modo, relleno=14, acento=ACENTO)
        app.rotulo(panel.cuerpo, titulo).pack(anchor="w")
        dentro = tk.Frame(panel.cuerpo, bg=PANEL)
        dentro.pack(fill="both", expand=True, pady=(app.px(6), 0))
        return dentro

    def _alternar_limite(self):
        """∞ encendido: sin límite de rondas. Apagado: se elige cuántas."""
        if self.sin_limite.get():
            self.sin_limite.set(False)
            self.rondas.set(self._rondas_guardadas)
        else:
            if self.rondas.get().strip() not in ("", "0"):
                self._rondas_guardadas = self.rondas.get().strip()
            self.sin_limite.set(True)
            self.rondas.set("0")
        self._pintar_limite()

    def _pintar_limite(self):
        sin = self.sin_limite.get()
        if sin:
            self.rondas.set("0")
            self.contador_rondas.pack_forget()
            self.texto_sin_limite.pack(side="left")
        else:
            self.texto_sin_limite.pack_forget()
            self.contador_rondas.pack(side="left")
        self.boton_limite.estilo = "secundario" if sin else "fantasma"
        self.boton_limite.ayuda = ("Sin límite: hasta el último tanque en "
                                   "pie. Clic para poner un límite"
                                   if sin else
                                   "Clic para jugar sin límite de rondas")
        self.boton_limite._dibujar()

    def _alternar_cuadrado(self):
        self.cuadrado.set(not self.cuadrado.get())
        if self.cuadrado.get():
            self.alto.set(self.ancho.get())
        self._pintar_tablero()

    def _medida(self, lado: int):
        self.ancho.set(str(lado))
        self.alto.set(str(lado))

    def _cambio_lado(self, origen, destino):
        """Con «cuadrado», el otro lado sigue al que se movió."""
        copiando = getattr(self, "_copiando", False)
        if (not copiando and self.cuadrado.get()
                and origen.get() != destino.get()):
            self._copiando = True
            try:
                destino.set(origen.get())
            finally:
                self._copiando = False
        self._pintar_tablero()

    def _pintar_tablero(self):
        """Miniatura, medidas rápidas y el botón «cuadrado» al día."""
        if not hasattr(self, "vista_tablero"):
            return
        n = sum(1 for v in self.rutas if v.get().strip())
        minimo = lado_minimo(n)

        def entero(var):
            try:
                return int(var.get())
            except ValueError:
                return None
        ancho, alto = entero(self.ancho), entero(self.alto)
        self.vista_tablero.dibujar(ancho, alto, minimo)
        for lado, b in self.medidas.items():
            self.app.activar(b, lado >= minimo)
            b.estilo = ("secundario" if ancho == alto == lado
                        else "fantasma")
            b._dibujar()
        self.boton_cuadrado.estilo = ("secundario" if self.cuadrado.get()
                                      else "fantasma")
        self.boton_cuadrado._dibujar()

    def _ajustar_lado(self):
        """El tablero crece con el escuadrón: 4 x 4 aguanta hasta 4 tanques
        y cada tanque más pide una casilla más por lado. Si el tablero
        queda chico, se agranda solo."""
        if not hasattr(self, "pista_tablero"):
            return                          # aún se arma el formulario
        n = sum(1 for v in self.rutas if v.get().strip())
        minimo = lado_minimo(n)
        for ajuste in self.lados.values():
            ajuste.rango(minimo)
        for var in (self.ancho, self.alto):
            try:
                if int(var.get()) < minimo:
                    var.set(str(minimo))
            except ValueError:
                pass
        self.pista_tablero.configure(
            text=f"mínimo {minimo} × {minimo}"
                 + (f" con {n} tanques" if minimo > TABLERO_MINIMO
                    else f" (hasta {TABLERO_MINIMO} tanques)"))
        self._pintar_tablero()

    # ------------------------------------------------------------ revisión
    def _ruta(self, texto: str) -> Path:
        ruta = Path(texto)
        return ruta if ruta.is_absolute() else self.app.raiz / ruta

    def _revisar(self, i):
        """Valida el programa de la ranura i y lo dice en su aviso."""
        texto = self.rutas[i].get().strip()
        aviso = self.avisos[i]
        self._errores.pop(i, None)
        self._fatales.discard(i)
        existe = bool(texto) and self._ruta(texto).is_file()
        if len(self.ver) > i:
            self.app.activar(self.ver[i], existe)
        if not texto:
            aviso.configure(text="— no juega", fg=GRIS_CLARO, cursor="")
            self.nombres[i].configure(text="Libre", fg=GRIS_CLARO)
        else:
            self.nombres[i].configure(text=Path(texto).stem, fg=TINTA)
            if not existe:
                self._fatales.add(i)
                aviso.configure(text="✗ el archivo no existe", fg=ROJO_UI,
                                cursor="")
            else:
                programa, errores = Interprete().cargar(self._ruta(texto))
                n = len(errores)
                if errores:
                    self._errores[i] = errores
                if not programa.instrucciones:
                    self._fatales.add(i)
                    aviso.configure(text="✗ ninguna instrucción válida",
                                    fg=ROJO_UI, cursor="hand2")
                elif errores:
                    aviso.configure(
                        text=f"▲ {n} error{'es' if n > 1 else ''} · se "
                             f"saltan", fg=ACENTO, cursor="hand2")
                else:
                    aviso.configure(
                        text=f"✓ {len(programa)} instrucciones",
                        fg=VERDE_OK, cursor="")
        self._pintar_muestra(i)
        jugando = sum(1 for r in self.rutas if r.get().strip())
        self.cuenta.configure(text=f"{jugando} de {MAX_TANQUES} tanques")

    def _ver_errores(self, i):
        """Clic en el aviso: abre el visor si hay algo que mostrar."""
        if i in self._errores:
            self._ver(i)

    def _ver(self, i):
        texto = self.rutas[i].get().strip()
        if not texto or not self._ruta(texto).is_file():
            return
        self.globo.ocultar()
        VisorPrograma(self.app, self._ruta(texto), i + 1, self.colores[i],
                      self.config, al_cerrar=lambda: self._revisar(i),
                      al_guardar=lambda ruta: self._asignar(i, ruta))

    def programar(self, i) -> EditorPrograma:
        """Abre el editor del juego para el tanque i: con su programa si
        ya tiene uno, o en blanco para escribir uno nuevo."""
        texto = self.rutas[i].get().strip()
        ruta = self._ruta(texto) if texto else None
        if ruta is not None and not ruta.is_file():
            ruta = None
        self.globo.ocultar()
        return EditorPrograma(self.app, ruta, i + 1, self.colores[i],
                              self.config,
                              al_guardar=lambda r: self._asignar(i, r))

    def _asignar(self, i, ruta: Path):
        """El programa guardado pasa a ser el del tanque i."""
        self.rutas[i].set(self._relativa(Path(ruta)))
        self._revisar(i)

    def _relativa(self, ruta: Path) -> str:
        """Ruta relativa al proyecto si está dentro; si no, absoluta."""
        try:
            ruta = ruta.resolve().relative_to(self.app.raiz.resolve())
        except ValueError:
            pass
        return ruta.as_posix()

    def _globo_aviso(self, i, e):
        """Al pasar sobre un aviso con errores, los resume en un globo."""
        errores = self._errores.get(i)
        if not errores:
            return
        lineas = [f"Línea {err.linea}: {err.mensaje}" if err.linea
                  else err.mensaje for err in errores[:4]]
        if len(errores) > 4:
            lineas.append(f"… y {len(errores) - 4} más")
        if i in self._fatales:
            titulo = "Este tanque no puede jugar"
            pie = "Ninguna línea es válida. Corrígelo con «Programar»."
            color = ROJO_UI
        else:
            titulo = f"{len(errores)} líneas se saltarán al jugar"
            pie = "El tanque juega con las demás. «Ver» las muestra."
            color = ACENTO
        self.globo.mostrar(self.app.root, e.x_root + self.app.px(16),
                           e.y_root + self.app.px(14), titulo,
                           "\n".join(lineas) + "\n\n" + pie, color)

    def _derivar(self):
        """El daño de cada arma sale del de la ametralladora."""
        try:
            amt = int(self.amt.get())
        except ValueError:
            self.derivados.configure(text="escribe un número entero")
            return
        d = Dano(amt, self.config.dano.choque_tanque,
                 self.config.dano.choque_pared)
        self.derivados.configure(
            text=f"misil {d.misil:g} · mina {d.mina:g} · choque "
                 f"{d.choque_tanque:g}")

    def _sortear(self):
        self.semilla.set(str(random.randint(1, 99999)))

    def _por_omision(self):
        base = Configuracion()
        for var, valor in ((self.ancho, base.tablero.ancho),
                           (self.alto, base.tablero.alto),
                           (self.amt, base.dano.ametralladora),
                           (self.misiles, base.municion.misiles),
                           (self.minas, base.municion.minas),
                           (self.reparar, base.reparar_puntos),
                           (self.escudo, base.escudo_puntos),
                           (self.armado, base.mina_rondas_armado)):
            var.set(str(valor))
        self.sin_limite.set(base.rondas_maximas == 0)
        if not self.sin_limite.get():
            self.rondas.set(str(base.rondas_maximas))
        self._pintar_limite()

    # ------------------------------------------------------------------
    def _pintar_muestra(self, i):
        """El tanque de la ranura con su color; punteado si está libre."""
        c = self.muestras[i]
        c.delete("all")
        lado = self.app.px(54)
        color = self.colores[i]
        if self.rutas[i].get().strip():
            c.create_oval(lado * 0.1, lado * 0.78, lado * 0.9, lado * 0.98,
                          fill="#070C12", width=0)
            sprites.tanque(c, lado / 2, lado / 2, lado * 0.95, i + 1, color,
                           Direccion.N, etiqueta="muestra")
        else:
            rect_redondeado(c, 3, 3, lado - 3, lado - 3, self.app.px(8),
                            outline=sprites.mezclar(color, PANEL, 0.4),
                            fill="", dash=(4, 3), width=2)
            icono(c, "cruz", lado / 2, lado / 2, lado * 0.32,
                  sprites.mezclar(color, PANEL, 0.3))
        if len(self._paneles) > i:
            self._paneles[i].acento = color
            self._paneles[i]._forma(self._paneles[i].winfo_width(),
                                    self._paneles[i].winfo_height())

    def _color(self, i):
        elegido = self.app.elegir_color(self.app.root, i + 1,
                                        self.colores[i])
        if elegido:
            self.colores[i] = elegido.upper()
            self._pintar_muestra(i)

    def _examinar(self, i):
        texto = self.rutas[i].get().strip()
        inicial = self._ruta(texto).parent if texto else None
        ruta = self.app.elegir_programa(self.app.root, i + 1, inicial)
        if ruta:
            self.rutas[i].set(self._relativa(Path(ruta)))

    def leer(self) -> tuple[Optional[Configuracion], list[str]]:
        """Arma la configuración del formulario y la valida."""
        problemas = []

        def entero(var, nombre):
            try:
                return int(var.get().strip())
            except ValueError:
                problemas.append(f"{nombre}: «{var.get()}» no es un número "
                                 f"entero")
                return 0

        ancho = entero(self.ancho, "Ancho del tablero")
        alto = entero(self.alto, "Alto del tablero")
        semilla = entero(self.semilla, "Semilla")
        rondas = (0 if self.sin_limite.get()
                  else entero(self.rondas, "Rondas máximas"))
        amt = entero(self.amt, "Daño de la ametralladora")
        misiles = entero(self.misiles, "Misiles")
        minas = entero(self.minas, "Minas")
        reparar = entero(self.reparar, "Reparar")
        escudo = entero(self.escudo, "Escudo")
        armado = entero(self.armado, "Armado de la mina")

        tanques, nombres = [], set()
        for var, color in zip(self.rutas, self.colores):
            ruta = var.get().strip()
            if not ruta:
                continue
            nombre, n = Path(ruta).stem, 2
            while nombre in nombres:       # dos tanques con el mismo archivo
                nombre, n = f"{Path(ruta).stem}-{n}", n + 1
            nombres.add(nombre)
            tanques.append(TanqueConfig(nombre, ruta, color))
        if problemas:
            return None, problemas

        c = self.config
        nueva = replace(c, tablero=Tablero(ancho, alto),
                        semilla=semilla, rondas_maximas=rondas,
                        dano=Dano(amt, c.dano.choque_tanque,
                                  c.dano.choque_pared),
                        municion=Municion(minas, misiles),
                        reparar_puntos=reparar, escudo_puntos=escudo,
                        mina_rondas_armado=armado,
                        tanques=tuple(tanques))
        problemas = nueva.validar()
        # Las líneas con errores se saltan; solo frena un programa que no
        # tiene ninguna instrucción válida o cuyo archivo no existe.
        if self._fatales and not problemas:
            filas = ", ".join(str(i + 1) for i in sorted(self._fatales))
            problemas.append(f"el programa de los tanques {filas} no tiene "
                             f"ninguna instrucción válida; ábrelo con «Ver» "
                             f"para corregirlo")
        return nueva, problemas


# ======================================================================
class VentanaPartida(Vista):
    """Figura 12: tablero, panel de estado, registro y controles."""

    def __init__(self, app: AppGrafica, config: Configuracion,
                 velocidad: int = 5, saltadas=()):
        self.app = app
        self.config = config
        self.saltadas = list(saltadas)     # líneas con errores omitidas
        self.accion: Optional[str] = None  # reiniciar | configurar | salir
        self.modo = "pausa"
        self._senal = tk.StringVar(app.root)
        self._reloj = tk.StringVar(app.root)
        self._estado = None               # lo último que se dibujó
        self._ronda_pedida = False        # «Una ronda»: no parar entre turnos
        self._numeros: dict[str, int] = {}
        self._instrucciones: dict[str, str] = {}
        self._tarjetas: dict[str, dict] = {}
        # Quemaduras que dejan las explosiones: casilla → ronda. Son
        # decorado: se van borrando con las rondas.
        self._marcas: dict[tuple[int, int], int] = {}
        self._fondos: dict[tuple[int, int], str] = {}
        self._fase = 0
        self._terminada = False
        self._armar(velocidad)
        self._ambiente()

    # ---------------------------------------------------------- armado
    def _armar(self, velocidad):
        app = self.app
        px = app.px
        p = app._nueva_pantalla("Ronda 0")
        # Avance de la partida: una línea dorada bajo el encabezado.
        self.progreso = tk.Canvas(p, height=px(5), bg=NOCHE,
                                  highlightthickness=0)
        self.progreso.pack(fill="x")
        cuerpo = tk.Frame(p, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=px(18), pady=px(12))

        # --- izquierda: el tablero en su panel, y los controles. La zona
        # pide el tamaño natural (el de siempre), pero al agrandar la
        # ventana se queda con todo el espacio que sobra: el tablero crece
        # y va centrado con sus controles (ver `_repartir`).
        izq = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        izq.pack(side="left", fill="both", expand=True)
        self.zona = izq
        marco = Panel(izq, app, modo="ambos", relleno=10, acento=ACENTO)
        self.marco = marco
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        self.celda = max(px(24), min(px(TABLERO_PX) // ancho,
                                     px(TABLERO_PX) // alto, px(96)))
        self.margen = px(26)                # para los números de coordenada
        self._celda_natural = self.celda    # la de la ventana normal
        self.canvas = tk.Canvas(
            marco.cuerpo, width=self.margen + ancho * self.celda + px(12),
            height=self.margen + alto * self.celda + px(12), bg=PANEL,
            highlightthickness=0)
        self.canvas.pack(anchor="nw")
        self.canvas.bind("<Motion>", self._sobre)
        self.canvas.bind("<Leave>", self._fuera)
        self._raton: Optional[tuple[int, int]] = None
        self.leyenda = tk.Label(marco.cuerpo, text="", font=app.f_chico,
                                fg=GRIS, bg=PANEL, anchor="w")
        self.leyenda.pack(fill="x", padx=px(4), pady=(px(4), 0))
        self._info_por_omision()

        controles = Panel(izq, app, modo="x", relleno=12)
        self.controles = controles
        c = controles.cuerpo
        # Cuatro botones del mismo ancho que llenan el panel; lo demás
        # (configurar, terminar, menú principal, sonido) está en el menú ☰
        # de arriba a la derecha.
        fila = tk.Frame(c, bg=PANEL)
        fila.pack(fill="x")
        self.botones = {}
        for k, (texto, senal, simbolo) in enumerate((
                ("Iniciar", "iniciar", "play"),
                ("Pausar", "pausar", "pausa"),
                ("Una ronda", "una", "paso"),
                ("Reiniciar", "reiniciar", "reiniciar"))):
            b = app.boton(fila, texto, lambda s=senal: self.senal(s),
                          primario=senal == "iniciar", icono=simbolo,
                          alto=40,
                          ayuda="La misma partida desde el principio  (R)"
                          if senal == "reiniciar" else "")
            b.grid(row=0, column=k, sticky="ew",
                   padx=(0 if k == 0 else px(6), 0))
            fila.columnconfigure(k, weight=1, uniform="control")
            self.botones[senal] = b
        self.botones["configurar"] = _Interruptor()
        app.poner_menu(self)

        vel = tk.Frame(c, bg=PANEL)
        vel.pack(fill="x", pady=(px(10), 0))
        app.rotulo(vel, "Velocidad", color=GRIS).pack(side="left",
                                                       padx=(0, px(10)))
        self.velocidad = Segmentos(vel, app, valor=velocidad,
                                   command=lambda _v: self._nombrar_velocidad())
        self.velocidad.pack(side="left")
        self.vel_texto = tk.Label(vel, text="", font=app.f_boton, fg=ACENTO,
                                  bg=PANEL, anchor="w")
        self.vel_texto.pack(side="left", padx=(px(12), 0))
        self._nombrar_velocidad()
        teclas = tk.Label(c, text="Espacio iniciar/pausar  ·  → ronda  ·  "
                          "+/− velocidad  ·  R reiniciar  ·  Esc menú",
                          font=app.f_chico, fg=GRIS_CLARO, bg=PANEL,
                          anchor="w", justify="left")
        teclas.pack(fill="x", pady=(px(8), 0))
        # Se acomoda en dos renglones si el tablero es angosto (4 x 4).
        teclas.bind("<Configure>", lambda e: teclas.configure(
            wraplength=max(1, e.width)))
        app.atajo("<space>", self._alternar, None)
        app.atajo("<Right>", lambda: self._si_activo("una"), None)
        app.atajo("<Key-r>", lambda: self._si_activo("reiniciar"), None)
        app.atajo("<Key-R>", lambda: self._si_activo("reiniciar"), None)
        app.atajo("<Escape>", self._abrir_menu)
        app.atajo("<Key-plus>", lambda: self._acelerar(1), "tic")
        app.atajo("<KP_Add>", lambda: self._acelerar(1), "tic")
        app.atajo("<Key-minus>", lambda: self._acelerar(-1), "tic")
        app.atajo("<KP_Subtract>", lambda: self._acelerar(-1), "tic")

        # --- derecha: el escuadrón y la bitácora
        # No se estira a lo ancho: con la ventana grande crece un poco, pero
        # el espacio es para el tablero.
        der = tk.Frame(izq, bg=FONDO_VENTANA)
        self._der = der
        app.rotulo(der, "Escuadrón").pack(anchor="w")
        # Con cuatro o más tanques las tarjetas van en dos columnas: la
        # columna necesita un ancho mínimo para que quepan.
        self._compacto = len(self.config.tanques) > 3
        self._ancho_columna = (px(520), px(720)) if self._compacto \
            else (px(340), px(460))
        self._columna = tk.Frame(der, bg=FONDO_VENTANA, height=0,
                                 width=self._ancho_columna[0])
        self._columna.pack()
        self.panel = tk.Frame(der, bg=FONDO_VENTANA)
        self.panel.pack(fill="x", pady=(px(4), px(8)))

        caja = Panel(der, app, modo="ambos", relleno=12)
        caja.configure(height=px(170), width=px(320))
        caja.pack(fill="both", expand=True)
        cab = tk.Frame(caja.cuerpo, bg=PANEL)
        cab.pack(fill="x")
        app.rotulo(cab, "Bitácora", color=CIAN).pack(side="left")
        self.detalle = tk.BooleanVar(app.root, True)
        tk.Checkbutton(cab, text="ver detalle", variable=self.detalle,
                       command=lambda: app.sonido.tocar("clic"),
                       font=app.f_chico, fg=GRIS, bg=PANEL,
                       activebackground=PANEL, activeforeground=TINTA,
                       selectcolor=PANEL_ALTO, takefocus=0,
                       cursor="hand2").pack(side="right")
        self.registro = tk.Text(caja.cuerpo, font=app.f_mono, height=5,
                                width=48, wrap="word", relief="flat",
                                bg=PANEL, fg=TINTA, padx=px(2), pady=px(6),
                                state="disabled", highlightthickness=0,
                                spacing1=1, insertbackground=TINTA)
        # Sin barra de desplazamiento: la de Windows no admite colores.
        # El texto se recorre con la rueda del ratón.
        self.registro.pack(fill="both", expand=True)
        self.registro.tag_configure("ronda", foreground=ACENTO,
                                    font=app.f_mini, spacing1=px(8),
                                    spacing3=px(2))
        self.registro.tag_configure("fin", font=app.f_seccion,
                                    foreground=ACENTO, spacing1=px(8))
        self.registro.tag_configure("detalle", foreground=GRIS)
        self.registro.tag_configure("dano", foreground=ROJO_UI)
        self.registro.tag_configure("cura", foreground=VERDE_OK)
        self.registro.tag_configure("escudo", foreground=CIAN)
        self.registro.tag_configure("aviso", foreground=ACENTO,
                                    font=app.f_boton)
        self.registro.tag_configure("aviso_detalle", foreground="#D9B36A")
        self.detalle.trace_add("write", lambda *_a: self.registro.tag_configure(
            "detalle", elide=not self.detalle.get()))
        self._botones_para("pausa")
        self._medida = None               # (ancho, alto) ya repartidos
        self._animando = False
        self._ultimo_cartel = None
        self._fijar_natural()
        izq.bind("<Configure>", lambda _e: self._repartir())

    # ---------------------------------------------------------- proporciones
    # El tablero (con sus controles debajo) y la columna del escuadrón se
    # colocan con `place` dentro de una sola zona. La zona pide el tamaño de
    # siempre, así que la ventana normal no cambia; en una ventana grande el
    # tablero se queda con el espacio que sobra, el escuadrón crece poco y
    # los dos van juntos y centrados.
    def _fijar_natural(self):
        """Mide el tamaño natural de cada parte y lo pide para la zona."""
        px = self.app.px
        self.app.root.update_idletasks()
        p = self.marco.p
        self._leyenda_alto = self.leyenda.winfo_reqheight() + px(4)
        lienzo_w, lienzo_h = self._lienzo_natural()
        ancho = lienzo_w + 2 * p
        alto = lienzo_h + self._leyenda_alto + 2 * p
        self._natural = (ancho, alto)
        columna = self._ancho_columna[0]
        self.zona.configure(
            width=ancho + px(16) + columna,
            height=max(alto + px(10) + self._alto_controles(),
                       self._der.winfo_reqheight()))
        self._medida = None
        self._colocar(ancho, alto, columna)

    def _lienzo_natural(self) -> tuple[int, int]:
        """El tamaño del lienzo del tablero en la ventana normal."""
        px, s = self.app.px, self._celda_natural
        return (self.margen + self.config.tablero.ancho * s + px(12),
                self.margen + self.config.tablero.alto * s + px(12))

    def _alto_controles(self) -> int:
        """El alto del panel de controles, esté o no en pantalla."""
        return self.controles.cuerpo.winfo_reqheight() + 2 * self.controles.p

    def _ancho_escuadron(self, W: int) -> int:
        """Crece con la ventana, pero poco y con tope."""
        minimo, maximo = self._ancho_columna
        return min(maximo, max(minimo, int(W * 0.24)))

    def _colocar(self, ancho_marco: int, alto_marco: int, columna: int):
        """Tablero y controles a la izquierda, el escuadrón a la derecha;
        el grupo, centrado en la zona."""
        px = self.app.px
        W = max(self.zona.winfo_width(), int(self.zona["width"]))
        H = max(self.zona.winfo_height(), int(self.zona["height"]))
        bloque = alto_marco + px(10) + self._alto_controles()
        x = max(0, (W - (ancho_marco + px(16) + columna)) // 2)
        y = max(0, (H - bloque) // 2)
        self.marco.place(x=x, y=y, width=ancho_marco, height=alto_marco)
        self.controles.place(x=x, y=y + alto_marco + px(10),
                             width=ancho_marco)
        self._columna.configure(width=columna)
        self._der.place(x=x + ancho_marco + px(16), y=0, width=columna,
                        height=H)

    def _repartir(self):
        """Al cambiar el tamaño de la ventana, el tablero toma el espacio
        que haya (celdas de hasta 150 px) y se vuelve a dibujar."""
        try:
            W, H = self.zona.winfo_width(), self.zona.winfo_height()
        except tk.TclError:
            return
        if W <= 1 or (W, H) == self._medida:
            return
        if self._animando:                 # se termina la jugada primero
            self.app.root.after(120, self._repartir)
            return
        self._medida = (W, H)
        px = self.app.px
        p = self.marco.p
        columna = self._ancho_escuadron(W)
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        libre_w = W - px(16) - columna - 2 * p - self.margen - px(12)
        libre_h = (H - px(10) - self._alto_controles()
                   - self._leyenda_alto - 2 * p - self.margen - px(12))
        celda = max(self._celda_natural,
                    min(libre_w // ancho, libre_h // alto, px(150)))
        if celda != self.celda:
            self.celda = celda
            self.canvas.configure(
                width=self.margen + ancho * celda + px(12),
                height=self.margen + alto * celda + px(12))
            if self._estado is not None:
                self.dibujar(self._estado, panel=False)
                if self._ultimo_cartel is not None:
                    self._cartel(*self._ultimo_cartel)
        nat_w, nat_h = self._natural
        self._colocar(
            max(nat_w, int(self.canvas["width"]) + 2 * p),
            max(nat_h, int(self.canvas["height"]) + self._leyenda_alto
                + 2 * p), columna)

    # ---------------------------------------------------------- controles
    def _si_activo(self, senal: str):
        """El atajo solo actúa si el botón correspondiente está activo, y
        suena como ese botón. Con el menú abierto también funcionan: la
        partida sigue detrás."""
        boton = self.botones[senal]
        if str(boton["state"]) == "normal":
            if boton.sonido:
                self.app.sonido.tocar(boton.sonido)
            self.senal(senal)
        else:
            self.app.sonido.tocar("apagado")

    # ---------------------------------------------------------- menú ☰
    @property
    def _menu(self):
        """El menú desplegado, si está abierto."""
        return self.app._desplegable

    @property
    def opciones_menu(self) -> dict:
        return self.app.opciones_menu

    def _abrir_menu(self):
        """Esc o ☰: abre o cierra el menú de arriba a la derecha."""
        self.app.alternar_menu()

    def al_abrir_menu(self):
        """Abrir el menú no pausa la partida: sigue jugándose detrás y el
        menú se pone al día solo. Para detenerla está «Pausar»."""
        return self.accion is None

    def opciones_del_menu(self):
        ronda = self._estado.ronda if self._estado else 0
        estado = ("terminada" if self._terminada
                  else "en curso" if self.modo == "auto"
                  else "en pausa" if ronda else "sin empezar")
        activo = {s: str(b["state"]) == "normal"
                  for s, b in self.botones.items()}
        limite = (f" de {self.config.rondas_maximas}"
                  if self.config.rondas_maximas else "")
        return ("Partida", f"Ronda {ronda}{limite}  ·  {estado}", (
            ("play", "Ver el resultado" if self._terminada
             else "Volver a la partida", "play",
             lambda: self.app.cerrar_menu(continuar=True), "primario", True),
            ("pausa", "Reanudar" if self.modo == "pausa" else "Pausar",
             "play" if self.modo == "pausa" else "pausa", self._alternar,
             "secundario", not self._terminada),
            ("reiniciar", "Reiniciar la partida", "reiniciar",
             lambda: self._elegir_del_menu("reiniciar"), "secundario",
             activo["reiniciar"]),
            ("engrane", "Volver a los tanques", "engrane",
             lambda: self._elegir_del_menu("configurar"), "secundario",
             activo["configurar"]),
            ("bandera", "Terminar la partida aquí", "bandera",
             lambda: self._elegir_del_menu("terminar"), "secundario",
             not self._terminada),
            ("casa", "Menú principal", "casa",
             lambda: self._elegir_del_menu("menu"), "fantasma", True)))

    def al_cerrar_menu(self, continuar: bool):
        """La partida nunca se detuvo: no hay nada que reanudar."""

    def _cerrar_menu(self, continuar: bool = False):
        self.app.cerrar_menu(continuar)

    def _elegir_del_menu(self, accion: str):
        self.app.cerrar_menu()
        self.senal(accion)

    def pide_terminar(self) -> bool:
        return self.accion == "terminar"

    def _ambiente(self):
        """Lo que se mueve aunque nadie juegue: la luz de las minas
        armadas late, las refacciones brillan y el escudo gira."""
        try:
            if not self.canvas.winfo_exists():
                return
            self._fase += 1
            f = self._fase
            onda = 0.5 + 0.5 * math.sin(f * 0.35)
            c = self.canvas
            c.itemconfigure("led", fill=sprites.mezclar(
                sprites.MINA_NUCLEO, sprites.MINA_ARMADA, 0.25 + 0.75 * onda))
            c.itemconfigure("brillo", outline=sprites.mezclar(
                sprites.REFACCION_CAJA, sprites.REFACCION, 0.45 + 0.55 * onda))
            c.itemconfigure("escudo", dashoffset=(f * 2) % 12)
            self.app.root.after(90, self._ambiente)
        except tk.TclError:
            return

    def _alternar(self):
        self._si_activo("pausar" if self.modo == "auto" else "iniciar")

    def _acelerar(self, paso: int):
        self.velocidad.set(min(10, max(1, self.velocidad.get() + paso)))
        self._nombrar_velocidad()

    def _nombrar_velocidad(self):
        v = int(self.velocidad.get())
        if retardo_ms(v) < RETARDO_MIN_ANIMAR:
            texto = f"{v} · sin animación"
        else:
            texto = f"{v} · {retardo_ms(v) / 1000:.1f} s por ronda"
        self.vel_texto.configure(text=texto)

    # ---------------------------------------------------------- información
    def _fuera(self, _evento=None):
        self._raton = None
        self._info_por_omision()

    def _info_por_omision(self):
        self.leyenda.configure(
            text="Pasa el ratón sobre una casilla para ver qué hay en ella",
            fg=GRIS_CLARO)

    def _sobre(self, evento):
        """Describe la casilla bajo el ratón."""
        self._raton = (evento.x, evento.y)
        self._describir(self._estado)

    def _describir(self, estado):
        if estado is None or self._raton is None:
            return
        px, py = self._raton
        x = int((px - self.margen) // self.celda) + 1
        y = int((py - self.margen) // self.celda) + 1
        if not (1 <= x <= estado.ancho and 1 <= y <= estado.alto):
            self._info_por_omision()
            return
        partes = []
        for t in estado.tanques:
            if t.vivo and t.posicion == (x, y):
                escudo = f" · escudo {t.escudo:g}" if t.escudo else ""
                partes.append(f"tanque {t.numero} {t.nombre} · vida "
                              f"{t.vida:g}{escudo} · cañón al "
                              f"{t.direccion.name}")
        for m in estado.minas:
            if m.posicion == (x, y):
                partes.append(f"mina de {m.dueno} "
                              f"({'armada' if m.armada else 'sin armar'})")
        if (x, y) in estado.refacciones:
            r = self.config.refaccion
            partes.append(f"tanque destruido: repara {r.minimo}–{r.maximo} "
                          f"a quien pase encima")
        texto = " · ".join(partes) if partes else "vacía"
        self.leyenda.configure(text=f"({x}, {y})  {texto}", fg=TINTA)

    def _ajustar_tablero(self):
        """El reporte promete 1280 x 720: el tablero cede lo que falte.

        Se mide lo que ocupa todo lo demás con las fuentes reales de este
        equipo, y el tablero se queda con el alto que sobre en la pantalla.
        """
        app = self.app
        px = app.px
        root = app.root
        self._fijar_natural()             # ya con las tarjetas puestas
        root.update_idletasks()
        resto = root.winfo_reqheight() - self._lienzo_natural()[1]
        lado = (root.winfo_screenheight() - px(MARGEN_PANTALLA) - resto
                - self.margen - px(12))
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        celda = max(px(24), min(lado // alto, px(TABLERO_PX) // ancho,
                                px(TABLERO_PX) // alto, px(96)))
        if celda < self._celda_natural:
            self._celda_natural = celda
            self._fijar_natural()
        self._repartir()

    def _tarjeta(self, t):
        """La tarjeta de un tanque: su dibujo, la vida en segmentos, la
        munición en íconos y la instrucción en curso."""
        app = self.app
        px = app.px
        panel = Panel(self.panel, app, modo="x", relleno=10,
                      acento=t.color)
        panel.configure(highlightbackground=BORDE_SUAVE)
        columnas = 2 if len(self._numeros) > 3 else 1
        compacto = columnas == 2
        k = t.numero - 1
        panel.grid(row=k // columnas, column=k % columnas, sticky="ew",
                   pady=px(3), padx=(0, px(6)) if k % columnas == 0
                   and columnas == 2 else 0)
        for col in range(columnas):
            self.panel.columnconfigure(col, weight=1, uniform="tarjeta")
        c = panel.cuerpo

        arriba = tk.Frame(c, bg=PANEL)
        arriba.pack(fill="x")
        sprite = tk.Canvas(arriba, width=px(40), height=px(40), bg=PANEL,
                           highlightthickness=0)
        sprite.pack(side="left")
        info = tk.Frame(arriba, bg=PANEL)
        info.pack(side="left", padx=(px(8), 0))
        tk.Label(info, text=espaciado(f"TANQUE {t.numero}"),
                 font=app.f_mini, fg=claro(t.color, 0.3), bg=PANEL,
                 anchor="w").pack(fill="x")
        nombre = tk.Label(info, text=t.nombre, font=app.f_seccion,
                          fg=TINTA, bg=PANEL, anchor="w")
        nombre.pack(fill="x")
        maxima = tk.Label(arriba, text=f"/{self.config.vida_inicial}",
                          font=app.f_chico, fg=GRIS, bg=PANEL)
        maxima.pack(side="right", anchor="s", pady=(0, px(6)))
        vida = tk.Label(arriba, text="", fg=TINTA, bg=PANEL,
                        font=(app.f_vida[0], 15) if compacto else app.f_vida)
        vida.pack(side="right", padx=(0, px(2)))

        barra = tk.Canvas(c, height=px(20), bg=PANEL, highlightthickness=0)
        barra.pack(fill="x", pady=(px(6), px(2)))
        stats = tk.Canvas(c, height=px(18), bg=PANEL, highlightthickness=0)
        stats.pack(fill="x")
        # width=1: la etiqueta toma el ancho de la tarjeta y recorta el
        # final de una instrucción larga en vez de ensanchar la ventana.
        linea = tk.Label(c, text="", font=app.f_mono, fg=GRIS, bg=PANEL,
                         anchor="w", width=1)
        linea.pack(fill="x", pady=(px(4), 0))
        return {"marco": panel, "nombre": nombre, "sprite": sprite,
                "linea": linea, "barra": barra, "stats": stats, "vida": vida,
                "color": t.color}

    def _resaltar(self, nombre: Optional[str]):
        """Ilumina con su color la tarjeta del tanque que está jugando."""
        for n, tarjeta in self._tarjetas.items():
            activo = n == nombre
            tarjeta["marco"].configure(
                highlightbackground=(tarjeta["color"] if activo
                                     else BORDE_SUAVE))
            tarjeta["marco"].resaltar(tarjeta["color"] if activo else None)

    # ---------------------------------------------------------- dibujo
    def _centro(self, pos):
        s, m = self.celda, self.margen
        return m + (pos[0] - 0.5) * s, m + (pos[1] - 0.5) * s

    def dibujar(self, estado, panel: bool = True):
        c, s, m = self.canvas, self.celda, self.margen
        px = self.app.px
        c.delete("all")
        for x in range(1, estado.ancho + 1):
            c.create_text(m + (x - 0.5) * s, m / 2, text=str(x),
                          font=self.app.f_mini, fill=GRIS)
        for y in range(1, estado.alto + 1):
            c.create_text(m / 2, m + (y - 0.5) * s, text=str(y),
                          font=self.app.f_mini, fill=GRIS)
        x1, y1 = m + estado.ancho * s, m + estado.alto * s
        for k, color in enumerate(("#1B2A3C", "#22364C")):   # resplandor
            g = px(5) - k * px(2)
            c.create_rectangle(m - g, m - g, x1 + g, y1 + g, outline=color,
                               width=px(2))
        # Damero nocturno, más iluminado hacia el centro como bajo un foco.
        self._fondos = {}
        for y in range(estado.alto):
            for x in range(estado.ancho):
                base = (sprites.FONDO if (x + y) % 2 == 0
                        else sprites.CASILLA_ALTERNA)
                dx = (x + 0.5) / estado.ancho - 0.5
                dy = (y + 0.5) / estado.alto - 0.5
                luz = max(0.0, 1 - math.hypot(dx, dy) * 1.5)
                fondo = sprites.mezclar(base, sprites.LUZ, 0.55 * luz)
                self._fondos[(x + 1, y + 1)] = fondo
                c.create_rectangle(m + x * s, m + y * s, m + (x + 1) * s,
                                   m + (y + 1) * s, fill=fondo,
                                   outline=sprites.REJILLA)
        # Cruces de mira en las intersecciones de la rejilla
        cruz = max(2, s * 0.07)
        for y in range(1, estado.alto):
            for x in range(1, estado.ancho):
                ix, iy = m + x * s, m + y * s
                c.create_line(ix - cruz, iy, ix + cruz + 1, iy,
                              fill=sprites.MARCA)
                c.create_line(ix, iy - cruz, ix, iy + cruz + 1,
                              fill=sprites.MARCA)
        c.create_rectangle(m, m, x1, y1, outline=sprites.MURO, width=2)
        for pos, ronda in self._marcas.items():
            edad = (estado.ronda - ronda) / 25
            if edad < 1 and pos in self._fondos:
                sprites.quemadura(c, *self._centro(pos), s,
                                  self._fondos[pos], 1 - edad, semilla=pos)
        largo, g = px(16), px(6)                 # esquineras doradas
        for cx, cy, dx, dy in ((m, m, 1, 1), (x1, m, -1, 1),
                               (m, y1, 1, -1), (x1, y1, -1, -1)):
            ex, ey = cx - dx * g, cy - dy * g
            c.create_line(ex, ey + dy * largo, ex, ey, ex + dx * largo, ey,
                          fill=ACENTO, width=px(3))

        centro = self._centro
        ocupadas = {t.posicion for t in estado.tanques if t.vivo}
        for pos in estado.refacciones:
            sprites.refaccion(c, *centro(pos), s, extra=(_tag(pos),))
        for mina in estado.minas:
            if mina.posicion not in ocupadas:
                sprites.mina(c, *centro(mina.posicion), s, mina.armada,
                             extra=(_tag(mina.posicion),))
        for t in estado.tanques:
            if t.vivo:
                sprites.tanque(c, *centro(t.posicion), s, t.numero, t.color,
                               t.direccion, t.escudo,
                               fondo=self._fondos[t.posicion])
        # Una mina bajo un tanque quedaría tapada: se ve chica en la esquina.
        for mina in estado.minas:
            if mina.posicion in ocupadas:
                x, y = centro(mina.posicion)
                sprites.mina(c, x + s * 0.3, y + s * 0.3, s * 0.45,
                             mina.armada, extra=(_tag(mina.posicion),))
        if not panel:
            return

        vivos = sum(1 for t in estado.tanques if t.vivo)
        self.app.titulo_barra.configure(
            text=f"Ronda {estado.ronda}"
                 + (f"  /  {self.config.rondas_maximas}"
                    if self.config.rondas_maximas else "  ·  sin límite"))
        self.app.subtitulo_barra.configure(
            text=f"{vivos} de {len(estado.tanques)} en pie   ·   tablero "
                 f"{estado.ancho}×{estado.alto}   ·   semilla "
                 f"{self.config.semilla}")
        p = self.progreso
        p.update_idletasks()
        p.delete("all")
        w, h = p.winfo_width(), int(p["height"])
        if self.config.rondas_maximas:
            lleno = w * min(1, estado.ronda / self.config.rondas_maximas)
        else:
            # Sin límite, la barra cuenta los tanques que ya cayeron.
            caidos = len(estado.tanques) - vivos
            lleno = w * min(1, caidos / max(1, len(estado.tanques) - 1))
        pasos = 24
        for k in range(pasos):
            p.create_rectangle(lleno * k / pasos, 0, lleno * (k + 1) / pasos
                               + 1, h, width=0,
                               fill=sprites.mezclar(ACENTO_OSCURO,
                                                    ACENTO_CLARO, k / pasos))
        self._actualizar_panel(estado)
        self._describir(estado)           # lo que hay bajo el ratón cambió

    def _actualizar_panel(self, estado):
        app = self.app
        px = app.px
        maxima = self.config.vida_inicial
        for t in estado.tanques:
            tarjeta = self._tarjetas[t.nombre]
            fraccion = max(0, t.vida) / maxima
            critica = t.vivo and fraccion <= 0.3

            # --- el dibujo del tanque
            sp = tarjeta["sprite"]
            sp.delete("all")
            lado = px(40)
            if t.vivo:
                sprites.tanque(sp, lado / 2, lado / 2, lado, t.numero,
                               t.color, t.direccion, etiqueta="mini")
            else:
                sprites.tanque(sp, lado / 2, lado / 2, lado, t.numero,
                               "#3A4656", t.direccion, etiqueta="mini")
                icono(sp, "x", lado / 2, lado / 2, lado * 0.9, ROJO_UI)

            # --- vida en segmentos inclinados; escudo debajo
            barra = tarjeta["barra"]
            barra.update_idletasks()
            w = max(barra.winfo_width(), px(220))
            barra.delete("all")
            n, hueco, sesgo = 20, px(3), px(4)
            ancho_seg = (w - sesgo - hueco * (n - 1)) / n
            llenos = math.ceil(n * fraccion) if t.vivo else 0
            color = ROJO_UI if critica else t.color
            alto_vida = px(12)
            for k in range(n):
                x0 = k * (ancho_seg + hueco)
                relleno = (claro(color, 0.15 * (k / n)) if k < llenos
                           else PANEL_ALTO)
                barra.create_polygon(x0 + sesgo, 0, x0 + sesgo + ancho_seg, 0,
                                     x0 + ancho_seg, alto_vida, x0, alto_vida,
                                     fill=relleno, outline="")
            if t.vivo and t.escudo:
                f = min(1, t.escudo / max(1, self.config.escudo_puntos))
                pildora(barra, 0, alto_vida + px(4), (w - sesgo) * f,
                        alto_vida + px(8), CIAN)

            # --- munición en íconos, y el daño hecho
            st = tarjeta["stats"]
            st.delete("all")
            h = px(18)
            cy = h / 2
            x = px(6)
            if t.vivo:
                for simbolo, tiene, tope, color_icono in (
                        ("misil", t.misiles, self.config.municion.misiles,
                         ACENTO),
                        ("mina", t.minas, self.config.municion.minas,
                         ROJO_UI)):
                    for k in range(tope):
                        icono(st, simbolo, x, cy, px(12),
                              color_icono if k < tiene else PANEL_HOVER)
                        x += px(11)
                    x += px(10)
                icono(st, "cruz", x, cy, px(12),
                      VERDE_OK if t.reparaciones else PANEL_HOVER)
                x += px(20)
                if t.escudo:
                    st.create_text(x, cy, text=f"ESC {t.escudo:g}",
                                   anchor="w", font=app.f_mini, fill=CIAN)
            else:
                st.create_text(0, cy, text=espaciado("DESTRUIDO"),
                               anchor="w", font=app.f_mini, fill=ROJO_UI)
            st.create_text(max(st.winfo_width(), px(220)), cy,
                           text=f"DAÑO {t.dano_infligido:g}", anchor="e",
                           font=app.f_mini, fill=ACENTO)

            tarjeta["vida"].configure(
                text=f"{t.vida:g}",
                fg=GRIS_CLARO if not t.vivo else ROJO_UI if critica
                else TINTA)
            tarjeta["nombre"].configure(fg=TINTA if t.vivo else GRIS_CLARO)
            instruccion = self._instrucciones.get(t.nombre)
            tarjeta["linea"].configure(
                text=(f"▸ L{t.linea}  {instruccion}"
                      if instruccion and t.vivo else ""))

    def _anotar(self, eventos):
        T = TipoEvento
        r = self.registro
        r.configure(state="normal")
        for e in eventos:
            if e.tipo is T.RONDA:
                r.insert("end", espaciado(f"RONDA {e.ronda}") + "\n", "ronda")
            elif e.tipo is T.INSTRUCCION:
                self._instrucciones[e.tanque] = e.datos["instruccion"]
                self._resaltar(e.tanque)
                n = self._numeros[e.tanque]
                r.insert("end", f"T{n}  ", f"t{n}")
                r.insert("end", f"L{e.datos['linea']} "
                                f"{e.datos['instruccion']}\n")
            elif e.tipo in (T.DESTRUCCION, T.MINA_EXPLOTA):
                # Lo importante se ve aunque se oculte el detalle.
                r.insert("end", f"      {e.texto}\n", "dano")
            elif e.tipo is not T.FIN:
                color = {T.DANO: "dano", T.REPARACION: "cura",
                         T.REFACCION: "cura", T.BLOQUEO: "escudo",
                         T.ESCUDO: "escudo"}.get(e.tipo)
                etiquetas = ("detalle", color) if color else ("detalle",)
                r.insert("end", f"      {e.texto}\n", etiquetas)
        r.configure(state="disabled")
        r.see("end")

    # ---------------------------------------------------------- contrato
    def inicio(self, estado, eventos):
        self._numeros = {t.nombre: t.numero for t in estado.tanques}
        for t in estado.tanques:
            self._tarjetas[t.nombre] = self._tarjeta(t)
            self.registro.tag_configure(
                f"t{t.numero}", foreground=claro(t.color),
                font=(self.app.f_mono[0], self.app.f_mono[1], "bold"))
        self._ajustar_tablero()           # ya con las tarjetas puestas
        self._avisar_saltadas()
        self._anotar(eventos)
        self.dibujar(estado)
        self._estado = estado
        return self._esperar_turno()

    def _avisar_saltadas(self):
        """Al empezar, la bitácora dice qué líneas se van a saltar."""
        if not self.saltadas:
            return
        r = self.registro
        r.configure(state="normal")
        r.insert("end", f"▲ Se saltan {len(self.saltadas)} líneas con "
                        f"errores; los tanques juegan con las demás:\n",
                 "aviso")
        for e in self.saltadas:
            r.insert("end", f"   {e.archivo} L{e.linea}  {e.mensaje}\n",
                     "aviso_detalle")
        r.configure(state="disabled")

    def _quemaduras(self, eventos, estado):
        """Anota dónde estalló algo para dejar la marca en el piso."""
        T = TipoEvento
        previo = self._estado or estado
        lugar = {t.nombre: t.posicion for t in previo.tanques}
        for e in eventos:
            d = e.datos
            if e.tipo in (T.MINA_EXPLOTA, T.DESTRUCCION):
                self._marcas[tuple(d["posicion"])] = estado.ronda
            elif e.tipo is T.DISPARO and d.get("arma") == "misil" \
                    and d.get("objetivo") in lugar:
                self._marcas[lugar[d["objetivo"]]] = estado.ronda

    def turno(self, estado, eventos):
        self._quemaduras(eventos, estado)
        self._anotar(eventos)
        retardo = retardo_ms(self.velocidad.get())
        if retardo >= RETARDO_MIN_ANIMAR and self._estado is not None:
            self._reproducir(eventos, estado, factor_animacion(retardo))
        self.dibujar(estado)
        self._estado = estado
        self.app.refrescar_menu()
        return self._entre_turnos()

    def ronda(self, estado, eventos):
        # Los eventos ya se anotaron y animaron turno por turno.
        return self._esperar_turno()

    def fin(self, estado, resultado):
        # «Terminar la partida aquí»: el motor ya decidió; ahora se espera
        # lo que el usuario quiera hacer después, como en cualquier final.
        if self.accion == "terminar":
            self.accion = None
        self._terminada = True
        self._estado = estado
        self._resaltar(None)
        self.dibujar(estado)
        self._botones_para("fin")
        if resultado is None:
            return
        if resultado.ganador is None:
            titular = "Empate"
        else:
            n = self._numeros[resultado.ganador]
            titular = f"Gana el tanque {n} · {resultado.ganador}"
            self.app.sonido.tocar("victoria")
        detalle = (f"{_MOTIVOS[resultado.motivo]} · "
                   f"{resultado.rondas} rondas")
        r = self.registro
        r.configure(state="normal")
        r.insert("end", f"{titular}\n", "fin")
        r.insert("end", f"{detalle}\n")
        r.configure(state="disabled")
        r.see("end")
        self._cartel(titular, detalle, estado, resultado)

    def despues(self) -> str:
        """Tras el final, espera: 'reiniciar', 'configurar', 'menu' (al
        menú principal) o 'salir'."""
        while self.accion is None:
            self._esperar_senal()
        return self.accion

    # ---------------------------------------------------------- control
    def senal(self, valor: str):
        """Lo que hace cada botón; también sirve para las pruebas."""
        if valor in ("reiniciar", "configurar", "salir", "menu", "terminar"):
            self.accion = valor
        elif valor == "iniciar":
            self.modo = "auto"
        elif valor == "pausar":
            self.modo = "pausa"
            self._ronda_pedida = False    # se detiene en el próximo turno
        if self.accion is None:
            self._botones_para(self.modo)
        self._senal.set(valor)

    def cerrar(self):
        self.senal("salir")

    def _esperar_senal(self) -> str:
        self._senal.set("")
        self.app.root.wait_variable(self._senal)
        return self._senal.get()

    def _esperar_turno(self) -> bool:
        """Decide cuándo se juega la siguiente ronda. False: salir."""
        while self.accion is None:
            if self.modo == "auto":
                tarea = self.app.root.after(
                    retardo_ms(self.velocidad.get()),
                    lambda: self._senal.set("tic"))
                valor = self._esperar_senal()
                self.app.root.after_cancel(tarea)
                if valor in ("tic", "una"):
                    self._ronda_pedida = True
                    return True
            elif self._esperar_senal() in ("una", "iniciar"):
                self._ronda_pedida = True
                return True
        return False

    def _entre_turnos(self) -> bool:
        """Si se pausó a media ronda, espera antes del siguiente turno."""
        while self.accion is None and self.modo == "pausa" \
                and not self._ronda_pedida:
            if self._esperar_senal() in ("una", "iniciar"):
                self._ronda_pedida = True
        return self.accion is None

    def _esperar_ms(self, ms: float) -> bool:
        """Deja pasar el tiempo de un cuadro sin congelar la ventana."""
        if self.accion is not None:
            return False
        self._reloj.set("")
        self.app.root.after(max(1, int(ms)), lambda: self._reloj.set("1"))
        self.app.root.wait_variable(self._reloj)
        return self.accion is None

    # ---------------------------------------------------------- animación
    def _crear_animador(self, factor: float) -> Animador:
        return Animador(self.canvas, self.celda, self._esperar_ms, factor,
                        sonar=self.app.sonido.tocar)

    def _reproducir(self, eventos, despues, factor: float) -> bool:
        """Anima los eventos de un turno partiendo del estado anterior."""
        actor = next((e.tanque for e in eventos
                      if e.tipo is TipoEvento.INSTRUCCION), None)
        if actor is None:
            return True
        # El cañón gira antes de disparar: se dibuja ya con la dirección
        # nueva del tanque que juega.
        nueva = {t.nombre: t.direccion for t in despues.tanques}
        previo = replace(self._estado, tanques=tuple(
            replace(t, direccion=nueva[t.nombre]) if t.nombre == actor
            else t for t in self._estado.tanques))
        self.dibujar(previo, panel=False)

        casillas = {t.nombre: t.posicion for t in previo.tanques if t.vivo}
        a = self._crear_animador(factor)
        if actor in casillas:
            a.resaltar(self._centro(casillas[actor]))
        self._animando = True
        try:
            for e in eventos:
                if not self._animar(a, e, casillas):
                    return False
            return True
        finally:
            self._animando = False

    def _borde(self, casilla, d: Direccion):
        """Punto de la pared en esa dirección, desde una casilla."""
        x, y = casilla
        while self.config.tablero.ancho >= x + d.dx >= 1 \
                and self.config.tablero.alto >= y + d.dy >= 1:
            x, y = x + d.dx, y + d.dy
        cx, cy = self._centro((x, y))
        return cx + d.dx * self.celda * 0.5, cy + d.dy * self.celda * 0.5

    def _animar(self, a: Animador, e, casillas) -> bool:
        """Elige la animación de un evento. False si el usuario salió."""
        T, d, quien = TipoEvento, e.datos, e.tanque
        if quien is not None and quien not in casillas:
            return True                   # ya no está en el tablero
        aqui = self._centro(casillas[quien]) if quien else None
        tag = f"tanque{self._numeros[quien]}" if quien else None

        if e.tipo is T.MOVIMIENTO and "hasta" in d:
            casillas[quien] = d["hasta"]
            return a.deslizar(tag, aqui, self._centro(d["hasta"]))
        if e.tipo is T.MOVIMIENTO:                     # contra la pared
            pared = Direccion[d["direccion"]]
            return a.embestida(tag, aqui, self._borde(casillas[quien],
                                                      pared), alcance=0.5)
        if e.tipo is T.DISPARO and d.get("arma") == "ametralladora":
            blanco = self._centro(casillas[d["objetivo"]])
            return a.rafaga(aqui, blanco, impacto=True, etiqueta=tag,
                            blanco=True)
        if e.tipo is T.SIN_EFECTO and d.get("arma") == "ametralladora":
            pared = self._borde(casillas[quien], Direccion[d["direccion"]])
            return a.rafaga(aqui, pared, impacto=True, etiqueta=tag)
        if e.tipo is T.DISPARO and d.get("arma") == "misil":
            if "objetivo" in d:
                destino = self._centro(casillas[d["objetivo"]])
            else:
                destino = self._borde(casillas[quien],
                                      Direccion[d["direccion"]])
            return (a.misil(aqui, destino, etiqueta=tag)
                    and a.explosion(destino, grande="objetivo" in d))
        if e.tipo is T.DISPARO and d.get("arma") == "choque":
            return a.embestida(tag, aqui,
                               self._centro(casillas[d["objetivo"]]))
        if e.tipo is T.DANO:
            return (a.golpe(tag, aqui)
                    and a.texto(aqui, f"−{d['puntos']:g}", ROJO))
        if e.tipo is T.BLOQUEO:
            return (a.bloqueo(aqui)
                    and a.texto(aqui, f"−{d['puntos']:g} escudo", AZUL))
        if e.tipo is T.ESCUDO:
            return a.escudo(aqui)
        if e.tipo in (T.REPARACION, T.REFACCION):
            if e.tipo is T.REFACCION:
                self.canvas.delete(_tag(d["posicion"]))
            return (a.curar(aqui)
                    and a.texto(aqui, f"+{d['puntos']:g}", VERDE))
        if e.tipo is T.RADAR:
            return a.radar(aqui, Direccion[d["direccion"]], d["lectura"])
        if e.tipo is T.MINA_COLOCADA:
            # La mina sale del tanque y cae en la esquina contigua.
            destino = self._centro(d["posicion"])
            return a.mina_nueva(aqui, destino, escala=1.0)
        if e.tipo is T.MINA_ARMADA:
            return a.mina_armada(self._centro(d["posicion"]))
        if e.tipo is T.MINA_EXPLOTA:
            self.canvas.delete(_tag(d["posicion"]))
            return a.explosion(self._centro(d["posicion"]), grande=True)
        if e.tipo is T.DESTRUCCION:
            # Una explosión grande y dos réplicas antes del humo
            seguir = a.explosion(aqui, grande=True)
            self.canvas.delete(tag)
            del casillas[quien]
            s = self.celda
            for dx, dy in ((0.22, -0.18), (-0.2, 0.2)):
                seguir = seguir and a.explosion(
                    (aqui[0] + dx * s, aqui[1] + dy * s), grande=False)
            return seguir and a.humo(aqui)
        if e.tipo is T.CONDICION_FALSA:
            return a.texto(aqui, "✗", "#8A8A8A", ms=380)
        if e.tipo is T.SIN_EFECTO:
            return a.texto(aqui, "…", "#8A8A8A", ms=380)
        return True

    def _botones_para(self, modo: str):
        activos = {"pausa": {"iniciar", "una", "reiniciar", "configurar"},
                   "auto": {"pausar", "una", "reiniciar", "configurar"},
                   "fin": {"reiniciar", "configurar"}}[modo]
        for senal, boton in self.botones.items():
            self.app.activar(boton, senal in activos)
        self.app.refrescar_menu()

    def _cartel(self, titular: str, detalle: str, estado=None,
                resultado=None):
        """Cartel final: oscurece el tablero y muestra la clasificación."""
        self._ultimo_cartel = (titular, detalle, estado, resultado)
        c, app = self.canvas, self.app
        px = app.px
        w, h = int(c["width"]), int(c["height"])
        c.create_rectangle(0, 0, w, h, fill=NOCHE, stipple="gray50",
                           width=0, tags="cartel")
        orden = []
        ganador = resultado.ganador if resultado else None
        if estado is not None:
            orden = sorted(estado.tanques, key=lambda t: (
                t.nombre != ganador, not t.vivo, -t.dano_infligido,
                t.numero))
        color = next((t.color for t in (estado.tanques if estado else ())
                      if t.nombre == ganador), ACENTO)
        renglon = px(26)
        alto = px(150) + renglon * len(orden)
        ancho = min(w - px(20), px(460))
        x0, y0 = (w - ancho) / 2, max(px(30), (h - alto) / 2)
        x1, y1 = x0 + ancho, y0 + alto
        chaflan(c, x0 - px(3), y0 - px(3), x1 + px(3), y1 + px(3), px(18),
                fill="", outline=sprites.mezclar(ACENTO, NOCHE, 0.55),
                width=px(4), tags="cartel")
        chaflan(c, x0, y0, x1, y1, px(16), fill=PANEL, outline=ACENTO,
                width=2, tags="cartel")
        # medallón con la estrella, montado sobre el borde superior
        mx, my, r = (x0 + x1) / 2, y0, px(26)
        c.create_oval(mx - r, my - r, mx + r, my + r, fill=NOCHE,
                      outline=ACENTO, width=px(3), tags="cartel")
        estrella(c, mx, my, r * 0.62, fill=ACENTO if ganador else GRIS,
                 outline="", tags="cartel")
        y = y0 + px(46)
        c.create_text(mx, y, text=espaciado("VICTORIA" if ganador
                                            else "EMPATE"),
                      font=app.f_mini, fill=claro(color, 0.3), tags="cartel")
        y += px(26)
        c.create_text(mx, y, text=titular, font=app.f_grande, fill=TINTA,
                      tags="cartel")
        y += px(24)
        c.create_text(mx, y, text=detalle, font=app.f_chico, fill=GRIS,
                      tags="cartel")
        y += px(16)
        for k, t in enumerate(orden, 1):
            y += renglon
            if k == 1 and ganador:
                c.create_rectangle(x0 + px(14), y - renglon / 2 + px(2),
                                   x1 - px(14), y + renglon / 2 - px(2),
                                   fill=sprites.mezclar(ACENTO, PANEL, 0.82),
                                   width=0, tags="cartel")
            rr = px(6)
            c.create_oval(x0 + px(30) - rr, y - rr, x0 + px(30) + rr, y + rr,
                          fill=t.color, outline=claro(t.color), tags="cartel")
            c.create_text(x0 + px(44), y,
                          text=f"{k}.  Tanque {t.numero} · {t.nombre}",
                          anchor="w", font=app.f_texto,
                          fill=TINTA if t.vivo else GRIS, tags="cartel")
            estado_t = f"vida {t.vida:g}" if t.vivo else "destruido"
            c.create_text(x1 - px(22), y,
                          text=f"{estado_t}  ·  daño {t.dano_infligido:g}",
                          anchor="e", font=app.f_chico,
                          fill=GRIS if t.vivo else ROJO_UI, tags="cartel")
        c.create_text(mx, y1 - px(18),
                      text="R  jugar otra vez    ·    Esc  menú",
                      font=app.f_chico, fill=GRIS_CLARO, tags="cartel")


def _tag(pos) -> str:
    """Etiqueta del Canvas para lo que hay en una casilla."""
    return f"en_{pos[0]}_{pos[1]}"


# ======================================================================
AYUDA = [
    ("h", "Cómo se juega"),
    ("", "Nadie controla los tanques durante la partida: cada uno ejecuta "
         "su programa, una instrucción por turno, y el usuario observa. "
         "En cada ronda juegan todos los tanques vivos; el orden gira una "
         "posición en cada ronda para que nadie conserve la ventaja de "
         "actuar primero."),
    ("", "Gana el último tanque en pie. Por omisión no hay límite de "
         "rondas: la partida sigue hasta que quede uno, y si los tanques se "
         "quedan dando vueltas, «Terminar la partida aquí» (menú ☰) la "
         "corta. En la configuración, el botón ∞ apagado deja elegir un "
         "límite; al llegar a él gana el que más daño haya infligido a sus "
         "rivales, y si coincide, es empate."),
    ("h", "El programa de un tanque"),
    ("", "Un archivo de texto con una instrucción por línea. Las líneas "
         "vacías se ignoran y # marca un comentario. Al terminar el "
         "archivo, el programa vuelve a la primera línea."),
    ("m", "MOV(d)       avanza una casilla; pared o tanque: choque de 12"),
    ("m", "AMT(d)       5 al primer tanque en esa dirección (configurable)"),
    ("m", "MISIL(d)     como AMT pero el doble de daño; tres por partida"),
    ("m", "MINA(NE)     lanza una mina a la esquina; 1.5 veces la AMT; tres"),
    ("m", "ESCUDO       vida extra: absorbe 20 puntos hasta agotarse"),
    ("m", "REPARAR      +20 de vida; una vez por partida"),
    ("m", "ESPERAR      no hace nada"),
    ("m", "IF RADAR(d) > 0 THEN AMT(d)"),
    ("m", "IF V < 40 THEN REPARAR"),
    ("", "Todo se escribe en mayúsculas, también las direcciones. RADAR(d) "
         "solo existe dentro de un IF: explora en ese momento y da la "
         "distancia, positiva a un tanque y negativa a la pared. V es la "
         "variable con la vida del tanque. Después del THEN va cualquier "
         "instrucción (MOV, AMT, MISIL, MINA, ESCUDO, REPARAR o ESPERAR), "
         "pero no otro IF. Las esquinas "
         "de MINA van sin coma: (NE), (NO), (SE) y (SO). Las direcciones son N, "
         "S, E y O; las coordenadas empiezan en 1 con la fila 1 al norte."),
    ("", "El daño no es una instrucción: lo causan las armas, las minas y "
         "los choques. En un choque entre tanques los dos reciben el daño."),
    ("h", "El tablero"),
    ("", "Cada tanque lleva su número y su color; el cañón apunta a la "
         "última dirección que usó. Un círculo punteado azul es el escudo. "
         "La mina roja de trazo continuo está armada; la de trazo punteado "
         "aún no. La caja verde es un tanque destruido: quien pasa por "
         "encima se repara de 15 a 35 puntos al azar."),
    ("h", "Animaciones"),
    ("", "Cada turno se anima: esquinas doradas marcan al tanque que "
         "juega; la ametralladora dispara una ráfaga; el misil sube en arco "
         "hasta el primer tanque o la pared y estalla; la mina sale "
         "volando a la esquina; el IF con radar lanza un haz verde que termina en un pulso rojo "
         "si encontró un tanque o gris si llegó a la pared. El daño sube en "
         "rojo (−5), la curación en verde (+20) y lo que el escudo absorbe "
         "en azul. Una ✗ gris es un IF cuya condición fue falsa."),
    ("", "Los disparos hacen retroceder al tanque, las explosiones "
         "grandes sacuden el tablero y dejan una quemadura en el piso que "
         "se borra con las rondas; el tanque que recibe daño destella en "
         "rojo. Las minas armadas laten y las refacciones brillan."),
    ("", "Cada arma suena: ráfaga, misil, explosión, motor, choque, radar, "
         "escudo y reparación. La portada arranca con su fanfarria y luego "
         "entra la música, una marcha arcade de guerra (metales, bajo, "
         "guitarra y batería) que sigue en todas las pantallas. El "
         "radar del título da un pulso; los botones suenan al pasar el ratón "
         "y al pulsarlos (el dorado confirma, Volver y Salir bajan de "
         "tono)."),
    ("", "El sonido se controla desde el menú ☰ de arriba a la derecha, "
         "en cualquier pantalla: la música y los efectos se encienden y "
         "apagan por separado, y la música tiene su volumen de 0 a 10 (− y "
         "+, un clic en las barras o la rueda del ratón)."),
    ("", "Una mina bajo un tanque se ve pequeña en la esquina de su "
         "casilla. En las velocidades 9 y 10 no se anima: avance rápido."),
    ("h", "Configuración"),
    ("", "Cada fila asocia un tanque a su programa y a un color. El aviso de "
         "la derecha revisa el programa al momento: verde si es válido, "
         "rojo con el número de errores; un clic en el aviso rojo los "
         "muestra. En «Campo de batalla» la miniatura enseña el tablero "
         "elegido: ancho y alto con − y +, el eslabón los mantiene "
         "iguales y los botones 4, 6, 8, 10 y 12 dan medidas rápidas. En "
         "«Arsenal y defensa» cada valor tiene su color, su rango y una "
         "pista con perilla: se arrastra, se pulsa − o +, se gira la "
         "rueda del ratón o se escribe el número. «Valores por omisión» "
         "los devuelve a los del reglamento y el dado elige otra semilla."),
    ("h", "Programar un tanque"),
    ("", "«Programar» en la tarjeta de un tanque (o «Editar» en el visor) "
         "abre el editor del juego. Se escribe una instrucción por línea y "
         "cada una se revisa al momento: ✓ verde si el tanque la entiende, "
         "✗ roja si no, con el motivo debajo y en un globo al pasar el "
         "ratón. A la derecha están las instrucciones disponibles: un clic "
         "inserta una. «Aleatorio» escribe un programa válido al azar que "
         "luego se puede modificar. «Guardar» (Ctrl+S) lo guarda en "
         "tanques/ y se lo asigna al tanque; si quedan errores, avisa "
         "antes."),
    ("h", "Teclado"),
    ("m", "Enter        iniciar (menú y configuración)"),
    ("m", "F1           esta ayuda (menú)"),
    ("m", "Espacio      iniciar o pausar la partida"),
    ("m", "→            una ronda"),
    ("m", "+ / −        más rápido / más lento"),
    ("m", "R            reiniciar la misma partida"),
    ("m", "Esc          menú ☰ (portada y partida)"),
    ("h", "Menú de la partida"),
    ("", "El botón ☰ de arriba a la derecha (o Esc) despliega el menú sin "
         "pausar la partida: sigue jugándose detrás y el menú se pone al "
         "día solo. Tiene Volver a la partida (cierra el menú), Pausar o "
         "Reanudar, Reiniciar la partida, Volver a los tanques (la "
         "configuración), Terminar la partida aquí (gana el tanque en pie "
         "con más daño infligido, como al llegar al límite de rondas, y se "
         "ve la clasificación) y Menú principal. Abajo está el sonido."),
    ("h", "Controles"),
    ("", "Iniciar reproduce la partida sola a la velocidad elegida; Pausar "
         "la detiene en el siguiente turno; Una ronda avanza de una en una. "
         "Reiniciar vuelve a jugar la misma partida: con la misma semilla, "
         "el resultado es idéntico. Cada partida se guarda en la carpeta "
         "bitacoras/."),
]
