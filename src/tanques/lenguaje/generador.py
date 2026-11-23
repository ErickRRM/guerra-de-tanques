"""Generador de programas aleatorios y catálogo de instrucciones.

Sirve al editor de programas de la interfaz: «Aleatorio» escribe un
programa válido que el usuario puede modificar después, y el catálogo es la
lista de instrucciones disponibles que el editor muestra como referencia.

No hay lógica de juego aquí: solo texto que el intérprete sabe leer.
"""
from __future__ import annotations

import random
from typing import Optional

DIRECCIONES = ("N", "S", "E", "O")
ESQUINAS = ("NE", "NO", "SE", "SO")
OPERADORES = (">", "<", ">=", "<=", "==")

#: Las instrucciones disponibles: (plantilla que se inserta, descripción).
CATALOGO: tuple[tuple[str, str], ...] = (
    ("MOV(N)", "Avanza una casilla en la dirección (N, S, E, O)."),
    ("AMT(N)", "Dispara la ametralladora en esa dirección."),
    ("MISIL(N)", "Lanza un misil en esa dirección (munición limitada)."),
    ("MINA(NE)", "Lanza una mina a una esquina: NE, NO, SE o SO."),
    ("ESCUDO", "Activa el escudo: absorbe parte del daño."),
    ("REPARAR", "Recupera vida. Un solo uso por partida."),
    ("ESPERAR", "No hace nada este turno."),
    ("IF RADAR(N) > 0 THEN AMT(N)",
     "Radar: distancia al primer tanque (positiva) o a la pared "
     "(negativa) en esa dirección."),
    ("IF V < 40 THEN REPARAR",
     "V es la vida del tanque. Compara con >, <, >=, <= o =="),
)

#: Notas breves sobre la sintaxis, para el panel de ayuda del editor.
NOTAS = (
    "Una instrucción por línea; el programa se repite al terminar.",
    "Direcciones: N S E O  ·  esquinas de MINA: NE NO SE SO",
    "Dentro de un IF va cualquier instrucción salvo otro IF.",
    "Lo que sigue a # es un comentario y se ignora.",
)


def _simple(rng: random.Random, direccion: Optional[str] = None) -> str:
    d = direccion or rng.choice(DIRECCIONES)
    tipo = rng.choices(
        ("MOV", "AMT", "MISIL", "MINA", "ESCUDO", "ESPERAR"),
        weights=(5, 5, 2, 2, 2, 1))[0]
    if tipo == "MINA":
        return f"MINA({rng.choice(ESQUINAS)})"
    if tipo in ("ESCUDO", "ESPERAR"):
        return tipo
    return f"{tipo}({d})"


def _condicional(rng: random.Random) -> str:
    if rng.random() < 0.7:
        d = rng.choice(DIRECCIONES)
        if rng.random() < 0.75:
            # Ve un tanque: dispárale en esa dirección.
            arma = rng.choice(("AMT", "AMT", "MISIL"))
            return f"IF RADAR({d}) > 0 THEN {arma}({d})"
        # Hay espacio libre antes de la pared: avanza.
        return f"IF RADAR({d}) < -{rng.randint(1, 3)} THEN MOV({d})"
    vida = rng.choice((30, 40, 50, 60, 70))
    accion = rng.choice(("ESCUDO", "REPARAR", "ESCUDO"))
    return f"IF V <= {vida} THEN {accion}"


def generar_programa(lineas: Optional[int] = None,
                     semilla: Optional[int] = None) -> str:
    """Un programa válido al azar, de `lineas` instrucciones (6 a 12 si no
    se indica). Con la misma semilla sale el mismo programa."""
    rng = random.Random(semilla)
    n = lineas if lineas is not None else rng.randint(6, 12)
    texto = [_condicional(rng) if rng.random() < 0.45 else _simple(rng)
             for _ in range(max(1, n))]
    return "\n".join(texto) + "\n"
