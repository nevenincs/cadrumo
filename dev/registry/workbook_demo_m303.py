"""Fictional Modelo 303 facts passed through the ordinary backend contracts.

The published backend supplies the calculation implementation and pinned tax
sources. The authoring snapshot supplies the new presentation. Their simplified
regime authorities must agree before any saved evidence is attached to the demo.
No taxpayer profile is read and no registry generation is published here.
"""

from datetime import UTC, datetime
from decimal import Decimal

from cadrumo.application.aggregation.m303_arrivals import M303ProrrataTransitionArrival, M303SupplierRegimeArrival
from cadrumo.application.calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.prorrata_register import ProrrataRegisterRegime
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister, compute_registro_regularizacion
from cadrumo.domain.bienes_inversion.regularizacion_parameters import resolve_bienes_inversion_regularizacion_parameters
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from cadrumo.domain.calculations.registry.m303_schema_vocabulary import m303_regime_composition_simplified_scope
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.deadlines.models import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from cadrumo.domain.filing_evidence import FilingEvidenceReference
from cadrumo.domain.iva.regimen_simplificado_rows import (
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
)
from cadrumo.domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from cadrumo.domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry


def m303_demonstration_facts(snapshot: RegistrySnapshot) -> tuple[CalculationRevision, FilingProducerSnapshot]:
    """Build a general-regime example with annual facts only at year end."""
    if str(snapshot.modelo.id) != "303" or snapshot.period not in ("1T", "2T", "3T", "4T"):
        raise ValueError("Modelo 303 demonstration requires a quarterly filing period")
    year_end = snapshot.period == "4T"
    period = snapshot.filing_period
    if period is None:
        raise ValueError("Modelo 303 demonstration requires a dated filing period")
    reference = FilingEvidenceReference(reference="fictional:workbook-303:annual-activity")
    with bundled_indexed_authority().operation() as operation:
        scope = M303RegimenSimplificadoScopeDecision(
            scope=m303_regime_composition_simplified_scope("general", authority=operation)
        )
        regimen = resolve_m303_regimen_simplificado_snapshot(registry_snapshot=snapshot, scope_decision=scope)
        published = operation.snapshot("303", filing_year=snapshot.filing_year, period=str(snapshot.period))
        if regimen != resolve_m303_regimen_simplificado_snapshot(registry_snapshot=published, scope_decision=scope):
            raise ValueError("Modelo 303 demo backend and authored template use different tax authorities")
        rows = RegimenSimplificadoFilingRows(ejercicio=snapshot.filing_year, activities=())
        simplified = M303RegimenSimplificadoFilingEvidence(
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen,
            dana_eligibility=None,
            calculation_result=calculate_m303_regimen_simplificado_result(
                period=period,
                scope_decision=scope,
                rows=rows,
                regimen_snapshot=regimen,
                dana_eligibility=None,
                operation=operation,
            ),
        )
        annual = M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=reference,
            endpoints=(
                M303Exonerado390EndpointEvidence(casilla_id="80", value=Decimal("48000"), evidence_reference=reference),
            ),
            activity_rows=(
                M303Exonerado390ActivityRowEvidence(
                    slot=1, codigo_actividad="A01", epigrafe_iae="8612", evidence_reference=reference
                ),
            ),
            operaciones_terceros_declarables=False,
            operaciones_terceros_reference=reference,
        )
        envelope = FilingInstanceEvidence(
            m303=M303FilingInstanceEvidence(
                period=period,
                joint_return_elected=False,
                annual_volume_nonzero=True if year_end else None,
                insolvency=None,
                exonerado_390=annual if year_end else None,
                regimen_simplificado=simplified,
            )
        )
        parameters = resolve_bienes_inversion_regularizacion_parameters(
            snapshot.revision, modelo_id="303", filing_period_date=period.end_date
        )
        bienes = BienesInversionIvaRegister()
        regularisation = compute_registro_regularizacion(
            bienes,
            regularizacion_year=snapshot.filing_year,
            prorrata_definitiva_by_identifier={},
            parameters=parameters,
        )
        prorrata = ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=snapshot.filing_year,
                    regime=ProrrataRegisterRegime.from_registry("ninguna"),
                    especial_transition=None,
                    source_registry_snapshot_refs=(),
                ),
            )
        )
        facts = resolve_m303_filing_facts(
            evidence=envelope,
            supplier_regime=M303SupplierRegimeArrival(
                period=period, recipient_of_cash_accounting_operations=False, source_ledger_ids=()
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
            prorrata_register=prorrata,
            differentiated_contributions=(),
            bienes_register=bienes,
            regularisation_result=regularisation,
            bienes_parameters=parameters,
        )
        producer = build_filing_producer_snapshot(
            modelo=Modelo("303"),
            taxpayer_tax_id="12345678Z",
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None, given_name="Ana", surnames="Ejemplo", full_name="Ana Ejemplo · persona ficticia"
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Presentador ficticio"),
            model_profile=ModeloIVAProfile(
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
            ),
            elections=FilingElectionFacts(
                result_disposition=ResultDisposition.INGRESO,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=None,
            m303_filing_facts=facts,
            refund_account=None,
            charge_account=None,
        )
        work_id = sha256_hex(f"fictional-303-{snapshot.revision.id}-{snapshot.filing_year}-{snapshot.period}".encode())
        now = datetime.combine(period.end_date, datetime.min.time(), tzinfo=UTC)
        saved = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=work_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
                source_transaction_ids=(),
                filing_instance_evidence=envelope,
                source_provenance=(),
            ),
            work_unit_id=work_id,
            registry_snapshot_ref=snapshot.snapshot_ref,
            state=CalculationRevisionState.BORRADOR,
            created_at=now,
            updated_at=now,
            filing_instance_evidence=envelope,
            source_provenance=(),
        )
    return saved, producer
