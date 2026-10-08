"""Pipeline transport preserves the canonical report without inventing facts."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ....core.period import Period
from ...ledger.models import LedgerStatusReport
from ...operator_actions.models import ActionArgumentBinding, ActionReference, DeclaredNextAction
from ..pipeline_health import ModeloHealthRow, ModeloReadinessState, PipelineHealthReport
from ..pipeline_projection import PipelineHealthSnapshot, PipelineLedgerSnapshot, PipelineNextActionSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PERIOD = Period.from_year_and_code(2025, "1T")


def _report(*, bucket_id: str = str(_PROFILE), period: Period | None = _PERIOD) -> PipelineHealthReport:
    return PipelineHealthReport(
        bucket_id=bucket_id,
        filing_year=2025,
        period="1T",
        ledger=LedgerStatusReport(
            bucket_id=bucket_id,
            period=period,
            business_income_total="12.30",
            business_expense_total="0.00",
            business_net_total="12.30",
            total_count=2,
            active_count=1,
            archived_count=0,
            stashed_count=1,
            pending_review_count=1,
            reviewed_count=0,
            skipped_count=0,
            ready=None,
        ),
        modelos=(
            ModeloHealthRow(
                modelo="130",
                state=ModeloReadinessState.NOT_STARTED,
                summary="No work unit",
                next_action=DeclaredNextAction(action=ActionReference(action_id="operator.modelo.work.create")),
            ),
        ),
        total_warning_findings=0,
        ready=False,
    )


def test_json_roundtrip_keeps_decimal_text_zero_none_action_and_scope() -> None:
    report = _report()
    snapshot = PipelineHealthSnapshot.from_report(report)
    decoded = PipelineHealthSnapshot.model_validate_json(snapshot.model_dump_json())

    assert decoded == snapshot
    assert decoded.to_report() == report
    assert decoded.ledger.business_income_total == "12.30"
    assert decoded.ledger.business_expense_total == "0.00"
    assert decoded.ledger.ready is None
    assert decoded.modelos[0].next_action is not None
    assert decoded.modelos[0].next_action.to_action() == report.modelos[0].next_action
    assert decoded.profile_id == _PROFILE
    assert decoded.period.to_period() == _PERIOD


def test_capture_refuses_missing_or_contradictory_ledger_scope() -> None:
    with pytest.raises(ValueError, match="exact profile and period"):
        PipelineHealthSnapshot.from_report(_report(period=None))
    with pytest.raises(ValueError, match="report and ledger periods"):
        PipelineHealthSnapshot.from_report(_report().model_copy(update={"period": "2T"}))
    with pytest.raises(ValueError, match="exact profile and period"):
        PipelineHealthSnapshot.from_report(
            _report().model_copy(update={"ledger": _report(bucket_id="6bb00000-0000-4000-8000-0000000000bb").ledger})
        )


def test_snapshot_rejects_unknown_shape_and_noncanonical_period() -> None:
    snapshot = PipelineHealthSnapshot.from_report(_report())
    with pytest.raises(ValidationError):
        PipelineHealthSnapshot.model_validate(snapshot.model_dump() | {"private_facts": {"x": "y"}})
    with pytest.raises(ValidationError):
        PipelineLedgerSnapshot.model_validate(snapshot.ledger.model_dump() | {"total_count": -1})
    with pytest.raises(ValidationError):
        PipelineHealthSnapshot.model_validate(snapshot.model_dump() | {"period": {"filing_year": 2025, "code": "bad"}})


def test_action_snapshot_preserves_decimal_integer_and_string_and_refuses_invalid_arguments() -> None:
    action = DeclaredNextAction(
        action=ActionReference(action_id="operator.modelo.work.create"),
        argument_bindings=tuple(
            ActionArgumentBinding(
                argument_name=name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=name,
            )
            for name, value in (("amount", Decimal("12.30")), ("year", 2025), ("modelo", "130"))
        ),
    )
    snapshot = PipelineNextActionSnapshot.from_action(action)
    decoded = PipelineNextActionSnapshot.model_validate_json(snapshot.model_dump_json())
    assert decoded.to_action() == action
    assert {item.argument_name: type(item.value) for item in decoded.to_action().argument_bindings} == {
        "amount": Decimal,
        "year": int,
        "modelo": str,
    }

    invalid = snapshot.model_dump(mode="python")
    invalid["argument_bindings"][0]["status"] = ActionArgumentStatus.MISSING
    with pytest.raises(ValidationError):
        PipelineNextActionSnapshot.model_validate(invalid)
    duplicated = snapshot.model_dump(mode="python")
    duplicated["argument_bindings"] = (*duplicated["argument_bindings"], duplicated["argument_bindings"][0])
    with pytest.raises(ValidationError):
        PipelineNextActionSnapshot.model_validate(duplicated)
