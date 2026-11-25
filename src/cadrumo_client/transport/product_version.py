"""The installed Cadrumo version that every connection handshake states and expects."""

from __future__ import annotations

from functools import cache
from importlib.metadata import version


@cache
def installed_product_version() -> str:
    """Return the installed ``cadrumo`` distribution's version, read once per process.

    Reading distribution metadata scans every import path entry, including the
    standard library archive, and a handshake runs for each runtime and worker
    connection. The installed version cannot change while a process runs.
    Raises :class:`importlib.metadata.PackageNotFoundError` when no ``cadrumo``
    distribution is installed; a failed read is not remembered.
    """
    return version("cadrumo")
