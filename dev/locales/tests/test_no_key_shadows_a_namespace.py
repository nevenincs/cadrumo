"""No declared locale key is also the prefix of another declared key.

A dotted key and a prefix of it cannot both be leaves: the catalogue is a
mapping, so ``a.b`` is either a string or the namespace holding ``a.b.c``. The
codebase declared both ``tui.ledger.reconciliation.direction`` and
``tui.ledger.reconciliation.direction.invoice_only``, and the catalogue
resolved the conflict the only way it could -- by keeping the namespace. The
column header that read the shorter key therefore had nothing to resolve to,
every time the reconciliation table was drawn.

The parity gate reported it as one missing key among hundreds. It is worth its
own check because the shape is impossible rather than merely absent: no amount
of authoring translations fixes it, and it is invisible to any gate that only
compares key sets.
"""

from __future__ import annotations

import pytest

from .._ast_scanner import scan_source_tree
from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_no_declared_key_is_a_prefix_of_another_declared_key() -> None:
    """A key that is also a namespace can never resolve to a string."""
    keys = scan_source_tree(SRC_DIR)
    assert keys, "the scanner found no keys at all; this check would be vacuous"

    prefixes = {key.rsplit(".", 1)[0] for key in keys if "." in key}
    shadowed = sorted(keys & prefixes)

    assert not shadowed, (
        "these declared keys are also namespaces holding other declared keys, so the "
        f"catalogue cannot carry a value for them: {shadowed}"
    )
