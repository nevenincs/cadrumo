"""Contract parity between auth-diagnostics application models and their CLI shells.

``AuthDiagnosticsListResult``, ``AuthDiagnosticsViewResult``, and
``AuthDiagnosticsReportResult`` must refuse the malformed nested-row,
unknown-field, closed-state, and timestamp shapes the canonical
``AuthDiagnosticSummary`` / ``AuthDiagnosticDetail`` / ``AuthDiagnosticReportResult``
models already refuse, and must accept the same real projections the CLI
emit sites build.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.auth.diagnostics import AuthDiagnosticDetail, AuthDiagnosticPhoneState, AuthDiagnosticSummary
from ....tests.aeat_literal_fixtures import AUTH_DIAGNOSTIC_SEDE_URL_FIXTURE
from .._config_payloads import AuthDiagnosticsListResult, AuthDiagnosticsReportResult, AuthDiagnosticsViewResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CAPTURED_AT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _summary(**overrides: object) -> AuthDiagnosticSummary:
    base: dict[str, object] = {
        "diagnostic_id": "diag-1",
        "reason": "auth_completion_timeout",
        "url": AUTH_DIAGNOSTIC_SEDE_URL_FIXTURE,
        "captured_at": _CAPTURED_AT,
        "html_captured": False,
        "screenshot_captured": False,
    }
    base.update(overrides)
    return AuthDiagnosticSummary.model_validate(base)


def _detail(**overrides: object) -> AuthDiagnosticDetail:
    base: dict[str, object] = {
        "diagnostic_id": "diag-1",
        "reason": "auth_completion_timeout",
        "url": AUTH_DIAGNOSTIC_SEDE_URL_FIXTURE,
        "captured_at": _CAPTURED_AT,
        "html_captured": False,
        "screenshot_captured": False,
    }
    base.update(overrides)
    return AuthDiagnosticDetail.model_validate(base)


def test_list_result_accepts_real_summary_rows() -> None:
    """A genuine ``AuthDiagnosticSummary`` row projects and validates cleanly."""
    result = AuthDiagnosticsListResult(row_count=1, rows=[_summary()])

    assert result.rows[0].diagnostic_id == "diag-1"


def test_list_result_rejects_a_row_the_canonical_summary_rejects() -> None:
    """An unknown extra field on a row is refused, matching the summary's own strictness."""
    with pytest.raises(ValidationError):
        AuthDiagnosticsListResult.model_validate(
            {
                "row_count": 1,
                "rows": [{**_summary().model_dump(), "unknown_extra_field": "surprise"}],
            },
        )


def test_list_result_rejects_a_non_datetime_captured_at() -> None:
    """A non-datetime ``captured_at`` on a row is refused under the strict nested model."""
    with pytest.raises(ValidationError):
        AuthDiagnosticsListResult.model_validate(
            {
                "row_count": 1,
                "rows": [{**_summary().model_dump(mode="json"), "captured_at": "not-a-time"}],
            },
        )


def test_show_result_accepts_a_real_detail_projection() -> None:
    """The show envelope reuses the detail model's own field set directly."""
    result = AuthDiagnosticsViewResult(**_detail().model_dump())

    assert result.diagnostic_id == "diag-1"
    assert result.reason == "auth_completion_timeout"


def test_show_result_rejects_an_unknown_field() -> None:
    """An unrecognised field is refused, matching the detail model's ``extra='forbid'``.

    Round-trips through the JSON-text path (``model_dump_json`` /
    ``model_validate_json``), not ``model_validate(x.model_dump(mode="json"))``: the
    detail model carries strict-typed fields (``captured_at: datetime``,
    ``operator_report_commands: tuple[str, ...]``, ``phone_state`` an enum) whose
    JSON-mode dict projection (isoformat string, list, bare string) does not
    re-validate under ``model_validate`` on a plain dict — only genuine JSON text
    gets that leniency. Feeding the dict form here would raise on those fields
    regardless of the injected unknown key, masking the assertion this test claims.
    """
    payload = json.loads(_detail().model_dump_json())
    payload["unexpected"] = "value"

    with pytest.raises(ValidationError):
        AuthDiagnosticsViewResult.model_validate_json(json.dumps(payload))


def test_report_result_accepts_a_real_phone_state() -> None:
    """A closed-vocabulary phone-state report round-trips cleanly."""
    result = AuthDiagnosticsReportResult(
        diagnostic_id="diag-1",
        phone_state=AuthDiagnosticPhoneState.APP_PROMPTED_AND_ACCEPTED,
        reported_at=_CAPTURED_AT,
    )

    assert result.phone_state is AuthDiagnosticPhoneState.APP_PROMPTED_AND_ACCEPTED


def test_report_result_rejects_blank_diagnostic_id() -> None:
    """A blank diagnostic id is refused, matching the application result's constraint."""
    with pytest.raises(ValidationError):
        AuthDiagnosticsReportResult(
            diagnostic_id="",
            phone_state=AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT,
            reported_at=_CAPTURED_AT,
        )


def test_report_result_rejects_unknown_phone_state() -> None:
    """A phone-state outside the closed vocabulary is refused."""
    with pytest.raises(ValidationError):
        AuthDiagnosticsReportResult.model_validate(
            {
                "diagnostic_id": "diag-1",
                "phone_state": "guessed",
                "reported_at": _CAPTURED_AT.isoformat(),
            },
        )


def test_report_result_rejects_malformed_reported_at() -> None:
    """A non-ISO ``reported_at`` is refused."""
    with pytest.raises(ValidationError):
        AuthDiagnosticsReportResult.model_validate(
            {
                "diagnostic_id": "diag-1",
                "phone_state": AuthDiagnosticPhoneState.APP_DID_NOT_PROMPT.value,
                "reported_at": "bad",
            },
        )
