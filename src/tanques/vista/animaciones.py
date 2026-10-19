"""Animaciones de cada acción sobre el tablero.

Cada método dibuja un efecto cuadro por cuadro —la ráfaga de la
ametralladora, el misil en arco, la explosión, el pulso del radar— y borra
lo que dibujó al terminar. La ventana redibuja después el estado real del
turno, así que una animación nunca decide qué hay en el tablero: solo
muestra cómo se llegó ahí.

No importa Tkinter. Recibe el canvas y una función `esperar(ms)` que deja
pasar el tiempo sin congelar la ventana y devuelve False si el usuario
pidió salir; en ese caso la animación se corta.

Tk no tiene transparencia: lo que «se desvanece» se va mezclando con el
color del fondo.
"""
from __future__ import annotations

import math
from itertools import count
from typing import Callable

from ..modelo import Direccion
from . import sprites

Punto = tuple[float, float]

AMARILLO = "#FFD34D"
NARANJA = "#F08A24"
ROJO = "#C62828"
BLANCO = "#FFFDF5"
HUMO = "#8C8C8C"
VERDE = "#3E9B4F"
AZUL = sprites.ESCUDO
RESALTE = "#F2B705"
_CUADRO_MS = 33                      # unos 30 cuadros por segundo
_ids = count()


def suave(t: float) -> float:
    """Aceleración y frenado suaves (ease in-out)."""
    return t * t * (3 - 2 * t)


def arco(a: Punto, b: Punto, altura: float, t: float) -> Punto:
    """Punto del arco de a a b; sube `altura` píxeles en la mitad."""
    x = a[0] + (b[0] - a[0]) * t
    y = a[1] + (b[1] - a[1]) * t - altura * 4 * t * (1 - t)
    return x, y


