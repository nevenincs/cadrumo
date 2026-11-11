"""A source no return can prove names the filer's statement of its figure, at every leaf that refuses on it.

A first-quarter Modelo 130 reads the previous ejercicio's net activity income from
that year's Modelo 100 (RIRPF art. 110.3.c). Below the support floor no Modelo 100
can be held, so the refusal's door is the statement of that figure: the declaration,
the binding and its coordinates come from the refusal, the figure from the filer.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ...operator_actions.catalogue import lookup_action
from ..preconditions import build_modelo_precondition_failure_for_scenario
from ..verification_cross_period import cross_period_door, cross_period_door_operator_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13000000-0000-4000-8000-000000000131"
_NOW = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
_BINDING = "irpf.previous_year_economic_activity_net_income"


def _target(year: int) -> WorkUnit:
    period = Period.from_year_and_code(year, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo="130", filing_year=year, period=period, revision_id="2019-y-siguientes"
        ),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=period,
        revision_id="2019-y-siguientes",
        name="Pagos fraccionados",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _evidence(source_year: int, *, outside_envelope: bool) -> CrossPeriodDependencyEvidence:
    return CrossPeriodDependencyEvidence(
        requirement=CrossPeriodDependencyRequirement(
            source_modelo="100",
            filing_year=source_year,
            period=Period.from_year_and_code(source_year, "0A"),
            source_casilla_ids=(validated_casilla_id("0224", surface="test"),),
            origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
            origin_ids=(_BINDING,),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instrucciones",),
            source_outside_envelope=outside_envelope,
        ),
        blockers=(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION,),
    )


def _door(evidence: CrossPeriodDependencyEvidence, target: WorkUnit) -> tuple[str, dict[str, str | int] | None]:
    with bundled_indexed_authority().operation() as operation:
        return cross_period_door(
            evidence,
            bucket_id=_BUCKET_ID,
            work_catalogue=WorkUnitCatalogue(),
            calculation_catalogue=CalculationRevisionCatalogue(),
            operation=operation,
            target=target,
        )


@pytest.mark.parametrize("leaf", ["modelo.work.verify", "modelo.work.file", "modelo.export"])
def test_the_statement_door_resolves_at_every_leaf_and_leaves_only_the_figure_to_the_filer(leaf: str) -> None:
    floor = filing_year_envelope().floor
    target = _target(floor)
    scenario, arguments = _door(_evidence(floor - 1, outside_envelope=True), target)

    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.cross_period_dependency.{scenario}",
        evidence_id=f"{leaf}.cross_period_dependency",
        evidence_values={"work_unit_id": target.work_unit_id, "source_modelo": "100"},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values=arguments,
        missing_action_arguments=cross_period_door_operator_arguments(scenario),
    )

    verdict = failure.verdict
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.attest_prior_value"
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert verdict.missing_argument_names == ("value",)
    resolved = {item.argument_name: item.value for item in verdict.argument_bindings}
    assert resolved == {
        "binding_id": _BINDING,
        "modelo": "130",
        "period": "1T",
        "value": None,
        "work_unit_id": target.work_unit_id,
        "year": floor,
    }
    assert {
        item.argument_name for item in verdict.argument_bindings if item.status is ActionArgumentStatus.MISSING
    } == {"value"}


def test_the_statement_targets_the_command_that_states_a_prior_figure() -> None:
    action = lookup_action("operator.modelo.work.attest_prior_value")

    assert action.target_command_key == "modelo.work.attest_prior_value"


def test_a_door_that_is_not_a_statement_leaves_nothing_to_the_filer() -> None:
    assert cross_period_door_operator_arguments("source_absent") == ()
    assert cross_period_door_operator_arguments("filed_evidence_missing") == ()
    assert cross_period_door_operator_arguments("unclean") == ()


def test_a_source_the_envelope_admits_keeps_its_own_door_and_names_no_statement() -> None:
    floor = filing_year_envelope().floor
    scenario, _ = _door(_evidence(floor, outside_envelope=False), _target(floor + 1))

    assert scenario != "attest_prior_value"
