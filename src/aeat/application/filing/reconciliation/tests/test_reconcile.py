"""Tests for registry-gated ModeloDraft to Justificante reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl

from .....adapters.inbound.justificante import parse_justificante
from .....core import Period
from .....domain.filing import ModeloBuilderError, ModeloDraft
from .....domain.justificante import Justificante
from .....domain.submission import ModeloDraftStatus
from .....tests import FIXTURES_DIR
from .....tests.aeat_literal_fixtures import justificante_cotejo_url
from ... import build_runtime_schema_provider
from ...runtime import RegistrySchemaProvider
from ...testing import build_registry_filing_draft
from .. import (
    ModeloDivergenceKind,
    ReconciliationStatus,
    reconcile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_FIXED_NOW = datetime(2026, 4, 24, 20, 0, 0, tzinfo=UTC)
_MODELO_130_INPUTS = {
    "01": Decimal("12500.00"),
    "02": Decimal("3500.00"),
    "05": Decimal("250"),
    "06": Decimal("100"),
    "08": Decimal("2000"),
    "10": Decimal("10"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}
_MODELO_130_BINDINGS = {
    "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
    "modelo-130-resultados-negativos-anteriores": Decimal("0"),
}
_MODELO_111_INPUTS = {
    "03": Decimal("180.25"),
    "06": Decimal("12.10"),
    "09": Decimal("300.00"),
    "12": Decimal("14.40"),
    "15": Decimal("25.00"),
    "18": Decimal("0.50"),
    "21": Decimal("7.00"),
    "24": Decimal("8.00"),
    "27": Decimal("9.00"),
    "29": Decimal("40.00"),
}
_MODELO_123_INPUTS = {
    "01": Decimal("2"),
    "02": Decimal("3"),
    "04": Decimal("1000.25"),
    "05": Decimal("200.75"),
    "07": Decimal("190.05"),
    "08": Decimal("38.14"),
    "10": Decimal("0"),
    "11": Decimal("7.50"),
    "13": Decimal("12.25"),
}
_P_2024_Q1 = Period.from_year_and_code(2024, "1T")
_P_2024_Q4 = Period.from_year_and_code(2024, "4T")
_P_2026_Q1 = Period.from_year_and_code(2026, "1T")


def _provider_for(draft: ModeloDraft) -> RegistrySchemaProvider:
    assert draft.snapshot_ref is not None
    return build_runtime_schema_provider(
        modelos=(draft.modelo,),
        filing_year=draft.snapshot_ref.modelo_year,
        period=Period.from_year_and_code(draft.snapshot_ref.modelo_year, draft.snapshot_ref.period),
    )


def _draft_for_130(
    *,
    period: Period = _P_2024_Q1,
    profile_tax_id: str = "12345678Z",
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
) -> ModeloDraft:
    return build_registry_filing_draft(
        modelo="130",
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=_MODELO_130_INPUTS,
        binding_values=_MODELO_130_BINDINGS,
        status=status,
    )


def _draft_for_111(
    *,
    period: Period = _P_2026_Q1,
    profile_tax_id: str = "12345678Z",
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
) -> ModeloDraft:
    return build_registry_filing_draft(
        modelo="111",
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=_MODELO_111_INPUTS,
        status=status,
    )


def _draft_for_123(
    *,
    period: Period = _P_2026_Q1,
    profile_tax_id: str = "12345678Z",
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
) -> ModeloDraft:
    return build_registry_filing_draft(
        modelo="123",
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=_MODELO_123_INPUTS,
        status=status,
    )


def _justificante(modelo: str, label: str) -> Justificante:
    return parse_justificante(FIXTURES_DIR / "justificantes" / modelo / f"{label}.pdf")


def _justificante_record(
    *,
    modelo: str,
    period: str,
    ejercicio: str,
    tax_id: str,
    total_a_ingresar: Decimal | None = None,
    total_a_devolver: Decimal | None = None,
) -> Justificante:
    return Justificante(
        csv="SANITIZEDCSV111",
        modelo=modelo,
        period=period,
        ejercicio=ejercicio,
        presentation_id="1114264149320",
        presented_at=_FIXED_NOW,
        tax_id=tax_id,
        total_a_ingresar=total_a_ingresar,
        total_a_devolver=total_a_devolver,
        verification_url=AnyHttpUrl(justificante_cotejo_url("SANITIZEDCSV111")),
        source_pdf_path=FIXTURES_DIR / "justificantes" / modelo / "synthetic.pdf",
        source_pdf_sha256="a" * 64,
        parsed_at=_FIXED_NOW,
    )


class TestReconcileMatch:
    def test_matching_modelo_130_fixture_reports_match(self) -> None:
        justificante = _justificante("130", "2024-1T")
        draft = _draft_for_130(
            period=_P_2024_Q1,
            profile_tax_id=justificante.tax_id,
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.COINCIDE
        assert report.mismatches == ()
        assert report.justificante is not None
        assert report.justificante.csv == justificante.csv
        assert report.draft_ref.period == _P_2024_Q1
        assert report.reconciled_at == _FIXED_NOW
        assert report.mode == "read"

    def test_quarter_period_normalization_uses_justificante_year(self) -> None:
        justificante = _justificante("130", "2024-4T")
        draft = _draft_for_130(
            period=_P_2024_Q4,
            profile_tax_id=justificante.tax_id,
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.COINCIDE

    def test_modelo_111_total_to_ingresar_is_projected_from_registry_casilla(self) -> None:
        draft = _draft_for_111()
        justificante = _justificante_record(
            modelo="111",
            period="1T",
            ejercicio="2026",
            tax_id=draft.profile_tax_id,
            total_a_ingresar=Decimal("516.25"),
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.COINCIDE

    def test_modelo_123_total_to_ingresar_is_projected_from_registry_casilla(self) -> None:
        draft = _draft_for_123()
        justificante = _justificante_record(
            modelo="123",
            period="1T",
            ejercicio="2026",
            tax_id=draft.profile_tax_id,
            total_a_ingresar=Decimal("223.44"),
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.COINCIDE

    def test_year_only_remote_period_does_not_match_quarterly_revision(self) -> None:
        justificante = _justificante("130", "2024-1T").model_copy(update={"period": "2024"})
        draft = _draft_for_130(
            period=_P_2024_Q1,
            profile_tax_id=justificante.tax_id,
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.DIVERGENTE
        assert any(mismatch.kind is ModeloDivergenceKind.PERIOD_MISMATCH for mismatch in report.mismatches)


class TestReconcileNotYetFound:
    def test_none_justificante_reports_not_yet_found(self) -> None:
        draft = _draft_for_130()

        report = reconcile(draft, None, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.NOT_YET_FOUND
        assert report.justificante is None
        assert len(report.mismatches) == 1
        assert report.mismatches[0].kind is ModeloDivergenceKind.FILING_NOT_YET_FOUND


class TestReconcileDivergent:
    def test_modelo_mismatch_surfaces(self) -> None:
        justificante = _justificante("100", "2022-0A")
        draft = _draft_for_130(profile_tax_id=justificante.tax_id)

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        kinds = tuple(m.kind for m in report.mismatches)
        assert report.status is ReconciliationStatus.DIVERGENTE
        assert ModeloDivergenceKind.MODELO_MISMATCH in kinds

    def test_tax_id_mismatch_surfaces(self) -> None:
        justificante = _justificante("130", "2024-1T")
        draft = _draft_for_130(period=_P_2024_Q1, profile_tax_id="12345678Z")

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        kinds = tuple(m.kind for m in report.mismatches)
        assert report.status is ReconciliationStatus.DIVERGENTE
        assert ModeloDivergenceKind.TAX_ID_MISMATCH in kinds

    def test_tax_id_comparison_is_case_insensitive(self) -> None:
        justificante = _justificante("130", "2024-1T")
        draft = _draft_for_130(
            period=_P_2024_Q1,
            profile_tax_id=justificante.tax_id.lower(),
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.COINCIDE

    def test_modelo_111_total_to_ingresar_drift_surfaces(self) -> None:
        draft = _draft_for_111()
        justificante = _justificante_record(
            modelo="111",
            period="1T",
            ejercicio="2026",
            tax_id=draft.profile_tax_id,
            total_a_ingresar=Decimal("516.27"),
        )

        report = reconcile(draft, justificante, schema_provider=_provider_for(draft), now=_FIXED_NOW)

        assert report.status is ReconciliationStatus.DIVERGENTE
        assert any(mismatch.kind is ModeloDivergenceKind.TOTAL_INGRESAR_MISMATCH for mismatch in report.mismatches)


class TestRegistryGate:
    def test_reconcile_requires_active_registry_snapshot(self) -> None:
        draft = _draft_for_130().model_copy(update={"schema_version": "registry:130:wrong-revision"})

        with pytest.raises(ModeloBuilderError, match="active registry snapshot"):
            reconcile(draft, None, schema_provider=_provider_for(draft), now=_FIXED_NOW)

    def test_reconcile_requires_period_declared_by_registry_snapshot(self) -> None:
        # Inject an annual period into a quarterly draft to force the registry gate.
        annual_period = Period.from_year_and_code(2024, "0A")
        draft = _draft_for_130().model_copy(update={"period": annual_period})

        with pytest.raises(ModeloBuilderError, match="draft period declared"):
            reconcile(draft, None, schema_provider=_provider_for(draft), now=_FIXED_NOW)
