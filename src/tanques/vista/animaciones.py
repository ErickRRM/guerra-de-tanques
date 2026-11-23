"""Animaciones de cada acción sobre el tablero.

Cada método dibuja un efecto cuadro por cuadro —la ráfaga de la
ametralladora, el misil en arco, la explosión, el pulso del radar— y borra
lo que dibujó al terminar. La ventana redibuja después el estado real del
turno, así que una animación nunca decide qué hay en el tablero: solo
muestra cómo se llegó ahí.

Además de los efectos, las armas sacuden: el tanque retrocede al disparar,
el tablero tiembla con las explosiones grandes y el tanque que recibe daño
destella. Todo vuelve a su lugar al terminar, aunque el usuario corte la
animación a la mitad.

No importa Tkinter. Recibe el canvas, una función `esperar(ms)` que deja
pasar el tiempo sin congelar la ventana y devuelve False si el usuario
pidió salir (en ese caso la animación se corta), y opcionalmente una
función `sonar(nombre)` que toca el efecto de sonido de cada acción.

Tk no tiene transparencia: lo que «se desvanece» se va mezclando con el
color del fondo.
"""
from __future__ import annotations

import math
import random
from itertools import count
from typing import Callable, Optional

from ..modelo import Direccion
from . import sprites

Punto = tuple[float, float]

AMARILLO = "#FFD34D"
NARANJA = "#F08A24"
ROJO = "#F25C54"
BLANCO = "#FFFDF5"
HUMO = "#6B7C90"
HUMO_OSCURO = "#2A3442"
VERDE = "#4ADE80"
AZUL = sprites.ESCUDO
RESALTE = "#F5B342"                 # el oro de la interfaz
HALO = "#05080C"                    # contorno oscuro de las cifras
POLVO = "#4A5A6E"
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


def _unitario(a: Punto, b: Punto) -> Punto:
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(dx, dy) or 1
    return dx / largo, dy / largo


