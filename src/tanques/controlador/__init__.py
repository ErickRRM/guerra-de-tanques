"""Capa de controlador: orquesta el modelo y la vista."""
from .partida import ejecutar, preparar
from .torneo import Torneo, escribir_csv, formato_resumen, jugar_torneo

__all__ = ["ejecutar", "preparar", "Torneo", "jugar_torneo",
           "escribir_csv", "formato_resumen"]
