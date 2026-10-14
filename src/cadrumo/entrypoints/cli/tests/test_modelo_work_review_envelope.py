"""Envelope contract for the canonical modelo work review record."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.json_contract import (
    EnvelopeStatus,
    SchemaEnvelope,
    derive_status,
)
from cadrumo.core.operator_action_enums import OperatorActionAxis
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
)

from .._modelo_payloads import WorkReviewPayload, WorkReviewResult
from .._modelo_rendering import verification_report_notices
from .._modelo_work_review_cli import _review_lines
from ..command_schema import command_schema_types
from .review_envelope_support import RAW_ROW_IDENTITY, ROW_FINGERPRINT, persist_blocked_review

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMMAND = "modelo.work.review"


def test_review_record_round_trips_through_registered_schema_envelope(
    tmp_path: Path, *, authority_operation: PinnedAuthorityOperation
) -> None:
    with persist_blocked_review(tmp_path, operation=authority_operation) as seeded:
        review, report = seeded.review, seeded.report
        result = WorkReviewResult(review=WorkReviewPayload.from_review(review))
        notices = verification_report_notices(report)
        envelope_cls = SchemaEnvelope[WorkReviewResult]
        envelope = envelope_cls(
            command=_COMMAND,
            status=derive_status(notices),
            result=result,
            notices=notices,
        )

        document = envelope.model_dump(mode="json")
        round_tripped = envelope_cls.model_validate_json(envelope.model_dump_json())

        assert command_schema_types()[_COMMAND] is WorkReviewResult
        assert result.review.casilla_count == len(review.casillas)
        assert result.review.row_source_fingerprint_count == len(review.row_source_fingerprints)
        assert round_tripped == envelope
        assert round_tripped.status is EnvelopeStatus.WARNING
        assert "casillas" not in document["result"]["review"]
        blocker = round_tripped.result.review.blockers[0]
        notice = round_tripped.notices[0]
        assert blocker.axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT
        assert blocker.native_code == ModeloVerificationFindingKind.BLOCKING_RULE.value
        assert blocker.facts == {"casilla_id": review.findings[0].casilla_id}
        assert notice.context is not None
        assert notice.context["kind"] == blocker.native_code
        assert notice.context["casilla_id"] == blocker.facts["casilla_id"]
        assert document["result"]["review"]["row_source_fingerprint_count"] == 1
        rendered = f"{document!r} {envelope.model_dump_json()} {_review_lines(result)!r} {result!r}"
        assert RAW_ROW_IDENTITY not in rendered
        assert ROW_FINGERPRINT not in rendered
        secure_context_dump = result.model_dump(
            mode="json",
            context={"secure_calculation_revision": True, "secure_modelo_binding_value": True},
        )
        assert RAW_ROW_IDENTITY not in repr(secure_context_dump)


def test_review_payload_refuses_raw_identity_fields_without_echoing_value(
    tmp_path: Path, *, authority_operation: PinnedAuthorityOperation
) -> None:
    with persist_blocked_review(tmp_path, operation=authority_operation) as seeded:
        review = seeded.review
        payload = WorkReviewPayload.from_review(review).model_dump(mode="python")
        payload["row_source_identity"] = RAW_ROW_IDENTITY

        with pytest.raises(ValidationError) as exc_info:
            WorkReviewPayload.model_validate(payload)

        rendered = f"{exc_info.value!r} {exc_info.value}"
        assert RAW_ROW_IDENTITY not in rendered
