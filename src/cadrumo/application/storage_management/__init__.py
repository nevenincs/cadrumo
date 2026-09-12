"""Inert namespace for storage-tree read and reclaim operations.

The ``service``, ``models``, and ``errors`` modules own inspection,
materialisation, and lifecycle-guarded reclaim. There is no relocation
operation, and the package initializer exports no symbols.

See Also:
    :data:`~cadrumo.core.STORAGE_TAXONOMY`
        The declaration every operation here reads.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
