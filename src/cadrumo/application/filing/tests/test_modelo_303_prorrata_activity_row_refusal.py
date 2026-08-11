"""Applicable Modelo 303 prorrata rows fail before target creation."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    ProrrataRegisterRegime,
    RefundElection,
    ResultDisposition,
)
from ....core.resources import resources
from ....domain.bienes_inversion import BienesInversionIvaRegister, compute_registro_regularizacion
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ....domain.filing import FilingExportError
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import M303Exonerado390FilingEvidence, M303RegimenSimplificadoFilingEvidence
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.submission import ModeloDraftStatus
from ...aggregation import M303ProrrataTransitionArrival, M303SupplierRegimeArrival
from .. import (
    FilingElectionFacts,
    M303FilingFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
    export_draft,
)
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m303_general_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _regimen_evidence(period: Period) -> M303RegimenSimplificadoFilingEvidence:
    scope = _m303_general_scope()
    return M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
        regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
            registry_snapshot=resources().modelos.authority.snapshot(
                "303",
                filing_year=period.filing_year,
                period=period.code,
            ),
            scope_decision=scope,
        ),
    )


def test_applicable_prorrata_without_all_five_rows_refuses_before_layout_or_target(tmp_path: Path) -> None:
    """The typed register gate runs before the withdrawn M303 layout can mask it."""
    period = Period.from_year_and_code(2025, "4T")
    provider = build_runtime_schema_provider(filing_year=2025, period=period, modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Prorrata row refusal proof"),
        inputs={
            "07": Decimal("0"),
            "iva.soportado.interiores": Decimal("0"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
        m303_regimen_simplificado_scope=_m303_general_scope(),
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    register = ProrrataRegister(
        entries=(ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.GENERAL),),
    )
    bienes_register = BienesInversionIvaRegister()
    producer_snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None,
            given_name="Ana",
            surnames="Prueba",
            full_name="Ana Prueba",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.COMMON_REGIME,
            regime_composition=M303RegimeComposition.GENERAL,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            roi_enrolled=False,
            oss_enrolled=False,
            group_member_enrolled=False,
            group_dominant_entity_enrolled=False,
            intracommunity_operations_exceed_50000_eur=False,
            sii_enrolled=False,
            redeme_enrolled=False,
        ),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=M303FilingFacts(
            joint_return_elected=False,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=FilingEvidenceReference(reference="test:prorrata:exonerado-390"),
            ),
            regimen_simplificado=_regimen_evidence(period),
            period=period,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=compute_registro_regularizacion(
                bienes_register,
                regularizacion_year=period.filing_year,
                prorrata_definitiva_by_identifier={},
            ),
        ),
    )
    output = tmp_path / "modelo-303-prorrata-row-refusal.txt"

    with pytest.raises(FilingExportError, match="per-activity prorrata rows are incomplete"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=producer_snapshot,
            schema_provider=provider,
        )

    assert not output.exists()
