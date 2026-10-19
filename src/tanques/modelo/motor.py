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

from ..config import AcreditaChoque, Configuracion, MedidaArmado, OrdenTurnos
from .acciones import ACCIONES
from .direccion import Direccion
from .entidades import Refaccion, Registro, Tanque
from .eventos import Evento, TipoEvento
from .tablero import Posicion, Tablero

#: Colores de reserva para tanques sin color en la configuración.
_PALETA = ("#2E5E8C", "#D97706", "#0F766E", "#B91C1C")


# ------------------------------------------------------------ resultado
class Motivo(Enum):
    DESTRUCCION = "destruccion"     # quedó un solo tanque
    DESEMPATE = "desempate"         # decidió el daño infligido
    EMPATE = "empate"               # el daño infligido coincide


@dataclass(frozen=True)
class Resultado:
    ganador: Optional[str]
    motivo: Motivo
    rondas: int
    dano_infligido: dict[str, int]


# ------------------------------------------------------- estado público
@dataclass(frozen=True)
class EstadoTanque:
    nombre: str
    numero: int
    color: str
    posicion: Posicion
    vida: int
    vivo: bool
    escudo: bool
    minas: int
    misiles: int
    reparaciones: int
    dano_infligido: int
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
                reparaciones=c.municion.reparaciones,
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

    def _turno(self, tanque: Tanque):
        tanque.escudo = False                   # «hasta su siguiente turno»
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

        self._avanzar_minas_del_turno(tanque)
        self._revisar_minas(tanque)
        self._retirar_destruidos()
        if not self._pendientes:
            self._cerrar_ronda()

    def ejecutar_instruccion(self, tanque: Tanque, instruccion):
        ACCIONES[instruccion.tipo.name].ejecutar(self, tanque, instruccion)

    def _cerrar_ronda(self):
        """Armado por rondas, y minas cuyo dueño ya no juega turnos."""
        for mina in self.registro.minas:
            if mina.armada or mina.ronda_colocada == self.ronda_actual:
                continue
            por_rondas = (self.config.mina_medida_armado
                          is MedidaArmado.RONDAS)
            if por_rondas or not mina.dueno.vivo:
                self._descontar(mina)

    # ------------------------------------------------------- minas
    def _avanzar_minas_del_turno(self, tanque: Tanque):
        if self.config.mina_medida_armado is not MedidaArmado.TURNOS_PROPIETARIO:
            return
        for mina in self.registro.minas:
            if (mina.dueno is tanque and not mina.armada
                    and mina.turno_colocada < tanque.turnos - 1):
                self._descontar(mina)

    def _descontar(self, mina):
        mina.faltan -= 1
        if mina.armada:
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
        self.registro.minas.remove(mina)
        self.emitir(TipoEvento.MINA_EXPLOTA,
                    f"{tanque.nombre} pisa la mina de {mina.dueno.nombre} "
                    f"en {mina.posicion}", tanque, posicion=mina.posicion,
                    dueno=mina.dueno.nombre)
        self.aplicar_dano(tanque, self.config.dano.mina, autor=mina.dueno,
                          origen="mina")

    # ------------------------------------------------------- daño
    def aplicar_dano(self, objetivo: Tanque, puntos: int,
                     autor: Optional[Tanque], origen: str,
                     bloqueable: bool = True, acreditar: bool = True) -> int:
        """Resta vida y acredita el daño. Devuelve los puntos aplicados.

        El daño a uno mismo nunca se acredita: se cuenta aparte como
        autoinfligido, igual que el choque contra la pared.
        """
        if bloqueable and objetivo.escudo:
            self.emitir(TipoEvento.BLOQUEO,
                        f"El escudo de {objetivo.nombre} absorbe {puntos} "
                        f"puntos ({origen})", objetivo, origen=origen)
            return 0
        objetivo.vida -= puntos
        objetivo.dano_recibido += puntos
        if autor is None or autor is objetivo:
            objetivo.dano_autoinfligido += puntos
        elif acreditar:
            autor.dano_infligido += puntos
        self.emitir(TipoEvento.DANO,
                    f"{objetivo.nombre} recibe {puntos} puntos ({origen}); "
                    f"vida {max(objetivo.vida, 0)}", objetivo,
                    puntos=puntos, origen=origen,
                    autor=autor.nombre if autor else None)
        return puntos

    def chocar(self, embestidor: Tanque, embestido: Tanque):
        """Choque entre tanques: 15 a cada uno, nadie cambia de casilla."""
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
                    f"{tanque.nombre} recoge una refacción "
                    f"+{tanque.vida - antes} (vida {tanque.vida})", tanque,
                    puntos=tanque.vida - antes, posicion=tanque.posicion)

    # ------------------------------------------------------- destrucción
    def _retirar_destruidos(self):
        self._muertos_ultimo_turno = []
        for t in self.registro.tanques:
            if t.vivo and t.vida <= 0:
                t.vivo = False
                t.vida = 0
                t.escudo = False
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
        elif (not self._pendientes
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
                 Motivo.EMPATE: "empate por daño infligido"}[motivo]
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
