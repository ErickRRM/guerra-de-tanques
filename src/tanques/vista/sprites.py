"""Sprites e íconos del tablero, dibujados con primitivas del Canvas.

Vista cenital como en las figuras 6, 7 y 9 del documento de arquitectura
(orugas, casco y torreta; el número sobre la torreta y el cañón hacia la
última dirección usada), con el aspecto de la interfaz: tablero nocturno
de rejilla táctica, casco con esquinas en chaflán como los paneles y
escudo cian. No se usan imágenes, así que el tablero escala a cualquier
tamaño de casilla.

El sprite se define mirando al norte, en unidades de casilla con el origen
en su centro, y se rota según la dirección. Este módulo no importa
Tkinter: recibe el canvas ya creado.
"""
from __future__ import annotations

import math
import random

from ..modelo import Direccion

# ------------------------------------------------------------ paleta
# El tablero comparte la noche azul de la interfaz (grafica.py).
FONDO = "#0F1A28"                  # casilla
CASILLA_ALTERNA = "#0C1622"        # casilla alterna del damero
LUZ = "#1C3049"                    # el centro del tablero, más iluminado
REJILLA = "#1B2B3F"
MARCA = "#36506F"                  # cruces en las intersecciones
MURO = "#05080C"
MINA_ARMADA = "#F25C54"
MINA_NUCLEO = "#3A1517"
MINA_SIN_ARMAR = "#C27C80"
REFACCION = "#4ADE80"
REFACCION_CAJA = "#143826"
ESCUDO = "#4CC9F0"                 # el cian de la interfaz
ORUGA = "#1A2330"
ESLABON = "#3A4A5E"
CANON = "#2A3646"
CONTORNO = "#070B11"
COLORES_TANQUE = ("#2E5E8C", "#D97706", "#0F766E", "#6D4C9F",
                  "#BE185D", "#4D7C0F")


def oscurecer(color: str, factor: float = 0.67) -> str:
    """El tono oscuro de la paleta: torreta y borde del casco."""
    h = color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(int(r * factor), int(g * factor),
                                        int(b * factor))


def mezclar(color: str, otro: str, t: float) -> str:
    """Color a la fracción t entre `color` (t=0) y `otro` (t=1).

    Tk no tiene transparencia: desvanecer algo es mezclarlo con el fondo.
    """
    t = min(1.0, max(0.0, t))
    a = [int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(otro.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#{:02X}{:02X}{:02X}".format(
        *(round(x + (y - x) * t) for x, y in zip(a, b)))


# ------------------------------------------------------------ geometría
def rotar(x: float, y: float, direccion: Direccion) -> tuple[float, float]:
    """Rota un punto definido mirando al norte (y crece hacia abajo)."""
    if direccion is Direccion.N:
        return x, y
    if direccion is Direccion.E:
        return -y, x
    if direccion is Direccion.S:
        return -x, -y
    return y, -x                                   # oeste


def puntos(locales, direccion, cx, cy, s) -> list[float]:
    """Puntos locales (mirando al norte) rotados, escalados y trasladados."""
    salida = []
    for x, y in locales:
        rx, ry = rotar(x, y, direccion)
        salida += [cx + rx * s, cy + ry * s]
    return salida


def rectangulo(x0, y0, x1, y1, direccion, cx, cy, s) -> list[float]:
    """Las cuatro esquinas de un rectángulo local, rotadas y escaladas."""
    return puntos(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), direccion,
                  cx, cy, s)


def chaflan(x0, y0, x1, y1, c, c_atras=None) -> list[tuple[float, float]]:
    """Rectángulo local con las esquinas cortadas en diagonal.

    `c` corta las esquinas de enfrente (y0) y `c_atras` las de atrás.
    """
    d = c if c_atras is None else c_atras
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - d),
            (x1 - d, y1), (x0 + d, y1), (x0, y1 - d), (x0, y0 + c)]


def octagono(cx, cy, r) -> list[tuple[float, float]]:
    k = r * 0.4142                         # tan(22.5°): lados iguales
    return [(cx - k, cy - r), (cx + k, cy - r), (cx + r, cy - k),
            (cx + r, cy + k), (cx + k, cy + r), (cx - k, cy + r),
            (cx - r, cy + k), (cx - r, cy - k)]


