r"""Writing a corpus file back without changing anything the run did not mean to change.

A campaign rewrite edits a handful of lines and must leave every other byte
alone, and the byte most easily changed by accident is the line ending. Python's
text layer translates ``\\n`` to the platform separator by default, so on Windows
an LF-authored fragment is rewritten to CRLF on every line: the run reports one
edited row and the diff shows the whole file. Worse, text that already carries
``\\r\\n`` is translated again into ``\\r\\r\\n``, which no reader repairs.

So the style is read off the file's own raw bytes and restored on write, and the
read-back proves it on the raw bytes rather than trusting the write: the file is
re-read, checked for ``\\r\\r\\n``, checked for the style it had, and parsed as
TOML. A file that fails any of those raises :class:`RegistryLoadError` and is
reported. Silent acceptance is the one outcome this module exists to prevent --
a corrupted fragment that nobody is told about is discovered by the next load,
long after the run that caused it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

__all__ = [
    "CRLF",
    "LF",
    "detect_newline",
    "verify_written",
    "write_preserving_newlines",
]

LF: Final = "\n"
CRLF: Final = "\r\n"

_DOUBLED_CR: Final = b"\r\r\n"


def detect_newline(raw: bytes) -> str:
    """Return the line-ending style of these bytes.

    The FIRST ending decides, because that is the style the file was authored
    in; a file mixing both is reported as whatever it opens with and its mixture
    is preserved verbatim by the write, which never translates.
    """
    index = raw.find(b"\n")
    if index == -1:
        return LF
    return CRLF if index and raw[index - 1 : index] == b"\r" else LF


def write_preserving_newlines(path: Path, text: str) -> str:
    """Write ``text`` to ``path`` in the line-ending style the file already had.

    ``text`` is expected to carry LF endings, as every reader in these tools
    produces. Returns the style written, for the read-back to check against.
    """
    style = detect_newline(path.read_bytes()) if path.exists() else LF
    body = text.replace(CRLF, LF).replace(LF, style) if style == CRLF else text.replace(CRLF, LF)
    path.write_bytes(body.encode("utf-8"))
    return style


def verify_written(path: Path, expected_newline: str, *, verify_toml: bool = True) -> None:
    """Re-read ``path`` from disk and prove the write did what it said.

    Raises :class:`RegistryLoadError` on a doubled carriage return, on a
    changed line-ending style, or on TOML the corpus loader could not parse. The
    check reads the bytes back rather than inspecting the string that was
    written, so a translating write layer cannot pass it.
    """
    raw = path.read_bytes()
    if _DOUBLED_CR in raw:
        raise RegistryLoadError(f"{path}: read back with a doubled carriage return")
    found = detect_newline(raw)
    if found != expected_newline:
        raise RegistryLoadError(f"{path}: line endings changed from {expected_newline!r} to {found!r}")
    if not verify_toml:
        return
    try:
        parse_toml(raw.decode("utf-8"))
    except (TomlDecodeError, UnicodeDecodeError) as exc:
        raise RegistryLoadError(f"{path}: read back as unparsable TOML: {exc}") from exc
