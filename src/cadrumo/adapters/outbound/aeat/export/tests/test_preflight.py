"""Submission preflight gates over production filing, deadline, and auth types."""

from __future__ import annotations

from datetime import date

import pytest

from ......core.errors.severity import BaseSeverity
from ......core.i18n import Translatable as tr
from ......domain.filing.schema import ModeloValidationFinding
from ......domain.submission.errors import SubmissionPreflightError
from ......domain.submission.models import ModeloDraftStatus
from ......domain.submission.preflight import Preflight
from ._preflight_support import clave_movil_provider, deadline_checker, modelo_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_OPEN_DAY = date(2026, 4, 10)
_CLOSED_DAY = date(2026, 6, 10)


def _preflight(*, identity: str | None = "12345678Z") -> Preflight:
    return Preflight(
        deadline_checker=deadline_checker(),
        auth_provider=clave_movil_provider(identity=identity),
    )


def test_approved_draft_passes_all_real_preflight_boundaries() -> None:
    assert _preflight().check(modelo_draft(), today=_OPEN_DAY) is None


@pytest.mark.parametrize(
    ("status", "message_key"),
    (
        pytest.param(
            ModeloDraftStatus.BORRADOR,
            "errors.refused.submission_preflight_draft_not_approved",
            id="draft",
        ),
        pytest.param(
            ModeloDraftStatus.LISTO_PARA_PRESENTAR,
            "errors.refused.submission_preflight_draft_not_approved",
            id="ready-but-unapproved",
        ),
        pytest.param(
            ModeloDraftStatus.APROBACION_CADUCADA,
            "errors.refused.submission_preflight_draft_stale",
            id="stale-approval",
        ),
    ),
)
def test_unapproved_production_draft_statuses_are_refused(
    status: ModeloDraftStatus,
    message_key: str,
) -> None:
    with pytest.raises(SubmissionPreflightError) as raised:
        _preflight().check(modelo_draft(status=status), today=_OPEN_DAY)

    assert raised.value.translated_message == message_key
    assert raised.value.context == {"status": status.value}


def test_error_finding_on_production_draft_is_refused() -> None:
    finding = ModeloValidationFinding(
        casilla_id=None,
        severity=BaseSeverity.ERROR,
        code="preflight-test-error",
        message=tr("errors.refused.submission_preflight_error_findings"),
    )

    with pytest.raises(SubmissionPreflightError) as raised:
        _preflight().check(modelo_draft(findings=(finding,)), today=_OPEN_DAY)

    assert raised.value.translated_message == "errors.refused.submission_preflight_error_findings"
    assert raised.value.context == {"finding_count": 1}


def test_warning_finding_on_production_draft_does_not_block() -> None:
    finding = ModeloValidationFinding(
        casilla_id=None,
        severity=BaseSeverity.WARNING,
        code="preflight-test-warning",
        message=tr("errors.refused.submission_preflight_draft_not_approved"),
    )

    assert _preflight().check(modelo_draft(findings=(finding,)), today=_OPEN_DAY) is None


def test_closed_registry_window_is_refused() -> None:
    with pytest.raises(SubmissionPreflightError) as raised:
        _preflight().check(modelo_draft(), today=_CLOSED_DAY)

    assert raised.value.translated_message == "errors.refused.submission_preflight_deadline_closed"
    assert raised.value.context == {"modelo": "130", "period": "2026 1T", "today": "2026-06-10"}


@pytest.mark.parametrize(
    ("identity", "configured"),
    (
        pytest.param("INVALID", True, id="malformed-configured-identity"),
        pytest.param(None, False, id="unconfigured-provider"),
    ),
)
def test_real_unavailable_auth_provider_is_refused(identity: str | None, configured: bool) -> None:
    with pytest.raises(SubmissionPreflightError) as raised:
        _preflight(identity=identity).check(modelo_draft(), today=_OPEN_DAY)

    assert raised.value.translated_message == "errors.refused.submission_preflight_auth_not_ready"
    assert raised.value.context is not None
    assert raised.value.context["kind"] == "clave_movil"
    assert raised.value.context["configured"] is configured
    assert raised.value.context["available"] is False


def test_local_preflight_can_skip_real_unconfigured_auth_provider() -> None:
    assert (
        _preflight(identity=None).check(
            modelo_draft(),
            today=_OPEN_DAY,
            skip_auth_readiness=True,
        )
        is None
    )
