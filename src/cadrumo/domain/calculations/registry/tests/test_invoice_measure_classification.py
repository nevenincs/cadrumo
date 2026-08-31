"""The invoice family's alternative-measure classification is grounded, not asserted.

No quantity screen runs on the invoice family today; the classification in
``_invoice_bindings`` is authored ahead of one, because it is a reading of AEAT law
rather than anything derivable from the code. An unchecked declaration would rot
silently, so these tests ground it in two directions.

The load-bearing test is the MIRROR. ``base_sum`` and ``invoice_total_sum`` are
claimed to be two readings of one magnitude, which implies no modelo ever draws
both. That claim is checked against the committed registry rather than restated:
Modelo 347 declares the importe total de la operación and Modelo 349 the base of an
intra-EU supply that carries no repercutido IVA, so each draws exactly one. Either
omission read alone looks like an unrouted quantity; the symmetry is the
discriminator, and a revision that ever drew both would falsify the classification
and red this test.
"""

from __future__ import annotations

from collections import defaultdict

import pytest
from pydantic import BaseModel

from ..errors import RegistryValidationError
from ..invoice_bindings import (
    _INVOICE_ALTERNATIVE_MEASURE_FACTS,
    _INVOICE_FACTS,
    _INVOICE_INDEPENDENT_QUANTITY_FACTS,
    _INVOICE_SCALAR_MEASURE_FACTS,
)
from ..quantity_screen_enrolment import independent_quantity_facts
from ._record_design_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_INVOICE_SOURCES = {"payable_invoice", "collectible_invoice", "m347_third_party_operation"}


def _invoice_facts_by_modelo() -> dict[str, set[str]]:
    """Return, per modelo, the invoice-family facts its committed bindings declare."""
    modelos, _catalogues = _committed_registry_tree()
    drawn: dict[str, set[str]] = defaultdict(set)
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if str(binding.source) not in _INVOICE_SOURCES:
                    continue
                selector = binding.selector
                if isinstance(selector, BaseModel):
                    selector = selector.model_dump()
                else:
                    selector = {str(key): value for key, value in selector.items()}
                fact = selector.get("fact")
                if fact is not None:
                    drawn[modelo.id].add(str(fact))
    return dict(drawn)


def test_no_modelo_draws_both_magnitude_measures() -> None:
    """The alternative-measure claim, checked against the committed registry.

    Declaring ``base_sum`` and ``invoice_total_sum`` alternatives asserts that no
    revision needs both. A modelo drawing both would mean they measure different
    things, and the classification would be excluding a real quantity from any
    future screen -- the silent narrowing the reason strings exist to expose.
    """
    both = {"base_sum", "invoice_total_sum"}
    offenders = {
        modelo: sorted(facts & both) for modelo, facts in _invoice_facts_by_modelo().items() if len(facts & both) > 1
    }
    assert offenders == {}, (
        "a modelo draws BOTH invoice magnitude measures, which refutes their "
        f"classification as alternatives in _INVOICE_ALTERNATIVE_MEASURE_FACTS: {offenders}"
    )


def test_the_magnitude_measures_are_each_actually_drawn_somewhere() -> None:
    """Both classified facts are live, so the classification is not describing dead vocabulary.

    A pair of facts no revision draws would make the mirror above hold vacuously.
    """
    drawn = set().union(*_invoice_facts_by_modelo().values())
    for fact in ("base_sum", "invoice_total_sum"):
        assert fact in drawn, f"{fact!r} is classified but no committed binding draws it"


def test_the_classified_set_holds_only_scalar_money_measures() -> None:
    """``operator_count`` and ``row_field`` are deliberately unclassified.

    One counts parties and the other projects a detail-row column; neither is a
    quantity a screen could fold, so classifying either would hand a future screen
    a fact it cannot sum.
    """
    assert set(_INVOICE_FACTS) >= _INVOICE_SCALAR_MEASURE_FACTS
    assert not _INVOICE_SCALAR_MEASURE_FACTS & {"operator_count", "row_field"}


def test_the_independent_set_is_the_complement() -> None:
    """The screened set is derived, so the two halves cannot drift apart."""
    assert (
        _INVOICE_SCALAR_MEASURE_FACTS
        - set(
            _INVOICE_ALTERNATIVE_MEASURE_FACTS,
        )
        == _INVOICE_INDEPENDENT_QUANTITY_FACTS
    )
    assert {"rectified_base_delta_sum"} == _INVOICE_INDEPENDENT_QUANTITY_FACTS


def test_every_classified_fact_states_a_reason() -> None:
    """A blank reason refuses: an exclusion nobody must justify is the silent narrowing."""
    for fact, reason in _INVOICE_ALTERNATIVE_MEASURE_FACTS.items():
        assert reason.strip(), f"{fact!r} is excluded with no stated reason"

    with pytest.raises(RegistryValidationError, match="declare no reason"):
        independent_quantity_facts(_INVOICE_SCALAR_MEASURE_FACTS, {"base_sum": "   "})


def test_a_stale_classification_refuses() -> None:
    """Naming a fact outside the family's scalar set excludes nothing and must fail."""
    with pytest.raises(RegistryValidationError, match="not in the family's supported fact set"):
        independent_quantity_facts(
            _INVOICE_SCALAR_MEASURE_FACTS,
            {"operator_count": "counts parties rather than measuring money"},
        )