class Animador:

    def __init__(self, canvas, celda: float, esperar: Callable[[float], bool],
                 factor: float = 1.0, fondo: str = sprites.FONDO,
                 sonar: Optional[Callable[[str], None]] = None):
        self.c = canvas
        self.s = celda
        self.esperar = esperar
        self.factor = factor
        self.fondo = fondo
        self.sonar = sonar or (lambda _nombre: None)

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

    def _circulo(self, p: Punto, r: float, et, **opciones):
        self.c.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r,
                           tags=self._tags(et), **opciones)

    def _destello(self, p: Punto, r: float, t: float, et):
        """Fogonazo: estrella de cuatro puntas que crece y se apaga."""
        if t >= 1:
            return
        g = r * (1 - t)
        for color, k in ((NARANJA, 1.0), (AMARILLO, 0.65), (BLANCO, 0.3)):
            a, b = g * k, g * k * 0.3
            self.c.create_polygon(p[0], p[1] - a, p[0] + b, p[1] - b,
                                  p[0] + a, p[1], p[0] + b, p[1] + b,
                                  p[0], p[1] + a, p[0] - b, p[1] + b,
                                  p[0] - a, p[1], p[0] - b, p[1] - b,
                                  fill=color, outline="",
                                  tags=self._tags(et))

    # ---------------------------------------------------------- marcas
    def resaltar(self, p: Punto):
        """Esquineras doradas del tanque que juega, como las del tablero;
        duran hasta el redibujo final."""
        m = self.s * 0.5 - 2
        largo = self.s * 0.22
        ancho = max(2, self.s / 22)
        self.c.delete("resalte")
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            ex, ey = p[0] + dx * m, p[1] + dy * m
            self.c.create_line(ex, ey - dy * largo, ex, ey,
                               ex - dx * largo, ey, fill=RESALTE,
                               width=ancho, capstyle="projecting",
                               tags=("efecto", "resalte"))

    # ---------------------------------------------------------- sacudidas
    def _retroceso(self, etiqueta: Optional[str], ux: float, uy: float,
                   t: float, hecho: list, fuerza: float = 0.08,
                   golpes: tuple = (0.0,)):
        """El tanque se echa hacia atrás con cada disparo y regresa."""
        if not etiqueta:
            return
        u = 0.0
        for inicio in golpes:
            v = (t - inicio) / 0.14
            if 0 <= v <= 1:
                u = max(u, math.sin(math.pi * v))
        x, y = -ux * self.s * fuerza * u, -uy * self.s * fuerza * u
        self.c.move(etiqueta, x - hecho[0], y - hecho[1])
        hecho[:] = [x, y]

    def _regresar(self, etiqueta: Optional[str], hecho: list):
        if etiqueta and hecho != [0.0, 0.0]:
            self.c.move(etiqueta, -hecho[0], -hecho[1])
            hecho[:] = [0.0, 0.0]

    def _temblor(self, t: float, fuerza: float, hecho: list):
        """Todo el tablero tiembla y se calma."""
        amplitud = self.s * fuerza * (1 - t) ** 2
        x = amplitud * math.sin(t * 61)
        y = amplitud * math.cos(t * 47)
        self.c.move("all", x - hecho[0], y - hecho[1])
        hecho[:] = [x, y]

    # ---------------------------------------------------------- armas
    def rafaga(self, desde: Punto, hasta: Punto, impacto: bool,
               etiqueta: Optional[str] = None,
               blanco: bool = False) -> bool:
        """Tres balas trazadoras de la boca del cañón al blanco.

        Cada bala tiene su fogonazo y su retroceso; los casquillos saltan
        a un lado del tanque.
        """
        ux, uy = _unitario(desde, hasta)
        boca = (desde[0] + ux * self.s * 0.52, desde[1] + uy * self.s * 0.52)
        cola = self.s * 0.24
        salidas = (0.0, 0.15, 0.30)
        hecho = [0.0, 0.0]
        self.sonar("ametralladora")

        def cuadro(t, et):
            self._retroceso(etiqueta, ux, uy, t, hecho, 0.06, salidas)
            for k, inicio in enumerate(salidas):
                v = (t - inicio) / 0.12
                if 0 <= v < 1:
                    self._destello(boca, self.s * 0.2, v, et)
                # Casquillo que sale disparado a la derecha del cañón
                w = (t - inicio) / 0.4
                if 0 < w <= 1:
                    lado = (-uy, ux)
                    x = desde[0] + lado[0] * self.s * (0.25 + 0.3 * w)
                    y = desde[1] + lado[1] * self.s * (0.25 + 0.3 * w) \
                        - math.sin(math.pi * w) * self.s * 0.2
                    r = max(1.5, self.s * 0.03)
                    self._circulo((x, y), r, et, outline="",
                                  fill=self._desvanecer(AMARILLO, w, 0.5))
                u = (t - inicio) / 0.5
                if not 0 < u <= 1:
                    continue
                x = boca[0] + (hasta[0] - boca[0]) * u
                y = boca[1] + (hasta[1] - boca[1]) * u
                for ancho, color in ((6, NARANJA), (2, BLANCO)):
                    self.c.create_line(x - ux * cola, y - uy * cola, x, y,
                                       fill=color, width=ancho,
                                       capstyle="round", tags=self._tags(et))

        seguir = self._correr(460, cuadro)
        self._regresar(etiqueta, hecho)
        if seguir and impacto:
            seguir = self.chispas(hasta, metal=blanco)
        return seguir

    def misil(self, desde: Punto, hasta: Punto,
              etiqueta: Optional[str] = None) -> bool:
        """Sale en arco hacia la casilla con su estela de humo; la mira
        marca el blanco y el lanzador retrocede con el arranque."""
        distancia = math.hypot(hasta[0] - desde[0], hasta[1] - desde[1])
        altura = self.s * 0.6 + distancia * 0.25
        ux, uy = _unitario(desde, hasta)
        estela: list[Punto] = []
        hecho = [0.0, 0.0]
        self.sonar("misil")

        def cuadro(t, et):
            self._retroceso(etiqueta, ux, uy, t, hecho, 0.12)
            # La mira sobre la casilla objetivo: gira y se cierra
            hx, hy = hasta
            r = self.s * (0.42 - 0.12 * suave(t))
            giro = t * math.pi
            self._circulo(hasta, r, et, outline=ROJO, width=2)
            for k in range(4):
                a = giro + k * math.pi / 2
                ca, sa = math.cos(a), math.sin(a)
                self.c.create_line(hx + ca * r * 0.6, hy + sa * r * 0.6,
                                   hx + ca * r * 1.35, hy + sa * r * 1.35,
                                   fill=ROJO, width=2, tags=self._tags(et))
            if t < 0.25:                    # arranque: fogonazo y humo
                self._destello(desde, self.s * 0.4, t / 0.25, et)
                for k in range(5):
                    a = k * 2 * math.pi / 5 + 0.4
                    d = self.s * (0.2 + 0.5 * t)
                    self._circulo((desde[0] + math.cos(a) * d,
                                   desde[1] + math.sin(a) * d),
                                  self.s * 0.12, et, outline="",
                                  fill=self._desvanecer(HUMO, t / 0.25, 0.2))
            p = arco(desde, hasta, altura, suave(t))
            estela.append(p)
            for k, (x, y) in enumerate(estela[-14:]):
                f = 1 - k / 14
                rr = self.s * 0.05 * (0.6 + 1.2 * f)
                self._circulo((x, y), rr, et, outline="",
                              fill=sprites.mezclar(HUMO, self.fondo, f))
            atras = arco(desde, hasta, altura, suave(max(0, t - 0.06)))
            self.c.create_line(atras[0], atras[1], p[0], p[1],
                               fill="#B8C4D2", width=max(4, self.s * 0.11),
                               capstyle="round", tags=self._tags(et))
            # Llama del motor del misil, parpadeante
            fx = atras[0] - (p[0] - atras[0]) * 0.6
            fy = atras[1] - (p[1] - atras[1]) * 0.6
            rr = self.s * (0.06 + 0.03 * math.sin(t * 50))
            self._circulo((fx, fy), rr, et, outline="", fill=NARANJA)
            rr = self.s * 0.06
            self._circulo(p, rr, et, outline="", fill=ROJO)

        seguir = self._correr(700, cuadro)
        self._regresar(etiqueta, hecho)
        return seguir

    def explosion(self, p: Punto, grande: bool = True) -> bool:
        """Destello, bola de fuego, onda expansiva, chispas que caen y
        humo. Las grandes hacen temblar el tablero."""
        radio = self.s * (0.55 if grande else 0.32)
        colores = (BLANCO, AMARILLO, NARANJA, ROJO)
        rng = random.Random(int(p[0] * 7 + p[1] * 13))
        brasas = [(rng.uniform(0, 2 * math.pi), rng.uniform(0.6, 1.5),
                   rng.uniform(0.6, 1.4)) for _ in range(14 if grande else 7)]
        temblor = [0.0, 0.0]
        self.sonar("explosion" if grande else "explosion_chica")

        def cuadro(t, et):
            if grande:
                self._temblor(t, 0.09, temblor)
            # Destello que ilumina alrededor, en halos que se apagan
            if t < 0.2:
                for k, r in enumerate((0.9, 0.7)):
                    self._circulo(p, radio * r * 1.6, et, outline="",
                                  fill=sprites.mezclar(
                                      AMARILLO, self.fondo,
                                      0.55 - 0.25 * k + 0.45 * t / 0.2))
            for k, ancho in ((0, 4), (0.12, 2)):          # ondas expansivas
                v = t - k
                if v > 0:
                    onda = radio * (0.5 + 1.6 * v)
                    self._circulo(p, onda, et, width=ancho,
                                  outline=self._desvanecer(NARANJA, v, 0.1))
            # Humo que queda y sube
            for k in range(5):
                a = k * 2 * math.pi / 5 + 0.7
                d = radio * 0.5 * t
                r = radio * (0.3 + 0.4 * t)
                self._circulo((p[0] + math.cos(a) * d,
                               p[1] + math.sin(a) * d - self.s * 0.2 * t),
                              r, et, outline="",
                              fill=self._desvanecer(HUMO_OSCURO, t, 0.5))
            # Bola de fuego en capas
            for k, color in enumerate(reversed(colores)):
                r = radio * (1 - k * 0.22) * min(1, t * 3) * (1.1 - 0.3 * t)
                if r <= 0:
                    continue
                self._circulo(p, r, et, outline="",
                              fill=self._desvanecer(color, t, 0.35))
            # Brasas que salen volando y caen
            for ang, rapidez, tam in brasas:
                d = radio * rapidez * (0.3 + 1.4 * t)
                x = p[0] + math.cos(ang) * d
                y = p[1] + math.sin(ang) * d + self.s * 0.5 * t * t
                rr = max(1.5, self.s * 0.04 * tam * (1 - t))
                self._circulo((x, y), rr, et, outline="",
                              fill=self._desvanecer(AMARILLO, t, 0.4))

        seguir = self._correr(650 if grande else 420, cuadro)
        self.c.move("all", -temblor[0], -temblor[1])
        return seguir

    def humo(self, p: Punto) -> bool:
        """Columna de humo que sube y se dispersa, con brasas."""
        def cuadro(t, et):
            for k, (ox, oy, retraso) in enumerate(
                    ((-0.12, 0, 0), (0.12, -0.05, 0.1), (0, -0.15, 0.2),
                     (-0.05, 0.05, 0.3), (0.08, 0.02, 0.4))):
                v = max(0.0, (t - retraso) / (1 - retraso))
                if v <= 0:
                    continue
                r = self.s * (0.12 + 0.22 * v)
                x = p[0] + (ox + 0.08 * math.sin(v * 5 + k)) * self.s
                y = p[1] + (oy - 0.45 * v) * self.s
                color = HUMO_OSCURO if k % 2 else HUMO
                self._circulo((x, y), r, et, outline="",
                              fill=self._desvanecer(color, v, 0.25))
            if t < 0.6:
                for k in range(3):
                    y = p[1] - self.s * (0.1 + 0.6 * t + 0.1 * k)
                    x = p[0] + self.s * 0.15 * math.sin(t * 12 + k * 2)
                    self._circulo((x, y), max(1.5, self.s * 0.025), et,
                                  outline="",
                                  fill=self._desvanecer(NARANJA, t / 0.6, 0.3))

        return self._correr(650, cuadro)

    def chispas(self, p: Punto, metal: bool = False) -> bool:
        """Chispas del impacto; contra un tanque suena a metal."""
        if metal:
            self.sonar("impacto")

        def cuadro(t, et):
            if t < 0.35:
                self._destello(p, self.s * 0.22, t / 0.35, et)
            for k in range(9):
                ang = k * 2 * math.pi / 9 + 0.2
                r0 = self.s * 0.06 + self.s * 0.28 * t
                r1 = r0 + self.s * 0.12 * (1 - t)
                caida = self.s * 0.15 * t * t
                self.c.create_line(p[0] + math.cos(ang) * r0,
                                   p[1] + math.sin(ang) * r0 + caida,
                                   p[0] + math.cos(ang) * r1,
                                   p[1] + math.sin(ang) * r1 + caida,
                                   fill=self._desvanecer(AMARILLO, t, 0.3),
                                   width=2, capstyle="round",
                                   tags=self._tags(et))

        return self._correr(260, cuadro)

    # ---------------------------------------------------------- movimiento
    def deslizar(self, etiqueta: str, desde: Punto, hasta: Punto) -> bool:
        """Mueve las piezas de un sprite ya dibujado; deja polvo y la
        huella de las orugas detrás."""
        hecho = [0.0, 0.0]
        ux, uy = _unitario(desde, hasta)
        lado = (-uy * self.s * 0.34, ux * self.s * 0.34)
        self.sonar("motor")

        def cuadro(t, et):
            u = suave(t)
            x = (hasta[0] - desde[0]) * u
            y = (hasta[1] - desde[1]) * u
            # Huellas de las orugas, del punto de partida a la cola
            cola = (desde[0] + x - ux * self.s * 0.38,
                    desde[1] + y - uy * self.s * 0.38)
            inicio = (desde[0] - ux * self.s * 0.38,
                      desde[1] - uy * self.s * 0.38)
            if u > 0.05:
                for signo in (-1, 1):
                    self.c.create_line(
                        inicio[0] + signo * lado[0],
                        inicio[1] + signo * lado[1],
                        cola[0] + signo * lado[0], cola[1] + signo * lado[1],
                        fill=sprites.mezclar(POLVO, self.fondo, 0.45),
                        width=max(2, self.s * 0.1), dash=(3, 2),
                        tags=self._tags(et))
            # Nubecitas de polvo que nacen en la cola y se disipan
            for k in range(6):
                nace = k / 7
                v = (t - nace) / 0.45
                if not 0 < v <= 1:
                    continue
                un = suave(nace)
                bx = desde[0] + (hasta[0] - desde[0]) * un - ux * self.s * 0.42
                by = desde[1] + (hasta[1] - desde[1]) * un - uy * self.s * 0.42
                signo = -1 if k % 2 else 1
                bx += signo * lado[0] * (1 + v * 0.4)
                by += signo * lado[1] * (1 + v * 0.4)
                self._circulo((bx, by), self.s * (0.05 + 0.1 * v), et,
                              outline="",
                              fill=self._desvanecer(POLVO, v, 0.2))
            self.c.tag_raise(etiqueta)
            self.c.move(etiqueta, x - hecho[0], y - hecho[1])
            self.c.move("resalte", x - hecho[0], y - hecho[1])
            hecho[:] = [x, y]

        return self._correr(340, cuadro)

    def embestida(self, etiqueta: str, desde: Punto, hacia: Punto,
                  alcance: float = 0.32) -> bool:
        """Se lanza hacia `hacia` y regresa; chispas y temblor en el
        golpe."""
        hecho = [0.0, 0.0]
        vx, vy = hacia[0] - desde[0], hacia[1] - desde[1]
        self.sonar("motor")

        def cuadro(t, _et):
            u = alcance * math.sin(math.pi * t)
            x, y = vx * u, vy * u
            self.c.move(etiqueta, x - hecho[0], y - hecho[1])
            hecho[:] = [x, y]

        seguir = self._correr(320, cuadro)
        if seguir:
            self.sonar("choque")
            golpe = (desde[0] + vx * alcance, desde[1] + vy * alcance)
            temblor = [0.0, 0.0]

            def sacudida(t, et):
                self._temblor(t, 0.05, temblor)
                if t < 0.5:
                    self._destello(golpe, self.s * 0.3, t / 0.5, et)

            seguir = self._correr(200, sacudida)
            self.c.move("all", -temblor[0], -temblor[1])
            if seguir:
                seguir = self.chispas(golpe)
        return seguir

    # ---------------------------------------------------------- daño
    def golpe(self, etiqueta: str, p: Punto, color: str = ROJO) -> bool:
        """El tanque que recibe daño destella y se sacude."""
        piezas = []
        for item in self.c.find_withtag(etiqueta):
            try:
                piezas.append((item, self.c.itemcget(item, "fill")))
            except Exception:              # noqa: BLE001 - piezas sin fill
                continue
        hecho = [0.0, 0.0]

        def cuadro(t, _et):
            k = (1 - t) * (0.5 + 0.5 * math.cos(t * 6 * math.pi))
            for item, relleno in piezas:
                if relleno and relleno.startswith("#"):
                    self.c.itemconfigure(
                        item, fill=sprites.mezclar(relleno, color, k * 0.8))
            x = self.s * 0.05 * (1 - t) * math.sin(t * 40)
            self.c.move(etiqueta, x - hecho[0], 0)
            hecho[0] = x

        seguir = self._correr(300, cuadro)
        for item, relleno in piezas:
            self.c.itemconfigure(item, fill=relleno)
        self.c.move(etiqueta, -hecho[0], 0)
        return seguir

    # ---------------------------------------------------------- sensores
    def radar(self, desde: Punto, direccion: Direccion,
              lectura: int) -> bool:
        """Ondas que salen del tanque, un haz que avanza hasta lo
        detectado y un pulso al llegar."""
        distancia = abs(lectura) - (0.5 if lectura < 0 else 0)
        fin = (desde[0] + direccion.dx * distancia * self.s,
               desde[1] + direccion.dy * distancia * self.s)
        ping = ROJO if lectura > 0 else HUMO
        self.sonar("radar")
        angulo = math.degrees(math.atan2(-direccion.dy, direccion.dx))

        def cuadro(t, et):
            # Abanico de ondas hacia la dirección del radar
            for k in range(3):
                v = (t - k * 0.12) / 0.5
                if not 0 < v <= 1:
                    continue
                r = self.s * (0.3 + 0.9 * v)
                self.c.create_arc(desde[0] - r, desde[1] - r, desde[0] + r,
                                  desde[1] + r, start=angulo - 25,
                                  extent=50, style="arc", width=2,
                                  outline=self._desvanecer(VERDE, v, 0.3),
                                  tags=self._tags(et))
            u = min(1, t / 0.6)
            x = desde[0] + (fin[0] - desde[0]) * u
            y = desde[1] + (fin[1] - desde[1]) * u
            color = self._desvanecer(VERDE, t, 0.6)
            self.c.create_line(desde[0], desde[1], x, y, fill=color,
                               width=3, dash=(6, 4), tags=self._tags(et))
            r = self.s * 0.16
            self._circulo((x, y), r, et, outline=color, width=2)
            if t > 0.6:
                v = (t - 0.6) / 0.4
                for k in (0, 0.35):
                    r = self.s * (0.1 + 0.4 * (v + k) / 1.35)
                    self._circulo(fin, r, et, width=3,
                                  outline=sprites.mezclar(ping, self.fondo,
                                                          v))

        return self._correr(560, cuadro)

    # ---------------------------------------------------------- estados
    def anillo(self, p: Punto, color: str, r0: float, r1: float,
               ms: float = 320, guiones: tuple = ()) -> bool:
        def cuadro(t, et):
            r = self.s * (r0 + (r1 - r0) * suave(t))
            self._circulo(p, r, et, outline=self._desvanecer(color, t, 0.5),
                          width=max(3, self.s / 16), dash=guiones)

        return self._correr(ms, cuadro)

    def escudo(self, p: Punto) -> bool:
        """El hexágono del escudo se forma desde el centro con destellos
        cian que giran alrededor."""
        self.sonar("escudo")

        def cuadro(t, et):
            u = suave(t)
            e = self.s * (0.15 + 0.36 * u)
            giro = (1 - u) * math.pi / 2
            puntos = []
            for k in range(6):
                a = math.radians(60 * k + 30) + giro
                puntos += [p[0] + e * math.cos(a), p[1] + e * math.sin(a)]
            self.c.create_polygon(puntos, fill="", width=max(2, self.s / 22),
                                  outline=self._desvanecer(AZUL, t, 0.7),
                                  tags=self._tags(et))
            for k in range(6):
                a = t * 2 * math.pi + k * math.pi / 3
                d = self.s * (0.55 - 0.1 * u)
                self._circulo((p[0] + math.cos(a) * d,
                               p[1] + math.sin(a) * d),
                              max(1.5, self.s * 0.035), et, outline="",
                              fill=self._desvanecer(BLANCO if k % 2 else AZUL,
                                                    t, 0.6))

        return self._correr(440, cuadro)

    def bloqueo(self, p: Punto) -> bool:
        """El escudo para el golpe: el hexágono destella y se ondula."""
        self.sonar("bloqueo")

        def cuadro(t, et):
            for k in range(2):
                v = t - k * 0.2
                if v <= 0:
                    continue
                e = self.s * (0.49 + 0.18 * v)
                puntos = []
                for j in range(6):
                    a = math.radians(60 * j + 30)
                    puntos += [p[0] + e * math.cos(a), p[1] + e * math.sin(a)]
                self.c.create_polygon(
                    puntos, fill="", width=max(3, self.s / 14 * (1 - v)),
                    outline=self._desvanecer(BLANCO if k == 0 else AZUL, v,
                                             0.2), tags=self._tags(et))

        return self._correr(300, cuadro)

    def curar(self, p: Punto) -> bool:
        """Cruces verdes que suben alrededor del tanque."""
        self.sonar("reparar")

        def cuadro(t, et):
            for k in range(5):
                v = (t - k * 0.1) / 0.6
                if not 0 < v <= 1:
                    continue
                x = p[0] + self.s * 0.32 * math.cos(k * 1.9 + 0.5)
                y = p[1] + self.s * (0.2 - 0.55 * v)
                b = self.s * 0.07
                color = self._desvanecer(VERDE, v, 0.5)
                ancho = max(2, self.s / 22)
                self.c.create_line(x - b, y, x + b, y, fill=color,
                                   width=ancho, tags=self._tags(et))
                self.c.create_line(x, y - b, x, y + b, fill=color,
                                   width=ancho, tags=self._tags(et))
            r = self.s * (0.2 + 0.3 * suave(min(1, t * 1.5)))
            self._circulo(p, r, et, width=max(2, self.s / 18),
                          outline=self._desvanecer(VERDE, t, 0.4))

        return self._correr(520, cuadro)

    def mina_armada(self, p: Punto) -> bool:
        """La mina se arma: su luz parpadea dos veces y lanza un pulso."""
        self.sonar("mina_armada")

        def cuadro(t, et):
            encendida = int(t * 4) % 2 == 0
            r = self.s * 0.06
            self._circulo(p, r, et, outline="",
                          fill=ROJO if encendida else sprites.MINA_NUCLEO)
            r = self.s * (0.1 + 0.35 * t)
            self._circulo(p, r, et, width=2,
                          outline=self._desvanecer(ROJO, t, 0.3))

        return self._correr(360, cuadro)

    def texto(self, p: Punto, texto: str, color: str,
              ms: float = 620) -> bool:
        """Cifra que salta, sube y se desvanece: −10, +20, bloqueado…"""
        tam = max(9, int(self.s * 0.26))

        def cuadro(t, et):
            y = p[1] - self.s * (0.25 + 0.45 * suave(t))
            # Entra grande y se asienta, como un golpe
            escala = 1 + 0.5 * max(0.0, 1 - t / 0.2)
            fuente = ("Segoe UI", int(tam * escala), "bold")
            c = self._desvanecer(color, t, 0.55)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.c.create_text(p[0] + ox, y + oy, text=texto,
                                   fill=sprites.mezclar(HALO, self.fondo, t),
                                   font=fuente, tags=self._tags(et))
            self.c.create_text(p[0], y, text=texto, fill=c, font=fuente,
                               tags=self._tags(et))

        return self._correr(ms, cuadro)

    def mina_nueva(self, desde: Punto, hasta: Punto,
                   escala: float = 1.0) -> bool:
        """La mina sale del tanque, grande, gira y se asienta donde queda.

        Empieza al doble de su tamaño final para que se note: la mina sin
        armar es de trazo claro y, chica, se perdería sobre el tanque.
        """
        final = self.s * escala
        self.sonar("mina")

        def cuadro(t, et):
            u = suave(min(1, t / 0.65))
            x = desde[0] + (hasta[0] - desde[0]) * u
            y = desde[1] + (hasta[1] - desde[1]) * u - math.sin(
                math.pi * u) * self.s * 0.35
            # Sombra en el piso que crece al acercarse
            sr = final * 0.2 * (0.5 + 0.5 * u)
            sx = desde[0] + (hasta[0] - desde[0]) * u
            sy = desde[1] + (hasta[1] - desde[1]) * u
            self.c.create_oval(sx - sr, sy - sr * 0.5, sx + sr, sy + sr * 0.5,
                               fill=sprites.mezclar(HALO, self.fondo, 0.4),
                               outline="", tags=self._tags(et))
            sprites.mina(self.c, x, y, final * (2.0 - u), armada=False,
                         extra=self._tags(et))
            if t > 0.55:
                v = (t - 0.55) / 0.45
                r = final * (0.3 + 0.6 * v)
                self._circulo(hasta, r, et, width=3,
                              outline=sprites.mezclar(sprites.MINA_ARMADA,
                                                      self.fondo, v))

        return self._correr(520, cuadro)
