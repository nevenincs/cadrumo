"""The registry's declared treatment survives the requirement-to-value join.

The registry declares, per source modelo per revision, whether a carry is a figure
that settles the return (``direct_annual_settlement``) or a fact to reconcile
against (``factual_evidence``). That declaration reaches the application layer
intact: it is a field on the fold requirement and a typed ``Literal`` at the
handoff. What used to happen next is that the resolvers dropped it at the join,
leaving the mesh a bare mapping of binding id to Decimal, so a ``factual_evidence``
Modelo 193 retención the taxpayer SUFFERED arrived by the identical path a
``direct_annual_settlement`` Modelo 130 pago fraccionado did, and no consumer could
tell them apart.

The value is CARRIED, not gated. A taxpayer is entitled to a suffered retención and
dropping it silently is an over-declaration, which is the direction this apparatus
does not otherwise watch, so nothing here withholds a figure. What changes is that
a consumer can now distinguish the two classes.

The undeclared case is pinned deliberately. Seventeen carries in the registry
declare no treatment at all, and the governing decision record explicitly declined
to rule on them. The field defaults to the empty string, so a gate written as
``treatment == "factual_evidence"`` is safe while one written as
``treatment != "direct_annual_settlement"`` would sweep all seventeen into the
reclassified set — ratifying by implementation what the ruling refused to rule.
That is a symmetry a later simplification would find tempting, which is why it is a
test and not a comment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....core.resources import resources
from cadrumo.domain.calculations.registry.relations import RegistryFoldRequirement, relation_source_requirements
from cadrumo.domain.calculations.registry.bindings import previous_filing_observation_requirements
from .._binding_prefill import PrefilledBinding, _prefilled_bindings
from .._relation_prefill import _relation_value_grounding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

_SETTLEMENT = "direct_annual_settlement"
_EVIDENCE = "factual_evidence"


def _m100_2024() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=2024, period="0A")


def _requirements_by_relation(snapshot: RegistrySnapshot) -> dict[str, RegistryFoldRequirement]:
    """Map each relation id to the fold requirement that carries its treatment."""
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    return {relation_id: requirement for requirement in requirements for relation_id in requirement.relation_ids}


def _grounded_treatments(snapshot: RegistrySnapshot) -> dict[str, str]:
    """Run the real join and collect the treatment it carries onto each relation."""
    by_relation = _requirements_by_relation(snapshot)
    treatments: dict[str, str] = {}
    for relation in snapshot.revision.relations or ():
        grounding = _relation_value_grounding(relation, by_relation.get(relation.id))
        treatments[str(relation.id)] = grounding["dependency_treatment"]
    return treatments


def test_the_join_carries_both_declared_treatments_and_they_differ() -> None:
    """Both classes survive the join, and they are not interchangeable afterwards.

    Asserted as the presence of two DISTINCT declared values rather than against a
    named relation id, so a registry rename does not make this pass vacuously while
    the distinction is lost.
    """
    snapshot = _m100_2024()

    treatments = _grounded_treatments(snapshot)

    assert treatments, "the revision declares no relations, so this proves nothing"
    declared = {value for value in treatments.values() if value}
    assert _SETTLEMENT in declared, f"no settlement carry survived the join: {sorted(declared)}"
    assert _EVIDENCE in declared, f"no evidence carry survived the join: {sorted(declared)}"
    assert len(declared) >= 2, "the join collapsed the two classes into one value"


def test_an_unresolved_relation_carries_no_treatment_rather_than_a_default_one() -> None:
    """No requirement means no treatment, and that is not a treatment.

    The join is exercised with the requirement absent, which is what happens when
    scoping removed the source periods. Reading the empty result as any particular
    treatment is the failure this pins.
    """
    snapshot = _m100_2024()
    relation = next(iter(snapshot.revision.relations or ()), None)
    assert relation is not None, "the revision declares no relation to exercise"

    grounding = _relation_value_grounding(relation, None)

    assert grounding["dependency_treatment"] == ""
    assert grounding["dependency_treatment"] != _SETTLEMENT
    assert grounding["dependency_treatment"] != _EVIDENCE


def test_the_prefilled_binding_treatment_defaults_to_undeclared() -> None:
    """A carry whose revision declares no treatment must not acquire one by default.

    Seventeen registry carries are in exactly this state and the ruling declined to
    rule on them. A gate keyed on inequality with the settlement value would sweep
    every one of them into the reclassified set, so the default must stay falsy and
    distinct from both declared values.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    binding = PrefilledBinding(
        binding_id="probe-binding",
        value=Decimal("1234.56"),
        source_modelo="130",
        source_filing_year=2024,
        source_periods=("4T",),
        resolved_at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
    )

    assert binding.dependency_treatment == ""
    assert binding.dependency_treatment not in {_SETTLEMENT, _EVIDENCE}
    assert binding.value == Decimal("1234.56"), "carrying the treatment must not disturb the value"


def test_direct_previous_filing_treatment_reaches_the_prefilled_provenance() -> None:
    """The direct carry reads its treatment from the typed registry requirement.

    Modelo 303's repeated IVA-compensation carry is a real direct
    ``previous_filing`` binding with a declared ``factual_evidence`` treatment.
    Exercise the production prefilled-binding projection against that loaded
    snapshot: no application-local classification lookup may reconstruct or
    override the treatment after the registry requirement has supplied it.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    snapshot = resources().modelos.authority.snapshot("303", filing_year=2025, period="1T")
    requirement = next(
        item
        for item in previous_filing_observation_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        if item.dependency_treatment == _EVIDENCE
    )
    binding_id = requirement.binding_ids[0]

    prefilled = _prefilled_bindings(
        snapshot,
        {binding_id: Decimal("1.00")},
        observations=(),
        activity_start_date=None,
        resolved_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
    )

    assert len(prefilled) == 1
    assert prefilled[0].dependency_treatment == requirement.dependency_treatment
    assert prefilled[0].value == Decimal("1.00")


def test_carrying_the_treatment_does_not_withhold_the_value() -> None:
    """The remedy is not a blank. An entitled figure survives either classification.

    Constructed at both declared treatments with the same amount, because the
    constraint is that classification changes what a consumer can tell about a
    value, never whether the value is there.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    amount = Decimal("2400.00")
    for treatment in (_SETTLEMENT, _EVIDENCE):
        binding = PrefilledBinding(
            binding_id="probe-binding",
            value=amount,
            dependency_treatment=treatment,
            source_modelo="193",
            source_filing_year=2024,
            source_periods=("0A",),
            resolved_at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )
        assert binding.value == amount, f"{treatment} withheld the value"
        assert binding.dependency_treatment == treatment
