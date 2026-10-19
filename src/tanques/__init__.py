"""Simulador de guerra de tanques en dos dimensiones.

El proyecto se organiza en cuatro capas independientes:

    lenguaje/     analiza los programas de tanque (léxico y sintáctico)
    modelo/       el dominio del juego y sus reglas
    vista/        presentación del estado de la partida
    controlador/  orquesta el modelo y la vista

Las dependencias van siempre en una sola dirección: el controlador conoce al
modelo y a la vista; el modelo no conoce a ninguno de los dos.
"""

__version__ = "0.4.0"
