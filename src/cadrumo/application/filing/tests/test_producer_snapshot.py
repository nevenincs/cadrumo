"""Real public-surface tests for typed filing producer snapshots."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import cadrumo.application.filing as filing
from cadrumo.application.filing import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingElectionFacts,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M202UnsupportedProducerId,
    Modelo111ProfileFacts,
    Modelo202ActivityFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    RefundAccountSelection,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.filing._export import _filing_producer_values
from cadrumo.core import (
    FilingProducerKey,
    Modelo,
    PaymentElection,
    PriorDomiciliationElection,
    RefundElection,
    ResultDisposition,
)
from cadrumo.domain.deadlines import ChargeAccount, IVARegime, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from cadrumo.domain.modelos import CalculationRevisionAmendmentKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAXPAYER_TAX_ID = "12345678Z"
_PRESENTER_TAX_ID = "00000000T"
_CHARGE_IBAN = "ES9121000418450200051332"
_REFUND_IBAN = "GB82WEST12345698765432"


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
        roi_enrolled=False,
        oss_enrolled=False,
        group_member_enrolled=False,
        group_dominant_entity_enrolled=False,
        intracommunity_operations_exceed_50000_eur=False,
        sii_enrolled=False,
        redeme_enrolled=False,
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
    )
    assert type(snapshot.model_profile) is ModeloIVAProfile


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
    source_profile = ModeloIVAProfile(refund_account=refund_account, charge_account=charge_account)
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
