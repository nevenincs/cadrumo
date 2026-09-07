"""The IVA derivation refusals reach an operator in their own language.

Both refusals in the operator-initiated derive path were raw English
f-strings built from the category and the derivation note. Every other refusal
in this command family goes through ``tr``, so a Spanish, Catalan or Hungarian
operator met English at exactly the point they were being told to supply three
values by hand.

The wording is now catalogued, and these hold the two things a catalogue entry
can silently get wrong. ``tr`` does NOT raise on a missing key -- it humanises
the last dotted segment -- so an unworded locale renders English-looking text
and nothing fails. And the sentences carry placeholders naming WHICH category
was refused and WHY, so a translation that drops one leaves the operator with a
refusal they cannot act on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"

#: Each refusal and the placeholders its sentence must carry. ``note`` belongs
#: only to the non-derivable case: it is the registry's own reason, and the
#: other refusal reports a broken contract for which there is no note.
_REQUIRED_PLACEHOLDERS = {
    "derive_non_derivable": ("{category}", "{note}"),
    "derive_substrate_incomplete": ("{category}",),
}


def _classify_copy(locale: str) -> dict[str, str]:
    """The real catalogue block these keys live in."""
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in catalogue["cli"]["ledger"]["classify"].items()}


@pytest.mark.parametrize("locale", _LOCALES)
def test_both_derive_refusals_are_worded_in_this_locale(locale: str) -> None:
    """An unworded key renders a humanised token, not a translation."""
    copy = _classify_copy(locale)

    missing = [key for key in _REQUIRED_PLACEHOLDERS if not copy.get(key, "").strip()]

    assert not missing, f"{locale} has no wording for: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_each_refusal_names_what_it_refused(locale: str) -> None:
    """A refusal the operator cannot attribute is not a diagnosis.

    The category is what tells them which row to fix by hand; the note is the
    registry's own reason for declining. A translation that drops either reads
    as a complete sentence while telling them less than the English does.
    """
    copy = _classify_copy(locale)

    dropped = [
        (key, placeholder)
        for key, placeholders in _REQUIRED_PLACEHOLDERS.items()
        for placeholder in placeholders
        if placeholder not in copy.get(key, "")
    ]

    assert not dropped, f"{locale} drops: {dropped}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_each_refusal_still_names_the_flags_that_resolve_it(locale: str) -> None:
    """Both refusals end in the same remedy, and it is the only way forward.

    A non-derivable category cannot be rated for the operator, so the sentence
    has to say what to supply instead. Checked as literal flag spellings
    because those are transport tokens: a translated flag name would name a
    flag the parser does not have.
    """
    copy = _classify_copy(locale)

    for key in _REQUIRED_PLACEHOLDERS:
        sentence = copy.get(key, "")
        for flag in ("--taxable-base", "--iva-rate", "--iva-amount"):
            assert flag in sentence, f"{locale}:{key} does not name {flag}"
