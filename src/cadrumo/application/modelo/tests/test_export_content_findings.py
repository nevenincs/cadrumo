"""Verification blocks an XML return no file can be built from, and leaves other formats alone."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.deadlines.models import IVARegime

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..verification_revision_findings import collect_revision_verification_findings
from .advisory_diagnostic_repositories import EmptyTransactionCatalogueRepository
from .invoice_catalogue_fake import InvoiceCatalogueFake

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_T0 = datetime(1980, 1, 15, 12, 0, 0, tzinfo=UTC)
_KEY_PREFIX = "application.modelo.findings.xml_"


def _content_findings(modelo_code: str, period_code: str) -> list[ModeloVerificationFinding]:
    """Run the real revision verification for a filer whose profile holds no identity."""
    modelo = ModeloCode(modelo_code)
    with bundled_indexed_authority().operation() as operation:
        filing_year = max(
            year
            for year in operation.supported_filing_years().years
            if operation.reachable_authority_grade(modelo_code, filing_year=year, period=period_code)
            is RegistryAuthorityGrade.FILING
        )
        period = Period.from_year_and_code(filing_year, period_code)
        revision_id = str(operation.snapshot(modelo_code, filing_year=filing_year, period=period_code).revision.id)
        work_unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id="export-content",
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                revision_id=revision_id,
            ),
            bucket_id="export-content",
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
            name=f"{modelo_code}-{filing_year}-{period_code}",
            created_at=_T0,
            updated_at=_T0,
        )
        target = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=work_unit.work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
                filing_instance_evidence=None,
                source_provenance=(),
            ),
            work_unit_id=work_unit.work_unit_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo=modelo,
                revision_id=revision_id,
                modelo_year=filing_year,
                period=period_code,
            ),
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            casilla_values={},
            observations=(),
            created_at=_T0,
            updated_at=_T0,
            filing_instance_evidence=None,
            source_provenance=(),
        )
        findings, _resolved, _missing, failures = collect_revision_verification_findings(
            work_unit=work_unit,
            target=target,
            profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
            transaction_repository=EmptyTransactionCatalogueRepository(bucket_id=work_unit.bucket_id),
            invoice_repository=InvoiceCatalogueFake(),
            operation=operation,
            work_profile=None,
        )
    matching = [finding for finding in findings if finding.message_locale_key.startswith(_KEY_PREFIX)]
    assert all(failures[id(finding)].scenario_id.endswith("xml_return_content.refused") for finding in matching)
    return matching


def test_an_xml_return_with_no_identity_to_state_blocks_without_naming_a_box() -> None:
    (finding,) = _content_findings("100", "0A")

    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == "application.modelo.findings.xml_return_not_rendered"
    assert finding.casilla_id is None
    assert finding.message_facts == {}


def test_a_fixed_width_return_is_not_judged_by_this_check() -> None:
    assert _content_findings("200", "0A") == []
