"""Flujo de la aplicación gráfica: menú → configuración → partida.

La vista dibuja y devuelve lo que el usuario eligió; aquí se decide qué
pasa después. Es el único lugar que junta la ventana con el motor.

Cada partida se guarda en `bitacoras/`, igual que con `jugar --bitacora`.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Configuracion
from ..lenguaje import formato_errores
from ..vista import VistaBitacora, VistaMultiple
from ..vista.bitacora import ruta_por_omision
from ..vista.grafica import AppGrafica
from .partida import ejecutar, preparar


def aplicacion(config: Configuracion, raiz: str | Path) -> int:
    raiz = Path(raiz)
    app = AppGrafica(raiz)
    try:
        while not app.cerrada:
            opcion = app.menu()
            if opcion == "ayuda":
                app.ayuda()
            elif opcion == "iniciar":
                config = _configurar_y_jugar(app, config, raiz)
            else:
                break
    finally:
        app.destruir()
    return 0


def _configurar_y_jugar(app: AppGrafica, config: Configuracion,
                        raiz: Path) -> Configuracion:
    """Repite configuración y partida hasta que el usuario vuelve al menú."""
    while not app.cerrada:
        elegida = app.configurar(config)
        if elegida is None:
            return config
        config = elegida
        if not _validar(app, config, raiz):
            continue
        accion, velocidad = "reiniciar", 5
        while accion == "reiniciar":
            accion, velocidad = _jugar(app, config, raiz, velocidad)
        if accion == "salir":
            break
    return config


def _validar(app: AppGrafica, config: Configuracion, raiz: Path) -> bool:
    _, errores = preparar(config, raiz)
    if errores:
        app.mostrar_errores(formato_errores(errores))
    return not errores


def _jugar(app, config, raiz, velocidad) -> tuple[str, int]:
    """Una partida. Devuelve lo que eligió el usuario al final."""
    motor, _ = preparar(config, raiz)
    ventana = app.partida(config, velocidad)
    bitacora = VistaBitacora(ruta_por_omision(raiz / "bitacoras",
                                              config.semilla), config)
    ejecutar(motor, VistaMultiple(ventana, bitacora))
    accion = ventana.despues()
    return accion, (ventana.velocidad.get() if accion != "salir"
                    else velocidad)
