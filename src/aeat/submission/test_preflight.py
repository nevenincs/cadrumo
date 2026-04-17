"""Unit tests for :class:`aeat.submission._preflight.Preflight`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

from . import (
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
    FilingFindingSeverity,
    LoadedCertificate,
    Preflight,
    SubmissionPreflightError,
)

pytestmark = pytest.mark.unit


@dataclass
class _Draft(FilingDraftLike):
    """Protocol-conforming test double for :class:`FilingDraftLike`.

    Written by hand per the project rule: real Protocol implementation,
    not a mock.
    """

    draft_id: str = "draft-1"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.READY_TO_SUBMIT
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


class _AlwaysOpenChecker:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return True


class _AlwaysClosedChecker:
    def is_window_open(self, modelo: str, period: str, today: date) -> bool:
        return False


class _OkCertBackend:
    def load(self) -> LoadedCertificate:
        return LoadedCertificate(
            subject="CN=Test",
            not_after=date(2099, 12, 31),
            fingerprint_sha256="a" * 64,
        )

    async def preload_into_browser_context(self, context: Any) -> None:
        return None


class _FailingCertBackend:
    def load(self) -> LoadedCertificate:
        raise RuntimeError("no smartcard")

    async def preload_into_browser_context(self, context: Any) -> None:
        return None


_TODAY = date(2026, 4, 10)


def _preflight(*, checker: Any | None = None, cert: Any | None = None) -> Preflight:
    return Preflight(
        deadline_checker=checker or _AlwaysOpenChecker(),
        cert_backend=cert or _OkCertBackend(),
    )


class TestPreflightGates:
    def test_happy_path_silent(self) -> None:
        _preflight().check(_Draft(), today=_TODAY)

    def test_gate_1_draft_not_ready(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="not ready"):
            _preflight().check(_Draft(status=DraftStatus.DRAFT), today=_TODAY)

    def test_gate_2_error_finding_blocks(self) -> None:
        findings = (
            FilingFinding(
                severity=FilingFindingSeverity.ERROR,
                message={"en": "bad", "es": "malo", "hu": "rossz"},
            ),
        )
        with pytest.raises(SubmissionPreflightError, match="ERROR-severity"):
            _preflight().check(_Draft(findings=findings), today=_TODAY)

    def test_gate_2_warning_does_not_block(self) -> None:
        findings = (
            FilingFinding(
                severity=FilingFindingSeverity.WARNING,
                message={"en": "warn", "es": "aviso", "hu": "figyelem"},
            ),
        )
        _preflight().check(_Draft(findings=findings), today=_TODAY)

    def test_gate_3_window_closed(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="deadline window"):
            _preflight(checker=_AlwaysClosedChecker()).check(_Draft(), today=_TODAY)

    def test_gate_4_cert_load_fails(self) -> None:
        with pytest.raises(SubmissionPreflightError, match="certificate"):
            _preflight(cert=_FailingCertBackend()).check(_Draft(), today=_TODAY)
