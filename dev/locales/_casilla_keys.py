"""Identity of the delta-keyed Modelo locale leaves.

Casilla labels and help, and construct titles, are addressed through key
chains -- an edition key, then a key shared across the editions that keep the
same identity -- rather than one key per edition. Their presence is governed by
:mod:`dev.locales.modelo_casilla_catalogue`, not by key-set parity: a leaf
exists only where it holds text no less specific key already provides. The
generic scaffold and parity checks therefore neither create, prune nor compare
these leaves.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["is_delta_keyed_leaf", "is_lineage_key"]

_DELTA_KEYED_LEAF: Final = re.compile(
    r"^modelo\.schema\.[^.]+\.(?:"
    r"(?:revision\.[^.]+\.casilla\.[^.]+|casilla\.continuidad\.[^.]+)\.(?:label|help)"
    r"|(?:revision\.[^.]+\.)?construct\.[^.]+\.field\.title"
    r")$"
)
_LINEAGE_KEY: Final = re.compile(r"^modelo\.schema\.[^.]+\.(?:casilla\.continuidad|construct)\.")


def is_delta_keyed_leaf(key: str) -> bool:
    """Return whether ``key`` is a casilla label/help leaf or a construct title leaf (not an alias)."""
    return _DELTA_KEYED_LEAF.match(key) is not None


def is_lineage_key(key: str) -> bool:
    """Return whether ``key`` is the tier shared across editions rather than an edition key."""
    return _LINEAGE_KEY.match(key) is not None
