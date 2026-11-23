"""Motor de simulación: el ciclo de ronda de la Figura 4.

    Motor(config, programas, semilla)
        .paso()      -> [Evento]     ejecuta un turno
        .ronda()     -> [Evento]     ejecuta una ronda completa
        .jugar()     -> [Evento]     juega hasta el final
        .estado()    -> EstadoJuego  copia de solo lectura
        .terminada() -> bool
        .resultado() -> Resultado

Todo el azar sale de un único `random.Random(semilla)`: con la misma
semilla y los mismos programas la partida se repite turno por turno.

El motor reparte los turnos, aplica el daño y revisa minas y destrucciones;
lo que hace cada instrucción está en `acciones.py`.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from ..config import (REPARACIONES_POR_PARTIDA, AcreditaChoque,
                      Configuracion, OrdenTurnos)
from .acciones import ACCIONES
from .direccion import Direccion
from .entidades import Refaccion, Registro, Tanque
from .eventos import Evento, TipoEvento
from .tablero import Posicion, Tablero

#: Colores de reserva para tanques sin color en la configuración.
_PALETA = ("#2E5E8C", "#D97706", "#0F766E", "#6D4C9F", "#BE185D",
           "#4D7C0F")


# ------------------------------------------------------------ resultado
class Motivo(Enum):
    DESTRUCCION = "destruccion"     # quedó un solo tanque
    DESEMPATE = "desempate"         # decidió el daño infligido
    EMPATE = "empate"               # el daño infligido coincide
    TERMINADA = "terminada"         # el usuario la cerró antes; decide el
                                    # daño infligido entre los vivos


@dataclass(frozen=True)
class Resultado:
    ganador: Optional[str]
    motivo: Motivo
    rondas: int
    dano_infligido: dict[str, float]


# ------------------------------------------------------- estado público
@dataclass(frozen=True)
class EstadoTanque:
    nombre: str
    numero: int
    color: str
    posicion: Posicion
    vida: float
    vivo: bool
    escudo: float               # puntos de escudo que le quedan
    minas: int
    misiles: int
    reparaciones: int
    dano_infligido: float
    linea: int
    direccion: Direccion


@dataclass(frozen=True)
class EstadoMina:
    posicion: Posicion
    dueno: str
    armada: bool


@dataclass(frozen=True)
class EstadoJuego:
    ancho: int
    alto: int
    ronda: int
    tanques: tuple[EstadoTanque, ...]
    minas: tuple[EstadoMina, ...]
    refacciones: tuple[Posicion, ...]
    terminada: bool


# --------------------------------------------------------------- motor
class Motor:
    """Ejecuta una partida a partir de programas ya validados."""

    def __init__(self, config: Configuracion, programas: Sequence,
                 semilla: Optional[int] = None,
                 posiciones: Optional[Sequence[Posicion]] = None):
        """`programas` son objetos con `.nombre` y `.en(i)`.

        `posiciones` fija dónde empieza cada tanque en lugar de sortearlo;
        sirve para el escenario de referencia y para las pruebas.
        """
        if not programas:
            raise ValueError("hace falta al menos un programa")
        self.config = config
        self.tablero = Tablero(config.tablero.ancho, config.tablero.alto)
        self.rng = random.Random(config.semilla if semilla is None
                                 else semilla)
        self.registro = Registro()
        self.ronda_actual = 0

        self._pendientes: list[Tanque] = []
        self._eventos: list[Evento] = []
        self._resultado: Optional[Resultado] = None
        self._muertos_ultimo_turno: list[Tanque] = []

        self._colocar(programas, posiciones)
        self._inicio = self._tomar_eventos()

    # ------------------------------------------------------- arranque
    def _colocar(self, programas, posiciones):
        if len(programas) > len(self.tablero.casillas()):
            raise ValueError("hay más tanques que casillas en el tablero")
        if posiciones is None:
            posiciones = self.rng.sample(self.tablero.casillas(),
                                         len(programas))
        elif len(posiciones) != len(programas):
            raise ValueError("hace falta una posición por tanque")
        colores = {t.nombre: t.color for t in self.config.tanques}
        c = self.config
        for i, (programa, pos) in enumerate(zip(programas, posiciones)):
            if not self.tablero.dentro(*pos):
                raise ValueError(f"posición fuera del tablero: {pos}")
            tanque = Tanque(
                nombre=programa.nombre, programa=programa,
                posicion=tuple(pos), vida=c.vida_inicial,
                vida_maxima=c.vida_inicial, minas=c.municion.minas,
                misiles=c.municion.misiles,
                reparaciones=REPARACIONES_POR_PARTIDA,
                color=colores.get(programa.nombre,
                                  _PALETA[i % len(_PALETA)]),
                numero=i + 1)
            self.registro.tanques.append(tanque)
            self.emitir(TipoEvento.INICIO,
                        f"{tanque.nombre} (#{tanque.numero}) empieza en "
                        f"{tanque.posicion}", tanque,
                        posicion=tanque.posicion)
        if len({t.posicion for t in self.registro.tanques}) \
                != len(self.registro.tanques):
            raise ValueError("dos tanques no pueden empezar en la misma "
                             "casilla")

    def eventos_iniciales(self) -> list[Evento]:
        """Los eventos de colocación, emitidos al construir el motor."""
        return list(self._inicio)

    # ------------------------------------------------------- interfaz
    def terminada(self) -> bool:
        return self._resultado is not None

    @property
    def ronda_completa(self) -> bool:
        """True si ya jugaron todos los tanques de la ronda en curso."""
        return not self._pendientes

    def resultado(self) -> Optional[Resultado]:
        return self._resultado

    def paso(self) -> list[Evento]:
        """Ejecuta el turno del siguiente tanque vivo."""
        if self.terminada():
            return []
        if not self._pendientes:
            self._iniciar_ronda()
        tanque = self._pendientes.pop(0)
        self._turno(tanque)
        self._pendientes = [t for t in self._pendientes if t.vivo]
        self._comprobar_fin()
        return self._tomar_eventos()

    def terminar_ahora(self) -> list[Evento]:
        """Termina la partida tal como está, a pedido del usuario.

        Gana el tanque vivo con más daño infligido, igual que al llegar al
        límite de rondas; si coinciden, es empate. Devuelve el evento FIN.
        """
        if not self.terminada():
            vivos = self.registro.vivos() or self.registro.tanques
            mayor = max(t.dano_infligido for t in vivos)
            mejores = [t for t in vivos if t.dano_infligido == mayor]
            self._terminar(mejores[0].nombre if len(mejores) == 1 else None,
                           Motivo.TERMINADA)
        return self._tomar_eventos()

    def ronda(self) -> list[Evento]:
        """Ejecuta los turnos que faltan de la ronda en curso."""
        eventos = self.paso()
        while self._pendientes and not self.terminada():
            eventos += self.paso()
        return eventos

    def jugar(self) -> list[Evento]:
        eventos: list[Evento] = []
        while not self.terminada():
            eventos += self.paso()
        return eventos

    def estado(self) -> EstadoJuego:
        return EstadoJuego(
            ancho=self.tablero.ancho, alto=self.tablero.alto,
            ronda=self.ronda_actual,
            tanques=tuple(EstadoTanque(
                t.nombre, t.numero, t.color, t.posicion, t.vida, t.vivo,
                t.escudo, t.minas, t.misiles, t.reparaciones,
                t.dano_infligido, t.ultima_linea, t.ultima_direccion)
                for t in self.registro.tanques),
            minas=tuple(EstadoMina(m.posicion, m.dueno.nombre, m.armada)
                        for m in self.registro.minas),
            refacciones=tuple(r.posicion
                              for r in self.registro.refacciones),
            terminada=self.terminada())

    # ------------------------------------------------------- la ronda
    def _iniciar_ronda(self):
        self.ronda_actual += 1
        vivos = self.registro.vivos()
        orden = self.config.orden_turnos
        if orden is OrdenTurnos.ROTATIVO:
            # Gira sobre la lista completa para que la rotación no se
            # descoloque cuando muere un tanque.
            todos = self.registro.tanques
            k = (self.ronda_actual - 1) % len(todos)
            vivos = [t for t in todos[k:] + todos[:k] if t.vivo]
        elif orden is OrdenTurnos.ALEATORIO:
            self.rng.shuffle(vivos)
        self._pendientes = vivos
        self.emitir(TipoEvento.RONDA,
                    f"Ronda {self.ronda_actual}: "
                    + ", ".join(t.nombre for t in vivos),
                    orden=[t.nombre for t in vivos])
        self._armar_minas()

    def _turno(self, tanque: Tanque):
        tanque.llego = False
        instruccion = tanque.programa.en(tanque.contador)
        tanque.contador += 1
        tanque.ultima_linea = getattr(instruccion, "linea", 0)
        self.emitir(TipoEvento.INSTRUCCION,
                    f"{tanque.nombre} L{tanque.ultima_linea}: {instruccion}",
                    tanque, linea=tanque.ultima_linea,
                    instruccion=str(instruccion))

        self.ejecutar_instruccion(tanque, instruccion)
        tanque.turnos += 1

        self._revisar_minas(tanque)
        self._retirar_destruidos()

    def ejecutar_instruccion(self, tanque: Tanque, instruccion):
        ACCIONES[instruccion.tipo.name].ejecutar(self, tanque, instruccion)

    # ------------------------------------------------------- minas
    def _armar_minas(self):
        """Al empezar la ronda se arman las minas a las que les toca."""
        for mina in self.registro.minas:
            if not mina.armada and mina.ronda_armado <= self.ronda_actual:
                mina.armada = True
                self.emitir(TipoEvento.MINA_ARMADA,
                            f"La mina de {mina.dueno.nombre} en "
                            f"{mina.posicion} está armada", mina.dueno,
                            posicion=mina.posicion)

    def _revisar_minas(self, tanque: Tanque):
        """Una mina armada estalla cuando un tanque entra a su casilla."""
        if not tanque.vivo or not tanque.llego:
            return
        mina = self.registro.mina_en(tanque.posicion)
        if mina is None or not mina.armada:
            return
        self._detonar(mina, tanque, "pisa")

    def detonar_si_ocupada(self, mina):
        """Una mina armada que cae sobre un tanque estalla en ese momento."""
        tanque = self.registro.tanque_en(mina.posicion)
        if tanque is not None and mina.armada:
            self._detonar(mina, tanque, "recibe")

    def _detonar(self, mina, tanque: Tanque, verbo: str):
        self.registro.minas.remove(mina)
        self.emitir(TipoEvento.MINA_EXPLOTA,
                    f"{tanque.nombre} {verbo} la mina de "
                    f"{mina.dueno.nombre} en {mina.posicion}", tanque,
                    posicion=mina.posicion, dueno=mina.dueno.nombre)
        self.aplicar_dano(tanque, self.config.dano.mina, autor=mina.dueno,
                          origen="mina")

    # ------------------------------------------------------- daño
    def aplicar_dano(self, objetivo: Tanque, puntos: float,
                     autor: Optional[Tanque], origen: str,
                     acreditar: bool = True) -> float:
        """Resta el daño, primero del escudo y luego de la vida.

        Devuelve los puntos que llegaron a la vida. Solo esos se acreditan:
        lo que absorbe el escudo no cuenta para el desempate. El daño a uno
        mismo nunca se acredita: se cuenta aparte como autoinfligido, igual
        que el choque contra la pared.
        """
        absorbido = min(objetivo.escudo, puntos)
        if absorbido > 0:
            objetivo.escudo -= absorbido
            self.emitir(TipoEvento.BLOQUEO,
                        f"El escudo de {objetivo.nombre} absorbe "
                        f"{absorbido:g} puntos ({origen}); le quedan "
                        f"{objetivo.escudo:g}", objetivo, origen=origen,
                        puntos=absorbido, escudo=objetivo.escudo)
        puntos -= absorbido
        if puntos <= 0:
            return 0
        objetivo.vida -= puntos
        objetivo.dano_recibido += puntos
        if autor is None or autor is objetivo:
            objetivo.dano_autoinfligido += puntos
        elif acreditar:
            autor.dano_infligido += puntos
        self.emitir(TipoEvento.DANO,
                    f"{objetivo.nombre} recibe {puntos:g} puntos ({origen}); "
                    f"vida {max(objetivo.vida, 0):g}", objetivo,
                    puntos=puntos, origen=origen,
                    autor=autor.nombre if autor else None)
        return puntos

    def chocar(self, embestidor: Tanque, embestido: Tanque):
        """Choque entre tanques: daño a los dos, nadie cambia de casilla."""
        puntos = self.config.dano.choque_tanque
        modo = self.config.acredita_choque
        self.emitir(TipoEvento.DISPARO,
                    f"{embestidor.nombre} embiste a {embestido.nombre}",
                    embestidor, arma="choque", objetivo=embestido.nombre)
        self.aplicar_dano(embestido, puntos, autor=embestidor,
                          origen="choque",
                          acreditar=modo is not AcreditaChoque.NINGUNO)
        self.aplicar_dano(embestidor, puntos, autor=embestido,
                          origen="choque",
                          acreditar=modo is AcreditaChoque.AMBOS)

    # ------------------------------------------------------- búsquedas
    def explorar(self, tanque: Tanque, direccion: Direccion) -> int:
        """Lectura del radar: +distancia a un enemigo, −distancia a la pared.

        No ve minas ni refacciones; los tanques destruidos ya no están.
        """
        for distancia, pos in self.tablero.linea(tanque.posicion,
                                                 direccion):
            if not self.tablero.dentro(*pos):
                return -distancia
            if self.registro.tanque_en(pos) is not None:
                return distancia
        raise AssertionError("la línea siempre termina en la pared")

    def primer_tanque(self, tanque: Tanque,
                      direccion: Direccion) -> Optional[Tanque]:
        for _, pos in self.tablero.linea(tanque.posicion, direccion):
            otro = self.registro.tanque_en(pos)
            if otro is not None:
                return otro
        return None

    def recoger_refaccion(self, tanque: Tanque):
        refaccion = self.registro.refaccion_en(tanque.posicion)
        if refaccion is None:
            return
        self.registro.refacciones.remove(refaccion)
        r = self.config.refaccion
        cura = self.rng.randint(r.minimo, r.maximo)
        antes = tanque.vida
        tanque.vida = min(tanque.vida_maxima, tanque.vida + cura)
        self.emitir(TipoEvento.REFACCION,
                    f"{tanque.nombre} pasa sobre un tanque destruido y "
                    f"se repara +{tanque.vida - antes:g} "
                    f"(vida {tanque.vida:g})", tanque,
                    puntos=tanque.vida - antes, posicion=tanque.posicion)

    # ------------------------------------------------------- destrucción
    def _retirar_destruidos(self):
        self._muertos_ultimo_turno = []
        for t in self.registro.tanques:
            if t.vivo and t.vida <= 0:
                t.vivo = False
                t.vida = 0
                t.escudo = 0
                self._muertos_ultimo_turno.append(t)
                # Una sola refacción por casilla aunque ya hubiera otra.
                if self.registro.refaccion_en(t.posicion) is None:
                    self.registro.refacciones.append(Refaccion(t.posicion))
                self.emitir(TipoEvento.DESTRUCCION,
                            f"{t.nombre} es destruido en {t.posicion} y "
                            f"deja una refacción", t, posicion=t.posicion)

    # ------------------------------------------------------- término
    def _comprobar_fin(self):
        vivos = self.registro.vivos()
        varios = len(self.registro.tanques) > 1
        if varios and len(vivos) == 1:
            self._terminar(vivos[0].nombre, Motivo.DESTRUCCION)
        elif not vivos:
            # Todos cayeron en el mismo turno: desempatan los últimos.
            self._desempatar(self._muertos_ultimo_turno)
        elif (not self._pendientes and self.config.rondas_maximas
              and self.ronda_actual >= self.config.rondas_maximas):
            self._desempatar(vivos)

    def _desempatar(self, candidatos: list[Tanque]):
        mayor = max(t.dano_infligido for t in candidatos)
        mejores = [t for t in candidatos if t.dano_infligido == mayor]
        if len(mejores) == 1:
            self._terminar(mejores[0].nombre, Motivo.DESEMPATE)
        else:
            self._terminar(None, Motivo.EMPATE)

    def _terminar(self, ganador: Optional[str], motivo: Motivo):
        self._pendientes = []
        self._resultado = Resultado(
            ganador=ganador, motivo=motivo, rondas=self.ronda_actual,
            dano_infligido={t.nombre: t.dano_infligido
                            for t in self.registro.tanques})
        texto = {Motivo.DESTRUCCION: f"gana {ganador}: último en pie",
                 Motivo.DESEMPATE: f"gana {ganador} por daño infligido",
                 Motivo.EMPATE: "empate por daño infligido",
                 Motivo.TERMINADA: (
                     f"terminada en la ronda {self.ronda_actual}; "
                     + (f"gana {ganador} por daño infligido" if ganador
                        else "empate por daño infligido"))}[motivo]
        self.emitir(TipoEvento.FIN, f"Fin de la partida: {texto}",
                    ganador=ganador, motivo=motivo.value)

    # ------------------------------------------------------- eventos
    def emitir(self, tipo: TipoEvento, texto: str,
               tanque: Optional[Tanque] = None, **datos):
        self._eventos.append(Evento(self.ronda_actual, tipo, texto,
                                    tanque.nombre if tanque else None,
                                    datos))

    def _tomar_eventos(self) -> list[Evento]:
        eventos, self._eventos = self._eventos, []
        return eventos
