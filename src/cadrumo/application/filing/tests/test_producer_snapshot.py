"""Real public-surface tests for typed filing producer snapshots."""

import json
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import (
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
from ....core.resources import resources
from ....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ....domain.calculations.registry import resolve_m303_regimen_simplificado_snapshot
from ....domain.deadlines import (
    ChargeAccount,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    RefundAccount,
    TaxpayerProfile,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....domain.iva import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
    RegimenSimplificadoFilingRows,
)
from ....domain.modelos import (
    CalculationRevisionAmendmentKind,
    FilingInstanceEvidence,
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from ....domain.prorrata_register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
)
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
from .._export import _filing_producer_values

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


def _empty_m303_export_arrivals(
    filing_year: int,
) -> tuple[ProrrataRegister, BienesInversionIvaRegister, RegistroRegularizacionResult]:
    register = ProrrataRegister()
    bienes_register = BienesInversionIvaRegister()
    regularisation = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=filing_year,
        prorrata_definitiva_by_identifier={},
    )
    return register, bienes_register, regularisation


def _m303_filing_facts() -> M303FilingFacts:
    period = Period.from_year_and_code(2026, "4T")
    register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    return M303FilingFacts(
        joint_return_elected=False,
        insolvency=None,
        exonerado_390=_m303_exonerado_evidence(applicable=False),
        regimen_simplificado=_m303_instance_evidence(period).regimen_simplificado,
        period=period,
        supplier_regime=M303SupplierRegimeArrival(
            period=period,
            recipient_of_cash_accounting_operations=False,
        ),
        prorrata_transition=M303ProrrataTransitionArrival(period=period),
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
            (
                M303Exonerado390ActivityRowEvidence(
                    slot=1,
                    codigo_actividad="A01",
                    epigrafe_iae="4191",
                    evidence_reference=reference,
                ),
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
        registry_snapshot=resources().modelos.authority.snapshot(
            "303",
            filing_year=period.filing_year,
            period="1T",
        ),
        scope_decision=scope,
    )
    return M303FilingInstanceEvidence(
        period=period,
        joint_return_elected=False,
        insolvency=None,
        exonerado_390=_m303_exonerado_evidence(applicable=False),
        regimen_simplificado=M303RegimenSimplificadoFilingEvidence(
            scope_decision=scope,
            rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
            regimen_snapshot=snapshot,
        ),
    )


def _m303_prorrata_transition_arrival(
    transition: ProrrataEspecialTransitionKind,
) -> M303ProrrataTransitionArrival:
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
        (ProrrataRegisterEntry(ejercicio=2025, regime=ProrrataRegisterRegime.ESPECIAL),)
        if transition is ProrrataEspecialTransitionKind.REVOCACION
        else ()
    )
    return resolve_m303_prorrata_transition_arrival(
        period=period,
        prorrata_register=ProrrataRegister(entries=(*prior_entries, entry)),
    )


def _m303_foral_snapshot(
    *,
    prorrata_transition: M303ProrrataTransitionArrival,
) -> FilingProducerSnapshot:
    period = prorrata_transition.period
    register, bienes_register, regularisation = _empty_m303_export_arrivals(period.filing_year)
    facts = M303FilingFacts(
        joint_return_elected=True,
        insolvency=M303InsolvencyFilingFact(
            judicial_order_date=date(2026, 8, 11),
            subtype=M303InsolvencyFilingSubtype.POST_ORDER,
        ),
        exonerado_390=_m303_exonerado_evidence(applicable=True),
        regimen_simplificado=_m303_instance_evidence(period).regimen_simplificado,
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
    with pytest.raises(TypeError, match="presenter"):
        build_filing_producer_snapshot(  # type: ignore[call-arg]
            modelo=Modelo.M111,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            taxpayer_identity=_taxpayer_identity(),
            model_profile=Modelo111ProfileFacts(colegio_concertado=False),
            elections=_elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
        )

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
    )
    assert snapshot.presenter.tax_id == _PRESENTER_TAX_ID
    assert snapshot.taxpayer_tax_id == _TAXPAYER_TAX_ID
    producer_values = _filing_producer_values(snapshot)
    assert producer_values[FilingProducerKey.PRESENTER_TAX_ID] == _PRESENTER_TAX_ID
    assert producer_values[FilingProducerKey.TAXPAYER_TAX_ID] == _TAXPAYER_TAX_ID
    with pytest.raises(ValidationError, match="frozen"):
        snapshot.presenter.full_name = "Mutated"  # type: ignore[misc]


def test_taxpayer_name_facts_are_required_and_not_derived_from_presenter() -> None:
    with pytest.raises(TypeError, match="taxpayer_identity"):
        build_filing_producer_snapshot(  # type: ignore[call-arg]
            modelo=Modelo.M111,
            taxpayer_tax_id=_TAXPAYER_TAX_ID,
            presenter=_presenter(),
            model_profile=Modelo111ProfileFacts(colegio_concertado=False),
            elections=_elections(ResultDisposition.NEGATIVA),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
        )

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
    snapshot = _m303_foral_snapshot(
        prorrata_transition=_m303_prorrata_transition_arrival(transition),
    )

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
    snapshot = _m303_foral_snapshot(prorrata_transition=M303ProrrataTransitionArrival(period=period))

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

    with pytest.raises(ValidationError, match="official quarterly or monthly period"):
        M303FilingFacts(
            joint_return_elected=False,
            insolvency=None,
            exonerado_390=_m303_exonerado_evidence(applicable=False),
            regimen_simplificado=_m303_instance_evidence(period).regimen_simplificado,
            period=period,
            supplier_regime=M303SupplierRegimeArrival(
                period=period,
                recipient_of_cash_accounting_operations=False,
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period),
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
            ),
            prorrata_transition=M303ProrrataTransitionArrival(period=period),
            prorrata_register=register,
            differentiated_contributions=(),
            bienes_register=bienes_register,
            regularisation_result=regularisation,
        )


def test_real_2026_dp30301_source_pins_a16_a30_lexical_domains_and_non_producer_a29() -> None:
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
    assert not any("annual" in key.value and "volume" in key.value for key in FilingProducerKey)


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
            motive="Corrección de la autoliquidación original",
            original_aeat_receipt=receipt,
        )


def test_amendment_flags_are_derived_from_one_typed_kind() -> None:
    evidence = AmendmentEvidence(
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        motive="Ingreso omitido en la declaración original",
        original_aeat_receipt="1234567890123",
    )
    assert evidence.is_complementaria
    assert not evidence.is_sustitutiva
    assert not evidence.is_rectificativa
    assert set(evidence.model_dump()) == {"kind", "motive", "original_aeat_receipt"}

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
    )
    values = _filing_producer_values(snapshot)
    assert values[FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA] is True
    assert values[FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA] is False
    assert values[FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT] == "1234567890123"
