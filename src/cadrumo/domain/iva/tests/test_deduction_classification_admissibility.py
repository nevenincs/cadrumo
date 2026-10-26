"""Whether a row needs a deduction classification is fact 0085's answer, not the flow's.

LIVA art. 92.Uno makes the object of a deduction a cuota that was devengada in
the territory and borne by direct repercusión. An exempt (art. 20) or not-subject
(art. 7) purchase raises no such cuota, so there is no deduction fact on it to
classify, and the deduction applicability catalogue accordingly admits no kind
for those categories.

Keyed on the flow direction alone the requirement was unsatisfiable, because
every received operation settles as ``soportado`` whatever it is: no kind met the
requirement and every kind failed admissibility, so an exempt insurance premium
and an out-of-scope RETA quota were representable in no form at all.

The last test is the teeth: it derives both answers from the registry for every
declared category and flow and asserts they agree. A hand-kept list of admitting
categories would pass every case above and diverge here the first time fact 0085
moved a category between families.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ...calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...calculations.registry.iva_deduction_catalogue import (
    iva_deduction_fact_kinds,
    resolve_iva_deduction_catalogue,
)
from ...calculations.registry.iva_flow_catalogue import resolve_iva_flow_direction_catalogue
from ..deduction_facts import (
    IvaDeductionClassificationProvenance,
    admits_iva_deduction_classification,
    required_deduction_evidence_authority,
    validate_iva_deduction_fact,
)
from ..errors import IvaValidationError
from ..flow import IvaFlowDirection, issued_flow_direction, received_flow_direction
from ..schema import IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_EVIDENCE_DIGEST = "a" * 64
_INVESTMENT_ASSET_ID = "BI-TEST-01"

#: Kinds whose own contract adds requirements orthogonal to the family table.
#:
#: A rectification needs a rectified ledger identity and signed non-zero
#: evidence; the regularisation kind is emitted by the bienes-inversion owner and
#: never by a ledger row. Neither tells us anything about which categories bear a
#: deduction, which is the axis under test.
_KINDS_OUTSIDE_THE_FAMILY_TABLE = frozenset({"rectification", "investment_goods_regularisation"})


@pytest.mark.parametrize(
    "category",
    ["domestic_general", "domestic_reduced", "domestic_super_reduced", "domestic_zero"],
)
def test_a_taxable_domestic_purchase_bears_a_deduction_to_classify(category: str) -> None:
    """The positive path, including the 0 % tipo: sujeta y no exenta, so art. 92 reaches it."""
    assert admits_iva_deduction_classification(
        category=IvaCategory(category),
        flow_direction=received_flow_direction(),
    )


@pytest.mark.parametrize(
    "category",
    ["domestic_exempt", "domestic_not_subject", "operacion_no_sujeta", "recargo_equivalencia"],
)
def test_a_purchase_that_raised_no_cuota_bears_none(category: str) -> None:
    """The rows that deadlocked: no cuota was repercutida, so nothing is deductible."""
    assert not admits_iva_deduction_classification(
        category=IvaCategory(category),
        flow_direction=received_flow_direction(),
    )


def test_the_reagp_compensation_keeps_its_deduction() -> None:
    """A zero-cuota category is not automatically outside the table.

    LIVA art. 134 makes the compensación a tanto alzado deductible, and fact 0085
    declares its own family for it. Reading "no cuota arises" off the component
    table instead of asking fact 0085 would have exempted this row from the
    requirement and lost the deduction silently.
    """
    assert admits_iva_deduction_classification(
        category=IvaCategory("reagp_compensation"),
        flow_direction=received_flow_direction(),
    )


def test_an_output_row_bears_no_deduction() -> None:
    """A sale repercutes its cuota onward; the customer deducts it, not the filer."""
    assert not admits_iva_deduction_classification(
        category=IvaCategory("domestic_general"),
        flow_direction=issued_flow_direction(),
    )


def _declared_kinds() -> tuple[IvaDeductionFactKind, ...]:
    return tuple(kind for kind in iva_deduction_fact_kinds() if kind.value not in _KINDS_OUTSIDE_THE_FAMILY_TABLE)


def _kind_validates(
    kind: IvaDeductionFactKind,
    *,
    category: IvaCategory,
    flow_direction: IvaFlowDirection,
) -> bool:
    """Return whether the pairing validator accepts ``kind`` on this row.

    Every requirement the validator makes outside the family table is satisfied
    here: the evidence authority fact 0085 declares for the kind, the reciprocal
    asset identity an investment kind needs, and both rate tiers a zero-cuota
    family might pin. What remains to fail is the category/flow pairing alone.
    """
    provenance = IvaDeductionClassificationProvenance(
        authority=required_deduction_evidence_authority(kind),
        source_locator=f"evidence:{kind.value}",
        evidence_digest=_EVIDENCE_DIGEST,
    )
    investment_asset_id = (
        _INVESTMENT_ASSET_ID
        if kind in resolve_iva_deduction_catalogue().projection("kind.investment_acquisition")
        else None
    )
    for rate_kind in (IvaRateKind("general"), IvaRateKind("exempt")):
        try:
            validate_iva_deduction_fact(
                kind=kind,
                provenance=provenance,
                category=category,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
                investment_asset_id=investment_asset_id,
                rectifies_ledger_id=None,
            )
        except IvaValidationError:
            continue
        return True
    return False


def test_the_predicate_and_the_validator_answer_the_same_registry() -> None:
    """Teeth: one reading cannot drift from the other without this failing.

    Both sides are derived from the live catalogues rather than listed, over every
    declared category and flow. The gate matters because the two are consulted at
    opposite ends of one decision: this predicate decides whether a
    classification is DEMANDED, the validator decides whether the one supplied is
    admissible. A category the predicate demands a classification for and the
    validator refuses every kind on is a row the operator cannot make filable --
    which is the defect these tests exist for -- and the reverse silently drops
    an input deduction the law grants.
    """
    kinds = _declared_kinds()
    assert kinds, "fact 0085 declares no operator-facing deduction kinds"
    flows = resolve_iva_flow_direction_catalogue().choices
    categories = resolve_iva_category_catalogue().all_categories

    disagreeing = [
        (category.value, flow.value)
        for category in categories
        for flow in flows
        if admits_iva_deduction_classification(category=category, flow_direction=flow)
        != any(_kind_validates(kind, category=category, flow_direction=flow) for kind in kinds)
    ]

    assert not disagreeing, (
        "the deduction-requirement predicate and the pairing validator disagree about which rows "
        f"bear a deduction: {sorted(disagreeing)}"
    )
