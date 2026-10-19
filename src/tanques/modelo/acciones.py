"""Una clase por instrucción del lenguaje.

El motor no sabe qué hace cada instrucción: busca en `ACCIONES` la clase
registrada con el nombre del tipo y le delega el turno. Añadir una
instrucción es escribir una clase nueva aquí, sin tocar el motor.

Las instrucciones se reconocen por `instruccion.tipo.name` y no importando
el enum de `lenguaje/`, para que el modelo siga sin depender de ninguna otra
capa. Lo único que se espera de una instrucción son los atributos `tipo`,
`direccion`, `x`, `y`, `condicion` y `accion`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import ModoRadar
from .entidades import Mina, Tanque
from .eventos import TipoEvento

if TYPE_CHECKING:
    from .motor import Motor


class Accion:
    """Contrato de una acción: ejecuta el turno y emite sus eventos."""

    def ejecutar(self, motor: "Motor", tanque: Tanque, instruccion) -> None:
        raise NotImplementedError


ACCIONES: dict[str, Accion] = {}


def registrar(nombre: str):
    """Decorador: asocia la clase al nombre del tipo de instrucción."""
    def decorar(clase):
        ACCIONES[nombre] = clase()
        return clase
    return decorar


# ------------------------------------------------------------- movimiento
@registrar("MOV")
class Mover(Accion):
    """Avanza una casilla. Pared: 5 puntos. Tanque: choque como DAÑAR."""

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        destino = motor.tablero.vecina(tanque.posicion, d)

        if not motor.tablero.dentro(*destino):
            motor.emitir(TipoEvento.MOVIMIENTO,
                         f"{tanque.nombre} choca contra la pared al {d.name}",
                         tanque, choque="pared", direccion=d.name)
            motor.aplicar_dano(tanque, motor.config.dano.choque_pared,
                               autor=None, origen="pared",
                               bloqueable=False)
            return

        otro = motor.registro.tanque_en(destino)
        if otro is not None:
            motor.chocar(tanque, otro)
            return

        origen = tanque.posicion
        tanque.posicion = destino
        tanque.llego = True
        motor.emitir(TipoEvento.MOVIMIENTO,
                     f"{tanque.nombre} avanza al {d.name} "
                     f"{origen} -> {destino}", tanque,
                     desde=origen, hasta=destino)
        motor.recoger_refaccion(tanque)


# ------------------------------------------------------------- armamento
@registrar("AMT")
class Ametralladora(Accion):
    """10 puntos al primer tanque en la línea. Munición ilimitada."""

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        objetivo = motor.primer_tanque(tanque, d)
        if objetivo is None:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} dispara al {d.name} y no "
                         f"alcanza a nadie", tanque,
                         arma="ametralladora", direccion=d.name)
            return
        motor.emitir(TipoEvento.DISPARO,
                     f"{tanque.nombre} dispara la ametralladora al {d.name} "
                     f"contra {objetivo.nombre}", tanque,
                     arma="ametralladora", objetivo=objetivo.nombre,
                     direccion=d.name)
        motor.aplicar_dano(objetivo, motor.config.dano.ametralladora,
                           autor=tanque, origen="ametralladora")


@registrar("MISIL")
class Misil(Accion):
    """30 puntos al tanque de la casilla. Gasta munición aunque falle."""

    def ejecutar(self, motor, tanque, instruccion):
        destino = (instruccion.x, instruccion.y)
        if tanque.misiles <= 0:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no tiene misiles", tanque)
            return
        tanque.misiles -= 1
        objetivo = motor.registro.tanque_en(destino)
        if objetivo is None:
            motor.emitir(TipoEvento.DISPARO,
                         f"{tanque.nombre} lanza un misil a {destino}; "
                         f"la casilla está vacía", tanque,
                         arma="misil", destino=destino)
            return
        motor.emitir(TipoEvento.DISPARO,
                     f"{tanque.nombre} lanza un misil a {destino} "
                     f"contra {objetivo.nombre}", tanque,
                     arma="misil", destino=destino,
                     objetivo=objetivo.nombre)
        motor.aplicar_dano(objetivo, motor.config.dano.misil,
                           autor=tanque, origen="misil")


@registrar("MINA")
class ColocarMina(Accion):
    """Mina en la casilla actual. Requiere munición y casilla sin mina."""

    def ejecutar(self, motor, tanque, instruccion):
        if tanque.minas <= 0:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no tiene minas", tanque)
            return
        if motor.registro.mina_en(tanque.posicion) is not None:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no puede colocar otra mina en "
                         f"{tanque.posicion}", tanque)
            return
        tanque.minas -= 1
        mina = Mina(tanque.posicion, tanque,
                    faltan=motor.config.mina_turnos_armado,
                    ronda_colocada=motor.ronda_actual,
                    turno_colocada=tanque.turnos)
        motor.registro.minas.append(mina)
        motor.emitir(TipoEvento.MINA_COLOCADA,
                     f"{tanque.nombre} coloca una mina en {mina.posicion}",
                     tanque, posicion=mina.posicion)
        if mina.armada:
            motor.emitir(TipoEvento.MINA_ARMADA,
                         f"La mina de {tanque.nombre} en {mina.posicion} "
                         f"está armada", tanque, posicion=mina.posicion)


@registrar("DANAR")
class Embestir(Accion):
    """Embiste al tanque contiguo: 15 puntos a cada uno."""

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        otro = motor.registro.tanque_en(
            motor.tablero.vecina(tanque.posicion, d))
        if otro is None:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} embiste al {d.name} pero no hay "
                         f"nadie", tanque, direccion=d.name)
            return
        motor.chocar(tanque, otro)


# ------------------------------------------------------------- defensa
@registrar("ESCUDO")
class Escudo(Accion):
    """Inmunidad hasta el inicio del siguiente turno del tanque."""

    def ejecutar(self, motor, tanque, instruccion):
        tanque.escudo = True
        motor.emitir(TipoEvento.ESCUDO,
                     f"{tanque.nombre} activa el escudo", tanque)


@registrar("REPARAR")
class Reparar(Accion):
    """+20 de vida sin pasar del máximo. Un uso por partida.

    Con la vida al máximo no hace nada y no gasta el uso: perderlo por
    haberlo pedido antes de tiempo castigaría un programa ajeno por algo
    que no pudo prever.
    """

    def ejecutar(self, motor, tanque, instruccion):
        if tanque.reparaciones <= 0:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} ya usó su reparación", tanque)
            return
        if tanque.vida >= tanque.vida_maxima:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} tiene la vida completa; no "
                         f"repara", tanque)
            return
        tanque.reparaciones -= 1
        antes = tanque.vida
        tanque.vida = min(tanque.vida_maxima,
                          tanque.vida + motor.config.reparar_puntos)
        motor.emitir(TipoEvento.REPARACION,
                     f"{tanque.nombre} se repara +{tanque.vida - antes} "
                     f"(vida {tanque.vida})", tanque,
                     puntos=tanque.vida - antes)


# ------------------------------------------------------------- otras
@registrar("RADAR")
class Radar(Accion):
    """Mide la distancia al primer elemento y la guarda para el IF."""

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        lectura = motor.explorar(tanque, d)
        tanque.ultimo_radar = (d, lectura)
        que = "enemigo" if lectura > 0 else "pared"
        motor.emitir(TipoEvento.RADAR,
                     f"{tanque.nombre} explora al {d.name}: {que} a "
                     f"{abs(lectura)}", tanque,
                     direccion=d.name, lectura=lectura)


@registrar("ESPERAR")
class Esperar(Accion):
    def ejecutar(self, motor, tanque, instruccion):
        motor.emitir(TipoEvento.SIN_EFECTO, f"{tanque.nombre} espera",
                     tanque)


@registrar("IF")
class Si(Accion):
    """Evalúa la condición; si es falsa el turno se pierde."""

    def ejecutar(self, motor, tanque, instruccion):
        condicion = instruccion.condicion
        lectura = self._leer(motor, tanque, condicion)
        if lectura is None or not condicion.evalua(lectura):
            valor = "sin lectura" if lectura is None else lectura
            motor.emitir(TipoEvento.CONDICION_FALSA,
                         f"{tanque.nombre}: {condicion} es falso "
                         f"({valor})", tanque)
            return
        motor.ejecutar_instruccion(tanque, instruccion.accion)

    @staticmethod
    def _leer(motor, tanque, condicion):
        """Valor que se compara; None si no hay lectura que usar (D-01)."""
        if condicion.fuente.name == "VIDA":
            return tanque.vida

        d = condicion.direccion
        previa = tanque.ultimo_radar
        tiene_previa = previa is not None and previa[0] is d
        modo = motor.config.modo_radar

        if modo is ModoRadar.DIRECTO:
            return motor.explorar(tanque, d)
        if tiene_previa:
            return previa[1]
        if modo is ModoRadar.REGISTRO:
            return None
        return motor.explorar(tanque, d)          # híbrido sin lectura previa
