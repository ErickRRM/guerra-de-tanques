#!/usr/bin/env python3
"""Punto de entrada del simulador.

Por ahora solo expone el validador de programas, que es lo único
implementado. Las órdenes `jugar` y `torneo` se añadirán junto con el motor.

    python3 main.py validar tanques/cazador.txt
    python3 main.py validar tanques/*.txt
    python3 main.py validar --config config.json tanques/cazador.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tanques.interprete import cargar, formato_errores  # noqa: E402

RAIZ = Path(__file__).resolve().parent


def lee_config(ruta: Path) -> dict:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"No se encontró {ruta}; se usa un tablero de 8 x 8.")
        return {}
    except json.JSONDecodeError as e:
        print(f"{ruta} no es un JSON válido: {e}")
        raise SystemExit(2)


def comando_validar(args) -> int:
    cfg = lee_config(Path(args.config)) if args.config else {}
    tablero = cfg.get("tablero", {})
    ancho = tablero.get("ancho", 8)
    alto = tablero.get("alto", 8)

    total_errores = 0
    for ruta in args.archivos:
        programa, errores = cargar(ruta, ancho=ancho, alto=alto)
        if errores:
            total_errores += len(errores)
            print(formato_errores(errores))
        else:
            print(f"{Path(ruta).name}: válido — {len(programa)} instrucciones")
            if args.detalle:
                for i in programa.instrucciones:
                    print(f"    L{i.linea:<3} {i}")
        print()

    if total_errores:
        print(f"Se encontraron {total_errores} errores. La partida no inicia.")
        return 1
    print("Todos los programas son válidos.")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
