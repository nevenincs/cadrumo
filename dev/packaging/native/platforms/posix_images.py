"""Recognize supported native image formats without executing them."""

from pathlib import Path


def native_image(path: Path) -> bool:
    """Recognize supported native image containers without executing them."""
    if not path.is_file():
        return False
    with path.open("rb") as source:
        magic = source.read(4)
        return magic.startswith(b"MZ") or magic in {
            b"\x7fELF",
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xce",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
        }
