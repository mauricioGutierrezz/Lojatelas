"""Red local de la tienda: quién puede conectarse y con qué dirección.

La tienda se sirve solo a este equipo y a direcciones privadas de la red local.
El firewall de Windows es la primera barrera; esta comprobación es la segunda.
"""
import ipaddress
import os
from pathlib import Path
import socket

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
    return any(ip in ipaddress.ip_network(network) for network in extra)


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
