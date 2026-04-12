"""Deterministic cache-key derivation for the status reader."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ._models import AeatStatusKind


def make_cache_key(
    *,
    tax_id: str,
    surface: AeatStatusKind,
    base_url: str = "",
    params: Mapping[str, Any] | None = None,
) -> str:
    """Return a stable 16-char hex cache key for a status fetch.

    The key is order-insensitive across ``params`` so that
    ``{"year": 2025, "since": None}`` and ``{"since": None, "year": 2025}``
    collapse to the same entry. ``None`` values are dropped before
    hashing so optional parameters do not bloat the keyspace.

    Args:
        tax_id: Spanish tax identifier for the user. Included in the
            hash so multi-tenant caches never collide.
        surface: The :class:`AeatStatusKind` being fetched.
        base_url: Configured AEAT base URL. Included in the hash so
            switching between prod / pre-prod against the same cache
            directory never serves cross-environment stale data.
        params: Optional additional query parameters.

    Returns:
        A 16-character lowercase hex string.
    """
    cleaned: dict[str, Any] = {}
    for k, v in (params or {}).items():
        if v is None:
            continue
        cleaned[k] = v.isoformat() if hasattr(v, "isoformat") else v

    payload = {
        "tax_id": tax_id,
        "surface": surface.value,
        "base_url": base_url,
        "params": cleaned,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
