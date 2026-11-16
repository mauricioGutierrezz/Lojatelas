"""Búsqueda sin acentos; no modifica los nombres almacenados."""
import unicodedata


def normalize_search(value):
    return ''.join(character for character in unicodedata.normalize('NFD', value)
        if not 0x300 <= ord(character) <= 0x36f).lower()


# translate evita instalar extensiones y coincide con NFD del filtro de Precios.
# Incluye letras latinas mayúsculas: también funciona con la colación C del test.
_letters = [(chr(code), normalize_search(chr(code))) for code in range(0xc0, 0x250)]
_letters = [(letter, plain) for letter, plain in _letters
    if len(plain)==1 and plain.isascii() and plain.isalpha() and letter!=plain]
ACCENTED = ''.join(letter for letter, _ in _letters) + ''.join(chr(code) for code in range(0x300, 0x370))
PLAIN = ''.join(plain for _, plain in _letters)
