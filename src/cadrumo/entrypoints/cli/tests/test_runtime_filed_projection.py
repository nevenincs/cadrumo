"""Filed-capture projections restore their reports only when they are unambiguous and receipt-consistent."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel

from ....application.live.filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
)
from ....application.live.remote_state_models import FiledCaptureEvidenceTally
from ....application.modelo.filing_chain_reconciliation import (
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
)
from ....core.json_contract import NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.period import Period
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..runtime_filed_projection import (
    capture_evidence_effect,
    capture_notice,
    context_from_pairs,
    reconciliation_result,
    settled_capture_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "c" * 64


class _Projection(BaseModel):
    captured: int


def _tally(**counts: int) -> FiledCaptureEvidenceTally:
    return FiledCaptureEvidenceTally(
        captured_count=counts.get("captured_count", 0),
        observation_paths=(),
        artefact_refs=(),
        filing_evidence_stamped_count=counts.get("filing_evidence_stamped_count", 0),
        casilla_count=0,
        calculation_observation_count=counts.get("calculation_observation_count", 0),
        calculation_observation_keys=(),
    )


def _row(**update: object) -> FiledReconciliationV1:
    fields: dict[str, object] = {
        "outcome": FilingReconciliationOutcome.CONFIRMED.value,
        "bucket_id": str(_PROFILE),
        "modelo": "303",
        "filing_year": 2024,
        "period": "1T",
        "evidence_basis": "casillas",
        "notices": (),
    }
    fields.update(update)
    return FiledReconciliationV1.model_validate(fields)


def test_a_notice_context_with_a_repeated_key_is_refused_instead_of_collapsed() -> None:
    assert context_from_pairs(None) is None
    assert context_from_pairs((("a", "1"), ("b", "2"))) == {"a": "1", "b": "2"}
    with pytest.raises(ValueError, match="duplicate keys"):
        context_from_pairs((("a", "1"), ("a", "2")))


def test_a_capture_notice_keeps_severity_code_message_and_context() -> None:
    notice = capture_notice(
        FiledCaptureNoticeV1(
            severity=NoticeSeverity.WARNING,
            code="live.example",
            message="Example advisory",
            context=(("reason", "capture"),),
        )
    )

    assert (notice.severity, notice.code, notice.message, notice.context) == (
        NoticeSeverity.WARNING,
        "live.example",
        "Example advisory",
        {"reason": "capture"},
    )


def test_a_reconciliation_restores_its_period_basis_and_notice_context() -> None:
    result = reconciliation_result(
        _row(
            notices=(
                FiledReconciliationNoticeV1(
                    code=FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY.value, context=(("k", "v"),)
                ),
            )
        ),
        profile_id=_PROFILE,
    )

    assert result.outcome is FilingReconciliationOutcome.CONFIRMED
    assert result.period == Period.from_year_and_code(2024, "1T")
    assert result.evidence_basis == "casillas"
    (notice,) = result.notices
    assert notice.code is FilingReconciliationNoticeCode.RECEIPT_TOTALS_ONLY
    assert notice.context == {"k": "v"}


@pytest.mark.parametrize(
    "update",
    [{"bucket_id": "5bb00000-0000-4000-8000-0000000000bb"}, {"evidence_basis": "guess"}],
)
def test_a_reconciliation_for_another_profile_or_with_an_unknown_basis_is_refused(update: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        reconciliation_result(_row(**update), profile_id=_PROFILE)


def test_a_missing_evidence_basis_stays_absent_rather_than_defaulted() -> None:
    assert reconciliation_result(_row(evidence_basis=None), profile_id=_PROFILE).evidence_basis is None


@pytest.mark.parametrize(
    ("counts", "effect"),
    [
        ({}, OperationEffect.NONE),
        ({"captured_count": 1}, OperationEffect.UPDATED),
        ({"calculation_observation_count": 1}, OperationEffect.UPDATED),
        ({"filing_evidence_stamped_count": 1}, OperationEffect.UPDATED),
    ],
)
def test_the_expected_effect_follows_what_the_capture_persisted(
    counts: dict[str, int], effect: OperationEffect
) -> None:
    assert capture_evidence_effect(_tally(**counts)) is effect


def _completion(
    *,
    effect: OperationEffect,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> RegisteredOperationCompletion[_Projection]:
    return RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_Projection(captured=1),
        effect=effect,
        terminal_condition=condition,
        refusal_code=refusal_code,
    )


def _settle(completed: RegisteredOperationCompletion[_Projection], expected: OperationEffect) -> int:
    return settled_capture_report(
        completed, _Projection, lambda projection: projection.captured, lambda _report: expected
    )


def test_a_report_is_restored_when_the_receipt_has_the_expected_effect() -> None:
    assert _settle(_completion(effect=OperationEffect.UPDATED), OperationEffect.UPDATED) == 1


def test_a_provider_refresh_may_update_state_even_when_the_capture_reports_no_effect() -> None:
    assert _settle(_completion(effect=OperationEffect.UPDATED), OperationEffect.NONE) == 1


@pytest.mark.parametrize(
    ("effect", "expected"),
    [
        (OperationEffect.NONE, OperationEffect.UPDATED),
        (OperationEffect.PARTIAL, OperationEffect.NONE),
    ],
)
def test_a_receipt_that_disagrees_with_the_report_is_an_invalid_frame_keeping_the_effect(
    effect: OperationEffect, expected: OperationEffect
) -> None:
    with pytest.raises(CliRefusedBoundaryError) as error:
        _settle(_completion(effect=effect), expected)

    assert error.value.context is not None
    assert error.value.context["effect"] == effect.value
    assert error.value.context["operation_id"] == _OPERATION_ID


def test_a_refused_receipt_never_restores_a_report_and_keeps_its_refusal_code() -> None:
    with pytest.raises(CliRefusedBoundaryError) as error:
        _settle(
            _completion(
                effect=OperationEffect.NONE,
                condition=OperationTerminalCondition.REFUSED,
                refusal_code="REFUSED_EXAMPLE",
            ),
            OperationEffect.NONE,
        )

    assert error.value.context is not None
    assert error.value.context["refusal_code"] == "REFUSED_EXAMPLE"
