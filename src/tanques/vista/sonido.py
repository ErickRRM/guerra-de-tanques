"""Efectos de sonido sintetizados: disparos, explosiones, motor, radar…
y los de la interfaz: la portada, el pulso del radar del título y los
botones (pasar el ratón, clic, confirmar, regresar). Además, la música:
una canción tipo arcade de guerra (metales, bajo, guitarra y batería de
marcha) que suena en todas las pantallas, en bucle. Música y efectos se
encienden y apagan por separado, y la música tiene su propio volumen.

No hay archivos de audio en el proyecto ni dependencias nuevas: cada
efecto se genera con unas cuantas ondas y ruido filtrado, se guarda como
WAV en la carpeta temporal del sistema la primera vez y se reproduce sin
bloquear la ventana.

- En Windows se usa MCI (winmm), que deja sonar varios efectos a la vez;
  la música va por el dispositivo `mpegvideo` de MCI, que la repite sola y
  deja cambiarle el volumen. Sin MCI, `winsound` (un efecto a la vez y sin
  música).
- En macOS y Linux se lanza el reproductor del sistema (afplay, paplay o
  aplay) si existe; la música se vuelve a lanzar al terminar cada vuelta.
- Sin nada de eso, o con la variable de entorno TANQUES_SIN_SONIDO, el
  juego queda en silencio sin fallar.

Este módulo no importa Tkinter.
"""
from __future__ import annotations

import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path
from typing import Optional

FRECUENCIA = 22050
VERSION = 4                       # súbela si cambia la síntesis


# ------------------------------------------------------------ síntesis
def _muestras(segundos: float) -> range:
    return range(int(segundos * FRECUENCIA))


def _ruido(segundos: float, suavizado: float, semilla: int) -> list[float]:
    """Ruido blanco con un filtro pasa bajos de un polo (0 < suavizado ≤ 1).

    Entre más chico el suavizado, más grave y sordo el ruido.
    """
    rng = random.Random(semilla)
    y, salida = 0.0, []
    for _ in _muestras(segundos):
        y += suavizado * (rng.uniform(-1, 1) - y)
        salida.append(y)
    pico = max(map(abs, salida)) or 1
    return [v / pico for v in salida]


def _seno(f0: float, segundos: float, f1: Optional[float] = None,
          vibrato: float = 0.0) -> list[float]:
    """Onda senoidal; con f1 barre la frecuencia de f0 a f1."""
    f1 = f0 if f1 is None else f1
    n = int(segundos * FRECUENCIA)
    fase, salida = 0.0, []
    for i in range(n):
        u = i / max(1, n - 1)
        f = f0 + (f1 - f0) * u
        if vibrato:
            f *= 1 + vibrato * math.sin(2 * math.pi * 18 * i / FRECUENCIA)
        fase += 2 * math.pi * f / FRECUENCIA
        salida.append(math.sin(fase))
    return salida


def _decae(senal: list[float], rapidez: float, ataque: float = 0.003
           ) -> list[float]:
    """Envolvente: sube en `ataque` segundos y cae exponencialmente."""
    salida = []
    for i, v in enumerate(senal):
        t = i / FRECUENCIA
        subida = min(1.0, t / ataque) if ataque else 1.0
        salida.append(v * subida * math.exp(-rapidez * t))
    return salida


def _campana(senal: list[float], subida: float, bajada: float
             ) -> list[float]:
    """Envolvente que entra y sale suave (fracciones de la duración)."""
    n = len(senal)
    salida = []
    for i, v in enumerate(senal):
        u = i / max(1, n - 1)
        g = min(1.0, u / subida if subida else 1.0,
                (1 - u) / bajada if bajada else 1.0)
        salida.append(v * g)
    return salida