class Animador:

    def __init__(self, canvas, celda: float, esperar: Callable[[float], bool],
                 factor: float = 1.0, fondo: str = sprites.FONDO):
        self.c = canvas
        self.s = celda
        self.esperar = esperar
        self.factor = factor
        self.fondo = fondo

    # ---------------------------------------------------------- motor
    def _correr(self, ms: float, cuadro: Callable[[float, str], None]
                ) -> bool:
        """Llama a cuadro(t, etiqueta) con t de 0 a 1 y borra al final."""
        etiqueta = f"ef{next(_ids)}"
        total = ms * self.factor
        n = max(2, round(total / _CUADRO_MS))
        seguir = True
        for i in range(1, n + 1):
            self.c.delete(etiqueta)
            cuadro(i / n, etiqueta)
            if not self.esperar(total / n):
                seguir = False
                break
        self.c.delete(etiqueta)
        return seguir

    def _tags(self, etiqueta):
        return ("efecto", etiqueta)

    def _desvanecer(self, color: str, t: float, desde: float = 0.6) -> str:
        """Color pleno hasta `desde`, luego se funde con el fondo."""
        return sprites.mezclar(color, self.fondo,
                               max(0.0, (t - desde) / (1 - desde)))

    # ---------------------------------------------------------- marcas
    def resaltar(self, p: Punto):
        """Recuadro del tanque que juega; dura hasta el redibujo final."""
        m = self.s * 0.5
        self.c.delete("resalte")
        self.c.create_rectangle(p[0] - m + 2, p[1] - m + 2, p[0] + m - 2,
                                p[1] + m - 2, outline=RESALTE, width=3,
                                tags=("efecto", "resalte"))

    # ---------------------------------------------------------- armas
    def rafaga(self, desde: Punto, hasta: Punto, impacto: bool) -> bool:
        """Tres balas trazadoras de la boca del cañón al blanco."""
        dx, dy = hasta[0] - desde[0], hasta[1] - desde[1]
        largo = math.hypot(dx, dy) or 1
        ux, uy = dx / largo, dy / largo
        boca = (desde[0] + ux * self.s * 0.47, desde[1] + uy * self.s * 0.47)
        cola = self.s * 0.2

        def cuadro(t, et):
            if t < 0.25:                                   # fogonazo
                r = self.s * (0.10 + 0.08 * math.sin(t * 40))
                self.c.create_oval(boca[0] - r, boca[1] - r, boca[0] + r,
                                   boca[1] + r, fill=AMARILLO,
                                   outline=NARANJA, tags=self._tags(et))
            for k in range(3):
                u = (t - k * 0.15) / 0.55
                if not 0 < u <= 1:
                    continue
                x = boca[0] + (hasta[0] - boca[0]) * u
                y = boca[1] + (hasta[1] - boca[1]) * u
                for ancho, color in ((5, NARANJA), (2, AMARILLO)):
                    self.c.create_line(x - ux * cola, y - uy * cola, x, y,
                                       fill=color, width=ancho,
                                       capstyle="round", tags=self._tags(et))

        seguir = self._correr(420, cuadro)
        if seguir and impacto:
            seguir = self.chispas(hasta)
        return seguir

    def misil(self, desde: Punto, hasta: Punto) -> bool:
        """Sale en arco hacia la casilla; la mira marca el blanco."""
        distancia = math.hypot(hasta[0] - desde[0], hasta[1] - desde[1])
        altura = self.s * 0.6 + distancia * 0.25
        estela: list[Punto] = []

        def cuadro(t, et):
            # La mira sobre la casilla objetivo
            r = self.s * (0.32 + 0.04 * math.sin(t * 18))
            hx, hy = hasta
            self.c.create_oval(hx - r, hy - r, hx + r, hy + r, outline=ROJO,
                               width=2, tags=self._tags(et))
            for ax, ay in ((1, 0), (0, 1)):
                self.c.create_line(hx - ax * r * 1.3, hy - ay * r * 1.3,
                                   hx + ax * r * 1.3, hy + ay * r * 1.3,
                                   fill=ROJO, tags=self._tags(et))
            p = arco(desde, hasta, altura, suave(t))
            estela.append(p)
            for k, (x, y) in enumerate(estela[-10:]):
                f = 1 - k / 10
                rr = self.s * 0.06 * (0.5 + k / 10)
                self.c.create_oval(x - rr, y - rr, x + rr, y + rr,
                                   fill=sprites.mezclar(HUMO, self.fondo, f),
                                   outline="", tags=self._tags(et))
            atras = arco(desde, hasta, altura, suave(max(0, t - 0.06)))
            self.c.create_line(atras[0], atras[1], p[0], p[1],
                               fill="#3A3A3A", width=max(4, self.s * 0.11),
                               capstyle="round", tags=self._tags(et))
            rr = self.s * 0.06
            self.c.create_oval(p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr,
                               fill=ROJO, outline="", tags=self._tags(et))

        return self._correr(650, cuadro)

    def explosion(self, p: Punto, grande: bool = True) -> bool:
        """Bola de fuego que crece, onda expansiva y escombros."""
        radio = self.s * (0.48 if grande else 0.3)
        colores = (BLANCO, AMARILLO, NARANJA, ROJO)

        def cuadro(t, et):
            onda = radio * (0.6 + 1.0 * t)
            self.c.create_oval(p[0] - onda, p[1] - onda, p[0] + onda,
                               p[1] + onda, outline=self._desvanecer(
                                   NARANJA, t, 0.2), width=3,
                               tags=self._tags(et))
            for k, color in enumerate(reversed(colores)):
                r = radio * (1 - k * 0.22) * min(1, t * 2.2)
                if r <= 0:
                    continue
                self.c.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r,
                                   fill=self._desvanecer(color, t, 0.45),
                                   outline="", tags=self._tags(et))
            for k in range(8):
                ang = k * math.pi / 4 + 0.3
                d = radio * (0.4 + 1.1 * t)
                x, y = p[0] + math.cos(ang) * d, p[1] + math.sin(ang) * d
                rr = max(1.5, self.s * 0.035 * (1 - t))
                self.c.create_oval(x - rr, y - rr, x + rr, y + rr,
                                   fill=self._desvanecer("#5A3A1A", t, 0.5),
                                   outline="", tags=self._tags(et))

        return self._correr(520 if grande else 360, cuadro)

    def humo(self, p: Punto) -> bool:
        def cuadro(t, et):
            for k, (ox, oy) in enumerate(((-0.12, 0), (0.12, -0.05),
                                          (0, -0.15))):
                r = self.s * (0.15 + 0.2 * t)
                x = p[0] + ox * self.s
                y = p[1] + (oy - 0.3 * t) * self.s
                self.c.create_oval(x - r, y - r, x + r, y + r,
                                   fill=self._desvanecer(HUMO, t, 0.2),
                                   outline="", tags=self._tags(et))

        return self._correr(450, cuadro)

    def chispas(self, p: Punto) -> bool:
        def cuadro(t, et):
            for k in range(7):
                ang = k * 2 * math.pi / 7
                r0 = self.s * 0.06 + self.s * 0.2 * t
                r1 = r0 + self.s * 0.12
                self.c.create_line(p[0] + math.cos(ang) * r0,
                                   p[1] + math.sin(ang) * r0,
                                   p[0] + math.cos(ang) * r1,
                                   p[1] + math.sin(ang) * r1,
                                   fill=self._desvanecer(AMARILLO, t, 0.3),
                                   width=2, tags=self._tags(et))

        return self._correr(220, cuadro)

    # ---------------------------------------------------------- movimiento
    def deslizar(self, etiqueta: str, desde: Punto, hasta: Punto) -> bool:
        """Mueve las piezas de un sprite ya dibujado."""
        hecho = [0.0, 0.0]

        def cuadro(t, _et):
            u = suave(t)
            x = (hasta[0] - desde[0]) * u
            y = (hasta[1] - desde[1]) * u
            self.c.move(etiqueta, x - hecho[0], y - hecho[1])
            self.c.move("resalte", x - hecho[0], y - hecho[1])
            hecho[:] = [x, y]

        return self._correr(300, cuadro)

    def embestida(self, etiqueta: str, desde: Punto, hacia: Punto,
                  alcance: float = 0.32) -> bool:
        """Se lanza hacia `hacia` y regresa; chispas en el golpe."""
        hecho = [0.0, 0.0]
        vx, vy = hacia[0] - desde[0], hacia[1] - desde[1]

        def cuadro(t, _et):
            u = alcance * math.sin(math.pi * t)
            x, y = vx * u, vy * u
            self.c.move(etiqueta, x - hecho[0], y - hecho[1])
            hecho[:] = [x, y]

        seguir = self._correr(320, cuadro)
        if seguir:
            golpe = (desde[0] + vx * 0.5, desde[1] + vy * 0.5)
            seguir = self.chispas(golpe)
        return seguir

    # ---------------------------------------------------------- sensores
    def radar(self, desde: Punto, direccion: Direccion,
              lectura: int) -> bool:
        """Un haz que avanza hasta lo detectado y un pulso al llegar."""
        distancia = abs(lectura) - (0.5 if lectura < 0 else 0)
        fin = (desde[0] + direccion.dx * distancia * self.s,
               desde[1] + direccion.dy * distancia * self.s)
        ping = ROJO if lectura > 0 else HUMO

        def cuadro(t, et):
            u = min(1, t / 0.6)
            x = desde[0] + (fin[0] - desde[0]) * u
            y = desde[1] + (fin[1] - desde[1]) * u
            color = self._desvanecer(VERDE, t, 0.6)
            self.c.create_line(desde[0], desde[1], x, y, fill=color,
                               width=3, dash=(6, 4), tags=self._tags(et))
            r = self.s * 0.16
            self.c.create_oval(x - r, y - r, x + r, y + r, outline=color,
                               width=2, tags=self._tags(et))
            if t > 0.6:
                v = (t - 0.6) / 0.4
                r = self.s * (0.1 + 0.3 * v)
                self.c.create_oval(fin[0] - r, fin[1] - r, fin[0] + r,
                                   fin[1] + r, width=3,
                                   outline=sprites.mezclar(ping, self.fondo,
                                                           v),
                                   tags=self._tags(et))

        return self._correr(480, cuadro)

    # ---------------------------------------------------------- estados
    def anillo(self, p: Punto, color: str, r0: float, r1: float,
               ms: float = 320, guiones: tuple = ()) -> bool:
        def cuadro(t, et):
            r = self.s * (r0 + (r1 - r0) * suave(t))
            self.c.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r,
                               outline=self._desvanecer(color, t, 0.5),
                               width=max(3, self.s / 16), dash=guiones,
                               tags=self._tags(et))

        return self._correr(ms, cuadro)

    def texto(self, p: Punto, texto: str, color: str,
              ms: float = 620) -> bool:
        """Cifra que sube y se desvanece: −10, +20, bloqueado…"""
        tam = max(9, int(self.s * 0.24))

        def cuadro(t, et):
            y = p[1] - self.s * (0.25 + 0.45 * suave(t))
            c = self._desvanecer(color, t, 0.55)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.c.create_text(p[0] + ox, y + oy, text=texto,
                                   fill=sprites.mezclar(BLANCO, self.fondo,
                                                        t),
                                   font=("Segoe UI", tam, "bold"),
                                   tags=self._tags(et))
            self.c.create_text(p[0], y, text=texto, fill=c,
                               font=("Segoe UI", tam, "bold"),
                               tags=self._tags(et))

        return self._correr(ms, cuadro)

    def mina_nueva(self, desde: Punto, hasta: Punto,
                   escala: float = 1.0) -> bool:
        """La mina sale del tanque, grande, y se asienta donde queda.

        Empieza al doble de su tamaño final para que se note: la mina sin
        armar es de trazo claro y, chica, se perdería sobre el tanque.
        """
        final = self.s * escala

        def cuadro(t, et):
            u = suave(min(1, t / 0.65))
            x = desde[0] + (hasta[0] - desde[0]) * u
            y = desde[1] + (hasta[1] - desde[1]) * u - math.sin(
                math.pi * u) * self.s * 0.35
            sprites.mina(self.c, x, y, final * (2.0 - u), armada=False,
                         extra=self._tags(et))
            if t > 0.55:
                v = (t - 0.55) / 0.45
                r = final * (0.3 + 0.6 * v)
                self.c.create_oval(hasta[0] - r, hasta[1] - r, hasta[0] + r,
                                   hasta[1] + r, width=3,
                                   outline=sprites.mezclar(
                                       sprites.MINA_ARMADA, self.fondo, v),
                                   tags=self._tags(et))

        return self._correr(520, cuadro)
