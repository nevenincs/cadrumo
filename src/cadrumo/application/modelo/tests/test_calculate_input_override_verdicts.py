"""Caller-override refusals on the calculate path carry their declared typed verdict.

A refusal without a verdict can only be reported as a generic "the stage was
refused" sentence by surfaces that cannot render its locale text, such as the
quickfile stage notice. Each test drives the same override resolver that
:func:`build_work_calculate_input_bundle` calls, against the published registry,
and proves the refusal keeps its registered message while carrying the
declared scenario, failed condition, registry evidence and recovery outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_selector_utils import boolean_binding_encoded_values
from ....domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    declared_casilla_ids,
    row_field_template_records_by_casilla,
)
from ....domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..calculate_input import (
    ModeloCalculateBindingInputError,
    ModeloCalculateCasillaInputError,
    ModeloCalculateDecimalInputError,
    _resolve_casilla_overrides,
    _validated_binding_input_channel,
    resolve_binding_overrides,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "calculate-override-verdict-bucket"
_CLOCK = datetime(2026, 1, 10, tzinfo=UTC)
_WORK_UNIT_REVISION_ID = "b" * 64
_FILING_YEAR = 2025
_PERIOD_CODE = "0A"
_LEAF = "modelo.work.calculate"
_UNDECLARED_CASILLA_KEY = "99999"
_ROW_FIELD_CASILLA_KEY = "perc.nif"


def _work_unit(modelo: str) -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=_WORK_UNIT_REVISION_ID,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=_WORK_UNIT_REVISION_ID,
        name=f"{modelo}-{_FILING_YEAR}-{_PERIOD_CODE}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(modelo: str) -> ModeloRevision:
    return published_snapshot(
        modelo,
        filing_year=_FILING_YEAR,
        period=_PERIOD_CODE,
        grade=RegistryAuthorityGrade.CALCULATION,
    ).revision


def _assert_verdict(
    error: ModeloCalculateBindingInputError | ModeloCalculateCasillaInputError | ModeloCalculateDecimalInputError,
    *,
    work_unit: WorkUnit,
    scenario_id: str,
    condition_id: str,
    evidence_id: str,
    facts: dict[str, str | int],
) -> PreconditionVerdict:
    """Assert the declared identity and evidence, and that the CLI boundary extracts this verdict."""
    failure = error.precondition_failure
    assert failure is not None
    assert failure.identity == (_LEAF, condition_id, scenario_id)
    verdict = error.terminal_precondition_verdict
    assert verdict is failure.verdict
    assert verdict.failed_condition_id == condition_id
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition_id
    assert evidence.evidence_id == evidence_id
    assert evidence.provenance is ActionEvidenceProvenance.REGISTRY_RECORD
    assert dict(evidence.values) == {
        "work_unit_id": work_unit.work_unit_id,
        "modelo": str(work_unit.modelo),
        "year": _FILING_YEAR,
        "period": _PERIOD_CODE,
        **facts,
    }
    assert nested_terminal_precondition_verdict(error) == verdict
    return verdict


def _assert_registry_listing_action(verdict: PreconditionVerdict, *, action_id: str, modelo: str) -> None:
    assert verdict.action is not None
    assert verdict.action.action_id == action_id
    assert verdict.no_recovery_outcome is None
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.missing_argument_names == ()
    assert {binding.argument_name: binding.value for binding in verdict.argument_bindings} == {
        "modelo": modelo,
        "year": _FILING_YEAR,
        "period": _PERIOD_CODE,
    }
    assert all(binding.status is ActionArgumentStatus.RESOLVED for binding in verdict.argument_bindings)
    assert all(binding.source is ActionArgumentSource.VERDICT_CONTEXT for binding in verdict.argument_bindings)


def test_unknown_binding_refusal_carries_its_bindings_list_verdict() -> None:
    work_unit = _work_unit("100")
    revision = _revision("100")
    known = {binding.id for binding in revision.bindings}
    assert "no-such-binding-id" not in known

    with pytest.raises(ModeloCalculateBindingInputError) as exc_info:
        resolve_binding_overrides({"no-such-binding-id": "1"}, revision, work_unit=work_unit)

    error = exc_info.value
    assert error.translated_message == "application.modelo.errors.calculate_binding_unknown"
    assert error.context is not None
    assert set(error.context) == {"key", "accepted"}
    verdict = _assert_verdict(
        error,
        work_unit=work_unit,
        scenario_id="modelo.work.calculate.caller_overrides.binding_unknown",
        condition_id="modelo.work.calculate.caller_overrides.binding_declared",
        evidence_id="modelo.work.calculate.binding_override",
        facts={
            "binding_id": "no-such-binding-id",
            "revision_id": revision.id,
            "declared_binding_count": len(known),
        },
    )
    _assert_registry_listing_action(verdict, action_id="operator.modelo.bindings.list", modelo="100")

    # A caller that is not the calculate verb names no calculate target and gets no verdict.
    with pytest.raises(ModeloCalculateBindingInputError) as untargeted:
        _validated_binding_input_channel(
            "no-such-binding-id",
            revision,
            known,
            enum_consumed_binding_ids(revision),
        )
    assert untargeted.value.precondition_failure is None


def test_boolean_binding_encoding_refusal_carries_its_bindings_list_verdict() -> None:
    work_unit = _work_unit("100")
    revision = _revision("100")
    enum_ids = enum_consumed_binding_ids(revision)
    date_ids = revision_date_binding_ids(revision)
    boolean_decimal_bindings = [
        binding
        for binding in revision.bindings
        if boolean_binding_encoded_values(binding) and binding.id not in enum_ids and binding.id not in date_ids
    ]
    assert boolean_decimal_bindings, "the published revision no longer declares a decimal-encoded boolean binding"
    binding = boolean_decimal_bindings[0]
    accepted = ", ".join(option.encoded_value for option in boolean_binding_encoded_values(binding))

    with pytest.raises(ModeloCalculateDecimalInputError) as exc_info:
        resolve_binding_overrides({binding.id: "false"}, revision, work_unit=work_unit)

    error = exc_info.value
    assert error.translated_message == "application.modelo.errors.calculate_boolean_binding_encoding_invalid"
    assert error.context is not None
    assert set(error.context) == {"flag", "key", "value", "accepted", "mapping"}
    verdict = _assert_verdict(
        error,
        work_unit=work_unit,
        scenario_id="modelo.work.calculate.caller_overrides.boolean_binding_encoding_invalid",
        condition_id="modelo.work.calculate.caller_overrides.binding_encoding_valid",
        evidence_id="modelo.work.calculate.binding_override",
        facts={"binding_id": binding.id, "accepted_encoded_values": accepted},
    )
    _assert_registry_listing_action(verdict, action_id="operator.modelo.bindings.list", modelo="100")


def test_unknown_casilla_refusal_carries_its_casillas_verdict(*, operation: PinnedAuthorityOperation) -> None:
    work_unit = _work_unit("200")
    revision = _revision("200")
    known = declared_casilla_ids(revision)
    assert _UNDECLARED_CASILLA_KEY not in known
    assert not casilla_noncanonical_reference_targets(revision, _UNDECLARED_CASILLA_KEY)

    with pytest.raises(ModeloCalculateCasillaInputError) as exc_info:
        _resolve_casilla_overrides(
            {_UNDECLARED_CASILLA_KEY: "1.00"},
            revision,
            operation=operation,
            work_unit=work_unit,
        )

    error = exc_info.value
    assert error.translated_message == "application.modelo.errors.calculate_casilla_unknown"
    assert error.context is not None
    assert set(error.context) == {"key", "accepted"}
    verdict = _assert_verdict(
        error,
        work_unit=work_unit,
        scenario_id="modelo.work.calculate.caller_overrides.casilla_unknown",
        condition_id="modelo.work.calculate.caller_overrides.casilla_declared",
        evidence_id="modelo.work.calculate.casilla_override",
        facts={
            "casilla_key": _UNDECLARED_CASILLA_KEY,
            "revision_id": revision.id,
            "declared_casilla_count": len(known),
        },
    )
    _assert_registry_listing_action(verdict, action_id="operator.modelo.casillas", modelo="200")


def test_a_row_field_casilla_is_refused_as_one_before_its_value_is_parsed(
    *, operation: PinnedAuthorityOperation
) -> None:
    """A casilla an export record fills once per detail row is refused for being one.

    The value is not a decimal, so a refusal from the value parser would blame
    the value; the row-field refusal names the casilla and the records carrying
    it, which is what the operator has to act on.
    """
    work_unit = _work_unit("180")
    revision = _revision("180")
    records = row_field_template_records_by_casilla(revision)[_ROW_FIELD_CASILLA_KEY]

    with pytest.raises(ModeloCalculateCasillaInputError) as exc_info:
        _resolve_casilla_overrides(
            {_ROW_FIELD_CASILLA_KEY: "B12345678"},
            revision,
            operation=operation,
            work_unit=work_unit,
        )

    error = exc_info.value
    assert error.translated_message == "errors.calc.row_field_template_supplied_as_input"
    assert error.context == {"casilla_ids": _ROW_FIELD_CASILLA_KEY, "record_ids": ",".join(records)}
    verdict = _assert_verdict(
        error,
        work_unit=work_unit,
        scenario_id="modelo.work.calculate.caller_overrides.row_field_casilla_refused",
        condition_id="modelo.work.calculate.caller_overrides.casilla_scalar",
        evidence_id="modelo.work.calculate.casilla_override",
        facts={"casilla_key": _ROW_FIELD_CASILLA_KEY},
    )
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_former_detail_alias_is_an_undeclared_casilla(*, operation: PinnedAuthorityOperation) -> None:
    """No key prefix is reserved any more: a name no revision declares is simply undeclared."""
    work_unit = _work_unit("180")
    revision = _revision("180")

    with pytest.raises(ModeloCalculateCasillaInputError) as exc_info:
        _resolve_casilla_overrides(
            {"perceptor.nif": "B12345678"},
            revision,
            operation=operation,
            work_unit=work_unit,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.calculate_casilla_unknown"
