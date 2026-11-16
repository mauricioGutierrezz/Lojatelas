"""Espera creciente tras intentos fallidos; no identifica personas ni guarda secretos."""
from threading import RLock
import time


class AttemptLimiter:
    """Una instancia por proceso local. El reinicio borra el conteo.

    Los primeros ``free`` fallos seguidos no esperan. Desde ahí, cada fallo
    bloquea nuevos intentos de la misma clave: 30 s, 60 s, 120 s... hasta
    ``maximum``. Un intento correcto borra el conteo.
    """

    def __init__(self, free=5, base=30, maximum=300, clock=time.monotonic):
        self.free, self.base, self.maximum, self._clock = free, base, maximum, clock
        self._state = {}
        self._lock = RLock()

    def wait_seconds(self, key):
        """Segundos que faltan para aceptar otro intento; 0 si está permitido."""
        with self._lock:
            failures, until = self._state.get(key, (0, 0))
            remaining = until - self._clock()
            return int(remaining) + 1 if remaining > 0 else 0

    def failure(self, key):
        with self._lock:
            failures = self._state.get(key, (0, 0))[0] + 1
            delay = 0
            if failures >= self.free:
                delay = min(self.base * 2 ** min(failures - self.free, 16), self.maximum)
            self._state[key] = (failures, self._clock() + delay)
            return delay

    def success(self, key):
        with self._lock:
            self._state.pop(key, None)


def wait_message(seconds):
    if seconds >= 60:
        minutes = (seconds + 59) // 60
        return f'Demasiados intentos. Esperá {minutes} minuto{"s" if minutes != 1 else ""} y volvé a intentar.'
    return f'Demasiados intentos. Esperá {seconds} segundos y volvé a intentar.'