def _mezcla(total: float, *capas: tuple[float, list[float], float]
            ) -> list[float]:
    """Suma capas (inicio en segundos, señal, volumen) y normaliza."""
    salida = [0.0] * int(total * FRECUENCIA)
    for inicio, senal, volumen in capas:
        k = int(inicio * FRECUENCIA)
        for i, v in enumerate(senal):
            if k + i < len(salida):
                salida[k + i] += v * volumen
    pico = max(map(abs, salida)) or 1
    return [v / pico for v in salida]


def _disparo(semilla: int) -> list[float]:
    golpe = _decae(_ruido(0.09, 0.55, semilla), 48)
    cuerpo = _decae(_seno(150, 0.09, 70), 40)
    return _mezcla(0.09, (0, golpe, 1.0), (0, cuerpo, 0.7))


def _explosion(segundos: float, rapidez: float, semilla: int
               ) -> list[float]:
    estruendo = _decae(_ruido(segundos, 0.035, semilla), rapidez, 0.01)
    chasquido = _decae(_ruido(0.12, 0.9, semilla + 1), 45)
    bum = _decae(_seno(62, segundos, 38), rapidez * 1.3, 0.005)
    return _mezcla(segundos, (0, estruendo, 1.0), (0, chasquido, 0.55),
                   (0, bum, 0.9))


def _metal(segundos: float, frecuencias, rapidez: float) -> list[float]:
    capas = [(0, _decae(_seno(f, segundos), rapidez * (1 + k * 0.4)),
              1 / (k + 1)) for k, f in enumerate(frecuencias)]
    return _mezcla(segundos, *capas)


def _notas(frecuencias, duracion: float, rapidez: float,
           brillo: float = 0.3) -> list[float]:
    capas = []
    for k, f in enumerate(frecuencias):
        tono = _decae(_seno(f, duracion * 2.2), rapidez, 0.004)
        armonico = _decae(_seno(f * 2, duracion * 2.2), rapidez * 1.6, 0.004)
        capas += [(k * duracion, tono, 1.0), (k * duracion, armonico, brillo)]
    return _mezcla(duracion * (len(frecuencias) + 1.3), *capas)


