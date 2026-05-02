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

from ....adapters.inbound.justificante import parse_justificante
from ....core.config import PROJECT_ROOT
from ....domain.filing._schema import FilingDraft, FilingDraftStatus, FilingValue, FilingValueKind
from ....domain.justificante import Justificante
from ..testing import synthesize_filing_draft
from . import (
    FilingDivergenceKind,
    ReconciliationStatus,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


class TestReadOnlyReconcile:
    """End-to-end read-only check: synthesize_filing_draft + corpus PDF -> MATCH.

    This pins the full Kent-observable happy path entirely offline:
    a synthesised APPROVED FilingDraft for one of the committed
    sanitised fixtures, paired with parse_justificante() reading the
    same fixture's PDF, must reconcile to MATCH. Equivalent to the
    live ``aeat filing reconcile`` flow but with no AEAT round-trip.
    """

    @pytest.mark.parametrize(
        "modelo,ejercicio,period",
        [
            ("100", "2021", "0A"),
            ("100", "2022", "0A"),
            ("100", "2023", "0A"),
            ("130", "2024", "1T"),
            ("130", "2024", "4T"),
            ("303", "2024", "1T"),
            ("303", "2024", "4T"),
            ("390", "2023", "0A"),
        ],
    )
    def test_synthesised_draft_matches_committed_fixture(
        self,
        modelo: str,
        ejercicio: str,
        period: str,
    ) -> None:
        pdf_path = PROJECT_ROOT / "tests" / "fixtures" / "justificantes" / modelo / f"{ejercicio}-{period}.pdf"
        justificante = parse_justificante(pdf_path)
        # Build an APPROVED draft whose modelo/period/tax_id match
        # the parsed fixture exactly.
        draft = synthesize_filing_draft(
            modelo=modelo,
            period=period,
            profile_tax_id=justificante.tax_id,
            casilla_values={"01": Decimal("0")},
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.MATCH, (
            f"{modelo}/{ejercicio}-{period} did not MATCH: mismatches={report.mismatches}"
        )
        # The match path must produce a clean multilingual narrative.
        assert report.narrative.get("es")
        assert report.narrative.get("en")
        assert report.narrative.get("hu")

    def test_synthesised_draft_with_wrong_modelo_diverges(self) -> None:
        from ....adapters.inbound.justificante import parse_justificante
        from ....core.config import PROJECT_ROOT
        from ..testing import synthesize_filing_draft

        pdf_path = PROJECT_ROOT / "tests" / "fixtures" / "justificantes" / "100" / "2022-0A.pdf"
        justificante = parse_justificante(pdf_path)
        # Deliberately mismatch — draft says 130, fixture is 100.
        draft = synthesize_filing_draft(
            modelo="130",
            period="0A",
            profile_tax_id=justificante.tax_id,
            casilla_values={"01": Decimal("0")},
        )
        report = reconcile(draft, justificante, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.DIVERGENT
        assert any(m.kind is FilingDivergenceKind.MODELO_MISMATCH for m in report.mismatches)

    def test_no_justificante_reports_not_yet_found(self) -> None:
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )
        # Reconcile against None — simulates the AEAT-has-no-record path.
        report = reconcile(draft, None, now=_FIXED_NOW)
        assert report.status is ReconciliationStatus.NOT_YET_FOUND
        assert any(m.kind is FilingDivergenceKind.FILING_NOT_YET_FOUND for m in report.mismatches)
