"""Sprites e íconos del tablero, dibujados con primitivas del Canvas.

Siguen las figuras 6, 7 y 9 del documento de arquitectura: vista cenital
con orugas, casco y torreta; el número sobre la torreta y el cañón hacia la
última dirección usada. No se usan imágenes, así que el tablero escala a
cualquier tamaño de casilla.

El sprite se define mirando al norte, en unidades de casilla con el origen
en su centro, y se rota según la dirección. Este módulo no importa
Tkinter: recibe el canvas ya creado.
"""
from __future__ import annotations

from ..modelo import Direccion

# ------------------------------------------------------------ paleta (fig. 6)
FONDO = "#F7F4EE"
CASILLA_ALTERNA = "#ECE6DA"
REJILLA = "#D4CCBC"
MURO = "#3C3C3C"
MINA_ARMADA = "#B91C1C"
MINA_SIN_ARMAR = "#E8A3A3"
REFACCION = "#6A994E"
ESCUDO = "#2E5E8C"
ORUGA = "#484848"
CANON = "#2B2B2B"
COLORES_TANQUE = ("#2E5E8C", "#D97706", "#0F766E", "#6D4C9F")


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


def rectangulo(x0, y0, x1, y1, direccion, cx, cy, s) -> list[float]:
    """Las cuatro esquinas de un rectángulo local, rotadas y escaladas."""
    puntos = []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        rx, ry = rotar(x, y, direccion)
        puntos += [cx + rx * s, cy + ry * s]
    return puntos


# ------------------------------------------------------------ dibujo
def tanque(canvas, cx: float, cy: float, s: float, numero: int, color: str,
           direccion: Direccion = Direccion.N, escudo: bool = False,
           etiqueta: str = "tanque"):
    """Dibuja un tanque centrado en (cx, cy) dentro de una casilla de lado s."""
    tags = (etiqueta, f"{etiqueta}{numero}")
    oscuro = oscurecer(color)

    def poli(x0, y0, x1, y1, relleno, borde, ancho=1):
        canvas.create_polygon(
            rectangulo(x0, y0, x1, y1, direccion, cx, cy, s),
            fill=relleno, outline=borde, width=ancho, tags=tags)

    # Orugas con sus eslabones
    for lado in (-1, 1):
        x0, x1 = sorted((lado * 0.40, lado * 0.25))
        poli(x0, -0.36, x1, 0.38, ORUGA, "#2A2A2A")
        for k in range(1, 6):
            y = -0.36 + k * 0.74 / 6
            ax, ay = rotar(x0, y, direccion)
            bx, by = rotar(x1, y, direccion)
            canvas.create_line(cx + ax * s, cy + ay * s, cx + bx * s,
                               cy + by * s, fill="#2A2A2A", tags=tags)
    # Casco, cañón y torreta
    poli(-0.28, -0.31, 0.28, 0.33, color, oscuro, max(1, s / 40))
    poli(-0.045, -0.47, 0.045, -0.05, CANON, CANON)
    r = 0.175 * s
    tx, ty = rotar(0, 0.02, direccion)
    tx, ty = cx + tx * s, cy + ty * s
    canvas.create_oval(tx - r, ty - r, tx + r, ty + r, fill=oscuro,
                       outline="#262626", width=max(1, s / 45), tags=tags)
    canvas.create_text(tx, ty, text=str(numero), fill="white",
                       font=("Segoe UI", max(7, int(s * 0.19)), "bold"),
                       tags=tags)
    if escudo:
        e = 0.49 * s
        canvas.create_oval(cx - e, cy - e, cx + e, cy + e, outline=ESCUDO,
                           width=max(2, s / 28), dash=(6, 4),
                           tags=tags + ("escudo",))


def mina(canvas, cx: float, cy: float, s: float, armada: bool,
         extra: tuple = ()):
    """Mina armada: trazo continuo. Sin armar: trazo punteado (fig. 9)."""
    color = MINA_ARMADA if armada else MINA_SIN_ARMAR
    trazo = () if armada else (3, 3)
    tags = ("mina", "armada" if armada else "sin_armar") + tuple(extra)
    r, pua = 0.15 * s, 0.26 * s
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0),
                   (0.707, 0.707), (0.707, -0.707), (-0.707, 0.707),
                   (-0.707, -0.707)):
        canvas.create_line(cx + dx * r, cy + dy * r, cx + dx * pua,
                           cy + dy * pua, fill=color, width=max(2, s / 30),
                           dash=trazo, tags=tags)
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=color if armada else "", outline=color,
                       width=max(2, s / 30), dash=trazo, tags=tags)


def refaccion(canvas, cx: float, cy: float, s: float, extra: tuple = ()):
    """Caja verde con una cruz blanca."""
    w, h, c = 0.22 * s, 0.16 * s, 0.10 * s
    tags = ("refaccion",) + tuple(extra)
    canvas.create_rectangle(cx - w, cy - h, cx + w, cy + h, fill=REFACCION,
                            outline="#4A6B37", width=2, tags=tags)
    canvas.create_line(cx - c, cy, cx + c, cy, fill="white",
                       width=max(2, s / 25), tags=tags)
    canvas.create_line(cx, cy - c, cx, cy + c, fill="white",
                       width=max(2, s / 25), tags=tags)