# ------------------------------------------------------------ dibujo
def tanque(canvas, cx: float, cy: float, s: float, numero: int, color: str,
           direccion: Direccion = Direccion.N, escudo: float = 0,
           etiqueta: str = "tanque", fondo: str | None = None):
    """Dibuja un tanque centrado en (cx, cy) dentro de una casilla de lado s.

    Con `fondo` (el color de la casilla) se dibuja además la placa con el
    color del equipo sobre la que está parado, como en el tablero.
    """
    tags = (etiqueta, f"{etiqueta}{numero}")
    oscuro = oscurecer(color)
    brillo = mezclar(color, "#FFFFFF", 0.35)
    fino = max(1, s / 48)

    def poli(locales, relleno, borde=CONTORNO, ancho=fino, extra=()):
        canvas.create_polygon(puntos(locales, direccion, cx, cy, s),
                              fill=relleno, outline=borde, width=ancho,
                              tags=tags + tuple(extra))

    def linea(a, b, color_linea, ancho=fino):
        canvas.create_line(*puntos((a, b), direccion, cx, cy, s),
                           fill=color_linea, width=ancho, tags=tags)

    # Placa del equipo: un recuadro en chaflán apenas teñido
    if fondo is not None:
        poli(chaflan(-0.46, -0.46, 0.46, 0.46, 0.12),
             mezclar(color, fondo, 0.86), mezclar(color, fondo, 0.45))
    # Orugas con sus eslabones
    for lado in (-1, 1):
        x0, x1 = sorted((lado * 0.42, lado * 0.26))
        poli(chaflan(x0, -0.39, x1, 0.39, 0.04), ORUGA)
        for k in range(1, 8):
            y = -0.39 + k * 0.78 / 8
            linea((x0 + 0.02, y), (x1 - 0.02, y), ESLABON)
    # Casco en chaflán, con el blindaje frontal más claro y la rejilla
    # del motor atrás
    poli(chaflan(-0.29, -0.33, 0.29, 0.35, 0.09, 0.05), color, oscuro,
         max(1, s / 36))
    poli([(-0.20, -0.33), (0.20, -0.33), (0.25, -0.27), (-0.25, -0.27)],
         brillo, brillo, 0)
    poli(chaflan(-0.17, 0.22, 0.17, 0.31, 0.02), oscuro, oscuro, 0)
    if s >= 30:
        for x in (-0.09, 0.0, 0.09):
            linea((x, 0.24), (x, 0.29), mezclar(oscuro, CONTORNO, 0.5))
    # Cañón con freno de boca
    poli([(-0.045, -0.50), (0.045, -0.50), (0.045, -0.08),
          (-0.045, -0.08)], CANON)
    poli(chaflan(-0.075, -0.54, 0.075, -0.45, 0.02), CANON)
    # Torreta octagonal con el número
    poli(octagono(0, 0.03, 0.19), oscuro, CONTORNO, max(1, s / 40))
    poli(octagono(0, 0.03, 0.15), "", mezclar(color, oscuro, 0.35),
         max(1, s / 60))
    tx, ty = rotar(0, 0.03, direccion)
    canvas.create_text(cx + tx * s, cy + ty * s, text=str(numero),
                       fill="white",
                       font=("Segoe UI", max(7, int(s * 0.19)), "bold"),
                       tags=tags)
    if escudo:
        e = 0.49 * s
        hexagono = []
        for k in range(6):
            a = math.radians(60 * k + 30)
            hexagono += [cx + e * math.cos(a), cy + e * math.sin(a)]
        canvas.create_polygon(hexagono, fill="", outline=ESCUDO,
                              width=max(2, s / 26), dash=(8, 4),
                              tags=tags + ("escudo",))


def mina(canvas, cx: float, cy: float, s: float, armada: bool,
         extra: tuple = ()):
    """Mina armada: núcleo encendido. Sin armar: trazo punteado (fig. 9)."""
    color = MINA_ARMADA if armada else MINA_SIN_ARMAR
    trazo = () if armada else (3, 3)
    tags = ("mina", "armada" if armada else "sin_armar") + tuple(extra)
    r, pua = 0.14 * s, 0.25 * s
    ancho = max(2, s / 30)
    for k in range(8):
        a = math.radians(45 * k)
        dx, dy = math.cos(a), math.sin(a)
        canvas.create_line(cx + dx * r, cy + dy * r, cx + dx * pua,
                           cy + dy * pua, fill=color, width=ancho,
                           dash=trazo, capstyle="round", tags=tags)
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=MINA_NUCLEO if armada else "", outline=color,
                       width=ancho, dash=trazo, tags=tags)
    if armada:
        n = max(1.5, 0.05 * s)
        canvas.create_oval(cx - n, cy - n, cx + n, cy + n, fill=color,
                           outline="", tags=tags + ("led",))


def refaccion(canvas, cx: float, cy: float, s: float, extra: tuple = ()):
    """Caja de refacciones: contorno verde y una cruz encendida."""
    w, c, k = 0.21 * s, 0.10 * s, 0.06 * s
    tags = ("refaccion",) + tuple(extra)
    canvas.create_polygon(
        puntos(chaflan(-w, -w, w, w, k), Direccion.N, cx, cy, 1),
        fill=REFACCION_CAJA, outline=REFACCION, width=max(2, s / 30),
        tags=tags + ("brillo",))
    canvas.create_line(cx - c, cy, cx + c, cy, fill=REFACCION,
                       width=max(2, s / 18), tags=tags)
    canvas.create_line(cx, cy - c, cx, cy + c, fill=REFACCION,
                       width=max(2, s / 18), tags=tags)


def quemadura(canvas, cx: float, cy: float, s: float, fondo: str,
              intensidad: float, semilla=0):
    """Mancha de hollín que deja una explosión; `intensidad` de 1 (recién
    hecha) a 0 (ya se borró). Es decorado: no marca nada del juego."""
    rng = random.Random(str(semilla))
    hollin = mezclar(fondo, CONTORNO, 0.75 * intensidad)
    medio = mezclar(fondo, CONTORNO, 0.45 * intensidad)
    for color, escala in ((medio, 1.0), (hollin, 0.6)):
        for _ in range(4):
            ox = rng.uniform(-0.1, 0.1) * s
            oy = rng.uniform(-0.1, 0.1) * s
            r = rng.uniform(0.18, 0.26) * s * escala
            canvas.create_oval(cx + ox - r, cy + oy - r, cx + ox + r,
                               cy + oy + r, fill=color, outline="",
                               tags=("quemadura",))
    for _ in range(6):                          # astillas alrededor
        a = rng.uniform(0, 2 * math.pi)
        d0, d1 = 0.22 * s, rng.uniform(0.32, 0.42) * s
        canvas.create_line(cx + math.cos(a) * d0, cy + math.sin(a) * d0,
                           cx + math.cos(a) * d1, cy + math.sin(a) * d1,
                           fill=medio, width=max(1, s / 30),
                           tags=("quemadura",))
