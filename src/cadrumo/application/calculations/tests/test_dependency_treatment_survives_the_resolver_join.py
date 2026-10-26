"""The registry's declared treatment survives the requirement-to-value join.

The registry declares, per source modelo per revision, whether a carry is a figure
that settles the return (``direct_annual_settlement``) or a fact to reconcile
against (``factual_evidence``). That declaration reaches the application layer
intact: it is a field on the fold requirement and a typed ``Literal`` at the
handoff. What used to happen next is that the resolvers dropped it at the join,
leaving the mesh a bare mapping of binding id to Decimal, so on Modelo 200 the
``factual_evidence`` carry of the prior year's pending bases imponibles negativas
arrived by the identical path the ``direct_annual_settlement`` Modelo 202 pagos
fraccionados did, and no consumer could tell them apart.

The value is CARRIED, not gated. Dropping a figure the taxpayer is entitled to is
an over-declaration, which is the direction this apparatus does not otherwise
watch, so nothing here withholds a figure. What changes is that a consumer can now
distinguish the two classes.

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

from ....domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ....domain.calculations.registry.relation_dependency import RelationDependencyTreatment
from ....domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_prefill_bindings_for_period,
    relation_source_requirements,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ..binding_prefill import PrefilledBinding, _prefilled_bindings
from ..relation_prefill import _relation_value_grounding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....domain.calculations.registry.schema import RegistrySnapshot

_SETTLEMENT = "direct_annual_settlement"
_EVIDENCE = "factual_evidence"


def _supported_years() -> tuple[int, ...]:
    catalogue = published_supported_filing_years()
    assert catalogue is not None, "the published legal support range is required"
    return catalogue.years


def _m100(filing_year: int | None = None) -> RegistrySnapshot:
    year = max(_supported_years()) if filing_year is None else filing_year
    return published_snapshot("100", filing_year=year, period="0A")


def _m200_2025() -> RegistrySnapshot:
    """Modelo 200 2025 relation-prefills both a settlement and an evidence carry."""
    return published_snapshot("200", filing_year=2025, period="0A")


def _requirements_by_binding(snapshot: RegistrySnapshot) -> dict[str, RegistryFoldRequirement]:
    """Map each provider-backed binding id to its fold requirement."""
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    return {binding_id: requirement for requirement in requirements for binding_id in requirement.target_bindings}


def _grounded_treatments(snapshot: RegistrySnapshot) -> dict[str, str]:
    """Run the real join and collect the treatment it carries onto each binding."""
    by_binding = _requirements_by_binding(snapshot)
    treatments: dict[str, str] = {}
    for binding, provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period):
        grounding = _relation_value_grounding(binding, provider, by_binding.get(binding.id))
        treatments[str(binding.id)] = grounding["dependency_treatment"]
    return treatments


@pytest.mark.parametrize("filing_year", _supported_years())
def test_the_join_carries_both_declared_treatments_and_they_differ(filing_year: int) -> None:
    """The real join preserves either typed treatment without requiring a withdrawn relation."""
    snapshot = _m100(filing_year)
    requirements = _requirements_by_binding(snapshot)
    binding, provider = next(
        (binding, provider)
        for binding, provider in relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)
        if binding.id in requirements
    )
    original = requirements[binding.id]
    carried = set()
    for treatment in (
        RelationDependencyTreatment.DIRECT_ANNUAL_SETTLEMENT,
        RelationDependencyTreatment.FACTUAL_EVIDENCE,
    ):
        requirement = RegistryFoldRequirement.model_validate(
            {**original.model_dump(), "dependency_treatment": treatment}
        )
        grounding = _relation_value_grounding(binding, provider, requirement)
        assert grounding["dependency_treatment"] == treatment
        carried.add(grounding["dependency_treatment"])
    assert carried == {_SETTLEMENT, _EVIDENCE}, "the join collapsed the two classes into one value"


@pytest.mark.parametrize("filing_year", _supported_years())
def test_the_join_preserves_the_selected_revision_treatments(filing_year: int) -> None:
    """Every live relation retains the treatment selected by temporal authority."""
    snapshot = _m100(filing_year)
    requirements = _requirements_by_binding(snapshot)
    treatments = _grounded_treatments(snapshot)
    assert treatments, "the revision declares no relations, so this proves nothing"
    for binding_id, treatment in treatments.items():
        requirement = requirements.get(binding_id)
        expected = requirement.dependency_treatment or "" if requirement is not None else ""
        assert treatment == expected


def test_an_unresolved_binding_carries_no_treatment_rather_than_a_default_one() -> None:
    """No requirement means no treatment, and that is not a treatment.

    The join is exercised with the requirement absent, which is what happens when
    scoping removed the source periods. Reading the empty result as any particular
    treatment is the failure this pins.
    """
    snapshot = _m100()
    binding_and_provider = next(
        iter(relation_prefill_bindings_for_period(snapshot.revision, period=snapshot.period)),
        None,
    )
    assert binding_and_provider is not None, "the revision declares no relation-prefill binding to exercise"
    binding, provider = binding_and_provider

    grounding = _relation_value_grounding(binding, provider, None)

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
        source_registry_snapshot_refs=(),
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

    snapshot = published_snapshot("303", filing_year=2025, period="1T")
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
            source_registry_snapshot_refs=(),
            resolved_at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        )
        assert binding.value == amount, f"{treatment} withheld the value"
        assert binding.dependency_treatment == treatment


def test_modelo_200_declared_settlement_and_evidence_treatments_remain_distinct() -> None:
    """Real published relations carry both treatments through the resolver join."""
    treatments = _grounded_treatments(_m200_2025())
    assert {_SETTLEMENT, _EVIDENCE} <= set(treatments.values())
