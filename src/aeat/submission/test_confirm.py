"""Unit tests for the internal live-submit confirmation hook."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

import pytest

from aeat.submission import (
    AeatLiveSubmitConfirmationRefusedError,
    AeatPytestLiveWriteRefusedError,
    DraftStatus,
    FilingDraftLike,
    FilingFinding,
)
from aeat.submission._confirm import confirm_live_submission

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Draft(FilingDraftLike):
    draft_id: str = "draft-confirm"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.READY_TO_SUBMIT
    values: dict[str, str] = field(default_factory=dict)
    findings: tuple[FilingFinding, ...] = ()


def test_confirm_refuses_under_pytest() -> None:
    with pytest.raises(AeatPytestLiveWriteRefusedError):
        confirm_live_submission(
            draft=_Draft(),
            draft_checksum_sha256="a" * 64,
            stdin=StringIO("CONFIRMO FILING 130 2026Q1\n"),
            stderr=StringIO(),
        )


def test_confirm_requires_exact_phrase(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    del tmp_path  # unused but keeps fixture symmetry with nearby suites
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    stderr = StringIO()
    with pytest.raises(AeatLiveSubmitConfirmationRefusedError):
        confirm_live_submission(
            draft=_Draft(),
            draft_checksum_sha256="b" * 64,
            stdin=StringIO("almost but not exact\n"),
            stderr=stderr,
        )
    rendered = stderr.getvalue()
    assert "draft_checksum_sha256=" in rendered
    assert "CONFIRMO FILING 130 2026Q1" in rendered
