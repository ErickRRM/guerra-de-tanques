"""Configuración de la partida.

Todo parámetro que pueda cambiar durante el balanceo vive aquí y se lee de
`config.json`. Nada de esto debe quedar escrito en el código del motor: la
razón es que ajustar el equilibrio es un trabajo de prueba y error, y
recompilar mentalmente el motor en cada ajuste lo vuelve impracticable.

Los valores que el reglamento declara configurables tienen un rango
permitido (`RANGOS`); `validar()` rechaza lo que quede fuera. El daño del
misil y de la mina no se configura por separado: se deriva del de la
ametralladora (×2 y ×1.5), sin redondear.

Las decisiones de reglas que el reglamento deja abiertas se resuelven aquí
como opciones con un valor por omisión. Su justificación está en
docs/DECISIONES.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: Máximo de tanques en una partida.
MAX_TANQUES = 6

#: Usos de REPARAR por tanque y por partida. Fijo por reglamento.
REPARACIONES_POR_PARTIDA = 1

#: Multiplicadores del daño de la ametralladora.
FACTOR_MISIL = 2
FACTOR_MINA = 1.5

#: Rango (mínimo, máximo) de cada valor configurable, ambos incluidos.
RANGOS = {
    "ametralladora": (5, 20),
    "misiles": (0, 10),
    "minas": (0, 10),
    "reparar": (15, 30),
    "escudo": (5, 50),
    "rondas_armado": (0, 10),
}


class OrdenTurnos(Enum):
    """Cómo se decide el orden en que actúan los tanques dentro de la ronda.

    ROTATIVO   el orden gira una posición en cada ronda. Es el valor por
               omisión: nadie conserva la ventaja de actuar primero y el
               intervalo entre dos turnos de un mismo tanque es constante.
    ALEATORIO  se sortea en cada ronda.
    FIJO       siempre el mismo orden; el primero tiene ventaja permanente.
    """

    ROTATIVO = "rotativo"
    ALEATORIO = "aleatorio"
    FIJO = "fijo"


class AcreditaChoque(Enum):
    """A quién se le acredita el daño de un choque entre tanques."""

    EMBESTIDOR = "embestidor"   # solo el daño causado al otro
    AMBOS = "ambos"             # cada uno se anota el que causó
    NINGUNO = "ninguno"


@dataclass(frozen=True)
class Tablero:
    ancho: int = 8
    alto: int = 8


@dataclass(frozen=True)
class Dano:
    """Daño de cada fuente. Misil y mina se derivan de la ametralladora."""

    ametralladora: int = 5
    choque_tanque: int = 12
    choque_pared: int = 12

    @property
    def misil(self) -> float:
        return self.ametralladora * FACTOR_MISIL

    @property
    def mina(self) -> float:
        return self.ametralladora * FACTOR_MINA


@dataclass(frozen=True)
class Municion:
    minas: int = 3
    misiles: int = 3


@dataclass(frozen=True)
class Refaccion:
    """Lo que cura pasar sobre un tanque destruido: un entero al azar."""

    minimo: int = 15
    maximo: int = 35


@dataclass(frozen=True)
class TanqueConfig:
    nombre: str
    programa: str
    color: str = "#2E5E8C"


@dataclass(frozen=True)
class Configuracion:
    """Parámetros completos de una partida."""

    semilla: int = 42
    tablero: Tablero = field(default_factory=Tablero)
    rondas_maximas: int = 200
    vida_inicial: int = 100
    municion: Municion = field(default_factory=Municion)
    dano: Dano = field(default_factory=Dano)
    reparar_puntos: int = 20
    escudo_puntos: int = 20
    refaccion: Refaccion = field(default_factory=Refaccion)
    tanques: tuple[TanqueConfig, ...] = ()

    # --- decisiones de reglas, documentadas en docs/DECISIONES.md
    orden_turnos: OrdenTurnos = OrdenTurnos.ROTATIVO
    mina_rondas_armado: int = 0
    acredita_choque: AcreditaChoque = AcreditaChoque.EMBESTIDOR

    # ------------------------------------------------------------------
    def validar(self) -> list[str]:
        """Devuelve los problemas encontrados; vacío si todo es correcto."""
        problemas: list[str] = []
        if self.tablero.ancho < 2 or self.tablero.alto < 2:
            problemas.append("el tablero debe tener al menos 2 x 2 casillas")
        if len(self.tanques) < 1:
            problemas.append("hace falta al menos un tanque")
        if len(self.tanques) > MAX_TANQUES:
            problemas.append(f"como máximo pueden jugar {MAX_TANQUES} "
                             f"tanques")
        if len(self.tanques) > self.tablero.ancho * self.tablero.alto:
            problemas.append("hay más tanques que casillas en el tablero")
        if self.vida_inicial < 1:
            problemas.append("la vida inicial debe ser positiva")
        if self.rondas_maximas < 1:
            problemas.append("el máximo de rondas debe ser positivo")
        if self.refaccion.minimo < 0:
            problemas.append("la refacción no puede curar menos de 0")
        if self.refaccion.minimo > self.refaccion.maximo:
            problemas.append("el mínimo de la refacción supera al máximo")
        if self.dano.choque_tanque < 0 or self.dano.choque_pared < 0:
            problemas.append("el daño de un choque no puede ser negativo")
        for nombre, valor, texto in (
                ("ametralladora", self.dano.ametralladora,
                 "el daño de la ametralladora"),
                ("misiles", self.municion.misiles, "los misiles"),
                ("minas", self.municion.minas, "las minas"),
                ("reparar", self.reparar_puntos, "lo que cura REPARAR"),
                ("escudo", self.escudo_puntos, "lo que absorbe el escudo"),
                ("rondas_armado", self.mina_rondas_armado,
                 "las rondas de armado de la mina")):
            minimo, maximo = RANGOS[nombre]
            if not minimo <= valor <= maximo:
                problemas.append(f"{texto} debe estar entre {minimo} y "
                                 f"{maximo} (es {valor})")
        nombres = [t.nombre for t in self.tanques]
        if len(nombres) != len(set(nombres)):
            problemas.append("hay nombres de tanque repetidos")
        return problemas


# ---------------------------------------------------------------- lectura
def _enum(clase, valor, por_omision):
    """Convierte un texto del JSON en el enum, avisando si no es válido."""
    if valor is None:
        return por_omision
    try:
        return clase(str(valor).strip().lower())
    except ValueError:
        admitidos = ", ".join(m.value for m in clase)
        raise ValueError(
            f"{valor!r} no es un valor válido; admitidos: {admitidos}")


def desde_diccionario(datos: dict) -> Configuracion:
    """Construye la configuración a partir de un diccionario ya leído."""
    base = Configuracion()
    tab = datos.get("tablero", {})
    mun = datos.get("municion", {})
    dan = datos.get("dano", {})
    ref = datos.get("refaccion", {})
    reglas = datos.get("reglas", {})
    mina = reglas.get("mina", {})

    return Configuracion(
        semilla=datos.get("semilla", base.semilla),
        tablero=Tablero(tab.get("ancho", 8), tab.get("alto", 8)),
        rondas_maximas=datos.get("rondas_maximas", base.rondas_maximas),
        vida_inicial=datos.get("vida_inicial", base.vida_inicial),
        municion=Municion(mun.get("minas", base.municion.minas),
                          mun.get("misiles", base.municion.misiles)),
        dano=Dano(dan.get("ametralladora", base.dano.ametralladora),
                  dan.get("choque_tanque", base.dano.choque_tanque),
                  dan.get("choque_pared", base.dano.choque_pared)),
        reparar_puntos=datos.get("reparar_puntos", base.reparar_puntos),
        escudo_puntos=datos.get("escudo_puntos", base.escudo_puntos),
        refaccion=Refaccion(ref.get("minimo", base.refaccion.minimo),
                            ref.get("maximo", base.refaccion.maximo)),
        tanques=tuple(
            TanqueConfig(t["nombre"], t["programa"], t.get("color", "#2E5E8C"))
            for t in datos.get("tanques", [])),
        orden_turnos=_enum(OrdenTurnos, reglas.get("orden_turnos"),
                           OrdenTurnos.ROTATIVO),
        mina_rondas_armado=mina.get("rondas_armado",
                                    base.mina_rondas_armado),
        acredita_choque=_enum(AcreditaChoque, reglas.get("acredita_choque"),
                              AcreditaChoque.EMBESTIDOR),
    )


def cargar(ruta: str | Path) -> Configuracion:
    """Lee `config.json` y devuelve la configuración validada."""
    ruta = Path(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    config = desde_diccionario(datos)
    problemas = config.validar()
    if problemas:
        detalle = "\n".join(f"  - {p}" for p in problemas)
        raise ValueError(f"{ruta.name} tiene problemas:\n{detalle}")
    return config
