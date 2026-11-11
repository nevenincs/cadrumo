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
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_selected_for
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...calculations.cross_period_models import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)
from ...operator_actions.catalogue import lookup_action
from ...operator_surface.action_targets import resolve_recorded_precondition_action
from ..precondition_action_bindings import AlternativeActionArguments
from ..preconditions import (
    ATTEST_PRIOR_VALUE_ACTION_ID,
    MODELO_PRECONDITION_PROFILES,
    ModeloPreconditionFailure,
    build_modelo_precondition_failure_for_scenario,
)
from ..verification_cross_period import CrossPeriodDoor, cross_period_door, cross_period_door_operator_arguments

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "13000000-0000-4000-8000-000000000131"
_NOW = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
_BINDING = "irpf.previous_year_economic_activity_net_income"


def _target(year: int) -> WorkUnit:
    period = Period.from_year_and_code(year, "1T")
    revision_id = str(revision_selected_for("130", year, "1T").id)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo="130", filing_year=year, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=period,
        revision_id=revision_id,
        name="Pagos fraccionados",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _evidence(
    source_year: int, *, outside_envelope: bool, blocker: CrossPeriodCleanStateBlocker | None = None
) -> CrossPeriodDependencyEvidence:
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
        blockers=(CrossPeriodCleanStateBlocker.MISSING_OBSERVATION if blocker is None else blocker,),
    )


def _door(evidence: CrossPeriodDependencyEvidence, target: WorkUnit) -> CrossPeriodDoor:
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
    scenario, arguments, alternatives = _door(_evidence(floor - 1, outside_envelope=True), target)

    assert alternatives == ()
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
    scenario, _, _ = _door(_evidence(floor, outside_envelope=False), _target(floor + 1))

    assert scenario != "attest_prior_value"


def _cross_period_outcomes(leaf: str) -> dict[str, tuple[str | None, object, tuple[str, ...]]]:
    outcomes: dict[str, tuple[str | None, object, tuple[str, ...]]] = {}
    for profile in MODELO_PRECONDITION_PROFILES:
        suffix = profile.scenario_id.removeprefix(f"{leaf}.")
        if profile.subject_leaf_key == leaf and suffix.startswith(("cross_period_dependency.", "activity_start_date.")):
            outcomes[suffix] = (
                profile.action.action_id if profile.action is not None else None,
                profile.no_recovery_outcome,
                tuple(item.action_id for item in profile.alternative_actions),
            )
    return outcomes


def test_an_export_refused_on_an_earlier_return_opens_the_same_door_filing_does() -> None:
    assert _cross_period_outcomes("modelo.export") == _cross_period_outcomes("modelo.work.file")
    assert "cross_period_dependency.attest_prior_value" in _cross_period_outcomes("modelo.export")


_LEAVES = ("modelo.work.verify", "modelo.work.file", "modelo.export")


@pytest.mark.parametrize("leaf", _LEAVES)
def test_every_leaf_declares_the_statement_after_the_door_of_an_absent_earlier_return(leaf: str) -> None:
    outcomes = _cross_period_outcomes(leaf)

    assert outcomes["cross_period_dependency.source_absent_attestable"] == (
        "operator.modelo.work.create",
        None,
        (ATTEST_PRIOR_VALUE_ACTION_ID,),
    )
    assert outcomes["cross_period_dependency.filed_evidence_missing_attestable"] == (
        "operator.live.filed.pull",
        None,
        (ATTEST_PRIOR_VALUE_ACTION_ID,),
    )
    assert outcomes["cross_period_dependency.attest_prior_value"] == (ATTEST_PRIOR_VALUE_ACTION_ID, None, ())
    assert outcomes["cross_period_dependency.source_absent"] == ("operator.modelo.work.create", None, ())


def _attestable_failure(leaf: str, blocker: CrossPeriodCleanStateBlocker) -> ModeloPreconditionFailure:
    floor = filing_year_envelope().floor
    target = _target(floor + 1)
    door = _door(
        _evidence(floor, outside_envelope=False, blocker=blocker).model_copy(update={"attestation_admitted": True}),
        target,
    )
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.cross_period_dependency.{door.scenario}",
        evidence_id=f"{leaf}.cross_period_dependency",
        evidence_values={"work_unit_id": target.work_unit_id, "source_modelo": "100"},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values=door.action_argument_values,
        missing_action_arguments=cross_period_door_operator_arguments(door.scenario),
        alternative_actions=door.alternative_actions,
    )


