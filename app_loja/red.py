"""Red local de la tienda: quién puede conectarse y con qué dirección.

La tienda se sirve solo a este equipo y a direcciones privadas de la red local.
El firewall de Windows es la primera barrera; esta comprobación es la segunda.
"""
from datetime import datetime
import ipaddress
import os
from pathlib import Path
import socket
import time

from . import windows_secret


def allowed_client(address, extra=()):
    """True para este equipo, redes privadas y las redes extra configuradas."""
    try:
        ip = ipaddress.ip_address((address or '').split('%')[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return True
    # IPv6 no tiene direcciones "privadas" como IPv4: un equipo de la misma red local
    # llega con una dirección global del mismo prefijo /64 que este equipo.
    if isinstance(ip, ipaddress.IPv6Address) and any(ip in network for network in local_ipv6_networks()):
        return True
    return any(ip in ipaddress.ip_network(network) for network in extra)


_ipv6_cache = (0.0, ())


def local_ipv6_networks(clock=time.monotonic):
    """Prefijos /64 de las direcciones IPv6 globales de este equipo (se renuevan cada minuto)."""
    global _ipv6_cache
    moment, networks = _ipv6_cache
    if clock() - moment < 60 and moment:
        return networks
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6):
            ip = ipaddress.ip_address(info[4][0].split('%')[0])
            if not (ip.is_loopback or ip.is_link_local):
                network = ipaddress.ip_network(f'{ip}/64', strict=False)
                if network not in found:
                    found.append(network)
    except OSError:
        pass
    _ipv6_cache = (clock(), tuple(found))
    return _ipv6_cache[1]


def keep_awake(enabled=True):
    """Mientras la tienda sirve a otros equipos, Windows no suspende este equipo por inactividad.

    Vale solo para este proceso: al cerrar la tienda, Windows vuelve a su configuración.
    """
    if os.name != 'nt':
        return False
    try:
        import ctypes
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; la pantalla puede apagarse igual.
        flags = 0x80000001 if enabled else 0x80000000
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except (OSError, AttributeError):
        return False


def access_log_path():
    return windows_secret.store_dir()/'accesos.log'


def log_access(address, method, path, status, limit=2_000_000):
    """Una línea por pedido en modo servidor: sin cuerpo, sin parámetros y sin contraseñas."""
    try:
        target = access_log_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size > limit:
            os.replace(target, Path(str(target)+'.anterior'))
        with target.open('a', encoding='utf-8') as log:
            log.write(f'{datetime.now():%Y-%m-%d %H:%M:%S} {address} {method} {path[:120]} {status}\n')
    except (OSError, ValueError):
        pass


def lan_addresses():
    """Direcciones IPv4 privadas de este equipo, para mostrar a los otros equipos."""
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            ip = ipaddress.ip_address(address)
            if ip.is_private and not ip.is_loopback and not ip.is_link_local and address not in found:
                found.append(address)
    except OSError:
        pass
    return found


def urls(port):
    """Direcciones para abrir la tienda desde otro equipo: por nombre y por IP."""
    names = [socket.gethostname(), *lan_addresses()]
    return [f'http://{name}:{port}' for name in names if name]


def _mode_file():
    return windows_secret.store_dir()/'modo.txt'


def network_mode():
    """Preferencia guardada por el asistente: servir a la red local o solo a este equipo."""
    try:
        return _mode_file().read_text(encoding='ascii').strip() == 'red'
    except (OSError, ValueError, UnicodeError):
        return False


def set_network_mode(enabled):
    path = _mode_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(str(path)+'.pending')
    pending.write_text('red\n' if enabled else 'local\n', encoding='ascii')
    os.replace(pending, path)