def _sintetizar() -> dict[str, tuple[list[float], float]]:
    """Cada efecto: (muestras normalizadas, volumen final)."""
    rafaga = _mezcla(0.42, *((k * 0.11, _disparo(10 + k), 1.0)
                             for k in range(3)))
    silbido = _campana(_ruido(0.65, 0.22, 20), 0.15, 0.5)
    tono = _campana(_seno(260, 0.65, 820), 0.1, 0.5)
    arranque = _decae(_ruido(0.15, 0.4, 21), 22)
    misil = _mezcla(0.65, (0, silbido, 1.0), (0, tono, 0.25),
                    (0, arranque, 0.8))
    rugido = _campana(_mezcla(0.4, (0, _seno(48, 0.4), 0.8),
                              (0, _seno(97, 0.4, 110), 0.5),
                              (0, _ruido(0.4, 0.08, 30), 0.9)), 0.15, 0.4)
    choque = _mezcla(0.5, (0, _decae(_seno(85, 0.5, 50), 12), 1.0),
                     (0, _metal(0.5, (410, 690, 1130), 9), 0.6),
                     (0, _decae(_ruido(0.2, 0.6, 40), 30), 0.6))
    escudo = _campana(_mezcla(0.6, (0, _seno(300, 0.6, 1150, 0.02), 1.0),
                              (0, _seno(600, 0.6, 2300, 0.02), 0.3)),
                      0.1, 0.45)
    bloqueo = _decae(_mezcla(0.3, (0, _seno(1500, 0.3, 380), 1.0),
                             (0, _ruido(0.3, 0.7, 50), 0.25)), 11)
    radar = _mezcla(0.7, (0, _decae(_seno(1320, 0.4), 11), 1.0),
                    (0.26, _decae(_seno(1320, 0.4), 13), 0.35))
    mina = _mezcla(0.3, (0, _decae(_ruido(0.04, 0.9, 60), 80), 0.7),
                   (0.05, _campana(_seno(880, 0.09), 0.1, 0.3), 0.8))
    armada = _mezcla(0.32, (0, _campana(_seno(1560, 0.07), 0.1, 0.3), 1.0),
                     (0.14, _campana(_seno(1560, 0.07), 0.1, 0.3), 1.0))
    # ---- interfaz: tonos limpios y cortos, como de consola de mando
    hover = _decae(_seno(2600, 0.04), 90, 0.002)
    clic = _mezcla(0.07, (0, _decae(_ruido(0.012, 0.9, 80), 260), 0.5),
                   (0.004, _decae(_seno(1650, 0.06, 1150), 55), 1.0))
    confirmar = _mezcla(0.32,
                        (0, _decae(_seno(880, 0.12), 22, 0.003), 1.0),
                        (0.07, _decae(_seno(1320, 0.2), 14, 0.003), 1.0),
                        (0.07, _decae(_seno(2640, 0.2), 24, 0.003), 0.25),
                        (0, _decae(_ruido(0.02, 0.9, 81), 200), 0.3))
    atras = _mezcla(0.24, (0, _decae(_seno(1100, 0.1), 25, 0.003), 1.0),
                    (0.06, _decae(_seno(740, 0.16), 18, 0.003), 1.0))
    apagado = _decae(_mezcla(0.14, (0, _seno(150, 0.14), 1.0),
                             (0, _seno(225, 0.14), 0.6)), 18, 0.004)
    tic = _decae(_seno(2100, 0.035), 110, 0.002)
    barrido = _mezcla(0.9, (0, _decae(_seno(1180, 0.6), 7), 1.0),
                      (0.3, _decae(_seno(1180, 0.5), 9), 0.3))
    # Arranque: un zumbido grave que crece, el radar que se enciende y
    # un acorde dorado, como el título.
    zumbido = _campana(_mezcla(2.6, (0, _seno(55, 2.6), 1.0),
                               (0, _seno(82.4, 2.6), 0.6),
                               (0, _ruido(2.6, 0.03, 90), 0.5)), 0.45, 0.3)
    subida = _campana(_seno(180, 1.1, 720), 0.6, 0.2)
    acorde = _mezcla(1.5, *((0.03 * k, _decae(_seno(f, 1.5), 3.2, 0.01), v)
                            for k, (f, v) in enumerate(((440, 1.0),
                                                        (554, 0.8),
                                                        (659, 0.7),
                                                        (880, 0.5)))))
    intro = _mezcla(2.8, (0, zumbido, 0.8), (0.1, subida, 0.25),
                    (1.1, acorde, 0.7), (1.1, _decae(_ruido(0.3, 0.5, 91),
                                                     12), 0.25))
    return {
        "hover": (hover, 0.12),
        "clic": (clic, 0.3),
        "confirmar": (confirmar, 0.32),
        "atras": (atras, 0.28),
        "apagado": (apagado, 0.25),
        "tic": (tic, 0.18),
        "barrido": (barrido, 0.1),
        "intro": (intro, 0.5),
        "ametralladora": (rafaga, 0.55),
        "misil": (misil, 0.5),
        "explosion": (_explosion(1.2, 3.6, 70), 0.9),
        "explosion_chica": (_explosion(0.55, 7.5, 71), 0.6),
        "impacto": (_metal(0.16, (1850, 2700, 3950), 30), 0.3),
        "motor": (rugido, 0.3),
        "choque": (choque, 0.7),
        "escudo": (escudo, 0.25),
        "bloqueo": (bloqueo, 0.4),
        "reparar": (_notas((660, 880, 1320), 0.11, 14), 0.35),
        "radar": (radar, 0.3),
        "mina": (mina, 0.45),
        "mina_armada": (armada, 0.3),
        "victoria": (_notas((523, 659, 784, 1046), 0.13, 5, 0.5), 0.45),
    }


