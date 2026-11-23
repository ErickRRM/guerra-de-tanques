"""Pruebas de los efectos de sonido sintetizados.

No se escucha nada: se revisa que los WAV salgan bien formados y que el
juego nunca falle por el sonido.
"""
import wave

from tanques.vista import sonido


def test_genera_un_wav_por_efecto(tmp_path):
    rutas = sonido.generar(tmp_path)
    assert set(rutas) == set(sonido.NOMBRES)
    for ruta in rutas.values():
        # MCI de Windows solo abre nombres en formato 8.3
        assert len(ruta.stem) <= 8
        with wave.open(str(ruta)) as w:
            assert w.getframerate() == sonido.FRECUENCIA
            assert w.getsampwidth() == 2
            # de un clic (30 ms) al ambiente de la portada (6 s)
            assert 0.02 < w.getnframes() / w.getframerate() <= 6


def test_no_regenera_lo_que_ya_existe(tmp_path):
    rutas = sonido.generar(tmp_path)
    antes = {n: r.stat().st_mtime_ns for n, r in rutas.items()}
    sonido.generar(tmp_path)
    assert {n: r.stat().st_mtime_ns for n, r in rutas.items()} == antes


class Falso:
    def __init__(self, falla=False):
        self.tocados, self.falla = [], falla

    def tocar(self, nombre, ruta):
        if self.falla:
            raise OSError("sin bocinas")
        self.tocados.append(nombre)
        return True

    def cerrar(self):
        pass


def test_toca_y_se_silencia(tmp_path, monkeypatch):
    monkeypatch.delenv("TANQUES_SIN_SONIDO", raising=False)
    falso = Falso()
    s = sonido.Sonido(tmp_path, reproductor=falso, en_segundo_plano=False)
    s.tocar("misil")
    s.tocar("no_existe")
    s.alternar_efectos()
    s.tocar("explosion")
    assert falso.tocados == ["misil"]
    s.alternar_musica()                 # la música no toca los efectos
    assert not s.musica_activa and not s.efectos


def test_si_el_reproductor_falla_calla(tmp_path, monkeypatch):
    monkeypatch.delenv("TANQUES_SIN_SONIDO", raising=False)
    s = sonido.Sonido(tmp_path, reproductor=Falso(falla=True),
                      en_segundo_plano=False)
    s.tocar("misil")                  # no lanza
    assert not s.disponible


def test_la_variable_de_entorno_lo_apaga(tmp_path, monkeypatch):
    monkeypatch.setenv("TANQUES_SIN_SONIDO", "1")
    s = sonido.Sonido(tmp_path, reproductor=Falso(), en_segundo_plano=False)
    assert not s.disponible
    s.tocar("misil")
