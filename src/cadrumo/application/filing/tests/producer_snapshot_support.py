"""Shared resolvers, repositories and invoice builders for the ledger source-mesh tests."""

from decimal import Decimal

from cadrumo.core.prorrata_register import ProrrataRegisterRegime
from cadrumo.domain.deadlines.models import M303RegimeComposition, M303TaxTerritory

from ....core.casilla_id import validated_casilla_id
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ....domain.bienes_inversion.tests.explicit_parameters import params_for
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.m303_schema_vocabulary import (
    m303_regime_composition_simplified_scope,
)
from ....domain.deadlines.models import (
    ModeloIVAProfile,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from ....domain.modelos.calculation_revision_m303_handoff import M303FilingInstanceEvidence
from ....domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
)
from ...aggregation.m303_arrivals import (
    M303SupplierRegimeArrival,
    resolve_m303_prorrata_transition_arrival,
)
from ...calculations.tests.filing_evidence import regimen_simplificado_filing_evidence
from ..producer_snapshot import (
    FilingElectionFacts,
    M303FilingFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
)

TAXPAYER_TAX_ID = "12345678Z"


PRESENTER_TAX_ID = "00000000T"


def producer_snapshot_presenter() -> PresenterIdentity:
    return PresenterIdentity(tax_id=PRESENTER_TAX_ID, full_name="Gestoría Ejemplo")


def taxpayer_identity() -> TaxpayerIdentityFacts:
    return TaxpayerIdentityFacts(
        legal_name=None,
        given_name="María",
        surnames="García López",
        full_name="María García López",
    )


def elections(disposition: ResultDisposition) -> FilingElectionFacts:
    return FilingElectionFacts(
        result_disposition=disposition,
        payment=(
            PaymentElection.DOMICILIACION if disposition is ResultDisposition.DOMICILIACION else PaymentElection.INGRESO
        ),
        refund=RefundElection.COMPENSAR,
        prior_domiciliation=PriorDomiciliationElection.KEEP,
    )


def m303_profile() -> ModeloIVAProfile:
    return ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
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
    )


def _covered_prorrata_register(filing_year: int) -> ProrrataRegister:
    """A whole-entity register whose current ejercicio is explicitly declared."""
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=filing_year,
                regime=ProrrataRegisterRegime.from_registry("ninguna"),
                especial_transition=None,
                source_registry_snapshot_refs=(),
            ),
        ),
    )


def empty_m303_export_arrivals(
    filing_year: int,
) -> tuple[ProrrataRegister, BienesInversionIvaRegister, RegistroRegularizacionResult]:
    register = _covered_prorrata_register(filing_year)
    bienes_register = BienesInversionIvaRegister()
    regularisation = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={},
        parameters=params_for(filing_year),
    )
    return register, bienes_register, regularisation


def m303_filing_facts(
    *,
    filing_year: int = 2026,
    period_code: str = "4T",
    annual_volume_nonzero: bool = False,
) -> M303FilingFacts:
    period = Period.from_year_and_code(filing_year, period_code)
    register, bienes_register, regularisation = empty_m303_export_arrivals(period.filing_year)
    evidence = m303_instance_evidence(period)
    with bundled_indexed_authority().operation() as operation:
        prorrata_transition = resolve_m303_prorrata_transition_arrival(
            period=period, prorrata_register=register, operation=operation
        )
    return M303FilingFacts(
        joint_return_elected=False,
        annual_volume_nonzero=annual_volume_nonzero,
        insolvency=None,
        exonerado_390=m303_exonerado_390_evidence(applicable=False),
        regimen_simplificado=evidence.regimen_simplificado,
        regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
        period=period,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=False,
            source_ledger_ids=(),
        ),
        prorrata_transition=prorrata_transition,
        prorrata_register=register,
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=regularisation,
        bienes_parameters=params_for(filing_year),
    )


def m303_exonerado_390_evidence(*, applicable: bool) -> M303Exonerado390FilingEvidence:
    reference = FilingEvidenceReference(reference="test:producer-snapshot:exonerado-390")
    endpoints = (
        (
            M303Exonerado390EndpointEvidence(
                casilla_id=validated_casilla_id("79", surface="producer snapshot test"),
                value=Decimal("1.00"),
                evidence_reference=reference,
            ),
        )
        if applicable
        else ()
    )
    return M303Exonerado390FilingEvidence(
        applicable=applicable,
        applicability_reference=reference,
        endpoints=endpoints,
        activity_rows=(
            tuple(
                M303Exonerado390ActivityRowEvidence(
                    slot=slot,
                    codigo_actividad="A01",
                    epigrafe_iae=f"419{slot}",
                    evidence_reference=reference,
                )
                for slot in range(1, 7)
            )
            if applicable
            else ()
        ),
        operaciones_terceros_declarables=False if applicable else None,
        operaciones_terceros_reference=reference if applicable else None,
    )


def m303_instance_evidence(period: Period) -> M303FilingInstanceEvidence:
    with bundled_indexed_authority().operation() as operation:
        scope = M303RegimenSimplificadoScopeDecision(
            scope=m303_regime_composition_simplified_scope("general", authority=operation),
        )
        snapshot = resolve_m303_regimen_simplificado_snapshot(
            registry_snapshot=operation.snapshot(
                "303",
                filing_year=period.filing_year,
                period="1T",
            ),
            scope_decision=scope,
        )
        return M303FilingInstanceEvidence(
            period=period,
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=m303_exonerado_390_evidence(applicable=False),
            regimen_simplificado=regimen_simplificado_filing_evidence(
                period=period,
                scope_decision=scope,
                rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
                regimen_snapshot=snapshot,
                dana_eligibility=None,
                operation=operation,
            ),
        )