# ------------------------------------------------------------ música
# Canción original al estilo de los arcades de guerra de los noventa:
# marcha rápida con metales que atacan en golpes cortos, bajo funky en
# semicorcheas, guitarra en power chords apagados con la palma y batería
# con redobles de caja. 160 pulsos por minuto, 16 compases en la menor.
TEMPO = 160
SEMI = 60 / TEMPO / 4                     # duración de una semicorchea

_ACORDES = {"Am": 45, "F": 41, "C": 48, "G": 43, "E": 40, "Dm": 50}
# Un acorde por compás, o dos (uno por cada mitad)
_PROGRESION = (("Am",), ("Am",), ("F",), ("G",), ("Am",), ("Am",),
               ("F", "G"), ("E",),
               ("C",), ("G",), ("Am",), ("F",), ("Dm",), ("E",),
               ("Am", "F"), ("G", "E"))
# Metales: (semicorchea de inicio, duración en semicorcheas, nota MIDI)
_MELODIA = (
    ((0, 2, 69), (3, 1, 69), (4, 2, 72), (6, 2, 76), (8, 3, 81),
     (11, 1, 79), (12, 4, 76)),
    ((0, 2, 74), (2, 2, 76), (4, 2, 72), (6, 2, 69), (8, 2, 71),
     (10, 2, 72), (12, 4, 74)),
    ((0, 3, 77), (3, 1, 76), (4, 2, 77), (6, 2, 81), (8, 4, 84),
     (12, 2, 81), (14, 2, 77)),
    ((0, 3, 79), (3, 1, 77), (4, 2, 79), (6, 2, 83), (8, 6, 86),
     (14, 2, 83)),
    ((0, 2, 81), (3, 1, 81), (4, 2, 81), (6, 2, 79), (8, 2, 76),
     (10, 2, 79), (12, 4, 81)),
    ((0, 2, 84), (2, 2, 83), (4, 2, 81), (6, 2, 79), (8, 4, 76),
     (12, 2, 74), (14, 2, 72)),
    ((0, 4, 77), (4, 4, 81), (8, 4, 79), (12, 4, 83)),
    ((0, 2, 80), (2, 2, 83), (4, 2, 88), (6, 2, 86), (8, 8, 83)),
    ((0, 2, 76), (2, 1, 76), (3, 1, 76), (4, 4, 79), (8, 2, 84),
     (10, 2, 83), (12, 4, 79)),
    ((0, 2, 74), (2, 1, 74), (3, 1, 74), (4, 4, 79), (8, 2, 83),
     (10, 2, 86), (12, 4, 83)),
    ((0, 2, 72), (2, 1, 72), (3, 1, 72), (4, 4, 76), (8, 2, 81),
     (10, 2, 79), (12, 4, 76)),
    ((0, 4, 77), (4, 2, 76), (6, 2, 74), (8, 8, 72)),
    ((0, 2, 74), (2, 2, 77), (4, 2, 81), (6, 2, 86), (8, 4, 84),
     (12, 4, 81)),
    ((0, 2, 80), (2, 2, 83), (4, 2, 86), (6, 2, 88), (8, 4, 86),
     (12, 4, 83)),
    ((0, 3, 81), (3, 1, 81), (4, 2, 81), (6, 2, 84), (8, 4, 84),
     (12, 4, 81)),
    ((0, 2, 79), (2, 2, 83), (4, 4, 86), (8, 2, 83), (10, 2, 80),
     (12, 4, 76)),
)
# Bajo: (semicorchea, intervalo sobre la raíz, duración)
_BAJO = ((0, 0, 2), (3, 0, 1), (4, 12, 1), (6, 0, 2), (8, 0, 1),
         (10, 7, 1), (11, 12, 1), (14, 0, 2))


def _hz(nota: float) -> float:
    return 440.0 * 2 ** ((nota - 69) / 12)


