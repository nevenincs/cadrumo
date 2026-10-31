"""Real public-surface tests for typed filing producer snapshots."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.deadlines.models import IVARegime, M303RegimeComposition, M303TaxTerritory

from ....core.filing_producer_key import FilingProducerKey
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.deadlines.models import (
    ChargeAccount,
    ModeloIVAProfile,
    RefundAccount,
    TaxpayerProfile,
)
from ....domain.filing.schema import ModeloDraft, compute_modelo_draft_id, registry_schema_version
from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ....domain.submission.models import ModeloDraftStatus
from ..export_producer import filing_producer_values
from ..producer_snapshot import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    AmendmentEvidence,
    ChargeAccountSelection,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M202UnsupportedProducerId,
    Modelo111ProfileFacts,
    Modelo202ActivityFacts,
    Modelo202ProducerProfile,
    RefundAccountSelection,
    build_filing_producer_snapshot,
)
from ..producer_snapshot_m200 import Modelo200ProfileFacts
from ..record_field_renderer import (
    m303_complementaria_marker,
    m303_no_activity_marker,
)
from .producer_snapshot_support import (
    _PRESENTER_TAX_ID,
    _TAXPAYER_TAX_ID,
    _elections,
    _m303_filing_facts,
    _m303_profile,
    _presenter,
    _taxpayer_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_CHARGE_IBAN = "ES9121000418450200051332"


_REFUND_IBAN = "GB82WEST12345698765432"


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


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


def test_presenter_is_required_and_never_derived_from_taxpayer() -> None:
    presenter = _presenter()
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("111"),
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
    producer_values = filing_producer_values(snapshot)
    assert producer_values[FilingProducerKey.PRESENTER_TAX_ID] == _PRESENTER_TAX_ID
    assert producer_values[FilingProducerKey.TAXPAYER_TAX_ID] == _TAXPAYER_TAX_ID
    with pytest.raises(ValidationError, match="frozen"):
        snapshot.presenter.__setattr__("full_name", "Mutated")


def test_taxpayer_name_facts_are_required_and_not_derived_from_presenter() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("111"),
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
            modelo=Modelo("111"),
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
    with bundled_indexed_authority().operation():
        taxpayer_profile = TaxpayerProfile(
            tax_id=_TAXPAYER_TAX_ID,
            iva=_m303_profile(),
            iva_regime=IVARegime("GENERAL"),
            incn_prior_12_months=Decimal("999999.99"),
        )
        facts = Modelo202ProducerProfile(
            taxpayer_profile=taxpayer_profile,
            activities=(Modelo202ActivityFacts(cnae="6201"), Modelo202ActivityFacts(cnae="6202")),
        )
        round_tripped = Modelo202ProducerProfile.model_validate_json(facts.model_dump_json())
    assert round_tripped == facts
    assert facts.taxpayer_profile is taxpayer_profile
    assert tuple(activity.cnae for activity in facts.activities) == ("6201", "6202")
    assert "principal" not in facts.model_dump()
    assert "selected" not in facts.model_dump()

    with pytest.raises(FilingProducerSnapshotError) as exc_info:
        build_filing_producer_snapshot(
            modelo=Modelo("202"),
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
    assert exc_info.value.context == {
        "missing_fact_ids": tuple(item.value for item in M202_UNSUPPORTED_PRODUCER_IDS),
        "reason": "m202_producer_facts_unsupported",
    }


def test_modelo_iva_profile_refuses_absent_tax_territory() -> None:
    with pytest.raises(ValidationError, match="tax_territory"):
        ModeloIVAProfile.model_validate({})


def test_modelo_without_specific_producers_requires_explicit_general_profile() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("131"),
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
        tax_territory=M303TaxTerritory.from_registry("common_regime"),
        regime_composition=M303RegimeComposition.from_registry("general"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )
    refund_snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
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
    assert _REFUND_IBAN in refund_snapshot.model_dump_json()
    assert _CHARGE_IBAN not in refund_snapshot.model_dump_json()
    refund_values = filing_producer_values(refund_snapshot)
    assert refund_values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] == _REFUND_IBAN
    assert refund_values[FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC] == ""

    charge_snapshot = build_filing_producer_snapshot(
        modelo=Modelo("303"),
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
    charge_values = filing_producer_values(charge_snapshot)
    assert charge_values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] == _CHARGE_IBAN
    assert charge_values[FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC] is None


@pytest.mark.parametrize(
    ("disposition", "expected"),
    [
        pytest.param(
            ResultDisposition.DEVOLUCION,
            {
                FilingProducerKey.M200_CUENTA_BANCARIA_MARCA_SEPA: "2",
                FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN: _REFUND_IBAN,
                FilingProducerKey.M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC: "",
                FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN_2: None,
            },
            id="refund-fills-the-devolucion-block",
        ),
        pytest.param(
            ResultDisposition.DOMICILIACION,
            {
                FilingProducerKey.M200_CUENTA_BANCARIA_MARCA_SEPA: None,
                FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN: None,
                FilingProducerKey.M200_CUENTA_BANCARIA_CODIGO_SWIFT_BIC: None,
                FilingProducerKey.M200_NUMERO_DE_CUENTA_IBAN_2: _CHARGE_IBAN,
            },
            id="charge-fills-the-ingreso-iban",
        ),
    ],
)
def test_modelo_200_account_fields_follow_the_selected_account_role(
    disposition: ResultDisposition,
    expected: dict[FilingProducerKey, object],
) -> None:
    """DR200 page DID: devolución block at 242-424 from the refund role, ingreso IBAN at 443 from the charge role."""
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("200"),
        taxpayer_tax_id=_TAXPAYER_TAX_ID,
        taxpayer_identity=_taxpayer_identity(),
        presenter=_presenter(),
        model_profile=Modelo200ProfileFacts(),
        elections=_elections(disposition),
        amendment_evidence=None,
        refund_account=RefundAccount(iban=_REFUND_IBAN),
        charge_account=ChargeAccount(iban=_CHARGE_IBAN),
        m303_filing_facts=None,
    )

    values = filing_producer_values(snapshot)

    assert {key: values[key] for key in expected} == expected


def test_missing_required_account_refuses_and_unneeded_accounts_are_not_retained() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="charge account"):
        build_filing_producer_snapshot(
            modelo=Modelo("303"),
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
            modelo=Modelo("303"),
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
        modelo=Modelo("303"),
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


@pytest.mark.parametrize(
    ("receipt", "refusal"),
    [
        ("123456789012", "aeat.receipt_digits"),
        ("12345678901234", "aeat.receipt_digits"),
        ("123456789012A", "string_pattern_mismatch"),
    ],
)
def test_amendment_evidence_requires_original_aeat_thirteen_digit_receipt(receipt: str, refusal: str) -> None:
    with pytest.raises(ValidationError, match=refusal):
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
        modelo=Modelo("111"),
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
    values = filing_producer_values(snapshot)
    assert values[FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA] is True
    assert values[FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA] is False
    assert values[FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT] == "1234567890123"


def test_m303_source_markers_share_immutable_amendment_and_disposition_evidence() -> None:
    """The 303 complementaria and no-activity markers read one immutable amendment and disposition state."""
    amendment = AmendmentEvidence(
        kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        m303_rectificativa_motive=None,
        original_aeat_receipt="1234567890123",
    )
    complemented = build_filing_producer_snapshot(
        modelo=Modelo("303"),
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
        modelo=Modelo("303"),
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
    assert m303_complementaria_marker(draft, complemented) == "X"
    assert m303_no_activity_marker(draft, complemented) == "X"
    assert m303_complementaria_marker(draft, ordinary) is None
    assert m303_no_activity_marker(draft, ordinary) is None


def test_taxpayer_tax_id_is_a_distinct_producer_without_presenter_fallback() -> None:
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("111"),
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

    values = filing_producer_values(snapshot)

    assert values[FilingProducerKey.TAXPAYER_TAX_ID] == _TAXPAYER_TAX_ID
    assert values[FilingProducerKey.PRESENTER_TAX_ID] == _PRESENTER_TAX_ID
