"""Capa de vista: presentación del estado de la partida."""
from .base import Vista, VistaMultiple
from .bitacora import VistaBitacora
from .consola import VistaConsola

__all__ = ["Vista", "VistaMultiple", "VistaBitacora", "VistaConsola"]
