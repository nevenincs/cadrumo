"""No committed locale leaf may be a scaffold placeholder in any namespace.

The scaffold's "no translation yet" convention writes a key's own dotted
path as its leaf value. Such a leaf passes the four-way parity gate (the
key exists everywhere) and the translation-honesty ratchet (the locales
differ from English, because each carries the same key string), yet it
renders the raw dotted key — humanised at best — to the operator in every
language. This gate closes that concealment class: a placeholder minted by
a scaffold run that raced its ``set`` pass reds CI instead of shipping.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..manager import LocaleManager, _flatten_leaf_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("ca", "en", "es", "hu")


def _self_referencing_leaves(leaves: dict[str, str]) -> list[str]:
    """Return the dotted keys whose committed value is the key itself."""
    return sorted(key for key, value in leaves.items() if value == key)


def test_committed_catalogues_carry_no_self_referencing_placeholder() -> None:
    """Every shipped leaf in every locale holds authored prose, not its key."""
    locales_dir = Path(__file__).resolve().parents[1]
    manager = LocaleManager(src_dir=locales_dir.parent, locales_dir=locales_dir)
    for locale in _LOCALES:
        leaves = _flatten_leaf_values(manager.load_locale(locales_dir / f"{locale}.yml"))
        assert _self_referencing_leaves(leaves) == [], locale


def test_detector_flags_a_synthetic_placeholder() -> None:
    """The assertion is not vacuous: a scaffold-shaped leaf is detected."""
    leaves = {
        "wizard.setup.review.title": "wizard.setup.review.title",
        "wizard.setup.review.hint": "Check every registered value.",
    }
    assert _self_referencing_leaves(leaves) == ["wizard.setup.review.title"]
