"""Unit tests for :class:`aeat.domain.submission.Preflight`."""

from __future__ import annotations

from .....core.errors import BaseSeverity
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .....domain.submission._preflight import AuthProviderProbe, DeadlineWindowChecker

import pytest

from .....application.auth import AuthProviderDescription, AuthProviderKind
from .....domain.submission import SubmissionPreflightError
from . import (
    ModeloDraftStatus,
    ModeloDraftLike,
    ModeloFinding,
    Preflight,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


@dataclass
class _Draft(ModeloDraftLike):
    """Protocol-conforming test double for :class:`ModeloDraftLike`."""

    draft_id: str = "draft-1"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: ModeloDraftStatus = ModeloDraftStatus.APPROVED
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[ModeloFinding, ...] = ()


class _AlwaysOpenChecker:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _AlwaysClosedChecker:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
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
        from .....core.errors import AeatError

        raise AeatError("no smartcard")


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
        with pytest.raises(SubmissionPreflightError, match="not approved"):
            _preflight().check(_Draft(status=ModeloDraftStatus.DRAFT), today=_TODAY)

    def test_gate_1_ready_but_unapproved_blocks(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="not approved"):
            _preflight().check(_Draft(status=ModeloDraftStatus.READY_TO_SUBMIT), today=_TODAY)

    def test_gate_1_stale_approval_blocks(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="stale"):
            _preflight().check(_Draft(status=ModeloDraftStatus.APPROVAL_STALE), today=_TODAY)

    def test_gate_2_error_finding_blocks(self) -> None:
        findings = (
            ModeloFinding(
                severity=BaseSeverity.ERROR,
                message="export.test_preflight.message_868279",
            ),
        )
        with pytest.raises(SubmissionPreflightError, match="ERROR-severity"):
            _preflight().check(_Draft(findings=findings), today=_TODAY)

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
        with pytest.raises(SubmissionPreflightError, match="deadline window"):
            _preflight(checker=_AlwaysClosedChecker()).check(_Draft(), today=_TODAY)

    def test_gate_4_cert_load_fails(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="auth provider"):
            _preflight(cert=_FailingAuthProvider()).check(_Draft(), today=_TODAY)