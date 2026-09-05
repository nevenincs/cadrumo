"""No shipped casilla label is cut off mid-phrase.

412 Modelo 200 / 2024 labels shipped with an ellipsis where the rest of the
official text should have been -- "Aume...", "Correccion temporaria con origen
en ejerc...". They passed every gate the project had, because nothing compared a
shipped label against the record design outside the small pinned set, and a
truncated label is still a non-empty string in the right key.

What made them worse than untidy is that the tail is where these labels
distinguish themselves. The Modelo 200 design names a box by a hierarchical
path, so two boxes routinely agree for a hundred characters and differ only at
the end -- an increase from a decrease, one year from the next. Cutting the tail
removes exactly the part that says which box it is.

This asserts the absence, per locale, so a re-truncation cannot ship. It says
nothing about whether a label is the RIGHT text: that is the pinned-label gate's
job, and the two are deliberately separate, because a label can be complete and
wrong or truncated and otherwise correct.
"""

from __future__ import annotations

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("es", "en", "ca", "hu")


def _labels(locale: str) -> dict[str, str]:
    path = REPO_ROOT / "src" / "cadrumo" / "locales" / locale / "modelo" / "schema" / "200.yml"
    catalogue = yaml.safe_load(path.read_text(encoding="utf-8"))
    revision = catalogue["modelo"]["schema"]["200"]["revision"]["2024"]["casilla"]
    return {casilla: entry["label"] for casilla, entry in revision.items() if entry.get("label")}


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_shipped_casilla_label_is_cut_off(locale: str) -> None:
    """An ellipsis in a label means the official text was lost, not abbreviated."""
    labels = _labels(locale)
    assert labels, f"{locale} ships no Modelo 200/2024 casilla labels at all"

    truncated = sorted(casilla for casilla, label in labels.items() if "..." in label)
    assert not truncated, (
        f"{locale} ships {len(truncated)} casilla label(s) cut off mid-phrase, first five: {truncated[:5]}"
    )
