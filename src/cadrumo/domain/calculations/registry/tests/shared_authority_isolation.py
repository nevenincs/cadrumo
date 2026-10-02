"""Serve the process-shared authority from a private copy for the length of one scope.

A case that opens, releases or leaks the process-shared owner would otherwise
act on the owner the whole session shares: releasing it forces every later
test to admit a new one, and a lease left open blocks the session's own release.
The copy is a real published pair, so the owner a case exercises reads a real
generation that nothing else in the session reads.
"""

from __future__ import annotations

import contextlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

from .....core.config import override_settings
from .. import authority as authority_module
from ..authority import bundled_authority_descriptor_path, release_bundled_indexed_authority


@contextlib.contextmanager
def isolated_shared_authority(directory: Path) -> Iterator[Path]:
    """Point the shared owner at a copy of the published pair in ``directory``.

    The session's own shared owner is set aside for the scope and restored after
    it. Whatever owner the scope left open is released on the way out, so the
    copy is not held once the scope ends; a lease still held then keeps it open.

    Yields:
        The copied database, whose deletion proves on Windows that nothing holds it.
    """
    source = bundled_authority_descriptor_path()
    database = source.parent / str(json.loads(source.read_text(encoding="utf-8"))["database"])
    shutil.copy2(source, directory / source.name)
    shutil.copy2(database, directory / database.name)
    session_owner = authority_module._bundled_indexed_authority
    authority_module._bundled_indexed_authority = None
    try:
        with override_settings(cadrumo_authority_root=directory):
            yield directory / database.name
    finally:
        release_bundled_indexed_authority()
        authority_module._bundled_indexed_authority = session_owner


__all__ = ["isolated_shared_authority"]
