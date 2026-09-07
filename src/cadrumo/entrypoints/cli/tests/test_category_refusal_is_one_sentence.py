"""An unknown `--category-id` is refused the same way whichever command took it.

``validate_category_id`` existed twice, once in the shared ledger support module
and once inside the rule command, with different wording behind different
locale keys. Both accepted and rejected the same values, so the duplication was
invisible in behaviour and plain in the operator's face: the same typo produced
one sentence from ``ledger classify`` and a different one from
``ledger rule add``.

The two were not equally good. The shared one was written against a real
observed mistake -- operators guessing compound keys like
``office:material_oficina`` -- so it demonstrates the exact shape with one
concrete id. The rule command's copy instead pasted all 42 category ids inline,
which is roughly a thousand characters of terminal output. An existing contract
test already asserted the first behaviour, but only through ``ledger classify``,
which is why the second copy could drift unnoticed.

There is one implementation now. These hold what a reader cannot see from the
call site: that every command taking the flag reaches the same refusal, and
that the refusal keeps the property it was written to have.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from ....domain.categories.spending_category import SpendingCategory
from .._ledger_rules_cli import validate_category_id as rules_validator
from .._ledger_support import validate_category_id as support_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"


def test_every_command_taking_the_flag_reaches_one_implementation() -> None:
    """The identity the duplication broke, stated as identity rather than equality.

    Two functions that merely behaved alike is exactly what was there before,
    and it drifted. Only sameness of object rules that out.
    """
    assert rules_validator is support_validator


def test_a_known_category_is_returned_unchanged() -> None:
    """The positive control: the validator admits the taxonomy it guards."""
    known = next(iter(SpendingCategory)).value

    assert support_validator(known) == known


def test_an_absent_or_blank_value_is_not_a_refusal() -> None:
    """The flag is optional, and whitespace is an operator typing nothing.

    Kept beside the refusal below so that one cannot be read as "any value the
    enum does not hold is refused" -- absence is a legitimate third answer.
    """
    assert support_validator(None) is None
    assert support_validator("   ") is None


def test_a_compound_key_is_refused_with_an_example_and_the_catalogue_verb() -> None:
    """The two properties the surviving refusal was written to have.

    The observed mistake was a family-prefixed guess, so a refusal that only
    said "unknown" would leave the operator guessing again. Asserted on the
    RENDERED message rather than the key, so a translation that drops the
    example fails here.

    The pointer to ``aeat app ledger categories`` is part of the same
    sentence. It had been promised by this validator's docstring and delivered
    by nothing -- no hint mechanism appended it and the wording did not carry
    it -- so an operator was told which shape to use but never where to read
    the 42 valid ids. Both halves are asserted here because both are the
    sentence's own content.
    """
    with pytest.raises(typer.BadParameter) as raised:
        support_validator("office:material_oficina")

    message = str(raised.value)
    assert any(category.value in message for category in SpendingCategory)
    assert "aeat app ledger categories" in message


def test_the_displaced_wording_is_gone_from_every_catalogue() -> None:
    """A key nothing reaches is a translation burden and a false choice.

    Left in place it invites the next author to reach for it, reintroducing
    the divergence this removed.
    """
    present = [
        locale
        for locale in _LOCALES
        if "invalid_category"
        in yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))["cli"]["ledger"]["errors"]
    ]

    assert not present, f"displaced category wording still catalogued in: {present}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_surviving_wording_is_present_in_this_locale(locale: str) -> None:
    """``tr`` humanises a missing key rather than raising, so absence is silent.

    The placeholders are checked too: without them the operator is told a
    category was rejected but not which, nor what a valid one looks like.
    """
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    wording = str(catalogue["cli"]["ledger"]["errors"].get("unknown_category", ""))

    assert wording.strip(), f"{locale} has no wording for an unknown category"
    # Both placeholders carry the ``!r`` conversion so the id is quoted in the
    # sentence: a bare value hides the leading or trailing space that produced
    # the typo in the first place.
    assert "{category!r}" in wording
    assert "{example!r}" in wording
    # The verb is a transport token, so it is the same literal in every
    # locale; a translated spelling would name a command the parser lacks.
    assert "aeat app ledger categories" in wording
