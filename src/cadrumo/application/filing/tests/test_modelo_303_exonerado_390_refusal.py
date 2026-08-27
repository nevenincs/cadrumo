"""The incomplete M303 exonerado-390 unit refuses before byte emission."""

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
    validated_casilla_id,
)
from ....domain.bienes_inversion import BienesInversionIvaRegister, compute_registro_regularizacion
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.submission import ModeloDraftStatus
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ...aggregation import M303ProrrataTransitionArrival, M303SupplierRegimeArrival
from .. import (
    FilingElectionFacts,
    FilingProducerSnapshotError,
    M303FilingFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_draft,
    build_filing_producer_snapshot,
    build_runtime_schema_provider,
    export_draft,
)
from .._export import FilingExportError
from ..runtime import ModeloOperatorProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ENDPOINTS = frozenset(
    {
        "79",
        "80",
        "81",
        "83",
        "84",
        "86",
        "88",
        "89",
        "90",
        "91",
        "92",
        "93",
        "94",
        "95",
        "96",
        "97",
        "98",
        "99",
        "107",
        "125",
        "126",
        "127",
        "128",
    }
)


def _general_m303_scope() -> M303RegimenSimplificadoScopeDecision:
    return M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )


def _exonerado_evidence() -> M303Exonerado390FilingEvidence:
    reference = FilingEvidenceReference(reference="test:exonerado-390:all-endpoints")
    return M303Exonerado390FilingEvidence(
        applicable=True,
        applicability_reference=reference,
        endpoints=tuple(
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id(endpoint, surface="exonerado refusal test"),
                value=Decimal("0"),
                evidence_reference=reference,
            )
            for endpoint in sorted(_ENDPOINTS)
        ),
        activity_rows=(
            M303Exonerado390ActivityRowEvidence(
                slot=1,
                codigo_actividad="A01",
                epigrafe_iae="4191",
                evidence_reference=reference,
            ),
        ),
        operaciones_terceros_declarables=False,
        operaciones_terceros_reference=reference,
    )


def _regimen_evidence(period: Period) -> M303RegimenSimplificadoFilingEvidence:
    scope = _general_m303_scope()
    return regimen_simplificado_filing_evidence(
        period=period,
        scope_decision=scope,
        rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
        regimen_snapshot=resolve_m303_regimen_simplificado_snapshot(
            registry_snapshot=bundled_authority().snapshot(
                "303",
                filing_year=period.filing_year,
                period=period.code,
            ),
            scope_decision=scope,
        ),
        dana_2024_eligibility=None,
    )


def test_exonerado_complete_revision_evidence_reaches_withdrawn_layout_without_override(tmp_path: Path) -> None:
    """Persisted A28 facts need no caller-authored export applicability envelope."""
    period = Period.from_year_and_code(2025, "4T")
    provider = build_runtime_schema_provider(filing_year=2025, period=period, modelos=("303",))
    inputs = {
        "07": Decimal("0"),
        "iva.soportado.interiores": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **{endpoint: Decimal("0") for endpoint in _ENDPOINTS},
    }
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Exonerado refusal proof"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    # A final period must state the year's prorrata regime explicitly: the
    # register must not turn an absent declaration into "no transition". This
    # taxpayer performs only deduction-granting operations, so NINGUNA (the LIVA
    # art. 94 full-deduction default) is the truthful whole-entity declaration.
    register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=period.filing_year,
                regime=ProrrataRegisterRegime.NINGUNA,
                especial_transition=None,
            ),
        ),
    )
    bienes_register = BienesInversionIvaRegister()
    regimen_evidence = _regimen_evidence(period)
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
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=_exonerado_evidence(),
            regimen_simplificado=regimen_evidence,
            regimen_simplificado_result=regimen_evidence.calculation_result,
            period=period,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
                source_ledger_ids=(),
            ),
            prorrata_transition=M303ProrrataTransitionArrival(
                period=period,
                transition=None,
                register_evidence=(),
            ),
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
    output = tmp_path / "modelo-303-exonerado.txt"

    with pytest.raises(FilingExportError, match="local declaration export is unsupported"):
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=producer_snapshot,
            schema_provider=provider,
        )

    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".tmp").exists()


def test_exonerado_numeric_payload_refuses_before_target_while_atomic_unit_is_incomplete(tmp_path: Path) -> None:
    """An incomplete M303 producer snapshot fails before an artifact can be emitted."""
    output = tmp_path / "modelo-303-exonerado.txt"

    with pytest.raises(FilingProducerSnapshotError, match="modelo 303 requires complete M303FilingFacts"):
        build_filing_producer_snapshot(
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
                roi_enrolled=False,
                oss_enrolled=False,
                group_member_enrolled=False,
                group_dominant_entity_enrolled=False,
                intracommunity_operations_exceed_50000_eur=False,
                sii_enrolled=False,
                redeme_enrolled=False,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
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
            m303_filing_facts=None,
        )

    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".tmp").exists()
