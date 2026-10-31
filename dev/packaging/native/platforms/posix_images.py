"""Recognize supported native image formats without executing them."""

from pathlib import Path

_MACHO_MAGIC = frozenset(
    {
        b"\xcf\xfa\xed\xfe",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xfe\xed\xfa\xce",
        b"\xca\xfe\xba\xbe",
        b"\xbe\xba\xfe\xca",
        b"\xca\xfe\xba\xbf",
        b"\xbf\xba\xfe\xca",
    }
)


def _magic(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    with path.open("rb") as source:
        return source.read(4)


def native_image(path: Path) -> bool:
    """Recognize supported native image containers without executing them."""
    magic = _magic(path)
    return magic is not None and (magic.startswith(b"MZ") or magic == b"\x7fELF" or magic in _MACHO_MAGIC)


def macho_image(path: Path) -> bool:
    """Recognize a thin or universal Mach-O image without executing it."""
    return _magic(path) in _MACHO_MAGIC
