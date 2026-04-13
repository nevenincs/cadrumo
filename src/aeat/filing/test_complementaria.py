"""Unit tests for the filing complementaria / amendment engine."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.filing import (
    QUARTERLY_303_INPUT_KEY,
    AmendmentKind,
    FilingAmendmentValidationError,
    FilingDraft,
    build_complementaria,
    build_draft,
    list_amendments,
    load_amendment,
)
from aeat.filing.testing import SyntheticProfile, default_schema_provider
from aeat.submission import SubmissionAttempt, SubmissionStatus, SubmittedFiling

pytestmark = pytest.mark.unit


def _profile(*modelos: str) -> SyntheticProfile:
    return SyntheticProfile(
        tax_id="00000000T",
        display_name="Synthetic amendment test profile",
        applicable_modelos=modelos,
    )


def _persist_original_draft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, draft: FilingDraft) -> None:
    drafts_dir = tmp_path / "drafts"
    submissions_dir = tmp_path / "submissions"
    drafts_dir.mkdir()
    submissions_dir.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(drafts_dir))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(submissions_dir))
    target = drafts_dir / f"{draft.modelo}_{draft.period}_{draft.draft_id}.json"
    target.write_text(draft.model_dump_json(indent=2), encoding="utf-8")


def _submitted_filing(draft: FilingDraft, *, submission_id: str = "sub-1") -> SubmittedFiling:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    return SubmittedFiling(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.SUBMITTED,
        justificante_csv=f"CSV-{submission_id}",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.SUBMITTED,
            ),
        ),
    )


def _build_130_draft(*, ingresos: str, gastos: str = "3500.00", retenciones: str = "400.00") -> FilingDraft:
    return build_draft(
        modelo="130",
        period="2024Q1",
        profile=_profile("130"),
        inputs={
            "01": Decimal(ingresos),
            "02": Decimal(gastos),
            "05": Decimal(retenciones),
            "06": Decimal("0.00"),
        },
        schema_provider=default_schema_provider(),
    )


def _build_303_draft(*, period: str, base_21: str, deducible_29: str = "200.00") -> FilingDraft:
    return build_draft(
        modelo="303",
        period=period,
        profile=_profile("303", "390"),
        inputs={
            "07": Decimal(base_21),
            "29": Decimal(deducible_29),
        },
        schema_provider=default_schema_provider(),
    )


def _build_390_draft(*, year: int, quarterly: tuple[FilingDraft, ...]) -> FilingDraft:
    return build_draft(
        modelo="390",
        period=str(year),
        profile=_profile("303", "390"),
        inputs={"01": year, QUARTERLY_303_INPUT_KEY: quarterly},
        schema_provider=default_schema_provider(),
    )


class TestBuildComplementaria:
    def test_modelo_130_delta_computation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _build_130_draft(ingresos="12500.00")
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft)

        amendment = build_complementaria(
            original,
            {
                "01": Decimal("13000.00"),
                "02": Decimal("3500.00"),
                "05": Decimal("400.00"),
                "06": Decimal("0.00"),
                "_reasons": {"01": "Late income invoice received after original filing."},
            },
        )

        by_casilla = {change.casilla_code: change for change in amendment.delta}
        assert amendment.amendment_kind is AmendmentKind.COMPLEMENTARIA
        assert by_casilla["01"].old_value == Decimal("12500.00")
        assert by_casilla["01"].new_value == Decimal("13000.00")
        assert by_casilla["01"].reason == "Late income invoice received after original filing."
        assert by_casilla["07"].old_value == Decimal("1400.0000")
        assert by_casilla["07"].new_value == Decimal("1500.0000")
        assert load_amendment(amendment.amendment_id) == amendment
        assert list_amendments(modelo="130") == (amendment,)

    def test_complementaria_cannot_reduce_liability(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        original_draft = _build_130_draft(ingresos="12500.00")
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-reduce")

        with pytest.raises(FilingAmendmentValidationError, match="cannot reduce liability"):
            build_complementaria(
                original,
                {
                    "01": Decimal("12000.00"),
                    "02": Decimal("3500.00"),
                    "05": Decimal("400.00"),
                    "06": Decimal("0.00"),
                },
            )

    def test_modelo_303_pre_rectificativa_is_complementaria(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        original_draft = _build_303_draft(period="2024Q2", base_21="10000.00")
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-303")

        amendment = build_complementaria(
            original,
            {
                "07": Decimal("11000.00"),
                "29": Decimal("200.00"),
                "_reasons": {"07": "Additional taxable turnover discovered during closing review."},
            },
        )

        by_casilla = {change.casilla_code: change for change in amendment.delta}
        assert amendment.amendment_kind is AmendmentKind.COMPLEMENTARIA
        assert by_casilla["69"].old_value is not None
        assert by_casilla["69"].new_value > by_casilla["69"].old_value

    def test_modelo_390_builds_sustitutiva(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        quarterly_original = tuple(
            _build_303_draft(period=f"2024Q{quarter}", base_21="10000.00") for quarter in (1, 2, 3, 4)
        )
        original_draft = _build_390_draft(year=2024, quarterly=quarterly_original)
        _persist_original_draft(monkeypatch, tmp_path, original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-390")

        quarterly_updated = (
            _build_303_draft(period="2024Q1", base_21="10000.00"),
            _build_303_draft(period="2024Q2", base_21="11000.00"),
            _build_303_draft(period="2024Q3", base_21="10000.00"),
            _build_303_draft(period="2024Q4", base_21="10000.00"),
        )
        amendment = build_complementaria(
            original,
            {
                "01": 2024,
                QUARTERLY_303_INPUT_KEY: quarterly_updated,
                "_reasons": {"109": "Annual total updated after revising Q2 quarterly VAT return."},
            },
        )

        assert amendment.amendment_kind is AmendmentKind.SUSTITUTIVA
        assert any(change.casilla_code == "109" for change in amendment.delta)
