"""The quantity screen's fact partition is checked, not assumed.

Each ledger family that runs the quantity screen splits its selector-fact
vocabulary in two: facts that are alternative MEASURES of one quantity (a
revision picks one and omitting the others is correct) and facts that are
INDEPENDENT quantities (omitting one loses a real amount). The screened set is
derived as the complement so the two cannot drift, and every screened fact must
declare a reader able to pull it off an observation.

Both halves used to be prose. A fact classified as independent with no reader
would have raised only for a taxpayer whose rows happened to carry it, and a
stale alternative-measure entry naming a fact the family no longer supports
would have silently excluded nothing. These tests pin the checks that make the
partition fail at registry build instead.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..ledger_bindings import (
    _IVA_ALTERNATIVE_MEASURE_FACTS,
    _IVA_INDEPENDENT_QUANTITY_FACTS,
    _IVA_SUPPORTED_FACTS,
    _RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS,
    _RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS,
)
from ..quantity_screen_enrolment import assert_quantity_readers_cover_independent_facts, independent_quantity_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_iva_family_excludes_nothing_as_an_alternative_measure() -> None:
    """Base, cuota and recargo are three independent quantities, so all three are screened.

    Stated as an assertion rather than a comment because it is the property the
    IVA adapter rests on: no one of the three stands in for another, so an empty
    exclusion set is correct here where the renta side's is deliberately not.
    """
    assert _IVA_ALTERNATIVE_MEASURE_FACTS == {}
    assert _IVA_INDEPENDENT_QUANTITY_FACTS == _IVA_SUPPORTED_FACTS
    assert (
        frozenset(
            {"base_amount_sum", "iva_amount_sum", "recargo_amount_sum"},
        )
        == _IVA_INDEPENDENT_QUANTITY_FACTS
    )


def test_the_renta_family_screens_only_the_withholding() -> None:
    """The contrast that makes the IVA empty set meaningful.

    Three renta income facts ARE alternative measures of one income, so only the
    suffered retención remains independent. If both families screened everything
    the empty IVA exclusion set would carry no information.
    """
    assert frozenset({"withheld_amount_sum"}) == _RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS


def test_every_declared_exclusion_states_its_reason() -> None:
    """The renta exclusions are declarations a reviewer can check, not bare members.

    Nothing can prove two facts measure one quantity -- that is a reading of the
    form. What is checkable is that somebody wrote down the claim, so a later
    author narrowing the screen has to state which quantity the fact re-measures
    instead of appending a member nobody has to justify.
    """
    assert set(_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS) == {
        "ingresos_integros_sum",
        "taxable_base_sum",
        "cash_received_sum",
    }
    for fact, reason in _RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS.items():
        assert reason.strip(), f"{fact} is excluded from the quantity screen with no stated reason"


def test_a_stale_alternative_measure_classification_is_refused() -> None:
    """An exclusion naming a fact the family does not support excludes nothing."""
    with pytest.raises(RegistryValidationError, match="stale"):
        independent_quantity_facts(frozenset({"a_sum"}), {"b_sum": "measures a_sum by another rule"})


def test_an_exclusion_with_no_reason_is_refused() -> None:
    """The narrowing direction no check can validate, forced into the open.

    Classifying a genuinely independent quantity as an alternative measure
    silently shrinks the screen and every other gate stays green. A blank reason
    refuses, so the edit cannot be made without writing a claim down.
    """
    with pytest.raises(RegistryValidationError, match="declare no reason"):
        independent_quantity_facts(frozenset({"a_sum", "b_sum"}), {"b_sum": "   "})


def test_a_screened_fact_with_no_reader_is_refused() -> None:
    """The partition break the import-time gate exists to catch."""
    with pytest.raises(RegistryValidationError, match="declare no reader"):
        assert_quantity_readers_cover_independent_facts(
            "test-family",
            frozenset({"a_sum", "b_sum"}),
            {"a_sum": lambda observation: Decimal("0")},
        )


def test_a_reader_for_an_unscreened_fact_is_refused() -> None:
    """The other direction: a reader nothing screens is dead and its fact misclassified."""
    with pytest.raises(RegistryValidationError, match="not screened"):
        assert_quantity_readers_cover_independent_facts(
            "test-family",
            frozenset({"a_sum"}),
            {
                "a_sum": lambda observation: Decimal("0"),
                "b_sum": lambda observation: Decimal("0"),
            },
        )
