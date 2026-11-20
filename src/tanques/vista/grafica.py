"""Interfaz gráfica con Tkinter: menú, configuración y ventana de partida.

Sigue los bosquejos de las figuras 10, 11 y 12 del documento de
arquitectura. Todo ocurre en una sola ventana que cambia de pantalla.

La ventana de partida implementa el mismo contrato `Vista` que la consola,
así que el controlador la conduce con el mismo `ejecutar()`. Para eso cada
método espera la orden del usuario con `wait_variable`, que sigue
atendiendo los eventos de Tk mientras espera: los botones, la velocidad y
el cierre de la ventana responden en todo momento.

Ninguna clase de aquí contiene reglas del juego: dibujan `EstadoJuego` y
los eventos, y devuelven lo que el usuario eligió.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import colorchooser, filedialog, font as tkfont, messagebox
from typing import Optional

from ..config import Configuracion, Tablero, TanqueConfig
from ..modelo import Direccion, Motivo, TipoEvento
from . import sprites
from .animaciones import AZUL, ROJO, VERDE, Animador
from .base import Vista

MAX_TANQUES = 4
TABLERO_PX = 520                 # lado máximo del tablero en pantalla
MARGEN_PANTALLA = 90             # barra de tareas y marco de la ventana
FONDO_VENTANA = "#FFFFFF"
FONDO_BARRA = "#ECECEC"
BORDE = "#5E5E5E"
GRIS = "#7A7A7A"
BOTON = "#E4E4E4"
_MOTIVOS = {Motivo.DESTRUCCION: "último tanque en pie",
            Motivo.DESEMPATE: "límite de rondas; decide el daño infligido",
            Motivo.EMPATE: "límite de rondas; el daño infligido coincide"}


def retardo_ms(velocidad: int) -> int:
    """Velocidad 1 (lenta) a 10 (rápida) → milisegundos entre rondas."""
    velocidad = min(10, max(1, int(velocidad)))
    return round(1200 * 0.68 ** (velocidad - 1))


#: Por debajo de este retardo (velocidades 9 y 10) no se anima: avance rápido.
RETARDO_MIN_ANIMAR = 60


def factor_animacion(retardo: int) -> float:
    """Cuánto se estiran o encogen las animaciones según la velocidad."""
    return min(2.2, max(0.45, retardo / 256))


# ======================================================================
class AppGrafica:
    """La ventana principal y la navegación entre pantallas."""

    def __init__(self, raiz: str | Path = "."):
        self.raiz = Path(raiz)
        self.root = tk.Tk()
        self.root.title("Guerra de tanques")
        self.root.configure(bg=FONDO_VENTANA)
        self.root.minsize(760, 560)
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.cerrada = False
        self._eleccion = tk.StringVar(self.root)
        self._pantalla: Optional[tk.Frame] = None
        self._partida: Optional["VentanaPartida"] = None
        self._fuentes()

    # ---------------------------------------------------------- utilidades
    def _fuentes(self):
        familias = set(tkfont.families(self.root))
        texto = next((f for f in ("Segoe UI", "Inter", "Helvetica",
                                  "DejaVu Sans") if f in familias),
                     "TkDefaultFont")
        mono = next((f for f in ("Consolas", "Cascadia Mono", "Menlo",
                                 "DejaVu Sans Mono") if f in familias),
                    "TkFixedFont")
        self.f_titulo = (texto, 26, "bold")
        self.f_barra = (texto, 15)
        self.f_seccion = (texto, 12, "bold")
        self.f_texto = (texto, 10)
        self.f_chico = (texto, 9)
        self.f_mono = (mono, 9)
        self.f_boton = (texto, 11)

    def boton(self, padre, texto, orden, ancho=14, **extra):
        return tk.Button(padre, text=texto, command=orden, width=ancho,
                         font=self.f_boton, bg=BOTON, relief="groove",
                         activebackground="#D6D6D6", bd=2, cursor="hand2",
                         **extra)

    def _nueva_pantalla(self, titulo: str) -> tk.Frame:
        if self._pantalla is not None:
            self._pantalla.destroy()
        self._pantalla = tk.Frame(self.root, bg=FONDO_VENTANA)
        self._pantalla.pack(fill="both", expand=True)
        barra = tk.Frame(self._pantalla, bg=FONDO_BARRA, height=48)
        barra.pack(fill="x")
        self.titulo_barra = tk.Label(barra, text=titulo, font=self.f_barra,
                                     bg=FONDO_BARRA, anchor="w")
        self.titulo_barra.pack(fill="x", padx=18, pady=10)
        tk.Frame(self._pantalla, bg=BORDE, height=2).pack(fill="x")
        return self._pantalla

    def _esperar(self) -> str:
        """Atiende eventos hasta que el usuario elige algo."""
        if self.cerrada:
            return "salir"
        self._eleccion.set("")
        self.root.wait_variable(self._eleccion)
        return "salir" if self.cerrada else self._eleccion.get()

    def _elegir(self, valor: str):
        self._eleccion.set(valor)

    def _al_cerrar(self):
        self.cerrada = True
        if self._partida is not None:
            self._partida.cerrar()
        self._eleccion.set("salir")

    def destruir(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------- menú
    def menu(self) -> str:
        """Figura 10. Devuelve 'iniciar', 'ayuda' o 'salir'."""
        p = self._nueva_pantalla("Guerra de tanques")
        cuerpo = tk.Frame(p, bg=FONDO_VENTANA)
        cuerpo.pack(expand=True)
        tk.Label(cuerpo, text="GUERRA DE TANQUES", font=self.f_titulo,
                 bg=FONDO_VENTANA, fg="#222222").pack(pady=(10, 4))
        tk.Label(cuerpo, text="Simulador de combate autónomo",
                 font=self.f_texto, fg=GRIS, bg=FONDO_VENTANA).pack()

        lienzo = tk.Canvas(cuerpo, width=4 * 96, height=104,
                           bg=FONDO_VENTANA, highlightthickness=0)
        lienzo.pack(pady=18)
        for i, color in enumerate(sprites.COLORES_TANQUE):
            sprites.tanque(lienzo, 48 + i * 96, 54, 88, i + 1, color)

        for texto, valor in (("Iniciar partida", "iniciar"),
                             ("¿Cómo jugar?", "ayuda"), ("Salir", "salir")):
            self.boton(cuerpo, texto, lambda v=valor: self._elegir(v),
                       ancho=22).pack(pady=6, ipady=4)
        return self._esperar()

    # ---------------------------------------------------------- ayuda
    def ayuda(self):
        ventana = tk.Toplevel(self.root, bg=FONDO_VENTANA)
        ventana.title("¿Cómo jugar?")
        ventana.geometry("640x560")
        texto = tk.Text(ventana, wrap="word", font=self.f_texto, padx=16,
                        pady=12, relief="flat", bg=FONDO_VENTANA)
        barra = tk.Scrollbar(ventana, command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(fill="both", expand=True)
        texto.tag_configure("h", font=self.f_seccion, spacing1=10,
                            spacing3=4)
        texto.tag_configure("m", font=self.f_mono)
        for estilo, linea in AYUDA:
            texto.insert("end", linea + "\n", estilo)
        texto.configure(state="disabled")
        self.boton(ventana, "Cerrar", ventana.destroy).pack(pady=8)
        ventana.transient(self.root)
        ventana.grab_set()
        self.root.wait_window(ventana)

    # ---------------------------------------------------------- configuración
    def configurar(self, config: Configuracion) -> Optional[Configuracion]:
        """Figura 11. Devuelve la configuración elegida, o None para volver."""
        pantalla = PantallaConfiguracion(self, config)
        while True:
            eleccion = self._esperar()
            if eleccion != "iniciar":
                return None
            nueva, problemas = pantalla.leer()
            if not problemas:
                return nueva
            messagebox.showerror("Configuración incompleta",
                                 "\n".join(problemas), parent=self.root)

    def mostrar_errores(self, texto: str):
        messagebox.showerror("Errores en los programas", texto,
                             parent=self.root)

    # ---------------------------------------------------------- partida
    def partida(self, config: Configuracion,
                velocidad: int = 5) -> "VentanaPartida":
        self._partida = VentanaPartida(self, config, velocidad)
        return self._partida


# ======================================================================
class PantallaConfiguracion:
    """Asocia cada tanque a un archivo y a un color; fija los parámetros."""

    def __init__(self, app: AppGrafica, config: Configuracion):
        self.app = app
        self.config = config
        p = app._nueva_pantalla(
            "Guerra de tanques  —  configuración de la partida")
        cuerpo = tk.Frame(p, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=36, pady=16)

        tk.Label(cuerpo, text="Programas de los tanques",
                 font=app.f_seccion, bg=FONDO_VENTANA).pack(anchor="w")
        tk.Label(cuerpo, text="cada tanque se asocia a un archivo de texto "
                 "y a un color fijo; deje vacía la fila de un tanque que "
                 "no participa", font=(app.f_texto[0], 10, "italic"),
                 fg=GRIS, bg=FONDO_VENTANA).pack(anchor="w", pady=(0, 8))

        self.rutas: list[tk.StringVar] = []
        self.colores: list[str] = []
        self.muestras: list[tk.Canvas] = []
        filas = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        filas.pack(fill="x")
        filas.columnconfigure(1, weight=1)
        for i in range(MAX_TANQUES):
            t = config.tanques[i] if i < len(config.tanques) else None
            self.rutas.append(tk.StringVar(app.root,
                                           t.programa if t else ""))
            self.colores.append(t.color if t else
                                sprites.COLORES_TANQUE[i])
            muestra = tk.Canvas(filas, width=30, height=30,
                                bg=FONDO_VENTANA, highlightthickness=0,
                                cursor="hand2")
            muestra.grid(row=i, column=0, padx=(0, 10), pady=5)
            muestra.bind("<Button-1>", lambda _e, k=i: self._color(k))
            self.muestras.append(muestra)
            self._pintar_muestra(i)
            tk.Entry(filas, textvariable=self.rutas[i], font=app.f_texto,
                     relief="solid", bd=1).grid(row=i, column=1,
                                                sticky="ew", ipady=4)
            app.boton(filas, "Examinar", lambda k=i: self._examinar(k),
                      ancho=10).grid(row=i, column=2, padx=(10, 6))
            app.boton(filas, "Color", lambda k=i: self._color(k),
                      ancho=8).grid(row=i, column=3)

        tk.Label(cuerpo, text="Parámetros de la partida", font=app.f_seccion,
                 bg=FONDO_VENTANA).pack(anchor="w", pady=(22, 6))
        params = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        params.pack(fill="x")
        self.ancho = tk.StringVar(app.root, str(config.tablero.ancho))
        self.alto = tk.StringVar(app.root, str(config.tablero.alto))
        self.semilla = tk.StringVar(app.root, str(config.semilla))
        self.rondas = tk.StringVar(app.root, str(config.rondas_maximas))

        def campo(columna, etiqueta, *variables):
            caja = tk.Frame(params, bg=FONDO_VENTANA)
            caja.grid(row=0, column=columna, sticky="w", padx=(0, 28))
            tk.Label(caja, text=etiqueta, font=app.f_texto, fg=GRIS,
                     bg=FONDO_VENTANA).pack(anchor="w")
            fila = tk.Frame(caja, bg=FONDO_VENTANA)
            fila.pack(anchor="w")
            for k, var in enumerate(variables):
                if k:
                    tk.Label(fila, text="×", bg=FONDO_VENTANA,
                             font=app.f_texto).pack(side="left", padx=4)
                tk.Entry(fila, textvariable=var, width=6, justify="center",
                         font=app.f_texto, relief="solid",
                         bd=1).pack(side="left", ipady=4)

        campo(0, "Tablero", self.ancho, self.alto)
        campo(1, "Semilla", self.semilla)
        campo(2, "Rondas máx.", self.rondas)

        botones = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        botones.pack(fill="x", pady=(28, 0))
        app.boton(botones, "Iniciar partida",
                  lambda: app._elegir("iniciar"),
                  ancho=18).pack(side="right", ipady=4)
        app.boton(botones, "Volver al menú", lambda: app._elegir("volver"),
                  ancho=16).pack(side="right", padx=10, ipady=4)

    # ------------------------------------------------------------------
    def _pintar_muestra(self, i):
        c = self.muestras[i]
        c.delete("all")
        c.create_oval(3, 3, 27, 27, fill=self.colores[i], outline="#5A5A5A",
                      width=1.5)
        c.create_text(15, 15, text=str(i + 1), fill="white",
                      font=(self.app.f_texto[0], 9, "bold"))

    def _color(self, i):
        _, elegido = colorchooser.askcolor(self.colores[i],
                                           parent=self.app.root,
                                           title=f"Color del tanque {i + 1}")
        if elegido:
            self.colores[i] = elegido.upper()
            self._pintar_muestra(i)

    def _examinar(self, i):
        inicial = self.app.raiz / "tanques"
        ruta = filedialog.askopenfilename(
            parent=self.app.root, title=f"Programa del tanque {i + 1}",
            initialdir=inicial if inicial.is_dir() else self.app.raiz,
            filetypes=[("Programas de tanque", "*.txt"), ("Todos", "*.*")])
        if ruta:
            ruta = Path(ruta)
            try:
                ruta = ruta.resolve().relative_to(self.app.raiz.resolve())
            except ValueError:
                pass                       # fuera del proyecto: absoluta
            self.rutas[i].set(ruta.as_posix())

    def leer(self) -> tuple[Optional[Configuracion], list[str]]:
        """Arma la configuración del formulario y la valida."""
        problemas = []

        def entero(var, nombre):
            try:
                return int(var.get().strip())
            except ValueError:
                problemas.append(f"{nombre}: «{var.get()}» no es un número "
                                 f"entero")
                return 0

        ancho = entero(self.ancho, "Ancho del tablero")
        alto = entero(self.alto, "Alto del tablero")
        semilla = entero(self.semilla, "Semilla")
        rondas = entero(self.rondas, "Rondas máximas")

        tanques, nombres = [], set()
        for var, color in zip(self.rutas, self.colores):
            ruta = var.get().strip()
            if not ruta:
                continue
            nombre, n = Path(ruta).stem, 2
            while nombre in nombres:       # dos tanques con el mismo archivo
                nombre, n = f"{Path(ruta).stem}-{n}", n + 1
            nombres.add(nombre)
            tanques.append(TanqueConfig(nombre, ruta, color))
        if problemas:
            return None, problemas

        nueva = replace(self.config, tablero=Tablero(ancho, alto),
                        semilla=semilla, rondas_maximas=rondas,
                        tanques=tuple(tanques))
        return nueva, nueva.validar()


# ======================================================================
class VentanaPartida(Vista):
    """Figura 12: tablero, panel de estado, registro y controles."""

    def __init__(self, app: AppGrafica, config: Configuracion,
                 velocidad: int = 5):
        self.app = app
        self.config = config
        self.accion: Optional[str] = None  # reiniciar | configurar | salir
        self.modo = "pausa"
        self._senal = tk.StringVar(app.root)
        self._reloj = tk.StringVar(app.root)
        self._estado = None               # lo último que se dibujó
        self._ronda_pedida = False        # «Una ronda»: no parar entre turnos
        self._numeros: dict[str, int] = {}
        self._instrucciones: dict[str, str] = {}
        self._tarjetas: dict[str, dict] = {}
        self._armar(velocidad)

    # ---------------------------------------------------------- armado
    def _armar(self, velocidad):
        app = self.app
        p = app._nueva_pantalla("Guerra de tanques")
        cuerpo = tk.Frame(p, bg=FONDO_VENTANA)
        cuerpo.pack(fill="both", expand=True, padx=24, pady=12)

        # --- izquierda: tablero y controles
        izq = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        izq.pack(side="left", fill="y")
        tk.Label(izq, text="Tablero", font=app.f_texto, fg=GRIS,
                 bg=FONDO_VENTANA).pack(anchor="w")
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        self.celda = max(24, min(TABLERO_PX // ancho, TABLERO_PX // alto,
                                 80))
        self.margen = 22                    # para los números de coordenada
        self.canvas = tk.Canvas(
            izq, width=self.margen + ancho * self.celda + 4,
            height=self.margen + alto * self.celda + 4, bg=FONDO_VENTANA,
            highlightthickness=0)
        self.canvas.pack(pady=(4, 2))
        self.leyenda = tk.Label(
            izq, text="mismo color y número que en el panel de la derecha",
            font=(app.f_texto[0], 9, "italic"), fg=GRIS, bg=FONDO_VENTANA)
        self.leyenda.pack(anchor="w")

        tk.Label(izq, text="Controles de reproducción", font=app.f_texto,
                 fg=GRIS, bg=FONDO_VENTANA).pack(anchor="w", pady=(10, 4))
        fila = tk.Frame(izq, bg=FONDO_VENTANA)
        fila.pack(anchor="w")
        self.botones = {}
        for texto, senal in (("Iniciar", "iniciar"), ("Pausar", "pausar"),
                             ("Una ronda", "una"),
                             ("Reiniciar", "reiniciar"),
                             ("Configurar", "configurar")):
            b = app.boton(fila, texto, lambda s=senal: self.senal(s),
                          ancho=9)
            b.pack(side="left", padx=(0, 6), ipady=2)
            self.botones[senal] = b

        vel = tk.Frame(izq, bg=FONDO_VENTANA)
        vel.pack(anchor="w", pady=(8, 0))
        tk.Label(vel, text="Velocidad", font=app.f_texto, fg=GRIS,
                 bg=FONDO_VENTANA).pack(side="left", padx=(0, 12))
        self.velocidad = tk.Scale(vel, from_=1, to=10, orient="horizontal",
                                  length=220, showvalue=False,
                                  bg=FONDO_VENTANA, highlightthickness=0,
                                  troughcolor="#DDDDDD")
        self.velocidad.set(velocidad)
        self.velocidad.pack(side="left")

        # --- derecha: estado de los tanques y registro
        der = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        der.pack(side="left", fill="both", expand=True, padx=(24, 0))
        tk.Label(der, text="Estado de los tanques", font=app.f_texto,
                 fg=GRIS, bg=FONDO_VENTANA).pack(anchor="w")
        self.panel = tk.Frame(der, bg=FONDO_VENTANA)
        self.panel.pack(fill="x", pady=(4, 8))

        caja = tk.Frame(der, bg="#FAFAFA", highlightbackground=BORDE,
                        highlightthickness=1)
        caja.pack(fill="both", expand=True)
        tk.Label(caja, text="Registro de la partida", font=app.f_texto,
                 fg=GRIS, bg="#FAFAFA").pack(anchor="w", padx=10,
                                             pady=(6, 0))
        self.registro = tk.Text(caja, font=app.f_mono, height=5, width=50,
                                wrap="word", relief="flat", bg="#FAFAFA",
                                padx=10, pady=4, state="disabled")
        barra = tk.Scrollbar(caja, command=self.registro.yview)
        self.registro.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.registro.pack(fill="both", expand=True)
        self.registro.tag_configure("ronda", foreground=GRIS,
                                    spacing1=6)
        self.registro.tag_configure("fin", font=app.f_seccion,
                                    spacing1=8)
        self._botones_para("pausa")

    def _ajustar_tablero(self):
        """El reporte promete 1280 x 720: el tablero cede lo que falte.

        Se mide lo que ocupa todo lo demás con las fuentes reales de este
        equipo, y el tablero se queda con el alto que sobre en la pantalla.
        """
        root = self.app.root
        root.update_idletasks()
        resto = root.winfo_reqheight() - self.canvas.winfo_reqheight()
        lado = (root.winfo_screenheight() - MARGEN_PANTALLA - resto
                - self.margen - 4)
        ancho, alto = self.config.tablero.ancho, self.config.tablero.alto
        celda = max(24, min(lado // alto, TABLERO_PX // ancho,
                            TABLERO_PX // alto, 80))
        if celda < self.celda:
            self.celda = celda
            self.canvas.configure(width=self.margen + ancho * celda + 4,
                                  height=self.margen + alto * celda + 4)

    def _tarjeta(self, t):
        """Una tarjeta del panel por tanque, como en la figura 12."""
        app = self.app
        marco = tk.Frame(self.panel, bg=FONDO_VENTANA,
                         highlightbackground=BORDE, highlightthickness=1)
        marco.pack(fill="x", pady=3)
        arriba = tk.Frame(marco, bg=FONDO_VENTANA)
        arriba.pack(fill="x", padx=10, pady=(6, 2))
        cuadro = tk.Canvas(arriba, width=18, height=18, bg=FONDO_VENTANA,
                           highlightthickness=0)
        cuadro.create_rectangle(1, 1, 17, 17, fill=t.color,
                                outline="#444444")
        cuadro.pack(side="left")
        tk.Label(arriba, text=f"Tanque {t.numero} · {t.nombre}",
                 font=app.f_seccion, bg=FONDO_VENTANA).pack(side="left",
                                                           padx=8)
        # Ancho fijo: si siguiera al texto, la ventana cambiaría de tamaño
        # en cada ronda.
        linea = tk.Label(arriba, text="", font=app.f_mono, fg=GRIS,
                         bg=FONDO_VENTANA, width=36, anchor="e")
        linea.pack(side="right")

        medio = tk.Frame(marco, bg=FONDO_VENTANA)
        medio.pack(fill="x", padx=10)
        barra = tk.Canvas(medio, height=14, width=260, bg="#E4E4E4",
                          highlightthickness=1,
                          highlightbackground="#9A9A9A")
        barra.pack(side="left", fill="x", expand=True)
        vida = tk.Label(medio, text="", width=4, anchor="e",
                        font=app.f_seccion, bg=FONDO_VENTANA)
        vida.pack(side="left", padx=(8, 0))

        datos = tk.Label(marco, text="", font=app.f_chico, fg=GRIS,
                         bg=FONDO_VENTANA, anchor="w")
        datos.pack(fill="x", padx=10, pady=(2, 6))
        return {"linea": linea, "barra": barra, "vida": vida,
                "datos": datos, "color": t.color}

    # ---------------------------------------------------------- dibujo
    def _centro(self, pos):
        s, m = self.celda, self.margen
        return m + (pos[0] - 0.5) * s, m + (pos[1] - 0.5) * s

    def dibujar(self, estado, panel: bool = True):
        c, s, m = self.canvas, self.celda, self.margen
        c.delete("all")
        for x in range(1, estado.ancho + 1):
            c.create_text(m + (x - 0.5) * s, m / 2, text=str(x),
                          font=self.app.f_chico, fill=GRIS)
        for y in range(1, estado.alto + 1):
            c.create_text(m / 2, m + (y - 0.5) * s, text=str(y),
                          font=self.app.f_chico, fill=GRIS)
        for y in range(estado.alto):
            for x in range(estado.ancho):
                fondo = (sprites.FONDO if (x + y) % 2 == 0
                         else sprites.CASILLA_ALTERNA)
                c.create_rectangle(m + x * s, m + y * s, m + (x + 1) * s,
                                   m + (y + 1) * s, fill=fondo,
                                   outline=sprites.REJILLA)
        c.create_rectangle(m, m, m + estado.ancho * s, m + estado.alto * s,
                           outline=sprites.MURO, width=3)

        centro = self._centro
        ocupadas = {t.posicion for t in estado.tanques if t.vivo}
        for pos in estado.refacciones:
            sprites.refaccion(c, *centro(pos), s, extra=(_tag(pos),))
        for mina in estado.minas:
            if mina.posicion not in ocupadas:
                sprites.mina(c, *centro(mina.posicion), s, mina.armada,
                             extra=(_tag(mina.posicion),))
        for t in estado.tanques:
            if t.vivo:
                sprites.tanque(c, *centro(t.posicion), s, t.numero, t.color,
                               t.direccion, t.escudo)
        # Una mina bajo un tanque quedaría tapada: se ve chica en la esquina.
        for mina in estado.minas:
            if mina.posicion in ocupadas:
                x, y = centro(mina.posicion)
                sprites.mina(c, x + s * 0.3, y + s * 0.3, s * 0.45,
                             mina.armada, extra=(_tag(mina.posicion),))
        if not panel:
            return

        self.app.titulo_barra.configure(
            text=f"Guerra de tanques  —  ronda {estado.ronda} de "
                 f"{self.config.rondas_maximas}")
        self._actualizar_panel(estado)

    def _actualizar_panel(self, estado):
        for t in estado.tanques:
            tarjeta = self._tarjetas[t.nombre]
            barra = tarjeta["barra"]
            barra.update_idletasks()
            largo = max(barra.winfo_width(), 260)
            barra.delete("all")
            fraccion = max(0, t.vida) / self.config.vida_inicial
            if t.vivo and fraccion > 0:
                barra.create_rectangle(0, 0, largo * min(1, fraccion), 16,
                                       fill=t.color, width=0)
            tarjeta["vida"].configure(text=str(t.vida),
                                      fg="#222222" if t.vivo else GRIS)
            instruccion = self._instrucciones.get(t.nombre)
            tarjeta["linea"].configure(
                text=(f"L{t.linea}  ·  {instruccion}" if instruccion
                      else ""))
            if t.vivo:
                escudo = "   escudo activo" if t.escudo else ""
                tarjeta["datos"].configure(
                    text=f"minas {t.minas}    misiles {t.misiles}    "
                         f"reparar {t.reparaciones}    daño infligido "
                         f"{t.dano_infligido}{escudo}")
            else:
                tarjeta["datos"].configure(
                    text=f"destruido    daño infligido {t.dano_infligido}")

    def _anotar(self, eventos):
        r = self.registro
        r.configure(state="normal")
        for e in eventos:
            if e.tipo is TipoEvento.RONDA:
                r.insert("end", f"— Ronda {e.ronda} —\n", "ronda")
            elif e.tipo is TipoEvento.INSTRUCCION:
                self._instrucciones[e.tanque] = e.datos["instruccion"]
                n = self._numeros[e.tanque]
                r.insert("end", f"T{n}  ", f"t{n}")
                r.insert("end", f"L{e.datos['linea']} "
                                f"{e.datos['instruccion']}\n")
            elif e.tipo is not TipoEvento.FIN:
                r.insert("end", f"      {e.texto}\n")
        r.configure(state="disabled")
        r.see("end")

    # ---------------------------------------------------------- contrato
    def inicio(self, estado, eventos):
        self._numeros = {t.nombre: t.numero for t in estado.tanques}
        for t in estado.tanques:
            self._tarjetas[t.nombre] = self._tarjeta(t)
            self.registro.tag_configure(f"t{t.numero}", foreground=t.color,
                                        font=(self.app.f_mono[0], 9, "bold"))
        self._ajustar_tablero()           # ya con las tarjetas puestas
        self._anotar(eventos)
        self.dibujar(estado)
        self._estado = estado
        return self._esperar_turno()

    def turno(self, estado, eventos):
        self._anotar(eventos)
        retardo = retardo_ms(self.velocidad.get())
        if retardo >= RETARDO_MIN_ANIMAR and self._estado is not None:
            self._reproducir(eventos, estado, factor_animacion(retardo))
        self.dibujar(estado)
        self._estado = estado
        return self._entre_turnos()

    def ronda(self, estado, eventos):
        # Los eventos ya se anotaron y animaron turno por turno.
        return self._esperar_turno()

    def fin(self, estado, resultado):
        self.dibujar(estado)
        self._botones_para("fin")
        if resultado is None:
            return
        if resultado.ganador is None:
            titular = "Empate"
        else:
            n = self._numeros[resultado.ganador]
            titular = f"Gana el tanque {n} · {resultado.ganador}"
        detalle = (f"{_MOTIVOS[resultado.motivo]} · "
                   f"{resultado.rondas} rondas")
        r = self.registro
        r.configure(state="normal")
        r.insert("end", f"{titular}\n", "fin")
        r.insert("end", f"{detalle}\n")
        r.configure(state="disabled")
        r.see("end")
        self._cartel(titular, detalle)

    def despues(self) -> str:
        """Tras el final, espera: 'reiniciar', 'configurar' o 'salir'."""
        while self.accion is None:
            self._esperar_senal()
        return self.accion

    # ---------------------------------------------------------- control
    def senal(self, valor: str):
        """Lo que hace cada botón; también sirve para las pruebas."""
        if valor in ("reiniciar", "configurar", "salir"):
            self.accion = valor
        elif valor == "iniciar":
            self.modo = "auto"
        elif valor == "pausar":
            self.modo = "pausa"
            self._ronda_pedida = False    # se detiene en el próximo turno
        if self.accion is None:
            self._botones_para(self.modo)
        self._senal.set(valor)

    def cerrar(self):
        self.senal("salir")

    def _esperar_senal(self) -> str:
        self._senal.set("")
        self.app.root.wait_variable(self._senal)
        return self._senal.get()

    def _esperar_turno(self) -> bool:
        """Decide cuándo se juega la siguiente ronda. False: salir."""
        while self.accion is None:
            if self.modo == "auto":
                tarea = self.app.root.after(
                    retardo_ms(self.velocidad.get()),
                    lambda: self._senal.set("tic"))
                valor = self._esperar_senal()
                self.app.root.after_cancel(tarea)
                if valor in ("tic", "una"):
                    self._ronda_pedida = True
                    return True
            elif self._esperar_senal() in ("una", "iniciar"):
                self._ronda_pedida = True
                return True
        return False

    def _entre_turnos(self) -> bool:
        """Si se pausó a media ronda, espera antes del siguiente turno."""
        while self.accion is None and self.modo == "pausa" \
                and not self._ronda_pedida:
            if self._esperar_senal() in ("una", "iniciar"):
                self._ronda_pedida = True
        return self.accion is None

    def _esperar_ms(self, ms: float) -> bool:
        """Deja pasar el tiempo de un cuadro sin congelar la ventana."""
        if self.accion is not None:
            return False
        self._reloj.set("")
        self.app.root.after(max(1, int(ms)), lambda: self._reloj.set("1"))
        self.app.root.wait_variable(self._reloj)
        return self.accion is None

    # ---------------------------------------------------------- animación
    def _crear_animador(self, factor: float) -> Animador:
        return Animador(self.canvas, self.celda, self._esperar_ms, factor)

    def _reproducir(self, eventos, despues, factor: float) -> bool:
        """Anima los eventos de un turno partiendo del estado anterior."""
        actor = next((e.tanque for e in eventos
                      if e.tipo is TipoEvento.INSTRUCCION), None)
        if actor is None:
            return True
        # El cañón gira antes de disparar: se dibuja ya con la dirección
        # nueva del tanque que juega.
        nueva = {t.nombre: t.direccion for t in despues.tanques}
        previo = replace(self._estado, tanques=tuple(
            replace(t, direccion=nueva[t.nombre]) if t.nombre == actor
            else t for t in self._estado.tanques))
        self.dibujar(previo, panel=False)

        casillas = {t.nombre: t.posicion for t in previo.tanques if t.vivo}
        a = self._crear_animador(factor)
        if actor in casillas:
            a.resaltar(self._centro(casillas[actor]))
        for e in eventos:
            if not self._animar(a, e, casillas):
                return False
        return True

    def _borde(self, casilla, d: Direccion):
        """Punto de la pared en esa dirección, desde una casilla."""
        x, y = casilla
        while self.config.tablero.ancho >= x + d.dx >= 1 \
                and self.config.tablero.alto >= y + d.dy >= 1:
            x, y = x + d.dx, y + d.dy
        cx, cy = self._centro((x, y))
        return cx + d.dx * self.celda * 0.5, cy + d.dy * self.celda * 0.5

    def _animar(self, a: Animador, e, casillas) -> bool:
        """Elige la animación de un evento. False si el usuario salió."""
        T, d, quien = TipoEvento, e.datos, e.tanque
        if quien is not None and quien not in casillas:
            return True                   # ya no está en el tablero
        aqui = self._centro(casillas[quien]) if quien else None
        tag = f"tanque{self._numeros[quien]}" if quien else None

        if e.tipo is T.MOVIMIENTO and "hasta" in d:
            casillas[quien] = d["hasta"]
            return a.deslizar(tag, aqui, self._centro(d["hasta"]))
        if e.tipo is T.MOVIMIENTO:                     # contra la pared
            pared = Direccion[d["direccion"]]
            return a.embestida(tag, aqui, self._borde(casillas[quien],
                                                      pared), alcance=0.5)
        if e.tipo is T.DISPARO and d.get("arma") == "ametralladora":
            blanco = self._centro(casillas[d["objetivo"]])
            return a.rafaga(aqui, blanco, impacto=True)
        if e.tipo is T.SIN_EFECTO and d.get("arma") == "ametralladora":
            pared = self._borde(casillas[quien], Direccion[d["direccion"]])
            return a.rafaga(aqui, pared, impacto=True)
        if e.tipo is T.DISPARO and d.get("arma") == "misil":
            destino = self._centro(d["destino"])
            return (a.misil(aqui, destino)
                    and a.explosion(destino, grande="objetivo" in d))
        if e.tipo is T.DISPARO and d.get("arma") == "choque":
            return a.embestida(tag, aqui,
                               self._centro(casillas[d["objetivo"]]))
        if e.tipo is T.DANO:
            return a.texto(aqui, f"−{d['puntos']}", ROJO)
        if e.tipo is T.BLOQUEO:
            return (a.anillo(aqui, AZUL, 0.42, 0.62, ms=260)
                    and a.texto(aqui, "bloqueado", AZUL))
        if e.tipo is T.ESCUDO:
            return a.anillo(aqui, AZUL, 0.15, 0.49, ms=380, guiones=(6, 4))
        if e.tipo in (T.REPARACION, T.REFACCION):
            if e.tipo is T.REFACCION:
                self.canvas.delete(_tag(d["posicion"]))
            return (a.anillo(aqui, VERDE, 0.2, 0.5, ms=300)
                    and a.texto(aqui, f"+{d['puntos']}", VERDE))
        if e.tipo is T.RADAR:
            return a.radar(aqui, Direccion[d["direccion"]], d["lectura"])
        if e.tipo is T.MINA_COLOCADA:
            x, y = self._centro(d["posicion"])
            esquina = (x + self.celda * 0.3, y + self.celda * 0.3)
            return a.mina_nueva((x, y), esquina, escala=0.45)
        if e.tipo is T.MINA_ARMADA:
            return a.anillo(self._centro(d["posicion"]), ROJO, 0.1, 0.4,
                            ms=300)
        if e.tipo is T.MINA_EXPLOTA:
            self.canvas.delete(_tag(d["posicion"]))
            return a.explosion(self._centro(d["posicion"]), grande=True)
        if e.tipo is T.DESTRUCCION:
            seguir = a.explosion(aqui, grande=True)
            self.canvas.delete(tag)
            del casillas[quien]
            return seguir and a.humo(aqui)
        if e.tipo is T.CONDICION_FALSA:
            return a.texto(aqui, "✗", "#8A8A8A", ms=380)
        if e.tipo is T.SIN_EFECTO:
            return a.texto(aqui, "…", "#8A8A8A", ms=380)
        return True

    def _botones_para(self, modo: str):
        activos = {"pausa": {"iniciar", "una", "reiniciar", "configurar"},
                   "auto": {"pausar", "una", "reiniciar", "configurar"},
                   "fin": {"reiniciar", "configurar"}}[modo]
        for senal, boton in self.botones.items():
            boton.configure(state="normal" if senal in activos
                            else "disabled")

    def _cartel(self, titular: str, detalle: str):
        c = self.canvas
        w, h = int(c["width"]), int(c["height"])
        c.create_rectangle(w * 0.1, h * 0.38, w * 0.9, h * 0.62,
                           fill="white", outline=sprites.MURO, width=2,
                           tags="cartel")
        c.create_text(w / 2, h * 0.46, text=titular, font=self.app.f_barra,
                      tags="cartel")
        c.create_text(w / 2, h * 0.55, text=detalle, font=self.app.f_chico,
                      fill=GRIS, tags="cartel")


def _tag(pos) -> str:
    """Etiqueta del Canvas para lo que hay en una casilla."""
    return f"en_{pos[0]}_{pos[1]}"


# ======================================================================
AYUDA = [
    ("h", "Cómo se juega"),
    ("", "Nadie controla los tanques durante la partida: cada uno ejecuta "
         "su programa, una instrucción por turno, y el usuario observa. "
         "En cada ronda juegan todos los tanques vivos; el orden gira una "
         "posición en cada ronda para que nadie conserve la ventaja de "
         "actuar primero."),
    ("", "Gana el último tanque en pie. Si se llega al límite de rondas, "
         "gana el que más daño haya infligido a sus rivales; si coincide, "
         "es empate."),
    ("h", "El programa de un tanque"),
    ("", "Un archivo de texto con una instrucción por línea. Las líneas "
         "vacías se ignoran y # marca un comentario. Al terminar el "
         "archivo, el programa vuelve a la primera línea."),
    ("m", "MOV(d)       avanza una casilla; pared: 5 de daño; tanque: choque"),
    ("m", "AMT(d)       10 al primer tanque en esa dirección"),
    ("m", "MISIL(x,y)   30 al tanque de esa casilla; tres por partida"),
    ("m", "MINA         se arma dos turnos después; 25 de daño; tres"),
    ("m", "DAÑAR(d)     embiste al tanque contiguo: 15 a cada uno"),
    ("m", "ESCUDO       inmune hasta su siguiente turno (salvo la pared)"),
    ("m", "RADAR(d)     distancia: positiva a un tanque, negativa a la pared"),
    ("m", "REPARAR      +20 de vida; una vez por partida"),
    ("m", "ESPERAR      no hace nada"),
    ("m", "IF RADAR(d) > 0 THEN AMT(d)"),
    ("m", "IF VIDA < 40 THEN REPARAR"),
    ("", "Dentro de un IF solo se admiten AMT, MISIL, ESCUDO y REPARAR. "
         "Las direcciones son N, S, E y O; las coordenadas empiezan en 1 "
         "con la fila 1 al norte."),
    ("h", "El tablero"),
    ("", "Cada tanque lleva su número y su color; el cañón apunta a la "
         "última dirección que usó. Un círculo punteado azul es el escudo. "
         "La mina roja de trazo continuo está armada; la de trazo punteado "
         "aún no. La caja verde es una refacción: la deja un tanque "
         "destruido y cura de 15 a 25 puntos a quien la pisa."),
    ("h", "Animaciones"),
    ("", "Cada turno se anima: un recuadro amarillo marca al tanque que "
         "juega; la ametralladora dispara una ráfaga; el misil sube en arco "
         "hacia la mira roja y estalla; la mina sale del tanque y se "
         "asienta; el radar lanza un haz verde que termina en un pulso rojo "
         "si encontró un tanque o gris si llegó a la pared. El daño sube en "
         "rojo (−10), la curación en verde (+20) y lo que el escudo absorbe "
         "en azul. Una ✗ gris es un IF cuya condición fue falsa."),
    ("", "Una mina bajo un tanque se ve pequeña en la esquina de su "
         "casilla. En las velocidades 9 y 10 no se anima: avance rápido."),
    ("h", "Controles"),
    ("", "Iniciar reproduce la partida sola a la velocidad elegida; Pausar "
         "la detiene en el siguiente turno; Una ronda avanza de una en una. "
         "Reiniciar vuelve a jugar la misma partida: con la misma semilla, "
         "el resultado es idéntico. Cada partida se guarda en la carpeta "
         "bitacoras/."),
]
