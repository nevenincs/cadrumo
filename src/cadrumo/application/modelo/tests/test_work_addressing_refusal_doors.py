"""Work addressing and selection refusals open the door of their cause.

Each refusal is raised by the owning code from a real trigger and read the way
the operation error detail reads it, through ``nested_terminal_precondition_verdict``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from ....core.operator_action_enums import ActionArgumentStatus, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..selectors import ModeloCalculationRevisionSelector, ModeloCalculationRevisionSelectorStateError
from ..work_address_errors import (
    ModeloRevisionPickError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkRegistryYearMismatchError,
    ModeloWorkRevisionConflictError,
    ModeloWorkVisibleTargetAmbiguousError,
)
from ..work_addressing import (
    ModeloRevisionPick,
    ModeloWorkAddress,
    _require_revision_state,
    law_selected_revision_for_work_target,
    modelo_work_address_from_operator_target,
    resolve_modelo_work_address,
)
from ..work_selection import ModeloWorkSelectorRequest, select_modelo_work_resolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "d1230300-0000-4000-8000-000000000411"
_UNIT_ID = "ab" * 32
_NOW = datetime.fromtimestamp(0, tz=UTC)


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bound(verdict: PreconditionVerdict) -> dict[str, object]:
    return {
        binding.argument_name: binding.value if binding.status is ActionArgumentStatus.RESOLVED else None
        for binding in verdict.argument_bindings
    }


def _action(verdict: PreconditionVerdict) -> str:
    assert verdict.action is not None
    return verdict.action.action_id


def _unit(*, revision_id: str) -> WorkUnit:
    year = filing_year_envelope().horizon
    period = Period.from_year_and_code(year, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo="130", filing_year=year, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=period,
        revision_id=revision_id,
        name="work",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _draft_revision_stand_in() -> object:
    """The three attributes the state gate reads, without building a sealed revision."""
    return SimpleNamespace(
        calculation_revision_id="c" * 64, work_unit_id=_UNIT_ID, state=CalculationRevisionState.BORRADOR
    )


def _request(**fields: object) -> ModeloWorkSelectorRequest:
    year = filing_year_envelope().horizon
    return ModeloWorkSelectorRequest.model_validate(
        {"modelo": "130", "filing_year": year, "period": Period.from_year_and_code(year, "1T"), **fields}
    )


def test_an_explicit_pick_without_a_revision_id_is_a_terminal_caller_defect() -> None:
    """The caller built a pick that contradicts itself; no operator action repairs it."""
    with pytest.raises(ModeloRevisionPickError) as refusal:
        ModeloRevisionPick(selector=ModeloCalculationRevisionSelector.EXPLICIT)
    verdict = _verdict(refusal.value)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_revision_id_without_the_explicit_selector_is_a_terminal_caller_defect() -> None:
    with pytest.raises(ModeloRevisionPickError) as refusal:
        ModeloRevisionPick(calculation_revision_id="c" * 64)
    verdict = _verdict(refusal.value)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_period_the_modelo_does_not_declare_opens_the_description_of_that_modelo() -> None:
    """The description states the periods the declaration accepts."""
    year = filing_year_envelope().horizon
    with pytest.raises(ModeloWorkPeriodTokenError) as refusal:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="303",
            year=year,
            period=Period.from_year_and_code(year, "0A"),
            registry_revision_id=None,
        )
    verdict = _verdict(refusal.value)
    assert _action(verdict) == "operator.modelo.describe"
    assert _bound(verdict) == {"modelo": "303"}


def test_a_period_of_another_year_opens_the_description_of_that_modelo() -> None:
    year = filing_year_envelope().horizon
    with pytest.raises(ModeloWorkPeriodTokenError) as refusal:
        modelo_work_address_from_operator_target(
            work_unit_id=None,
            modelo="130",
            year=year - 1,
            period=Period.from_year_and_code(year, "1T"),
            registry_revision_id=None,
        )
    assert _action(_verdict(refusal.value)) == "operator.modelo.describe"


def test_an_address_naming_nothing_opens_the_work_list() -> None:
    with pytest.raises(ModeloWorkAddressNotFoundError) as refusal:
        modelo_work_address_from_operator_target(
            work_unit_id=None, modelo=None, year=None, period=None, registry_revision_id=None
        )
    assert _action(_verdict(refusal.value)) == "operator.modelo.work.list"


def test_a_declaration_with_no_work_unit_opens_its_creation() -> None:
    year = filing_year_envelope().horizon
    address = ModeloWorkAddress(modelo="130", filing_year=year, period=Period.from_year_and_code(year, "1T"))
    with pytest.raises(ModeloWorkAddressNotFoundError) as refusal:
        resolve_modelo_work_address(address, catalogue=WorkUnitCatalogue(), bucket_id=_BUCKET_ID)
    verdict = _verdict(refusal.value)
    assert _action(verdict) == "operator.modelo.work.create"
    assert _bound(verdict)["modelo"] == "130"
    assert _bound(verdict)["year"] == year


def test_a_revision_in_the_wrong_state_opens_the_revisions_of_its_work_unit() -> None:
    revision = cast("CalculationRevision", _draft_revision_stand_in())
    with pytest.raises(ModeloCalculationRevisionSelectorStateError) as refusal:
        _require_revision_state(revision, allowed=(CalculationRevisionState.VERIFICADO_COMPLETO,), purpose="export")
    verdict = _verdict(refusal.value)
    assert _action(verdict) == "operator.modelo.work.revisions"
    assert _bound(verdict)["work_unit_id"] == _UNIT_ID


def test_a_revision_assertion_the_law_refuses_is_the_operator_decision_with_served_words() -> None:
    year = filing_year_envelope().horizon
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(ModeloWorkRegistryYearMismatchError) as refusal,
    ):
        law_selected_revision_for_work_target(
            modelo="130",
            filing_year=year,
            period=Period.from_year_and_code(year, "1T"),
            requested_revision_id="no-such-revision",
            operation=operation,
        )
    verdict = _verdict(refusal.value)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert str(refusal.value) == "application.modelo.errors.work_registry_revision_not_law_selected"


def test_an_ambiguous_short_id_opens_the_work_list_with_served_words() -> None:
    operator_id = "a" * 12
    prefix = _unit(revision_id="first").model_copy(update={"work_unit_id": operator_id + "0" * 52})
    suffix = _unit(revision_id="second").model_copy(update={"work_unit_id": "1" * 52 + operator_id})
    catalogue = WorkUnitCatalogue.model_construct(work_units={u.work_unit_id: u for u in (prefix, suffix)})
    with pytest.raises(ModeloWorkVisibleTargetAmbiguousError) as refusal:
        select_modelo_work_resolution(
            ModeloWorkSelectorRequest(operator_work_unit_id=operator_id), catalogue=catalogue, bucket_id=_BUCKET_ID
        )
    assert _action(_verdict(refusal.value)) == "operator.modelo.work.list"
    assert str(refusal.value) == "errors.refused.modelo_work_selector_ambiguous"


def test_an_ambiguous_natural_target_opens_the_work_list_with_served_words() -> None:
    units = (_unit(revision_id="first"), _unit(revision_id="second"))
    catalogue = WorkUnitCatalogue(work_units={u.work_unit_id: u for u in units})
    with pytest.raises(ModeloWorkVisibleTargetAmbiguousError) as refusal:
        select_modelo_work_resolution(_request(), catalogue=catalogue, bucket_id=_BUCKET_ID)
    assert _action(_verdict(refusal.value)) == "operator.modelo.work.list"
    assert str(refusal.value) == "errors.refused.modelo_work_selector_ambiguous"


def test_a_revision_conflict_opens_the_status_of_the_existing_work_unit() -> None:
    unit = _unit(revision_id="first")
    catalogue = WorkUnitCatalogue(work_units={unit.work_unit_id: unit})
    with pytest.raises(ModeloWorkRevisionConflictError) as refusal:
        select_modelo_work_resolution(_request(revision_id="other"), catalogue=catalogue, bucket_id=_BUCKET_ID)
    verdict = _verdict(refusal.value)
    assert _action(verdict) == "operator.modelo.work.status"
    assert _bound(verdict)["work_unit_id"] == unit.work_unit_id
