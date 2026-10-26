"""Identity of the delta-keyed Modelo locale leaves.

Casilla labels and help, and construct titles, are addressed through key
chains -- an edition key, then a key shared across the editions that keep the
same identity -- rather than one key per edition. Their presence is governed by
:mod:`dev.locales.modelo_casilla_catalogue`, not by key-set parity: a leaf
exists only where it holds text no less specific key already provides. The
generic scaffold and parity checks therefore neither create, prune nor compare
these leaves.

Binding labels, help and printed codes are optional leaves shared by binding
identity. A binding without its own text follows its declared casilla
relationships in the form read model. Its resolution tests govern those
fallbacks and four-language coverage; scaffolding every binding would create
empty keys even where an existing casilla supplies the name.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["is_delta_keyed_leaf", "is_lineage_key"]

_DELTA_KEYED_LEAF: Final = re.compile(
    r"^modelo\.schema\.[^.]+\.(?:"
    r"(?:revision\.[^.]+\.casilla\.[^.]+|casilla\.continuidad\.[^.]+)\.(?:label|help)"
    r"|(?:revision\.[^.]+\.)?construct\.[^.]+\.field\.title"
    r"|binding\.[^.]+\.(?:label|help|box_number)"
    r")$"
)
_LINEAGE_KEY: Final = re.compile(r"^modelo\.schema\.[^.]+\.(?:casilla\.continuidad|construct)\.")


def is_delta_keyed_leaf(key: str) -> bool:
    """Whether ``key`` is optional text resolved through a schema identity or relationship chain."""
    return _DELTA_KEYED_LEAF.match(key) is not None


def is_lineage_key(key: str) -> bool:
    """Return whether ``key`` is the tier shared across editions rather than an edition key."""
    return _LINEAGE_KEY.match(key) is not None
