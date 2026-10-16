"""Configuración de la partida.

Todo parámetro que pueda cambiar durante el balanceo vive aquí y se lee de
`config.json`. Nada de esto debe quedar escrito en el código del motor: la
razón es que ajustar el equilibrio es un trabajo de prueba y error, y
recompilar mentalmente el motor en cada ajuste lo vuelve impracticable.

Las cuatro decisiones de reglas que quedaron abiertas en el diseño se
resuelven también aquí, como opciones con un valor por omisión. Su
justificación está en docs/DECISIONES.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ModoRadar(Enum):
    """Cómo obtiene su lectura la condición `IF RADAR(dir) ...`.

    HIBRIDO   usa la lectura previa en esa dirección si existe; si no,
              explora en ese momento. Es el valor por omisión porque nunca
              falla, sea cual sea la forma en que esté escrito el archivo.
    REGISTRO  solo consulta el registro; sin una lectura previa la condición
              es falsa. Obliga a gastar un turno en explorar.
    DIRECTO   siempre explora en el momento de evaluar; el RADAR suelto pasa
              a ser meramente informativo.
    """

    HIBRIDO = "hibrido"
    REGISTRO = "registro"
    DIRECTO = "directo"


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


class MedidaArmado(Enum):
    """En qué se cuentan los turnos de armado de la mina."""

    TURNOS_PROPIETARIO = "turnos_propietario"
    RONDAS = "rondas"


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
    ametralladora: int = 10
    mina: int = 25
    misil: int = 30
    choque_tanque: int = 15
    choque_pared: int = 5


@dataclass(frozen=True)
class Municion:
    minas: int = 3
    misiles: int = 3
    restauraciones: int = 1


@dataclass(frozen=True)
class Refaccion:
    minimo: int = 15
    maximo: int = 25


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
    restaurar_puntos: int = 20
    refaccion: Refaccion = field(default_factory=Refaccion)
    tanques: tuple[TanqueConfig, ...] = ()

    # --- las cuatro decisiones abiertas, documentadas en docs/DECISIONES.md
    modo_radar: ModoRadar = ModoRadar.HIBRIDO
    orden_turnos: OrdenTurnos = OrdenTurnos.ROTATIVO
    mina_turnos_armado: int = 2
    mina_medida_armado: MedidaArmado = MedidaArmado.TURNOS_PROPIETARIO
    acredita_choque: AcreditaChoque = AcreditaChoque.EMBESTIDOR

    # ------------------------------------------------------------------
    def validar(self) -> list[str]:
        """Devuelve los problemas encontrados; vacío si todo es correcto."""
        problemas: list[str] = []
        if self.tablero.ancho < 2 or self.tablero.alto < 2:
            problemas.append("el tablero debe tener al menos 2 x 2 casillas")
        if len(self.tanques) < 1:
            problemas.append("hace falta al menos un tanque")
        if len(self.tanques) > self.tablero.ancho * self.tablero.alto:
            problemas.append("hay más tanques que casillas en el tablero")
        if self.vida_inicial < 1:
            problemas.append("la vida inicial debe ser positiva")
        if self.rondas_maximas < 1:
            problemas.append("el máximo de rondas debe ser positivo")
        if self.refaccion.minimo > self.refaccion.maximo:
            problemas.append("el mínimo de la refacción supera al máximo")
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
    tab = datos.get("tablero", {})
    mun = datos.get("municion", {})
    dan = datos.get("dano", {})
    ref = datos.get("refaccion", {})
    reglas = datos.get("reglas", {})
    mina = reglas.get("mina", {})

    return Configuracion(
        semilla=datos.get("semilla", 42),
        tablero=Tablero(tab.get("ancho", 8), tab.get("alto", 8)),
        rondas_maximas=datos.get("rondas_maximas", 200),
        vida_inicial=datos.get("vida_inicial", 100),
        municion=Municion(mun.get("minas", 3), mun.get("misiles", 3),
                          mun.get("restauraciones", 1)),
        dano=Dano(dan.get("ametralladora", 10), dan.get("mina", 25),
                  dan.get("misil", 30), dan.get("choque_tanque", 15),
                  dan.get("choque_pared", 5)),
        restaurar_puntos=datos.get("restaurar_puntos", 20),
        refaccion=Refaccion(ref.get("minimo", 15), ref.get("maximo", 25)),
        tanques=tuple(
            TanqueConfig(t["nombre"], t["programa"], t.get("color", "#2E5E8C"))
            for t in datos.get("tanques", [])),
        modo_radar=_enum(ModoRadar, reglas.get("modo_radar"),
                         ModoRadar.HIBRIDO),
        orden_turnos=_enum(OrdenTurnos, reglas.get("orden_turnos"),
                           OrdenTurnos.ROTATIVO),
        mina_turnos_armado=mina.get("turnos_armado", 2),
        mina_medida_armado=_enum(MedidaArmado, mina.get("medida"),
                                 MedidaArmado.TURNOS_PROPIETARIO),
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
