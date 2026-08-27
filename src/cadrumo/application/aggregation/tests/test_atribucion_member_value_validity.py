"""Real-behavior tests: a present-but-invalid socio row is refused, not used.

The reader's completeness rule asked only whether a field was present and
non-blank. A value that was present and wrong therefore counted as usable,
and the two ways it could be wrong failed differently -- neither of them as
a diagnostic anybody could act on.

An out-of-range percentage flowed straight through. `share_pct` declares
`0..100`, and `999` was carried into the attribution calculation that
divides a taxable amount between members: a socio attributed 999% of the
base, in a filing a human submits to AEAT, with nothing raised anywhere.

A malformed percentage crashed. `abc` reached `Decimal(...)` inside the
builders and raised a bare `InvalidOperation` from the middle of a
calculation, naming neither the field nor the row.

Both now stop at the reader as a diagnostic naming the row, which is how
this module already reports an incomplete one.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._atribucion_member import (
    _decimal,
    _invalid_value_refusals,
    _missing_fields,
    _SocioFacts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _socio(share_pct: object, *, index: int = 0) -> _SocioFacts:
    return _SocioFacts(
        index=index,
        values={
            "nif": "22222222B",
            "name": "Member Two",
            "share_pct": share_pct,
            "base_imponible_assigned": Decimal("4000"),
            "clave": "D",
        },
    )


def test_an_out_of_range_share_is_refused_though_every_field_is_present() -> None:
    """The silent one: presence was the whole test, and 999% passed it.

    Asserted alongside the completeness check to pin that the two disagree
    about this row -- the row IS complete, and is still not usable. Without
    that pairing the case would pass on a reader that simply called it
    incomplete for the wrong reason.
    """
    socio = _socio(Decimal("999"))

    assert _missing_fields(socio) == frozenset()
    assert _invalid_value_refusals(socio)


def test_a_malformed_share_is_refused_before_it_can_crash_a_calculation() -> None:
    """The loud one, moved from mid-calculation to the reader's own gate."""
    assert _invalid_value_refusals(_socio("abc"))


@pytest.mark.parametrize("share_pct", [Decimal("0"), Decimal("100")])
def test_a_share_exactly_on_a_bound_stays_usable(share_pct: Decimal) -> None:
    """The refusal must not eat legitimate rows at the boundary.

    A socio holding none of an entity or all of it are ordinary filings; a
    guard that refuses them trades a silent wrong number for a silent
    missing member, which is no better.
    """
    assert _invalid_value_refusals(_socio(share_pct)) == ()


def test_a_valid_row_is_not_refused() -> None:
    """The control: without it, a rule that refused everything would pass."""
    assert _invalid_value_refusals(_socio(Decimal("40"))) == ()


def test_the_refusal_names_the_field_and_the_range() -> None:
    """A diagnostic that does not say what is wrong cannot be acted on."""
    refusals = _invalid_value_refusals(_socio(Decimal("999")))

    assert any("share_pct" in refusal and "100" in refusal for refusal in refusals)


def test_a_malformed_string_raises_the_module_s_own_error() -> None:
    """The conversion guard's message used to be dead code.

    It fired only for a wrong TYPE, while the case that actually occurs -- a
    malformed string -- bypassed it and raised a bare `InvalidOperation`
    from `Decimal`. This is the input that reaches it in practice.
    """
    with pytest.raises(ValueError, match="Decimal-compatible"):
        _decimal("abc")


def test_a_well_formed_string_still_converts() -> None:
    """The guard must catch the parse failure without refusing valid text."""
    assert _decimal(" 40 ") == Decimal("40")
