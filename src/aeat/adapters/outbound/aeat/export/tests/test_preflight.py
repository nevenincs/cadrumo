"""Unit tests for :class:`aeat.domain.submission.Preflight`."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ......application.auth import AuthProviderDescription, AuthProviderKind
from ......core import Period
from ......core.errors import BaseSeverity
from ......domain.submission import (
    ModeloDraftStatus,
    ModeloFinding,
    Preflight,
    SubmissionPreflightError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from ......domain.submission._preflight import AuthProviderProbe, DeadlineWindowChecker


class _Draft(BaseModel):
    """Frozen Protocol-conforming test double for ``ModeloDraftLike``.

    Structural conformance only — ``ModeloDraftLike`` declares read-only
    properties, so a frozen pydantic model satisfies it without
    inheritance and without the no-dataclasses mandate violation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    draft_id: str = "draft-1"
    modelo: str = "130"
    period: Period = Field(default_factory=lambda: Period.from_year_and_code(2026, "1T"))
    profile_tax_id: str = "X1234567L"
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO
    values: dict[str, str] = Field(default_factory=dict)
    findings: tuple[ModeloFinding, ...] = ()


class _AlwaysOpenChecker:
    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        return True


class _AlwaysClosedChecker:
    def is_window_open(self, modelo: str, period: Period, today: date) -> bool:
        return False


class _OkAuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="Test certificate",
            configured=True,
            available=True,
            identity_nif="X1234567L",
            subject="CN=Test",
            expires_on=date(2099, 12, 31),
            health_summary="OK:26800",
        )


class _FailingAuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        from ......core.errors import AeatError

        raise AeatError("no smartcard")


class _UnavailableAuthProvider:
    kind = AuthProviderKind.CERTIFICATE

    def describe(self) -> AuthProviderDescription:
        return AuthProviderDescription(
            kind=self.kind,
            label="Test certificate",
            configured=True,
            available=False,
            identity_nif=None,
            subject=None,
            expires_on=None,
            health_summary="not ready",
        )


_TODAY = date(2026, 4, 10)


def _preflight(*, checker: DeadlineWindowChecker | None = None, cert: AuthProviderProbe | None = None) -> Preflight:
    return Preflight(
        deadline_checker=checker or _AlwaysOpenChecker(),
        auth_provider=cert or _OkAuthProvider(),
    )


class TestPreflightGates:
    def test_happy_path_silent(self) -> None:
        draft = _Draft()
        result = _preflight().check(draft, today=_TODAY)
        assert result is None

    def test_gate_1_draft_not_approved(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight().check(_Draft(status=ModeloDraftStatus.BORRADOR), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_draft_not_approved"
        assert raised.value.context == {"status": "BORRADOR"}

    def test_gate_1_ready_but_unapproved_blocks(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight().check(_Draft(status=ModeloDraftStatus.LISTO_PARA_PRESENTAR), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_draft_not_approved"
        assert raised.value.context == {"status": "LISTO_PARA_PRESENTAR"}

    def test_gate_1_stale_approval_blocks(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight().check(_Draft(status=ModeloDraftStatus.APROBACION_CADUCADA), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_draft_stale"
        assert raised.value.context == {"status": "APROBACION_CADUCADA"}

    def test_gate_2_error_finding_blocks(self) -> None:
        findings = (
            ModeloFinding(
                severity=BaseSeverity.ERROR,
                message="export.test_preflight.message_868279",
            ),
        )
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight().check(_Draft(findings=findings), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_error_findings"
        assert raised.value.context == {"finding_count": 1}

    def test_gate_2_warning_does_not_block(self) -> None:
        findings = (
            ModeloFinding(
                severity=BaseSeverity.WARNING,
                message="export.test_preflight.message_620739",
            ),
        )
        assert findings[0].severity == BaseSeverity.WARNING
        result = _preflight().check(_Draft(findings=findings), today=_TODAY)
        assert result is None

    def test_gate_3_window_closed(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight(checker=_AlwaysClosedChecker()).check(_Draft(), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_deadline_closed"
        assert raised.value.context == {"modelo": "130", "period": "2026 1T", "today": "2026-04-10"}

    def test_gate_4_cert_load_fails(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight(cert=_FailingAuthProvider()).check(_Draft(), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_auth_describe_failed"
        assert raised.value.context == {"cause_type": "AeatError"}

    def test_gate_4_unavailable_provider_surfaces_structured_context(self) -> None:
        with pytest.raises(SubmissionPreflightError) as raised:
            _preflight(cert=_UnavailableAuthProvider()).check(_Draft(), today=_TODAY)
        assert raised.value.translated_message == "errors.refused.submission_preflight_auth_not_ready"
        assert raised.value.context is not None
        assert raised.value.context["kind"] == "certificate"
        assert raised.value.context["configured"] is True
        assert raised.value.context["available"] is False
        assert "configured but not ready" in str(raised.value.context["operator_impact"])
