"""Configuración común de las pruebas."""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

# Las pruebas abren ventanas de verdad: que no suenen.
os.environ.setdefault("TANQUES_SIN_SONIDO", "1")