def _acorde_en(compas: tuple, semi: int) -> int:
    return _ACORDES[compas[0] if semi < 8 or len(compas) == 1
                    else compas[1]]


def _metales(buf, inicio, segundos, nota, volumen):
    """Sección de metales: dos sierras desafinadas apenas, con el «scoop»
    de entrada (la nota sube medio tono al atacar) y vibrato en las largas.
    """
    k0 = int(inicio * FRECUENCIA)
    n = int(segundos * FRECUENCIA)
    f = _hz(nota)
    fases = [0.0, 0.37]
    largo = segundos > 4 * SEMI
    suelta = int(0.02 * FRECUENCIA)
    for i in range(min(n, len(buf) - k0)):
        t = i / FRECUENCIA
        subida = 2 ** (-max(0.0, 0.035 - t) / 0.035 / 12)
        vib = 1 + (0.008 * math.sin(2 * math.pi * 6 * t) if largo
                   and t > 0.15 else 0)
        valor = 0.0
        for k, desafine in enumerate((1.0, 1.006)):
            fases[k] = (fases[k] + f * subida * vib * desafine
                        / FRECUENCIA) % 1.0
            valor += 2 * fases[k] - 1
        g = min(1.0, t / 0.008)
        g *= 0.7 + 0.3 * math.exp(-t / 0.09)          # el golpe del ataque
        if i > n - suelta:
            g *= (n - i) / suelta
        buf[k0 + i] += valor * 0.5 * volumen * g


def _bajo(buf, inicio, segundos, nota, volumen):
    """Bajo de dedo: onda cuadrada que se apaga rápido, con «slap»."""
    k0 = int(inicio * FRECUENCIA)
    n = int(segundos * FRECUENCIA)
    paso = _hz(nota) / FRECUENCIA
    fase = 0.0
    for i in range(min(n, len(buf) - k0)):
        fase = (fase + paso) % 1.0
        valor = 1.0 if fase < 0.5 else -1.0
        g = math.exp(-i / (0.09 * FRECUENCIA))
        if i > n - 120:
            g *= (n - i) / 120
        buf[k0 + i] += valor * volumen * g


def _guitarra(buf, inicio, segundos, raiz, volumen, apagada=True):
    """Power chord distorsionado (raíz, quinta y octava) recortado con
    tanh; apagado con la palma suena corto y seco."""
    k0 = int(inicio * FRECUENCIA)
    n = int(segundos * FRECUENCIA)
    pasos = [_hz(raiz + d) / FRECUENCIA for d in (0, 7, 12)]
    fases = [0.0, 0.2, 0.5]
    caida = 0.05 if apagada else 0.4
    for i in range(min(n, len(buf) - k0)):
        valor = 0.0
        for k in range(3):
            fases[k] = (fases[k] + pasos[k]) % 1.0
            valor += 2 * fases[k] - 1
        valor = math.tanh(valor * 2.2) * 0.8
        g = math.exp(-i / (caida * FRECUENCIA))
        if i > n - 100:
            g *= (n - i) / 100
        buf[k0 + i] += valor * volumen * g


def _golpe(buf, inicio, muestras, volumen):
    k0 = int(inicio * FRECUENCIA)
    for i, v in enumerate(muestras):
        if k0 + i < len(buf):
            buf[k0 + i] += v * volumen