@pytest.mark.parametrize("leaf", _LEAVES)
@pytest.mark.parametrize(
    ("blocker", "primary_target"),
    [
        (CrossPeriodCleanStateBlocker.MISSING_OBSERVATION, "modelo.work.create"),
        (CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE, "app.live.filed.pull"),
    ],
)
def test_the_attestable_refusal_resolves_both_doors_against_their_command_leaves(
    leaf: str, blocker: CrossPeriodCleanStateBlocker, primary_target: str
) -> None:
    resolved = resolve_recorded_precondition_action(_attestable_failure(leaf, blocker).verdict)

    assert resolved.action is not None
    assert resolved.action.target_command_key == primary_target
    assert resolved.conditionality is ActionConditionality.IMMEDIATE
    assert resolved.missing_argument_names == ()
    assert [item.action.action_id for item in resolved.alternative_actions] == [ATTEST_PRIOR_VALUE_ACTION_ID]
    statement = resolved.alternative_actions[0]
    assert statement.action.target_command_key == "modelo.work.attest_prior_value"
    assert statement.action.cli_path is not None
    assert statement.action.cli_path[-1] == "attest-prior-value"
    assert statement.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert statement.missing_argument_names == ("value",)
    assert {item.argument_name for item in statement.argument_bindings} == {
        "binding_id",
        "modelo",
        "period",
        "value",
        "work_unit_id",
        "year",
    }


def _attestable_scenario_arguments(alternatives: tuple[AlternativeActionArguments, ...]) -> ModeloPreconditionFailure:
    target = _target(filing_year_envelope().floor + 1)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id="modelo.work.verify.cross_period_dependency.source_absent_attestable",
        evidence_id="modelo.work.verify.cross_period_dependency",
        evidence_values={"work_unit_id": target.work_unit_id},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values={"modelo": "100", "period": "0A", "year": filing_year_envelope().floor},
        alternative_actions=alternatives,
    )


def _statement_arguments() -> AlternativeActionArguments:
    target = _target(filing_year_envelope().floor + 1)
    return AlternativeActionArguments(
        action_id=ATTEST_PRIOR_VALUE_ACTION_ID,
        action_argument_values={
            "work_unit_id": target.work_unit_id,
            "modelo": "130",
            "year": target.filing_year,
            "period": "1T",
            "binding_id": _BINDING,
        },
        missing_action_arguments=("value",),
    )


def test_an_attestable_scenario_refuses_a_producer_that_omits_its_declared_statement() -> None:
    with pytest.raises(ValueError, match="alternative actions contradict their declaration"):
        _attestable_scenario_arguments(())


def test_an_attestable_scenario_refuses_an_undeclared_alternative() -> None:
    undeclared = AlternativeActionArguments(
        action_id="operator.modelo.work.calculate", action_argument_values={"work_unit_id": "0" * 16}
    )

    with pytest.raises(ValueError, match="alternative actions contradict their declaration"):
        _attestable_scenario_arguments((_statement_arguments(), undeclared))


def test_a_scenario_without_alternatives_refuses_a_producer_that_adds_one() -> None:
    target = _target(filing_year_envelope().floor + 1)

    with pytest.raises(ValueError, match="alternative actions contradict their declaration"):
        build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.work.verify",
            scenario_id="modelo.work.verify.cross_period_dependency.source_absent",
            evidence_id="modelo.work.verify.cross_period_dependency",
            evidence_values={"work_unit_id": target.work_unit_id},
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            action_argument_values={"modelo": "100", "period": "0A", "year": filing_year_envelope().floor},
            alternative_actions=(_statement_arguments(),),
        )


def test_a_failure_whose_verdict_drops_the_declared_alternative_is_refused() -> None:
    failure = _attestable_scenario_arguments((_statement_arguments(),))
    stripped = failure.verdict.model_copy(update={"alternative_actions": ()})

    with pytest.raises(ValueError, match="alternative actions contradict its declaration"):
        ModeloPreconditionFailure(
            subject_leaf_key=failure.subject_leaf_key, scenario_id=failure.scenario_id, verdict=stripped
        )
