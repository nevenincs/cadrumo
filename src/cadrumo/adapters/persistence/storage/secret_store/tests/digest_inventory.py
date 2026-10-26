"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from collections.abc import Iterable

from ..store import SecretStore


def list_digests(self: SecretStore) -> Iterable[str]:
    """Yield every persisted lookup digest.

    Plaintext keys are NOT recoverable from digests by design; this
    method exists for inventory diagnostics (e.g. counting records,
    rotating store-wide).

    Returns:
        A tuple of 64-character hex digests in iteration order.
    """
    index = self._read_index()
    return tuple(index.entries.keys())