def cancion() -> list[float]:
    """Una vuelta completa de la canción; al repetirse empata sin saltos."""
    compas = 16 * SEMI
    total = compas * len(_PROGRESION)
    buf = [0.0] * int(total * FRECUENCIA)
    bombo = _mezcla(0.18, (0, _decae(_seno(140, 0.18, 42), 18, 0.001), 1.0),
                    (0, _decae(_ruido(0.01, 0.9, 302), 300), 0.4))
    caja = _mezcla(0.16, (0, _decae(_ruido(0.16, 0.8, 300), 22), 1.0),
                   (0, _decae(_seno(190, 0.1, 160), 35), 0.6))
    plato = _decae(_ruido(0.05, 1.0, 301), 90)
    abierto = _decae(_ruido(0.2, 1.0, 303), 16)
    choque = _decae(_ruido(1.2, 1.0, 304), 3.2, 0.002)
    for c, acordes in enumerate(_PROGRESION):
        t0 = c * compas
        # Bajo funky en semicorcheas
        for semi, intervalo, largo in _BAJO:
            raiz = _acorde_en(acordes, semi) - 12
            _bajo(buf, t0 + semi * SEMI, largo * SEMI * 0.95,
                  raiz + intervalo, 0.42)
        # Guitarra: corcheas apagadas, acentos abiertos en 1 y 3
        for k in range(8):
            semi = 2 * k
            abierta = semi in (0, 8)
            _guitarra(buf, t0 + semi * SEMI, 2 * SEMI * 0.95,
                      _acorde_en(acordes, semi), 0.11 if abierta else 0.08,
                      apagada=not abierta)
        # Metales
        for inicio, largo, nota in _MELODIA[c]:
            _metales(buf, t0 + inicio * SEMI, largo * SEMI * 0.9, nota,
                     0.24)
        # Batería de marcha: bombo sincopado, caja en 2 y 4, platillo en
        # corcheas, platillo abierto al final de cada compás
        for k in (0, 6, 8, 11):
            _golpe(buf, t0 + k * SEMI, bombo, 0.6)
        for k in (4, 12):
            _golpe(buf, t0 + k * SEMI, caja, 0.42)
        for k in range(0, 14, 2):
            _golpe(buf, t0 + k * SEMI, plato, 0.13)
        _golpe(buf, t0 + 14 * SEMI, abierto, 0.12)
        if c % 8 == 7:                     # redoble que cierra la sección
            for k in range(8, 16):
                _golpe(buf, t0 + k * SEMI, caja, 0.15 + 0.035 * (k - 8))
        if c % 8 == 0:                     # platillo de choque al empezar
            _golpe(buf, t0, choque, 0.22)
    # Un poco de saturación para que suene a máquina de arcade
    pico = max(map(abs, buf)) or 1
    return [math.tanh(1.4 * v / pico) / math.tanh(1.4) for v in buf]


NOMBRES = ("ametralladora", "misil", "explosion", "explosion_chica",
           "impacto", "motor", "choque", "escudo", "bloqueo", "reparar",
           "radar", "mina", "mina_armada", "victoria",
           # interfaz
           "hover", "clic", "confirmar", "atras", "apagado", "tic",
           "barrido", "intro")


