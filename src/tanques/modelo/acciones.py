"""Una clase por instrucción del lenguaje.

El motor no sabe qué hace cada instrucción: busca en `ACCIONES` la clase
registrada con el nombre del tipo y le delega el turno. Añadir una
instrucción es escribir una clase nueva aquí, sin tocar el motor.

El daño no es una instrucción: es lo que provocan las armas, los choques y
las minas, y lo reparte `Motor.aplicar_dano`.

Las instrucciones se reconocen por `instruccion.tipo.name` y no importando
el enum de `lenguaje/`, para que el modelo siga sin depender de ninguna otra
capa. Lo único que se espera de una instrucción son los atributos `tipo`,
`direccion`, `direccion2`, `condicion` y `accion`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

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
    """Avanza una casilla. Contra la pared o contra un tanque, choca."""

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        destino = motor.tablero.vecina(tanque.posicion, d)

        if not motor.tablero.dentro(*destino):
            motor.emitir(TipoEvento.MOVIMIENTO,
                         f"{tanque.nombre} choca contra la pared al {d.name}",
                         tanque, choque="pared", direccion=d.name)
            motor.aplicar_dano(tanque, motor.config.dano.choque_pared,
                               autor=None, origen="pared")
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
    """Daño base al primer tanque en la línea. Munición ilimitada."""

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
    """En línea recta, como la ametralladora, con el doble de daño.

    Gasta munición aunque no alcance a nadie.
    """

    def ejecutar(self, motor, tanque, instruccion):
        d = instruccion.direccion
        tanque.ultima_direccion = d
        if tanque.misiles <= 0:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no tiene misiles", tanque)
            return
        tanque.misiles -= 1
        objetivo = motor.primer_tanque(tanque, d)
        if objetivo is None:
            motor.emitir(TipoEvento.DISPARO,
                         f"{tanque.nombre} lanza un misil al {d.name} y no "
                         f"alcanza a nadie", tanque,
                         arma="misil", direccion=d.name)
            return
        motor.emitir(TipoEvento.DISPARO,
                     f"{tanque.nombre} lanza un misil al {d.name} "
                     f"contra {objetivo.nombre}", tanque,
                     arma="misil", direccion=d.name,
                     objetivo=objetivo.nombre)
        motor.aplicar_dano(objetivo, motor.config.dano.misil,
                           autor=tanque, origen="misil")


@registrar("MINA")
class LanzarMina(Accion):
    """Lanza una mina a una esquina contigua: MINA(NE) cae en (x+1, y-1).

    Si la esquina queda fuera del tablero o ya tiene mina, no pasa nada y
    no se gasta munición. Con armado inmediato, si cae sobre un tanque
    estalla en ese momento.
    """

    def ejecutar(self, motor, tanque, instruccion):
        vertical, horizontal = instruccion.direccion, instruccion.direccion2
        x, y = tanque.posicion
        destino = (x + horizontal.dx, y + vertical.dy)
        esquina = f"{vertical.name}{horizontal.name}"
        if tanque.minas <= 0:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no tiene minas", tanque)
            return
        if not motor.tablero.dentro(*destino):
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no puede lanzar una mina al "
                         f"{esquina}: cae fuera del tablero", tanque)
            return
        if motor.registro.mina_en(destino) is not None:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} no puede lanzar otra mina a "
                         f"{destino}", tanque)
            return
        tanque.minas -= 1
        rondas = motor.config.mina_rondas_armado
        mina = Mina(destino, tanque,
                    ronda_armado=motor.ronda_actual + rondas,
                    armada=rondas <= 0)
        motor.registro.minas.append(mina)
        motor.emitir(TipoEvento.MINA_COLOCADA,
                     f"{tanque.nombre} lanza una mina al {esquina}, a "
                     f"{destino}", tanque, posicion=destino,
                     desde=tanque.posicion)
        if mina.armada:
            motor.emitir(TipoEvento.MINA_ARMADA,
                         f"La mina de {tanque.nombre} en {destino} "
                         f"está armada", tanque, posicion=destino)
            motor.detonar_si_ocupada(mina)


# ------------------------------------------------------------- defensa
@registrar("ESCUDO")
class Escudo(Accion):
    """Vida extra: absorbe daño hasta agotarse.

    Activarlo lo recarga hasta su valor configurado; no se acumula.
    """

    def ejecutar(self, motor, tanque, instruccion):
        puntos = motor.config.escudo_puntos
        if tanque.escudo >= puntos:
            motor.emitir(TipoEvento.SIN_EFECTO,
                         f"{tanque.nombre} ya tiene el escudo completo",
                         tanque)
            return
        tanque.escudo = puntos
        motor.emitir(TipoEvento.ESCUDO,
                     f"{tanque.nombre} activa el escudo ({puntos:g})",
                     tanque, puntos=puntos)


@registrar("REPARAR")
class Reparar(Accion):
    """Recupera vida sin pasar del máximo. Un uso por partida.

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
                     f"{tanque.nombre} se repara +{tanque.vida - antes:g} "
                     f"(vida {tanque.vida:g})", tanque,
                     puntos=tanque.vida - antes)


# ------------------------------------------------------------- otras
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
        if not condicion.evalua(lectura):
            motor.emitir(TipoEvento.CONDICION_FALSA,
                         f"{tanque.nombre}: {condicion} es falso "
                         f"({lectura:g})", tanque)
            return
        motor.ejecutar_instruccion(tanque, instruccion.accion)

    @staticmethod
    def _leer(motor, tanque, condicion):
        """Valor que se compara. RADAR explora en el momento de evaluar."""
        if condicion.fuente.name == "VIDA":
            return tanque.vida
        d = condicion.direccion
        tanque.ultima_direccion = d
        lectura = motor.explorar(tanque, d)
        que = "enemigo" if lectura > 0 else "pared"
        motor.emitir(TipoEvento.RADAR,
                     f"{tanque.nombre} explora al {d.name}: {que} a "
                     f"{abs(lectura)}", tanque,
                     direccion=d.name, lectura=lectura)
        return lectura
