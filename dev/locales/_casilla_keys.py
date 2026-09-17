"""Identity of the delta-keyed Modelo casilla locale leaves.

Casilla label and help leaves are addressed through key chains, not one key per
occurrence, so their presence is governed by
:mod:`dev.locales.modelo_casilla_catalogue` rather than by key-set parity: a
leaf exists only where it holds text no less specific key already provides.
The generic scaffold and parity checks therefore neither create, prune nor
compare these leaves.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["is_casilla_key"]

_CASILLA_KEY: Final = re.compile(
    r"^modelo\.schema\.[^.]+\.(?:revision\.[^.]+\.casilla\.[^.]+|casilla\.continuidad\.[^.]+)\.(?:label|help)$"
)


def is_casilla_key(key: str) -> bool:
    """Return whether ``key`` addresses a casilla label or help leaf (not an alias)."""
    return _CASILLA_KEY.match(key) is not None