def escribir_wav(ruta: Path, muestras: list[float], volumen: float):
    datos = b"".join(struct.pack("<h", int(max(-1, min(1, v * volumen))
                                           * 32000)) for v in muestras)
    temporal = ruta.with_suffix(".tmp")
    with wave.open(str(temporal), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(datos)
    os.replace(temporal, ruta)


def generar_musica(carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "musica.wav"
    if not ruta.exists():
        escribir_wav(ruta, cancion(), 0.85)
    return ruta


def generar(carpeta: Path) -> dict[str, Path]:
    """Escribe los WAV que falten en `carpeta` y devuelve sus rutas."""
    carpeta.mkdir(parents=True, exist_ok=True)
    # Nombres cortos: MCI rechaza los que no caben en el formato 8.3.
    rutas = {n: carpeta / f"s{k:02d}.wav" for k, n in enumerate(NOMBRES)}
    if not all(r.exists() for r in rutas.values()):
        for nombre, (muestras, volumen) in _sintetizar().items():
            escribir_wav(rutas[nombre], muestras, volumen)
    return rutas


def carpeta_por_omision() -> Path:
    return Path(tempfile.gettempdir()) / f"guerra_de_tanques_sonidos_v{VERSION}"


# ------------------------------------------------------------ reproducción
class _Mci:
    """Windows: un dispositivo MCI por efecto, así suenan varios juntos."""

    def __init__(self):
        import ctypes
        self._mci = ctypes.windll.winmm.mciSendStringW
        self._buffer = ctypes.create_unicode_buffer(128)
        self._abiertos: set[str] = set()

    def _orden(self, texto: str) -> bool:
        return self._mci(texto, self._buffer, 127, 0) == 0

    def tocar(self, nombre: str, ruta: Path) -> bool:
        alias = f"tanques_{nombre}"
        if alias not in self._abiertos:
            if not self._orden(f'open "{ruta}" type waveaudio alias {alias}'):
                return False
            self._abiertos.add(alias)
        return self._orden(f"play {alias} from 0")

    def detener(self, nombre: str):
        alias = f"tanques_{nombre}"
        if alias in self._abiertos:
            self._orden(f"stop {alias}")

    # La música va por mpegvideo: se repite sola y acepta volumen.
    def musica(self, ruta: Path, volumen: float) -> bool:
        alias = "tanques_musica"
        if alias not in self._abiertos:
            if not self._orden(f'open "{ruta}" type mpegvideo alias {alias}'):
                return False
            self._abiertos.add(alias)
        self.volumen_musica(volumen)
        return self._orden(f"play {alias} repeat")

    def volumen_musica(self, volumen: float):
        self._orden(f"setaudio tanques_musica volume to "
                    f"{int(1000 * volumen)}")

    def parar_musica(self):
        self.detener("musica")

    def cerrar(self):
        for alias in self._abiertos:
            self._orden(f"close {alias}")
        self._abiertos.clear()


class _Winsound:
    def __init__(self):
        import winsound
        self._ws = winsound

    def tocar(self, nombre: str, ruta: Path) -> bool:
        w = self._ws
        w.PlaySound(str(ruta), w.SND_FILENAME | w.SND_ASYNC
                    | w.SND_NODEFAULT)
        return True

    def detener(self, nombre: str):
        self._ws.PlaySound(None, 0)

    def cerrar(self):
        self._ws.PlaySound(None, 0)


class _Comando:
    def __init__(self, programa: str):
        self._programa = programa
        self._procesos: dict[str, subprocess.Popen] = {}

    def tocar(self, nombre: str, ruta: Path) -> bool:
        self._procesos[nombre] = subprocess.Popen(
            [self._programa, str(ruta)], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        return True

    def detener(self, nombre: str):
        proceso = self._procesos.pop(nombre, None)
        if proceso is not None and proceso.poll() is None:
            proceso.terminate()

    def musica(self, ruta: Path, volumen: float) -> bool:
        """Sin bucle propio: un hilo vuelve a lanzar el reproductor."""
        self.parar_musica()
        argumentos = {"afplay": ["-v", f"{volumen:.2f}"],
                      "paplay": [f"--volume={int(65536 * volumen)}"]}.get(
            self._programa, [])
        orden = [self._programa, *argumentos, str(ruta)]
        self._sigue = True

        def bucle():
            while self._sigue:
                proceso = subprocess.Popen(orden, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                self._procesos["musica"] = proceso
                proceso.wait()
        threading.Thread(target=bucle, daemon=True).start()
        return True

    def volumen_musica(self, volumen: float):
        pass                                # se aplica al relanzar

    def parar_musica(self):
        self._sigue = False
        self.detener("musica")

    def cerrar(self):
        self.parar_musica()
        for nombre in list(self._procesos):
            self.detener(nombre)


def _reproductor():
    if sys.platform == "win32":
        try:
            return _Mci()
        except (OSError, AttributeError):
            try:
                return _Winsound()
            except ImportError:
                return None
    for programa in ("afplay", "paplay", "aplay"):
        if shutil.which(programa):
            return _Comando(programa)
    return None


class Sonido:
    """Toca efectos por nombre. Nunca lanza: si algo falla, calla."""

    def __init__(self, carpeta: Optional[Path] = None,
                 reproductor: Optional[object] = None,
                 en_segundo_plano: bool = True):
        self.efectos = True                    # disparos, botones, etc.
        self.musica_activa = True
        self._rutas: dict[str, Path] = {}
        self._musica: Optional[Path] = None
        self.volumen_musica = 5               # de 0 (callada) a 10
        self._sonando = False
        self._apagado = bool(os.environ.get("TANQUES_SIN_SONIDO"))
        if self._apagado:
            self._reproductor = None
            return
        self._reproductor = reproductor or _reproductor()
        if self._reproductor is None:
            return
        carpeta = carpeta or carpeta_por_omision()
        if en_segundo_plano:
            threading.Thread(target=self._preparar, args=(carpeta,),
                             daemon=True).start()
        else:
            self._preparar(carpeta)

    @property
    def disponible(self) -> bool:
        return self._reproductor is not None

    @property
    def listo(self) -> bool:
        """Ya están los WAV: lo que se toque ahora sí suena."""
        return bool(self._rutas)

    def _preparar(self, carpeta: Path):
        try:
            self._rutas = generar(carpeta)
            if hasattr(self._reproductor, "musica"):
                self._musica = generar_musica(carpeta)
        except OSError:
            self._rutas = {}

    # ---------------------------------------------------------- música
    @property
    def hay_musica(self) -> bool:
        return self._musica is not None

    @staticmethod
    def _nivel(volumen: int) -> float:
        """El oído no es lineal: los pasos bajos se reparten más finos."""
        return (max(0, min(10, volumen)) / 10) ** 1.7

    def musica(self):
        """Pone (o reanuda) la música si se puede y se debe oír."""
        if not (self.hay_musica and self._reproductor):
            return
        if not self.musica_activa or self.volumen_musica == 0:
            self._parar_musica()
            return
        try:
            if self._sonando:
                self._reproductor.volumen_musica(
                    self._nivel(self.volumen_musica))
            else:
                self._sonando = self._reproductor.musica(
                    self._musica, self._nivel(self.volumen_musica))
        except Exception:                 # noqa: BLE001
            self._sonando = False

    def _parar_musica(self):
        if self._sonando:
            try:
                self._reproductor.parar_musica()
            except Exception:             # noqa: BLE001
                pass
            self._sonando = False

    def cambiar_volumen_musica(self, volumen: int) -> int:
        self.volumen_musica = max(0, min(10, int(volumen)))
        self.musica()
        return self.volumen_musica

    def tocar(self, nombre: str, canal: str = ""):
        """Toca un efecto. Con `canal` distinto, el mismo efecto puede
        sonar encimado consigo mismo."""
        if not (self.efectos and self._reproductor
                and nombre in self._rutas):
            return
        try:
            if not self._reproductor.tocar(nombre + canal,
                                           self._rutas[nombre]):
                self._reproductor = None
        except Exception:                 # noqa: BLE001 - el sonido es opcional
            self._reproductor = None

    def detener(self, nombre: str, canal: str = ""):
        if self._reproductor is None:
            return
        try:
            self._reproductor.detener(nombre + canal)
        except Exception:                 # noqa: BLE001
            pass

    def alternar_efectos(self) -> bool:
        """Enciende o apaga los efectos; la música no cambia."""
        self.efectos = not self.efectos
        if not self.efectos:
            self.detener("intro")
        return self.efectos

    def alternar_musica(self) -> bool:
        """Enciende o apaga la música; los efectos no cambian."""
        self.musica_activa = not self.musica_activa
        self.musica()
        return self.musica_activa

    def cerrar(self):
        self._parar_musica()
        if self._reproductor is not None:
            try:
                self._reproductor.cerrar()
            except Exception:             # noqa: BLE001
                pass
