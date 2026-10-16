#!/usr/bin/env python3
"""Punto de entrada del simulador.

Por ahora expone el validador de programas y la revisión de la
configuración, que es lo que está implementado. Las órdenes `jugar` y
`torneo` se añadirán junto con el motor.

    python3 main.py validar tanques/cazador.txt
    python3 main.py validar tanques/*.txt --detalle
    python3 main.py config
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tanques import config as cfg          # noqa: E402
from tanques.lenguaje import Interprete, formato_errores   # noqa: E402

RAIZ = Path(__file__).resolve().parent


def _configuracion(ruta: str | None) -> cfg.Configuracion:
    """Lee la configuración; si no se puede, sigue con los valores por omisión."""
    if not ruta:
        return cfg.Configuracion()
    try:
        return cfg.cargar(ruta)
    except FileNotFoundError:
        print(f"No se encontró {ruta}; se usan los valores por omisión.\n")
        return cfg.Configuracion()
    except ValueError as e:
        print(f"Error en la configuración: {e}")
        raise SystemExit(2)


# ----------------------------------------------------------------- validar
def comando_validar(args) -> int:
    configuracion = _configuracion(args.config)
    interprete = Interprete(configuracion.tablero.ancho,
                            configuracion.tablero.alto)

    total_errores = 0
    for ruta in args.archivos:
        programa, errores = interprete.cargar(ruta)
        if errores:
            total_errores += len(errores)
            print(formato_errores(errores))
        else:
            print(f"{Path(ruta).name}: válido — {len(programa)} instrucciones")
            if args.detalle:
                for i in programa:
                    print(f"    L{i.linea:<3} {i}")
        print()

    if total_errores:
        print(f"Se encontraron {total_errores} errores. La partida no inicia.")
        return 1
    print("Todos los programas son válidos.")
    return 0


# ------------------------------------------------------------------ config
def comando_config(args) -> int:
    """Muestra la configuración tal como la entiende el programa."""
    c = _configuracion(args.config)
    print(f"Tablero            {c.tablero.ancho} x {c.tablero.alto}")
    print(f"Semilla            {c.semilla}")
    print(f"Rondas máximas     {c.rondas_maximas}")
    print(f"Vida inicial       {c.vida_inicial}")
    print(f"Restaurar          +{c.restaurar_puntos} "
          f"({c.municion.restauraciones} uso por partida)")
    print(f"Refacción          +{c.refaccion.minimo} a "
          f"+{c.refaccion.maximo} al azar")
    print()
    print("Reglas ajustables (docs/DECISIONES.md)")
    print(f"  Modo del radar   {c.modo_radar.value}")
    print(f"  Orden de turnos  {c.orden_turnos.value}")
    print(f"  Armado de mina   {c.mina_turnos_armado} "
          f"{c.mina_medida_armado.value}")
    print(f"  Daño del choque  se acredita al {c.acredita_choque.value}")
    print()
    print("Tanques")
    for t in c.tanques:
        print(f"  {t.nombre:<12} {t.programa}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="guerra-de-tanques",
        description="Simulador de guerra de tanques en dos dimensiones.")
    sub = parser.add_subparsers(dest="orden", required=True)

    v = sub.add_parser("validar",
                       help="comprueba uno o varios programas de tanque")
    v.add_argument("archivos", nargs="+", help="archivos .txt a validar")
    v.add_argument("--config", default=str(RAIZ / "config.json"),
                   help="archivo de configuración (para el tamaño del tablero)")
    v.add_argument("--detalle", action="store_true",
                   help="muestra las instrucciones reconocidas")
    v.set_defaults(func=comando_validar)

    c = sub.add_parser("config", help="muestra la configuración vigente")
    c.add_argument("--config", default=str(RAIZ / "config.json"),
                   help="archivo de configuración a revisar")
    c.set_defaults(func=comando_config)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
