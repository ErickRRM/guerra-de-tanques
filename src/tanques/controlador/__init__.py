"""Capa de controlador: orquesta el modelo y la vista."""
from .partida import cargar_programas, ejecutar, lineas_saltadas, preparar
from .torneo import Torneo, escribir_csv, formato_resumen, jugar_torneo

__all__ = ["ejecutar", "preparar", "cargar_programas", "lineas_saltadas", "Torneo", "jugar_torneo",
           "escribir_csv", "formato_resumen"]
