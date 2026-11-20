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
import os
import random
import re
import subprocess
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import colorchooser, filedialog, font as tkfont, messagebox
from typing import Callable, Optional

from ..config import (MAX_TANQUES, RANGOS, Configuracion, Dano, Municion,
                      Tablero, TanqueConfig)
from ..lenguaje import Interprete, formato_errores
from ..modelo import Direccion, Motivo, TipoEvento
from . import sprites
from .animaciones import AZUL, ROJO, VERDE, Animador
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
            Motivo.EMPATE: "límite de rondas; el daño infligido coincide"}


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
    }

    def __init__(self, padre, app: "AppGrafica", texto: str,
                 orden: Callable, estilo: str = "secundario",
                 icono_: Optional[str] = None, minimo: int = 0,
                 alto: int = 36, ayuda: str = ""):
        self._listo = False
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
            self.orden()

    def _sobre(self, encima):
        self._encima = encima
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

    def __init__(self, padre, app, valor=5, command=None, n=10):
        self.app, self.n, self.command = app, n, command
        self._valor = valor
        super().__init__(padre, width=app.px(16) * n, height=app.px(26),
                         bg=_fondo_de(padre), highlightthickness=0,
                         cursor="hand2")
        self.bind("<Button-1>", self._clic)
        self.bind("<B1-Motion>", self._clic)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self._dibujar()

    def get(self) -> int:
        return self._valor

    def set(self, valor):
        self._valor = min(self.n, max(1, int(round(float(valor)))))
        self._dibujar()

    def _clic(self, e):
        paso = self.winfo_width() / self.n
        nuevo = min(self.n, max(1, int(e.x // paso) + 1))
        if nuevo != self._valor:
            self.set(nuevo)
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
                 al_cerrar: Optional[Callable[[], None]] = None):
        self.app, self.ruta, self.numero = app, Path(ruta), numero
        self.color, self.config, self.al_cerrar = color, config, al_cerrar
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
                  ayuda="Volver a leer el archivo después de corregirlo"
                  ).pack(side="right", padx=px(8))
        app.boton(pie, "Editar", self._abrir, icono="carpeta",
                  ayuda="Abrir el archivo en el editor de texto para "
                        "corregirlo").pack(side="right")
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
        t.tag_configure("comentario", foreground=GRIS_CLARO,
                        font=(mono, 10, "italic"))
        t.tag_configure("explica", foreground=GRIS,
                        font=(app.f_texto[0], 9))
        t.tag_configure("explica_error", foreground=ROJO_UI,
                        font=(app.f_texto[0], 9))
        t.tag_configure("error", background="#3A161C")
        t.tag_configure("codigo_error", foreground="#FFB4B4",
                        underline=True)
        t.tag_configure("encima", background=PANEL_HOVER)
        for palabra, tono in _COLOR_PALABRA.items():
            t.tag_configure(f"p_{palabra}", foreground=tono,
                            font=(mono, 10, "bold"))
        t.tag_configure("direccion", foreground=_COLOR_DIRECCION)
        t.tag_configure("entero", foreground=_COLOR_NUMERO)
        t.tag_configure("signo", foreground=GRIS)
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
        for parte in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ_]+|-?\d+|\s+|.",
                                codigo):
            if parte.isspace():
                etiqueta = ()
            elif parte in _COLOR_PALABRA:
                etiqueta = (f"p_{parte}",)
            elif parte in ("N", "S", "E", "O") or parte in _ESQUINAS:
                etiqueta = ("direccion",)
            elif re.fullmatch(r"-?\d+", parte):
                etiqueta = ("entero",)
            elif parte in "(),<>=":
                etiqueta = ("signo",)
            else:
                etiqueta = ()
            t.insert("end", parte, etiqueta + extra)
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
        c, px = self.cabeza, self.app.px
        w = max(c.winfo_width(), px(600))
        h = int(c["height"])
        c.delete("all")
        degradado(c, w, h, "#132235", FONDO_BARRA, horizontal=True,
                  pasos=32)
        c.create_line(0, h - 2, w, h - 2, fill=self.color, width=2)
        sprites.tanque(c, px(42), h / 2, px(52), self.numero, self.color,
                       Direccion.E, etiqueta="visor")
        c.create_text(px(80), h / 2 - px(12),
                      text=espaciado(f"TANQUE {self.numero}"),
                      anchor="w", font=self.app.f_mini,
                      fill=claro(self.color, 0.3))
        c.create_text(px(80), h / 2 + px(10), text=self.ruta.name,
                      anchor="w", font=self.app.f_barra, fill=TINTA)
        x = w - px(18)
        validas = getattr(self, "validas", 0)
        con_error = getattr(self, "con_error", 0)
        for texto, tono in ((f"{con_error} con error", ROJO_UI if con_error
                             else GRIS_CLARO),
                            (f"{validas} válidas", VERDE_OK if validas
                             else GRIS_CLARO)):
            ancho = self.app.fuente_boton.measure(texto) + px(24)
            rect_redondeado(c, x - ancho, h / 2 - px(13), x, h / 2 + px(13),
                            px(13), fill=PANEL_ALTO, outline=tono)
            c.create_text(x - ancho / 2, h / 2, text=texto, fill=tono,
                          font=self.app.f_boton)
            x -= ancho + px(8)

    # ------------------------------------------------------------ acciones
    def _abrir(self):
        """Abre el archivo en el editor del sistema para corregirlo."""
        try:
            if sys.platform == "win32":
                os.startfile(self.ruta)                    # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.ruta)])
            else:
                subprocess.Popen(["xdg-open", str(self.ruta)])
        except OSError as e:
            messagebox.showerror("No se pudo abrir el archivo", str(e),
                                 parent=self.ventana)

    def cerrar(self):
        self.globo.ocultar()
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
              alto: int = 36, ayuda: str = "") -> Boton:
        """Botón de la aplicación; `ancho` es el mínimo en píxeles a 96 ppp.

        No toma el foco: así la barra espaciadora es siempre el atajo de
        la pantalla y no «pulsa» el último botón usado.
        """
        return Boton(padre, self, texto, orden,
                     estilo or ("primario" if primario else "secundario"),
                     icono, minimo=ancho, alto=alto, ayuda=ayuda)

    def activar(self, boton, activo: bool):
        boton.configure(state="normal" if activo else "disabled")

    def atajo(self, secuencia: str, orden):
        """Tecla de la pantalla actual; se olvida al cambiar de pantalla."""
        self.root.bind(secuencia, lambda _e: (orden(), "break")[1])
        self._atajos.append(secuencia)

    def rotulo(self, padre, texto, color=ACENTO, fondo=None):
        """Rótulo de sección: mayúsculas espaciadas en color."""
        return tk.Label(padre, text=espaciado(texto.upper()),
                        font=self.f_mini, fg=color,
                        bg=fondo or _fondo_de(padre))

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
            barra.coords(sub, e.width - px(20), px(29))

        barra.bind("<Configure>", redibujar)
        return self._pantalla

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
        try:
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
        self.atajo("<Return>", lambda: self._elegir("iniciar"))
        self.atajo("<F1>", lambda: self._elegir("ayuda"))
        self.root.after(40, self._animar_portada)
        return self._esperar()

    def _dibujar_portada(self, w, h):
        est = self._portada
        c, px = est["c"], self.px
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
        c.create_text(w / 2 + px(4), ty + px(5), text="GUERRA DE TANQUES",
                      font=self.f_portada, fill="#000000")
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            c.create_text(w / 2 + dx, ty + dy, text="GUERRA DE TANQUES",
                          font=self.f_portada, fill=ACENTO_OSCURO)
        c.create_text(w / 2, ty, text="GUERRA DE TANQUES",
                      font=self.f_portada, fill=ACENTO)
        c.create_text(w / 2, ty + px(48),
                      text=espaciado("SIMULADOR DE COMBATE AUTÓNOMO"),
                      font=self.f_mini, fill=CIAN)
        c.create_text(w / 2, ty + px(76),
                      text="Programa tu tanque. Míralo pelear.",
                      font=(self.f_texto[0], 12), fill=GRIS)

        y = ty + px(140)
        for b in est["botones"]:
            fondo = sprites.mezclar(cielo_arriba, cielo_abajo,
                                    min(1, y / horizonte))
            b.configure(bg=fondo)
            c.create_window(w / 2, y, window=b)
            y += px(56)
        c.create_text(w / 2, y - px(8), text="Enter  iniciar   ·   F1  ayuda",
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
            messagebox.showerror("Configuración incompleta",
                                 "\n".join(problemas), parent=self.root)

    def mostrar_errores(self, texto: str):
        messagebox.showerror("Errores en los programas", texto,
                             parent=self.root)

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
        cuerpo = tk.Frame(p, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=px(24), pady=px(12))

        # --- el escuadrón
        cabeza = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        cabeza.pack(fill="x")
        app.rotulo(cabeza, "Escuadrón").pack(side="left")
        self.cuenta = tk.Label(cabeza, text="", font=app.f_boton, fg=ACENTO,
                               bg=FONDO_VENTANA)
        self.cuenta.pack(side="right")
        tk.Label(cuerpo, text="Asigna un programa .txt a cada tanque. Se "
                 "revisa al momento: «Ver» lo muestra línea por línea y las "
                 "líneas con errores se saltan al jugar. Clic en el tanque "
                 "para cambiar su color.",
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

        # --- reglas, en dos paneles
        grupos = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        grupos.pack(fill="x", pady=(px(12), 0))
        partida = self._grupo(grupos, "Partida", "ajustar")
        partida.master.master.pack(side="left", anchor="n",
                                   padx=(0, px(10)))
        armas = self._grupo(grupos, "Arsenal y defensa", "x")
        armas.master.master.pack(side="left", fill="x", expand=True,
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

        self._campo(partida, 0, 0, "Tablero (ancho × alto)",
                    (self.ancho, 2, 30), (self.alto, 2, 30))
        caja = self._campo(partida, 1, 0, "Semilla", (self.semilla, None))
        app.boton(caja, "", self._sortear, icono="dado", alto=30).pack(
            side="left", padx=(px(6), 0))
        self._campo(partida, 2, 0, "Rondas máximas",
                    (self.rondas, 1, 5000, 10))

        for k, (etiqueta, variable, clave) in enumerate((
                ("Daño AMT", self.amt, "ametralladora"),
                ("Misiles", self.misiles, "misiles"),
                ("Minas", self.minas, "minas"),
                ("REPARAR cura", self.reparar, "reparar"),
                ("Escudo absorbe", self.escudo, "escudo"),
                ("Mina se arma en (rondas)", self.armado,
                 "rondas_armado"))):
            minimo, maximo = RANGOS[clave]
            self._campo(armas, k % 3, k // 3,
                        f"{etiqueta}  ({minimo}–{maximo})",
                        (variable, minimo, maximo))
        resumen = tk.Frame(armas, bg=PANEL)
        resumen.grid(row=0, column=2, rowspan=3, sticky="nsew",
                     padx=(px(6), 0))
        armas.columnconfigure(2, weight=1)
        self.medidores = tk.Canvas(resumen, height=px(92), bg=PANEL,
                                   highlightthickness=0)
        self.medidores.pack(fill="x")
        self.derivados = tk.Label(resumen, text="", font=app.f_chico,
                                  fg=GRIS, bg=PANEL, anchor="w",
                                  justify="left", wraplength=px(240))
        self.derivados.pack(fill="x", pady=(px(4), 0))
        self.amt.trace_add("write", lambda *_a: self._derivar())
        self.medidores.bind("<Configure>", lambda _e: self._derivar())

        botones = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        botones.pack(fill="x", pady=(px(14), 0))
        app.boton(botones, "Valores por omisión", self._por_omision,
                  icono="reiniciar").pack(side="left")
        app.boton(botones, "INICIAR BATALLA", lambda: app._elegir("iniciar"),
                  ancho=220, primario=True, icono="play", alto=44
                  ).pack(side="right")
        app.boton(botones, "Volver", lambda: app._elegir("volver"),
                  estilo="fantasma", icono="atras", alto=44
                  ).pack(side="right", padx=px(10))
        app.atajo("<Return>", lambda: app._elegir("iniciar"))
        app.atajo("<Escape>", lambda: app._elegir("volver"))

        for i in range(MAX_TANQUES):
            self._revisar(i)
        self._derivar()

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
        app.boton(acciones, "Examinar", lambda k=i: self._examinar(k),
                  icono="carpeta", alto=30).pack(side="left")
        ver = app.boton(acciones, "Ver", lambda k=i: self._ver(k),
                        icono="ojo", alto=30,
                        ayuda="Ver el programa línea por línea")
        ver.pack(side="left", padx=(px(6), 0))
        self.ver.append(ver)
        app.boton(acciones, "", lambda k=i: self.rutas[k].set(""),
                  icono="x", alto=30, ayuda="Quitar este tanque"
                  ).pack(side="right")
        app.boton(acciones, "", lambda k=i: self._color(k), icono="paleta",
                  alto=30, ayuda="Cambiar el color"
                  ).pack(side="right", padx=px(6))
        var.trace_add("write", lambda *_a, k=i: self._revisar(k))

    def _grupo(self, padre, titulo, modo):
        """Panel con rótulo; devuelve el marco interior para los campos."""
        app = self.app
        panel = Panel(padre, app, modo=modo, relleno=14, acento=ACENTO)
        app.rotulo(panel.cuerpo, titulo).pack(anchor="w")
        dentro = tk.Frame(panel.cuerpo, bg=PANEL)
        dentro.pack(fill="both", expand=True, pady=(app.px(6), 0))
        return dentro

    def _campo(self, grupo, fila, columna, etiqueta, *variables):
        """Etiqueta y uno o más campos: (variable, mínimo, máximo[, paso]).

        Con mínimo None el campo es libre; si no, una caja con flechas que
        ya marca el rango permitido.
        """
        app = self.app
        caja = tk.Frame(grupo, bg=PANEL)
        caja.grid(row=fila, column=columna, sticky="w",
                  padx=(0, app.px(18)), pady=app.px(3))
        tk.Label(caja, text=etiqueta, font=app.f_chico, fg=GRIS,
                 bg=PANEL).pack(anchor="w")
        linea = tk.Frame(caja, bg=PANEL)
        linea.pack(anchor="w")
        for k, (variable, minimo, *resto) in enumerate(variables):
            if k:
                tk.Label(linea, text="×", bg=PANEL, fg=GRIS,
                         font=app.f_texto).pack(side="left", padx=4)
            if minimo is None:
                caja_texto = app.campo_texto(linea, variable, ancho=8)
            else:
                maximo = resto[0]
                paso = resto[1] if len(resto) > 1 else 1
                valor = variable.get()
                caja_texto = tk.Spinbox(
                    linea, textvariable=variable, from_=minimo, to=maximo,
                    increment=paso, width=6, relief="flat", bd=0,
                    bg=PANEL_ALTO, fg=TINTA, buttonbackground=PANEL_HOVER,
                    insertbackground=ACENTO, highlightthickness=1,
                    highlightbackground=BORDE, highlightcolor=ACENTO,
                    selectbackground=ACENTO, selectforeground=TINTA_ACENTO)
                # Spinbox reemplaza el texto por `from_` al crearse.
                variable.set(valor)
            caja_texto.configure(justify="center", font=app.f_texto)
            caja_texto.pack(side="left", ipady=app.px(4))
        return linea

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
                      self.config, al_cerrar=lambda: self._revisar(i))

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
            pie = "Ninguna línea es válida. Corrígelo con «Ver»."
            color = ROJO_UI
        else:
            titulo = f"{len(errores)} líneas se saltarán al jugar"
            pie = "El tanque juega con las demás. «Ver» las muestra."
            color = ACENTO
        self.globo.mostrar(self.app.root, e.x_root + self.app.px(16),
                           e.y_root + self.app.px(14), titulo,
                           "\n".join(lineas) + "\n\n" + pie, color)

    def _derivar(self):
        """Medidores del daño de cada arma, derivado de la ametralladora."""
        try:
            amt = int(self.amt.get())
        except ValueError:
            self.derivados.configure(text="")
            return
        d = Dano(amt, self.config.dano.choque_tanque,
                 self.config.dano.choque_pared)
        self.derivados.configure(
            text=f"Con AMT {amt}: misil {d.misil:g} · mina {d.mina:g} · "
                 f"choque {d.choque_tanque:g} a cada tanque · pared "
                 f"{d.choque_pared:g}")
        c, px = self.medidores, self.app.px
        c.delete("all")
        w = max(c.winfo_width(), px(220))
        tope = RANGOS["ametralladora"][1] * 2       # el misil más fuerte
        for k, (nombre, valor, color) in enumerate((
                ("AMT", d.ametralladora, CIAN), ("MISIL", d.misil, ACENTO),
                ("MINA", d.mina, ROJO_UI),
                ("CHOQUE", d.choque_tanque, GRIS))):
            y = px(10) + k * px(22)
            c.create_text(0, y, text=espaciado(nombre), anchor="w",
                          font=self.app.f_mini, fill=GRIS)
            x0, x1 = px(70), w - px(40)
            pildora(c, x0, y - px(4), x1, y + px(4), PANEL_ALTO)
            pildora(c, x0, y - px(4), x0 + (x1 - x0) * min(1, valor / tope),
                    y + px(4), color)
            c.create_text(w, y, text=f"{valor:g}", anchor="e",
                          font=self.app.f_boton, fill=TINTA)

    def _sortear(self):
        self.semilla.set(str(random.randint(1, 99999)))

    def _por_omision(self):
        base = Configuracion()
        for var, valor in ((self.ancho, base.tablero.ancho),
                           (self.alto, base.tablero.alto),
                           (self.rondas, base.rondas_maximas),
                           (self.amt, base.dano.ametralladora),
                           (self.misiles, base.municion.misiles),
                           (self.minas, base.municion.minas),
                           (self.reparar, base.reparar_puntos),
                           (self.escudo, base.escudo_puntos),
                           (self.armado, base.mina_rondas_armado)):
            var.set(str(valor))

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
        _, elegido = colorchooser.askcolor(self.colores[i],
                                           parent=self.app.root,
                                           title=f"Color del tanque {i + 1}")
        if elegido:
            self.colores[i] = elegido.upper()
            self._pintar_muestra(i)

    def _examinar(self, i):
        inicial = self.app.raiz / "tanques"
        ruta = filedialog.askopenfilename(
            parent=self.app.root, title=f"Programa del tanque {i + 1}",
            initialdir=inicial if inicial.is_dir() else self.app.raiz,
            filetypes=[("Programas de tanque", "*.txt"), ("Todos", "*.*")])
        if ruta:
            ruta = Path(ruta)
            try:
                ruta = ruta.resolve().relative_to(self.app.raiz.resolve())
            except ValueError:
                pass                       # fuera del proyecto: absoluta
            self.rutas[i].set(ruta.as_posix())

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
        rondas = entero(self.rondas, "Rondas máximas")
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
        self._armar(velocidad)

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

        # --- izquierda: el tablero en su panel, y los controles
        izq = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        izq.pack(side="left", fill="y")
        marco = Panel(izq, app, modo="ajustar", relleno=10, acento=ACENTO)
        marco.pack(anchor="w")
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        self.celda = max(px(24), min(px(TABLERO_PX) // ancho,
                                     px(TABLERO_PX) // alto, px(80)))
        self.margen = px(26)                # para los números de coordenada
        self.canvas = tk.Canvas(
            marco.cuerpo, width=self.margen + ancho * self.celda + px(12),
            height=self.margen + alto * self.celda + px(12), bg=PANEL,
            highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Motion>", self._sobre)
        self.canvas.bind("<Leave>", self._fuera)
        self._raton: Optional[tuple[int, int]] = None
        self.leyenda = tk.Label(marco.cuerpo, text="", font=app.f_chico,
                                fg=GRIS, bg=PANEL, anchor="w")
        self.leyenda.pack(fill="x", padx=px(4), pady=(px(4), 0))
        self._info_por_omision()

        controles = Panel(izq, app, modo="x", relleno=12)
        controles.pack(fill="x", pady=(px(10), 0))
        c = controles.cuerpo
        fila = tk.Frame(c, bg=PANEL)
        fila.pack(fill="x")
        self.botones = {}
        for texto, senal, simbolo in (("Iniciar", "iniciar", "play"),
                                      ("Pausar", "pausar", "pausa"),
                                      ("Una ronda", "una", "paso")):
            b = app.boton(fila, texto, lambda s=senal: self.senal(s),
                          primario=senal == "iniciar", icono=simbolo,
                          ancho=96, alto=40)
            b.pack(side="left", padx=(0, px(6)))
            self.botones[senal] = b
        for senal, simbolo, ayuda in (
                ("configurar", "engrane", "Configurar  (Esc)"),
                ("reiniciar", "reiniciar", "Reiniciar la misma partida  (R)")):
            b = app.boton(fila, "", lambda s=senal: self.senal(s),
                          icono=simbolo, estilo="fantasma", alto=40,
                          ancho=40, ayuda=ayuda)
            b.pack(side="right", padx=(px(6), 0))
            self.botones[senal] = b

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
        tk.Label(c, text="Espacio iniciar/pausar  ·  → una ronda  ·  +/− "
                 "velocidad  ·  R reiniciar  ·  Esc configurar",
                 font=app.f_chico, fg=GRIS_CLARO, bg=PANEL, anchor="w"
                 ).pack(fill="x", pady=(px(8), 0))
        app.atajo("<space>", self._alternar)
        app.atajo("<Right>", lambda: self._si_activo("una"))
        app.atajo("<Key-r>", lambda: self._si_activo("reiniciar"))
        app.atajo("<Key-R>", lambda: self._si_activo("reiniciar"))
        app.atajo("<Escape>", lambda: self._si_activo("configurar"))
        app.atajo("<Key-plus>", lambda: self._acelerar(1))
        app.atajo("<KP_Add>", lambda: self._acelerar(1))
        app.atajo("<Key-minus>", lambda: self._acelerar(-1))
        app.atajo("<KP_Subtract>", lambda: self._acelerar(-1))

        # --- derecha: el escuadrón y la bitácora
        der = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        der.pack(side="left", fill="both", expand=True, padx=(px(16), 0))
        app.rotulo(der, "Escuadrón").pack(anchor="w")
        # Con cuatro o más tanques las tarjetas van en dos columnas: la
        # columna necesita un ancho mínimo para que quepan.
        self._compacto = len(self.config.tanques) > 3
        tk.Frame(der, bg=FONDO_VENTANA, height=0,
                 width=px(520 if self._compacto else 340)).pack()
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

    # ---------------------------------------------------------- controles
    def _si_activo(self, senal: str):
        """El atajo solo actúa si el botón correspondiente está activo."""
        if str(self.botones[senal]["state"]) == "normal":
            self.senal(senal)

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
        root.update_idletasks()
        resto = root.winfo_reqheight() - self.canvas.winfo_reqheight()
        lado = (root.winfo_screenheight() - px(MARGEN_PANTALLA) - resto
                - self.margen - px(12))
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        celda = max(px(24), min(lado // alto, px(TABLERO_PX) // ancho,
                                px(TABLERO_PX) // alto, px(80)))
        if celda < self.celda:
            self.celda = celda
            self.canvas.configure(
                width=self.margen + ancho * celda + px(12),
                height=self.margen + alto * celda + px(12))

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
        for y in range(estado.alto):
            for x in range(estado.ancho):
                fondo = (sprites.FONDO if (x + y) % 2 == 0
                         else sprites.CASILLA_ALTERNA)
                c.create_rectangle(m + x * s, m + y * s, m + (x + 1) * s,
                                   m + (y + 1) * s, fill=fondo,
                                   outline=sprites.REJILLA)
        c.create_rectangle(m, m, x1, y1, outline="#05080C", width=2)
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
                               t.direccion, t.escudo)
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
            text=f"Ronda {estado.ronda}  /  {self.config.rondas_maximas}")
        self.app.subtitulo_barra.configure(
            text=f"{vivos} de {len(estado.tanques)} en pie   ·   tablero "
                 f"{estado.ancho}×{estado.alto}   ·   semilla "
                 f"{self.config.semilla}")
        p = self.progreso
        p.update_idletasks()
        p.delete("all")
        w, h = p.winfo_width(), int(p["height"])
        lleno = w * min(1, estado.ronda / self.config.rondas_maximas)
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

    def turno(self, estado, eventos):
        self._anotar(eventos)
        retardo = retardo_ms(self.velocidad.get())
        if retardo >= RETARDO_MIN_ANIMAR and self._estado is not None:
            self._reproducir(eventos, estado, factor_animacion(retardo))
        self.dibujar(estado)
        self._estado = estado
        return self._entre_turnos()

    def ronda(self, estado, eventos):
        # Los eventos ya se anotaron y animaron turno por turno.
        return self._esperar_turno()

    def fin(self, estado, resultado):
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
        """Tras el final, espera: 'reiniciar', 'configurar' o 'salir'."""
        while self.accion is None:
            self._esperar_senal()
        return self.accion

    # ---------------------------------------------------------- control
    def senal(self, valor: str):
        """Lo que hace cada botón; también sirve para las pruebas."""
        if valor in ("reiniciar", "configurar", "salir"):
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
        return Animador(self.canvas, self.celda, self._esperar_ms, factor)

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
        for e in eventos:
            if not self._animar(a, e, casillas):
                return False
        return True

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
            return a.rafaga(aqui, blanco, impacto=True)
        if e.tipo is T.SIN_EFECTO and d.get("arma") == "ametralladora":
            pared = self._borde(casillas[quien], Direccion[d["direccion"]])
            return a.rafaga(aqui, pared, impacto=True)
        if e.tipo is T.DISPARO and d.get("arma") == "misil":
            if "objetivo" in d:
                destino = self._centro(casillas[d["objetivo"]])
            else:
                destino = self._borde(casillas[quien],
                                      Direccion[d["direccion"]])
            return (a.misil(aqui, destino)
                    and a.explosion(destino, grande="objetivo" in d))
        if e.tipo is T.DISPARO and d.get("arma") == "choque":
            return a.embestida(tag, aqui,
                               self._centro(casillas[d["objetivo"]]))
        if e.tipo is T.DANO:
            return a.texto(aqui, f"−{d['puntos']:g}", ROJO)
        if e.tipo is T.BLOQUEO:
            return (a.anillo(aqui, AZUL, 0.42, 0.62, ms=260)
                    and a.texto(aqui, f"−{d['puntos']:g} escudo", AZUL))
        if e.tipo is T.ESCUDO:
            return a.anillo(aqui, AZUL, 0.15, 0.49, ms=380, guiones=(6, 4))
        if e.tipo in (T.REPARACION, T.REFACCION):
            if e.tipo is T.REFACCION:
                self.canvas.delete(_tag(d["posicion"]))
            return (a.anillo(aqui, VERDE, 0.2, 0.5, ms=300)
                    and a.texto(aqui, f"+{d['puntos']:g}", VERDE))
        if e.tipo is T.RADAR:
            return a.radar(aqui, Direccion[d["direccion"]], d["lectura"])
        if e.tipo is T.MINA_COLOCADA:
            # La mina sale del tanque y cae en la esquina contigua.
            destino = self._centro(d["posicion"])
            return a.mina_nueva(aqui, destino, escala=1.0)
        if e.tipo is T.MINA_ARMADA:
            return a.anillo(self._centro(d["posicion"]), ROJO, 0.1, 0.4,
                            ms=300)
        if e.tipo is T.MINA_EXPLOTA:
            self.canvas.delete(_tag(d["posicion"]))
            return a.explosion(self._centro(d["posicion"]), grande=True)
        if e.tipo is T.DESTRUCCION:
            seguir = a.explosion(aqui, grande=True)
            self.canvas.delete(tag)
            del casillas[quien]
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

    def _cartel(self, titular: str, detalle: str, estado=None,
                resultado=None):
        """Cartel final: oscurece el tablero y muestra la clasificación."""
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
                      text="R  jugar otra vez    ·    Esc  configurar",
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
    ("", "Gana el último tanque en pie. Si se llega al límite de rondas, "
         "gana el que más daño haya infligido a sus rivales; si coincide, "
         "es empate."),
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
    ("", "Cada turno se anima: un recuadro amarillo marca al tanque que "
         "juega; la ametralladora dispara una ráfaga; el misil sube en arco "
         "hasta el primer tanque o la pared y estalla; la mina sale "
         "volando a la esquina; el IF con radar lanza un haz verde que termina en un pulso rojo "
         "si encontró un tanque o gris si llegó a la pared. El daño sube en "
         "rojo (−5), la curación en verde (+20) y lo que el escudo absorbe "
         "en azul. Una ✗ gris es un IF cuya condición fue falsa."),
    ("", "Una mina bajo un tanque se ve pequeña en la esquina de su "
         "casilla. En las velocidades 9 y 10 no se anima: avance rápido."),
    ("h", "Configuración"),
    ("", "Cada fila asocia un tanque a su programa y a un color. El aviso de "
         "la derecha revisa el programa al momento: verde si es válido, "
         "rojo con el número de errores; un clic en el aviso rojo los "
         "muestra. Los valores de armas y defensa tienen flechas que ya "
         "marcan su rango; «Valores por omisión» los devuelve a los del "
         "reglamento y «Sortear» elige otra semilla."),
    ("h", "Teclado"),
    ("m", "Enter        iniciar (menú y configuración)"),
    ("m", "F1           esta ayuda (menú)"),
    ("m", "Espacio      iniciar o pausar la partida"),
    ("m", "→            una ronda"),
    ("m", "+ / −        más rápido / más lento"),
    ("m", "R            reiniciar la misma partida"),
    ("m", "Esc          volver a la configuración"),
    ("h", "Controles"),
    ("", "Iniciar reproduce la partida sola a la velocidad elegida; Pausar "
         "la detiene en el siguiente turno; Una ronda avanza de una en una. "
         "Reiniciar vuelve a jugar la misma partida: con la misma semilla, "
         "el resultado es idéntico. Cada partida se guarda en la carpeta "
         "bitacoras/."),
]
