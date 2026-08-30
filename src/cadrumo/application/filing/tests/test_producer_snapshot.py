"""Real public-surface tests for typed filing producer snapshots."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import (
    STR_KEYED_MAPPING_ADAPTER,
    FilingProducerKey,
    Modelo,
    PaymentElection,
    Period,
    PriorDomiciliationElection,
    ProrrataEspecialTransitionKind,
    ProrrataRegisterRegime,
    RefundElection,
    ResultDisposition,
    validated_casilla_id,
)
from ....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionKind,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines.models import ChargeAccount, IVARegime, M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ....domain.filing.schema import ModeloDraft, compute_modelo_draft_id, registry_schema_version
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision, RegimenSimplificadoFilingRows
from ....domain.modelos.calculation_revision import (
    CalculationRevisionAmendmentKind,
    FilingInstanceEvidence,
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
)
from ....domain.prorrata_register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
)
from ....domain.submission import ModeloDraftStatus
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ...aggregation import (
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
    resolve_m303_prorrata_transition_arrival,
)
from .. import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingElectionFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M202UnsupportedProducerId,
    M303FilingFacts,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    Modelo202ActivityFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    RefundAccountSelection,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from .. import __init__ as filing
from .._export import (
    _complementaria_page_marker,
    _filing_producer_values,
    _m303_complementaria_marker,
    _m303_no_activity_marker,
)
from .._export_producer import m303_profile_lexicals

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAXPAYER_TAX_ID = "12345678Z"
_PRESENTER_TAX_ID = "00000000T"
_CHARGE_IBAN = "ES9121000418450200051332"
_REFUND_IBAN = "GB82WEST12345698765432"
_M303_2026_IR_SHA256 = "0be8b156da2250c6b11f6253e0165221ed2e549ec4c65a562021bec6b9b8489b"


def _presenter() -> PresenterIdentity:
    return PresenterIdentity(tax_id=_PRESENTER_TAX_ID, full_name="Gestoría Ejemplo")


def _taxpayer_identity() -> TaxpayerIdentityFacts:
    return TaxpayerIdentityFacts(
        legal_name=None,
        given_name="María",
        surnames="García López",
        full_name="María García López",
    )


def _elections(disposition: ResultDisposition) -> FilingElectionFacts:
    return FilingElectionFacts(
        result_disposition=disposition,
        payment=(
            PaymentElection.DOMICILIACION if disposition is ResultDisposition.DOMICILIACION else PaymentElection.INGRESO
        ),
        refund=RefundElection.COMPENSAR,
        prior_domiciliation=PriorDomiciliationElection.KEEP,
    )


def _m303_profile() -> ModeloIVAProfile:
    return ModeloIVAProfile(
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
    )


def _marker_draft() -> ModeloDraft:
    """Provide the typed draft context required by computed marker producers."""
    period = Period.from_year_and_code(2025, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2025-y-siguientes",
        modelo_year=2025,
        period="1T",
    )
    values = ()
    return ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="303",
            period=period,
            profile_tax_id=_TAXPAYER_TAX_ID,
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo="303",
        period=period,
        profile_tax_id=_TAXPAYER_TAX_ID,
        subject_tax_id=_TAXPAYER_TAX_ID,
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        schema_version=registry_schema_version(modelo="303", revision_id="2025-y-siguientes"),
    )


def _covered_prorrata_register(filing_year: int) -> ProrrataRegister:
    """A whole-entity register whose current ejercicio is explicitly declared."""
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=filing_year,
                regime=ProrrataRegisterRegime.NINGUNA,
                especial_transition=None,
            ),
        ),
    )


def _empty_m303_export_arrivals(
    filing_year: int,
) -> tuple[ProrrataRegister, BienesInversionIvaRegister, RegistroRegularizacionResult]:
    register = _covered_prorrata_register(filing_year)
    bienes_register = BienesInversionIvaRegister()
    regularisation = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={},
    )
    return register, bienes_register, regularisation


def _bien_inversion(identifier: str) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description=f"Bien de inversión {identifier}",
        acquisition_year=2024,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("70"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id=f"ledger:{identifier}",
    )


def _m303_filing_facts_payload(
    *,
    bienes_register: BienesInversionIvaRegister,
    regularisation_result: RegistroRegularizacionResult,
) -> dict[str, object]:
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_m303_filing_facts().model_dump())
    payload["bienes_register"] = bienes_register.model_dump()
    payload["regularisation_result"] = regularisation_result.model_dump()
    return payload


def _m303_filing_facts(
    *,
    filing_year: int = 2026,
    period_code: str = "4T",
    annual_volume_nonzero: bool = False,
) -> M303FilingFacts:
    period = Period.from_year_and_code(filing_year, period_code)
    register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    evidence = _m303_instance_evidence(period)
    return M303FilingFacts(
        joint_return_elected=False,
        annual_volume_nonzero=annual_volume_nonzero,
        insolvency=None,
        exonerado_390=_m303_exonerado_evidence(applicable=False),
        regimen_simplificado=evidence.regimen_simplificado,
        regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
        period=period,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=False,
            source_ledger_ids=(),
        ),
        prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
        prorrata_register=register,
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=regularisation,
    )


def _m303_exonerado_evidence(*, applicable: bool) -> M303Exonerado390FilingEvidence:
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


def _m303_instance_evidence(period: Period) -> M303FilingInstanceEvidence:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot(
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
        exonerado_390=_m303_exonerado_evidence(applicable=False),
        regimen_simplificado=regimen_simplificado_filing_evidence(
            period=period,
            scope_decision=scope,
            rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
            regimen_snapshot=snapshot,
            dana_2024_eligibility=None,
        ),
    )


def _m303_prorrata_transition_arrival(
    transition: ProrrataEspecialTransitionKind,
) -> tuple[M303ProrrataTransitionArrival, ProrrataRegister]:
    period = Period.from_year_and_code(2026, "4T")
    entry = ProrrataRegisterEntry(
        ejercicio=period.filing_year,
        regime=(
            ProrrataRegisterRegime.ESPECIAL
            if transition is ProrrataEspecialTransitionKind.OPCION
            else ProrrataRegisterRegime.GENERAL
        ),
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=transition,
            evidence_reference=f"modelo-303-2026-prorrata-{transition.value}",
        ),
    )
    prior_entries = (
        (
            ProrrataRegisterEntry(
                ejercicio=2025,
                regime=ProrrataRegisterRegime.ESPECIAL,
                especial_transition=None,
            ),
        )
        if transition is ProrrataEspecialTransitionKind.REVOCACION
        else ()
    )
    register = ProrrataRegister(entries=(*prior_entries, entry))
    arrival = resolve_m303_prorrata_transition_arrival(period=period, prorrata_register=register)
    return arrival, register


def _m303_foral_snapshot(
    *,
    prorrata_transition: M303ProrrataTransitionArrival,
    prorrata_register: ProrrataRegister | None = None,
) -> FilingProducerSnapshot:
    period = prorrata_transition.period
    default_register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    register = default_register if prorrata_register is None else prorrata_register
    evidence = _m303_instance_evidence(period)
    facts = M303FilingFacts(
        joint_return_elected=True,
        annual_volume_nonzero=False,
        insolvency=M303InsolvencyFilingFact(
            judicial_order_date=date(2026, 8, 11),
            subtype=M303InsolvencyFilingSubtype.POST_ORDER,
        ),
        exonerado_390=_m303_exonerado_evidence(applicable=True),
        regimen_simplificado=evidence.regimen_simplificado,
        regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
        period=period,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=True,
            source_ledger_ids=("foral-supplier-regime-ledger",),
        ),
        prorrata_transition=prorrata_transition,
        prorrata_register=register,
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=regularisation,
    )
    profile = _m303_profile().model_copy(
        update={
            "tax_territory": M303TaxTerritory.FORAL,
            "regime_composition": M303RegimeComposition.MIXED,
            "redeme_enrolled": True,
            "cash_accounting_regime_enrolled": True,
            "voluntary_sii_enrolled": True,
            "hydrocarbon_deposit_advance_payment_deduction_entitled": True,
        },
    )
    return build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=profile,
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )


def test_presenter_is_required_and_never_derived_from_taxpayer() -> None:
    presenter = _presenter()
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=presenter,
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    assert snapshot.presenter.tax_id == _PRESENTER_TAX_ID
    assert snapshot.taxpayer_tax_id == _TAXPAYER_TAX_ID
    producer_values = _filing_producer_values(snapshot)
    assert producer_values[FilingProducerKey.PRESENTER_TAX_ID] == _PRESENTER_TAX_ID
    assert producer_values[FilingProducerKey.TAXPAYER_TAX_ID] == _TAXPAYER_TAX_ID
    with pytest.raises(ValidationError, match="frozen"):
        snapshot.presenter.__setattr__("full_name", "Mutated")


def test_taxpayer_name_facts_are_required_and_not_derived_from_presenter() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    assert snapshot.taxpayer_identity.full_name == "María García López"
    assert snapshot.taxpayer_identity.full_name != snapshot.presenter.full_name


def test_modelo_111_unknown_profile_fact_refuses_snapshot_but_false_is_valid() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="colegio_concertado"):
        build_filing_producer_snapshot(
            modelo=Modelo.M111,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            presenter=_presenter(),
            model_profile=Modelo111ProfileFacts(colegio_concertado=None),
            elections=_elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )


def test_modelo_202_exact_unsupported_inventory_includes_no_silent_filler() -> None:
    expected = (
        M202UnsupportedProducerId.PRINCIPAL_CNAE,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_122,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_123,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_124,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_125,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_126,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_127,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_128,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_129,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_130,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_131,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_132,
        M202UnsupportedProducerId.OFFICIAL_OFFSET_147,
    )
    assert expected == M202_UNSUPPORTED_PRODUCER_IDS


def test_modelo_202_uses_canonical_taxpayer_profile_without_scalarising_repeatable_cnae() -> None:
    taxpayer_profile = TaxpayerProfile(
        tax_id=_TAXPAYER_TAX_ID,
        iva=_m303_profile(),
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("999999.99"),
        ley_49_2002_special_regime_option_declared=True,
        ley_49_2002_special_regime_option_date=date(2025, 1, 1),
        ley_49_2002_special_regime_renunciation_declared=False,
        ley_49_2002_special_regime_renunciation_date=date(2026, 1, 1),
    )
    facts = Modelo202ProducerProfile(
        taxpayer_profile=taxpayer_profile,
        activities=(Modelo202ActivityFacts(cnae="6201"), Modelo202ActivityFacts(cnae="6202")),
    )
    assert Modelo202ProducerProfile.model_validate_json(facts.model_dump_json()) == facts
    assert facts.taxpayer_profile is taxpayer_profile
    assert tuple(activity.cnae for activity in facts.activities) == ("6201", "6202")
    assert "principal" not in facts.model_dump()
    assert "selected" not in facts.model_dump()

    with pytest.raises(FilingProducerSnapshotError) as exc_info:
        build_filing_producer_snapshot(
            modelo=Modelo.M202,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            presenter=_presenter(),
            model_profile=facts,
            elections=_elections(ResultDisposition.INGRESO),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
    for producer_id in M202_UNSUPPORTED_PRODUCER_IDS:
        assert producer_id.value in str(exc_info.value)


def test_legacy_duplicate_profile_classes_are_not_public() -> None:
    assert not hasattr(filing, "Modelo202ProfileFacts")
    assert not hasattr(filing, "Modelo303ProfileFacts")


def test_modelo_303_uses_the_canonical_iva_profile_type() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert type(snapshot.model_profile) is ModeloIVAProfile
    values = _filing_producer_values(snapshot)
    assert values[FilingProducerKey.M303_EXCLUSIVELY_FORAL] == "2"
    assert values[FilingProducerKey.M303_REDEME_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO] is None
    assert values[FilingProducerKey.M303_JOINT_RETURN_ELECTED] == "2"
    assert values[FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS] == "2"
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION] == "2"
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION] == "2"
    assert values[FilingProducerKey.M303_INSOLVENCY_DECLARED] == "2"
    assert values[FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE] is None
    assert values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE] is None
    assert values[FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED] == "2"
    assert values[FilingProducerKey.M303_EXONERADO_390_APPLICABLE] == "2"
    assert values[FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED] == "0"


@pytest.mark.parametrize(
    ("period_code", "entitled", "expected"),
    (
        ("1T", False, "0"),
        ("1T", True, "0"),
        ("02", False, "2"),
        ("02", True, "1"),
    ),
)
def test_modelo_303_hydrocarbon_entitlement_uses_the_official_period_and_yes_no_codes(
    period_code: str,
    entitled: bool,
    expected: str,
) -> None:
    """DP30301 Nota 8/9 reserves ``0`` and maps the applicable decision to 1/2.

    The 2026 official design writes ``0`` for quarterly/01 filings and admits
    the typed entitlement only from period 02.  This test mutates the boolean
    itself so true and false cannot silently collapse into a numeric default.
    """
    profile = _m303_profile().model_copy(
        update={"hydrocarbon_deposit_advance_payment_deduction_entitled": entitled},
    )

    # This lexical branch reads only the typed filing period.  A partial typed
    # instance keeps the proof at the producer boundary instead of requiring a
    # whole bundled-registry load unrelated to this source-stated wire rule.
    facts = M303FilingFacts.model_construct(period=Period.from_year_and_code(2026, period_code))
    lexical = m303_profile_lexicals(profile, facts)

    assert lexical.hydrocarbon_deposit_advance_payment_deduction_entitled == expected


def test_modelo_303_annual_volume_marker_requires_explicit_evidence() -> None:
    """The art. 121 marker is not silently inferred from rows or the profile."""
    facts = _m303_filing_facts(annual_volume_nonzero=True)
    payload = facts.model_dump(mode="python")
    del payload["annual_volume_nonzero"]
    with pytest.raises(ValidationError, match="annual_volume_nonzero"):
        M303FilingFacts.model_validate(payload)

    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )
    assert _filing_producer_values(snapshot)[FilingProducerKey.M303_ANNUAL_VOLUME_NONZERO] == "1"


def test_modelo_303_foral_territory_projects_true_without_a_constant_fallback() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile().model_copy(update={"tax_territory": M303TaxTerritory.FORAL}),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )

    assert _filing_producer_values(snapshot)[FilingProducerKey.M303_EXCLUSIVELY_FORAL] == "1"


@pytest.mark.parametrize(
    "transition",
    (ProrrataEspecialTransitionKind.OPCION, ProrrataEspecialTransitionKind.REVOCACION),
)
def test_modelo_303_foral_note_5_overrides_each_a16_to_a30_lexical_branch(
    transition: ProrrataEspecialTransitionKind,
) -> None:
    """DP30301 Nota 5 supersedes the contradictory typed input values."""
    arrival, register = _m303_prorrata_transition_arrival(transition)
    snapshot = _m303_foral_snapshot(prorrata_transition=arrival, prorrata_register=register)

    values = _filing_producer_values(snapshot)

    assert {
        FilingProducerKey.M303_REDEME_ENROLLED: values[FilingProducerKey.M303_REDEME_ENROLLED],
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: values[FilingProducerKey.M303_EXCLUSIVELY_FORAL],
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: values[FilingProducerKey.M303_REGIME_COMPOSITION_CODE],
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: values[FilingProducerKey.M303_JOINT_RETURN_ELECTED],
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: values[
            FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED
        ],
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: values[
            FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS
        ],
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION],
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION],
        FilingProducerKey.M303_INSOLVENCY_DECLARED: values[FilingProducerKey.M303_INSOLVENCY_DECLARED],
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: values[
            FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE
        ],
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE],
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: values[FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED],
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: values[FilingProducerKey.M303_EXONERADO_390_APPLICABLE],
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: values[
            FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED
        ],
    } == {
        FilingProducerKey.M303_REDEME_ENROLLED: "2",
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: "1",
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: "3",
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: "2",
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: "2",
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: "2",
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: "2",
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: "2",
        FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: "2",
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: "2",
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: "2",
    }


def test_modelo_303_foral_note_5_retains_blank_prorrata_slots_before_final_period() -> None:
    period = Period.from_year_and_code(2026, "1T")
    snapshot = _m303_foral_snapshot(
        prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=())
    )

    values = _filing_producer_values(snapshot)

    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION] is None
    assert values[FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION] is None


@pytest.mark.parametrize(
    ("composition", "expected"),
    (
        (M303RegimeComposition.SIMPLIFIED, "1"),
        (M303RegimeComposition.MIXED, "2"),
        (M303RegimeComposition.GENERAL, "3"),
    ),
)
def test_m303_regime_composition_projects_only_the_exclusively_simplified_arm(
    composition: M303RegimeComposition,
    expected: str,
) -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile().model_copy(update={"regime_composition": composition}),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert _filing_producer_values(snapshot)[FilingProducerKey.M303_REGIME_COMPOSITION_CODE] == expected


@pytest.mark.parametrize(
    ("subtype", "expected"),
    (
        (M303InsolvencyFilingSubtype.PRE_ORDER, "1"),
        (M303InsolvencyFilingSubtype.POST_ORDER, "2"),
    ),
)
def test_m303_insolvency_fact_projects_coupled_date_and_official_subtype_code(
    subtype: M303InsolvencyFilingSubtype,
    expected: str,
) -> None:
    facts = _m303_filing_facts().model_copy(
        update={
            "insolvency": M303InsolvencyFilingFact(
                judicial_order_date=date(2026, 8, 11),
                subtype=subtype,
            ),
        },
    )
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )
    values = _filing_producer_values(snapshot)
    assert values[FilingProducerKey.M303_INSOLVENCY_DECLARED] == "1"
    assert values[FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE] == "11082026"
    assert values[FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE] == expected


@pytest.mark.parametrize("period_code", ("0A", "1P", "EXT-1T", "AD-HOC"))
def test_m303_filing_facts_refuse_annual_and_non_official_filing_periods(period_code: str) -> None:
    period = Period.from_year_and_code(2026, period_code)
    register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    evidence = _m303_instance_evidence(period)

    with pytest.raises(ValidationError, match="official quarterly or monthly period"):
        M303FilingFacts(
            joint_return_elected=False,
            annual_volume_nonzero=False,
            insolvency=None,
            exonerado_390=_m303_exonerado_evidence(applicable=False),
            regimen_simplificado=evidence.regimen_simplificado,
            regimen_simplificado_result=evidence.regimen_simplificado.calculation_result,
            period=period,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
                source_ledger_ids=(),
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=regularisation,
        )


@pytest.mark.parametrize("period_code", ("0A", "EXT-1T"))
def test_m303_filing_facts_resolver_refuses_non_official_period_before_producer_output(period_code: str) -> None:
    period = Period.from_year_and_code(2026, period_code)
    register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    evidence = FilingInstanceEvidence(
        m303=_m303_instance_evidence(period),
    )

    with pytest.raises(ValueError, match="official quarterly or monthly period"):
        resolve_m303_filing_facts(
            evidence=evidence,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
                source_ledger_ids=(),
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period, transition=None, register_evidence=()),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=regularisation,
        )


def test_real_2026_dp30301_source_pins_a16_a30_lexical_domains() -> None:
    """The official 2026 design pins the A16-A30 lexical domains verbatim.

    This case once also asserted that A29, the non-zero annual volume marker,
    had NO producer key. That pin was written while the box was unmodelled and
    was never revisited when the marker was implemented three days later as a
    deliberate, evidence-gated producer grounded in art. 121 -- see
    ``test_modelo_303_annual_volume_marker_requires_explicit_evidence``, which
    proves the value cannot be inferred from rows or the profile. Two claims
    about the same box disagreed, and the newer one is the one with the
    grounding, so the stale assertion is gone rather than the producer.
    """
    source = (
        Path(__file__).parents[3]
        / "_data/corpus/aeat_official/disenos_registro/modelo_303/files"
        / "01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx"
    )
    extracted = Path(f"{source}.extracted.json")
    assert sha256(source.read_bytes()).hexdigest() == _M303_2026_IR_SHA256
    payload = json.loads(extracted.read_text(encoding="utf-8"))
    page = next(unit["text"] for unit in payload["units"] if unit["section"] == "DP30301")

    exact_source_domains = (
        '"1" SI, "2" NO',
        '"1" SI (sólo RS)',
        '"2" NO (RG + RS)',
        '"3" NO (sólo RG)',
        "DDMMYYYY",
        '"1" SI Preconcursal',
        '"2" SI Postconcursal',
        "0 | Para todos los periodos distintos del último (12 y 4T)",
        "0 | Para los periodos 1T, 2T, 3T, 4T y 01",
        "Sólo para periodo 02 y siguientes",
    )
    assert all(domain in page for domain in exact_source_domains)
    exact_nota_5 = (
        "Nota 5 - Tributación exclusivamente a una Administración Foral",
        'se cumplimentarán con el valor "2" NO',
        'IVA a la importación liquidado por la Aduana pendiente de ingreso >> "1" SI',
        'Tributa exclusivamente en Régimen Simplificado (RS) >> "3" NO (sólo RG).',
        "Auto de declaración de concurso dictado en el período >> blanco NO",
        'Opción por la aplicación de la prorrata especial (art. 103.Dos.1º LIVA) >> "2" blanco',
        'Revocación de la opción por la aplicación de la prorrata especial >> "2" blanco',
    )
    assert all(note in page for note in exact_nota_5)
    assert "Sujeto pasivo con volumen anual de operaciones distinto de cero" in page


def test_modelo_iva_profile_refuses_absent_tax_territory() -> None:
    with pytest.raises(ValidationError, match="tax_territory"):
        ModeloIVAProfile.model_validate({})


def test_modelo_without_specific_producers_requires_explicit_general_profile() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M131,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=GeneralFilingProfileFacts(),
        elections=_elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    assert type(snapshot.model_profile) is GeneralFilingProfileFacts


def test_disposition_selects_only_the_secure_account_with_the_matching_role() -> None:
    refund_account = RefundAccount(iban=_REFUND_IBAN)
    charge_account = ChargeAccount(iban=_CHARGE_IBAN)
    source_profile = ModeloIVAProfile(
        tax_territory=M303TaxTerritory.COMMON_REGIME,
        regime_composition=M303RegimeComposition.GENERAL,
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        refund_account=refund_account,
        charge_account=charge_account,
    )
    refund_snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=source_profile,
        elections=_elections(ResultDisposition.DEVOLUCION),
        amendment_evidence=None,
        refund_account=refund_account,
        charge_account=charge_account,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert isinstance(refund_snapshot.selected_account, RefundAccountSelection)
    assert isinstance(refund_snapshot.model_profile, ModeloIVAProfile)
    assert refund_snapshot.model_profile.refund_account is None
    assert refund_snapshot.model_profile.charge_account is None
    assert _REFUND_IBAN in refund_snapshot.model_dump_json()
    assert _CHARGE_IBAN not in refund_snapshot.model_dump_json()
    refund_values = _filing_producer_values(refund_snapshot)
    assert refund_values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] == _REFUND_IBAN
    assert refund_values[FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC] == ""

    charge_snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=source_profile,
        elections=_elections(ResultDisposition.DOMICILIACION),
        amendment_evidence=None,
        refund_account=refund_account,
        charge_account=charge_account,
        m303_filing_facts=_m303_filing_facts(),
    )
    assert isinstance(charge_snapshot.selected_account, ChargeAccountSelection)
    assert _CHARGE_IBAN in charge_snapshot.model_dump_json()
    assert _REFUND_IBAN not in charge_snapshot.model_dump_json()
    charge_values = _filing_producer_values(charge_snapshot)
    assert charge_values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] == _CHARGE_IBAN
    assert charge_values[FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC] is None


def test_missing_required_account_refuses_and_unneeded_accounts_are_not_retained() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="charge account"):
        build_filing_producer_snapshot(
            modelo=Modelo.M303,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            presenter=_presenter(),
            model_profile=_m303_profile(),
            elections=_elections(ResultDisposition.DOMICILIACION),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=_m303_filing_facts(),
        )
    with pytest.raises(FilingProducerSnapshotError, match="refund account"):
        build_filing_producer_snapshot(
            modelo=Modelo.M303,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            presenter=_presenter(),
            model_profile=_m303_profile(),
            elections=_elections(ResultDisposition.DEVOLUCION),
            amendment_evidence=None,
            refund_account=RefundAccount(iban=None),
            charge_account=None,
            m303_filing_facts=_m303_filing_facts(),
        )

    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
        charge_account=ChargeAccount(iban=_CHARGE_IBAN),
        m303_filing_facts=_m303_filing_facts(),
    )
    assert snapshot.selected_account is None
    assert _REFUND_IBAN not in snapshot.model_dump_json()
    assert _CHARGE_IBAN not in snapshot.model_dump_json()


@pytest.mark.parametrize("receipt", ["123456789012", "12345678901234", "123456789012A"])
def test_amendment_evidence_requires_original_aeat_thirteen_digit_receipt(receipt: str) -> None:
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            m303_rectificativa_motive=None,
            original_aeat_receipt=receipt,
        )


def test_amendment_flags_are_derived_from_one_typed_kind() -> None:
    evidence = AmendmentEvidence(
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        m303_rectificativa_motive=None,
        original_aeat_receipt="1234567890123",
    )
    assert evidence.is_complementaria
    assert not evidence.is_sustitutiva
    assert not evidence.is_rectificativa
    assert set(evidence.model_dump()) == {"kind", "m303_rectificativa_motive", "original_aeat_receipt"}

    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    values = _filing_producer_values(snapshot)
    assert values[FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA] is True
    assert values[FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA] is False
    assert values[FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT] == "1234567890123"


def test_m303_source_markers_share_immutable_amendment_and_disposition_evidence() -> None:
    """The 2023 X/C wire spellings do not introduce a second producer state."""
    amendment = AmendmentEvidence(
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        m303_rectificativa_motive=None,
        original_aeat_receipt="1234567890123",
    )
    complemented = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=amendment,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )
    ordinary = build_filing_producer_snapshot(
        modelo=Modelo.M303,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=_m303_profile(),
        elections=_elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=_m303_filing_facts(),
    )

    draft = _marker_draft()
    assert _m303_complementaria_marker(draft, complemented) == "X"
    assert _complementaria_page_marker(draft, complemented) == "C"
    assert _m303_no_activity_marker(draft, complemented) == "X"
    assert _m303_complementaria_marker(draft, ordinary) is None
    assert _complementaria_page_marker(draft, ordinary) is None
    assert _m303_no_activity_marker(draft, ordinary) is None


def test_taxpayer_tax_id_is_a_distinct_producer_without_presenter_fallback() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo.M111,
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False),
        elections=_elections(ResultDisposition.NEGATIVA),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )

    values = _filing_producer_values(snapshot)

    assert values[FilingProducerKey.TAXPAYER_TAX_ID] == _TAXPAYER_TAX_ID
    assert values[FilingProducerKey.PRESENTER_TAX_ID] == _PRESENTER_TAX_ID


@pytest.mark.parametrize(
    ("modelo", "model_profile"),
    (
        (Modelo.M111, Modelo111ProfileFacts(colegio_concertado=False)),
        (
            Modelo.M202,
            Modelo202ProducerProfile(
                taxpayer_profile=TaxpayerProfile(tax_id=_TAXPAYER_TAX_ID, iva_regime=IVARegime.GENERAL),
                activities=(),
            ),
        ),
        (Modelo.M131, GeneralFilingProfileFacts()),
    ),
)
def test_m303_filing_facts_are_refused_for_every_non_m303_modelo(
    modelo: Modelo,
    model_profile: Modelo111ProfileFacts | Modelo202ProducerProfile | GeneralFilingProfileFacts,
) -> None:
    """Modelo-specific filing facts never cross into M111, M202, or generic producers."""
    with pytest.raises(FilingProducerSnapshotError, match="M303FilingFacts are valid only for modelo 303"):
        build_filing_producer_snapshot(
            modelo=modelo,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            presenter=_presenter(),
            model_profile=model_profile,
            elections=_elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=_m303_filing_facts(),
        )


def test_m303_filing_facts_refuse_a_regularisation_result_for_another_year() -> None:
    payload = _m303_filing_facts().model_dump()
    payload["regularisation_result"]["regularizacion_year"] = 2025

    with pytest.raises(ValidationError, match="regularisation result must use the filing year"):
        M303FilingFacts.model_validate(payload)


def test_m303_filing_facts_accept_the_canonical_bienes_regularisation_result() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("canonical-bien"),))
    regularisation = compute_registro_regularizacion(
        register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={"canonical-bien": Decimal("80")},
    )

    facts = M303FilingFacts.model_validate(
        _m303_filing_facts_payload(
            bienes_register=register,
            regularisation_result=regularisation,
        )
    )

    assert facts.bienes_register == register
    assert facts.regularisation_result == regularisation


def test_m303_filing_facts_refuse_an_empty_regularisation_for_a_register_bien() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("unrepresented-bien"),))
    empty = RegistroRegularizacionResult(
        regularizacion_year=2026,
        rows=(),
        proposed_casilla_43=Decimal("0"),
        computed_count=0,
        pending_percentage_count=0,
        sector_contributions=(),
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=register,
                regularisation_result=empty,
            )
        )


def test_m303_filing_facts_refuse_a_regularisation_from_another_bienes_register() -> None:
    canonical_register = BienesInversionIvaRegister(records=(_bien_inversion("canonical-bien"),))
    foreign_register = BienesInversionIvaRegister(records=(_bien_inversion("foreign-bien"),))
    foreign_regularisation = compute_registro_regularizacion(
        foreign_register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={"foreign-bien": Decimal("80")},
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=canonical_register,
                regularisation_result=foreign_regularisation,
            )
        )


def test_m303_filing_facts_refuse_a_regularisation_that_omits_an_in_window_bien() -> None:
    register = BienesInversionIvaRegister(records=(_bien_inversion("first-bien"), _bien_inversion("second-bien")))
    canonical = compute_registro_regularizacion(
        register,
        regularizacion_year=2026,
        prorrata_definitiva_by_identifier={},
    )
    omitted = RegistroRegularizacionResult(
        regularizacion_year=2026,
        rows=(canonical.rows[0],),
        proposed_casilla_43=Decimal("0"),
        computed_count=0,
        pending_percentage_count=1,
        sector_contributions=(),
    )

    with pytest.raises(ValidationError, match="canonical projection of the supplied Bienes register"):
        M303FilingFacts.model_validate(
            _m303_filing_facts_payload(
                bienes_register=register,
                regularisation_result=omitted,
            )
        )


def test_m303_filing_facts_refuse_final_period_register_coverage_gaps() -> None:
    payload = _m303_filing_facts().model_dump()
    payload["prorrata_register"] = ProrrataRegister()

    with pytest.raises(ValidationError, match="complete current-year prorrata register coverage"):
        M303FilingFacts.model_validate(payload)


def test_m303_filing_facts_refuse_transition_arrival_evidence_from_another_register() -> None:
    period = Period.from_year_and_code(2026, "4T")
    canonical_entry = ProrrataRegisterEntry(
        ejercicio=period.filing_year,
        regime=ProrrataRegisterRegime.ESPECIAL,
        especial_transition=ProrrataEspecialTransitionEvidence(
            kind=ProrrataEspecialTransitionKind.OPCION,
            evidence_reference="operator-evidence:canonical-option",
        ),
    )
    foreign_entry = canonical_entry.model_copy(
        update={
            "especial_transition": ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.OPCION,
                evidence_reference="operator-evidence:foreign-option",
            )
        }
    )
    payload = _m303_filing_facts().model_dump()
    payload["prorrata_transition"] = M303ProrrataTransitionArrival(
        period=period,
        transition=ProrrataEspecialTransitionKind.OPCION,
        register_evidence=(foreign_entry,),
    )
    payload["prorrata_register"] = ProrrataRegister(entries=(canonical_entry,))

    with pytest.raises(ValidationError, match="transition arrival evidence must belong to the supplied register"):
        M303FilingFacts.model_validate(payload)
