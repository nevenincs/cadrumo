"""Unit tests for the FilingDraft ↔ Justificante reconciler.

Uses captured-live IRPF justificante PDFs (parsed at test time)
paired with synthetic FilingDraft fixtures to exercise every triad
branch. No network, no mocks — the tests confirm the compare actually
produces the right verdict for the shapes AEAT really emits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...justificante import Justificante
from .._schema import FilingDraft, FilingDraftStatus, FilingValue, FilingValueKind
from . import (
    FilingDivergenceKind,
    ReconciliationStatus,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXED_NOW = datetime(2026, 4, 24, 20, 0, 0, tzinfo=UTC)


def _make_draft(
    *,
    modelo: str = "100",
    period: str = "2023",
    profile_tax_id: str = "Y4113523X",
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
) -> FilingDraft:
    values = (
        FilingValue(
            casilla_id="01",
            value=Decimal("100.00"),
            kind=FilingValueKind.LITERAL,
            source="test",
            formula_trace=None,
        ),
    )
    return FilingDraft(
        draft_id="test-draft-00000000000000000000000000000000",
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        status=status,
        values=values,
        findings=(),
        created_at=_FIXED_NOW,
        updated_at=_FIXED_NOW,
        schema_version="2025.01",
        notes="",
    )


def _justificante_for(year: str) -> Justificante:
    """Parse one of the real IRPF captures under scratch/ if present."""
    from ...justificante import parse_justificante

    candidates = list(Path("scratch/recon-corpus").rglob(f"irpf-{year}/justificante.pdf"))
    if not candidates:
        pytest.skip(f"no live IRPF {year} capture under scratch/recon-corpus/")
    return parse_justificante(candidates[0])


class TestReconcileMatch:
    def test_matching_draft_reports_match(self) -> None:
        justificante = _justificante_for("2023")
        draft = _make_draft(
            modelo=justificante.modelo,
            period=justificante.period,
            profile_tax_id=justificante.tax_id,
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.MATCH
        assert report.mismatches == ()
        assert report.justificante is not None
        assert report.justificante.csv == justificante.csv
        assert report.reconciled_at == _FIXED_NOW
        assert report.mode == "read"


class TestReconcileNotYetFound:
    def test_none_justificante_reports_not_yet_found(self) -> None:
        draft = _make_draft()
        report = reconcile(draft, None, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.NOT_YET_FOUND
        assert report.justificante is None
        assert len(report.mismatches) == 1
        assert report.mismatches[0].kind is FilingDivergenceKind.FILING_NOT_YET_FOUND


class TestReconcileDivergent:
    def test_modelo_mismatch_surfaces(self) -> None:
        justificante = _justificante_for("2023")
        draft = _make_draft(
            modelo="303",  # wrong modelo
            period=justificante.period,
            profile_tax_id=justificante.tax_id,
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.DIVERGENT
        kinds = tuple(m.kind for m in report.mismatches)
        assert FilingDivergenceKind.MODELO_MISMATCH in kinds

    def test_tax_id_mismatch_surfaces(self) -> None:
        justificante = _justificante_for("2023")
        draft = _make_draft(
            modelo=justificante.modelo,
            period=justificante.period,
            profile_tax_id="X9999999Z",  # wrong NIE
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.DIVERGENT
        kinds = tuple(m.kind for m in report.mismatches)
        assert FilingDivergenceKind.TAX_ID_MISMATCH in kinds

    def test_tax_id_comparison_is_case_insensitive(self) -> None:
        justificante = _justificante_for("2023")
        draft = _make_draft(
            modelo=justificante.modelo,
            period=justificante.period,
            profile_tax_id=justificante.tax_id.lower(),
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.MATCH


class TestTriadIsExhaustive:
    """The three Kent-observable states cover every reconcile() outcome."""

    def test_status_values(self) -> None:
        assert {m.value for m in ReconciliationStatus} == {
            "match",
            "divergent",
            "not_yet_found",
        }
