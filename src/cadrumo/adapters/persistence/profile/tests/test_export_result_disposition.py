"""Result-disposition resolver coverage for modelo export headers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....application.modelo.action_errors import (
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloRefundElectionNotEligibleError,
    ModeloResultDispositionUncodifiedError,
)
from .....application.modelo.result_disposition_resolution import (
    require_admissible_charge_account,
    resolve_modelo_result_disposition,
)
from .....core.casilla_id import CasillaId
from .....core.payment_election import PaymentElection
from .....core.period import Period
from .....core.refund_election import RefundElection
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.deadlines.models import (
    ChargeAccount,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from .modelo_export_support import (
    _M130_RESULT_CASILLA,
    _M200_REFUND_RESULT_CASILLA,
    _M303_RESULT_CASILLA,
)
from .modelo_export_support import (
    export_taxpayer_profile as _profile,
)
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CLOCK = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
_BUCKET_ID = "6e84e19e-58f8-4241-b2d1-6ab9bcc3dd7b"


def _result_disposition_work_unit(*, modelo: str, period: Period) -> WorkUnit:
    snapshot = published_authority_operation().snapshot(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=period.filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"{modelo}-{period.filing_year}-{period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _result_disposition_revision(
    *,
    work_unit: WorkUnit,
    casilla_values: dict[CasillaId, Decimal],
) -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-58-2003:art-120",),
                source_refs=("aeat-modelo-disposition-fixture",),
            )
            for casilla_id, value in casilla_values.items()
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _resolve_result_disposition(
    *,
    modelo: str,
    casilla_values: dict[CasillaId, Decimal],
    profile: TaxpayerProfile,
    period: Period,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    refund_account_country: str | None = None,
) -> str | None:
    work_unit = _result_disposition_work_unit(modelo=modelo, period=period)
    revision = _result_disposition_revision(work_unit=work_unit, casilla_values=casilla_values)
    disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=profile,
        period=period,
        refund_election=refund_election,
        payment_election=payment_election,
        refund_account_country=refund_account_country,
    )
    return None if disposition is None else disposition.value


def _result_disposition_profile(kind: str) -> TaxpayerProfile:
    if kind == "redeme":
        return TaxpayerProfile(
            tax_id="B66012345",
            iva_regime=IVARegime("GENERAL"),
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.from_registry("common_regime"),
                regime_composition=M303RegimeComposition.from_registry("general"),
                redeme_enrolled=True,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
        )
    if kind == "ordinary":
        return TaxpayerProfile(
            tax_id="B66012345",
            iva_regime=IVARegime("GENERAL"),
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.from_registry("common_regime"),
                regime_composition=M303RegimeComposition.from_registry("general"),
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
                redeme_enrolled=False,
            ),
        )
    raise AssertionError(f"unknown result-disposition profile kind: {kind}")


@pytest.mark.parametrize(
    ("modelo", "casilla_values", "period", "expected"),
    (
        ("303", {_M303_RESULT_CASILLA: Decimal("357.00")}, Period.from_year_and_code(2024, "1T"), "I"),
        ("303", {_M303_RESULT_CASILLA: Decimal("-210.00")}, Period.from_year_and_code(2024, "1T"), "C"),
        ("303", {_M303_RESULT_CASILLA: Decimal("0.00")}, Period.from_year_and_code(2024, "1T"), "N"),
        ("303", {}, Period.from_year_and_code(2024, "1T"), "N"),
        ("130", {_M130_RESULT_CASILLA: Decimal("-50.00")}, Period.from_year_and_code(2024, "1T"), "B"),
        ("130", {_M130_RESULT_CASILLA: Decimal("-50.00")}, Period.from_year_and_code(2024, "3T"), "B"),
        ("130", {_M130_RESULT_CASILLA: Decimal("-50.00")}, Period.from_year_and_code(2024, "4T"), "N"),
        ("130", {_M130_RESULT_CASILLA: Decimal("0.00")}, Period.from_year_and_code(2024, "4T"), "N"),
        ("200", {_M200_REFUND_RESULT_CASILLA: Decimal("-1000.00")}, Period.from_year_and_code(2025, "0A"), "D"),
        # A filing-grade Modelo 390 year: the 2026 edition claims applicability only.
        # Its layout declares no Tipo de declaración, so it records no disposition.
        ("390", {}, Period.from_year_and_code(2025, "0A"), None),
        ("360", {}, Period.from_year_and_code(2025, "AD-HOC"), "D"),
    ),
    ids=(
        "m303-positive-ingreso",
        "m303-negative-carry-forward",
        "m303-zero-negative",
        "m303-missing-result-defaults-zero",
        "m130-negative-deducir",
        "m130-negative-third-quarter-deducir",
        "m130-negative-fourth-quarter-negativa",
        "m130-zero-fourth-quarter-negativa",
        "m200-negative-refund",
        "modelo-without-disposition-records-none",
        "m360-fixed-devolucion",
    ),
)
def test_resolve_modelo_result_disposition_maps_result_to_disposition(
    modelo: str,
    casilla_values: dict[CasillaId, Decimal],
    period: Period,
    expected: str | None,
) -> None:
    """The fichero 'Tipo de declaración' is derived from the result, never hardcoded."""
    assert (
        _resolve_result_disposition(
            modelo=modelo,
            casilla_values=casilla_values,
            profile=_result_disposition_profile("ordinary") if modelo == "303" else _profile(),
            period=period,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("profile_kind", "period_code", "casilla_values", "expected"),
    (
        *(("redeme", code, {_M303_RESULT_CASILLA: Decimal("-210.00")}, "D") for code in ("01", "02", "03", "12")),
        *(("ordinary", code, {_M303_RESULT_CASILLA: Decimal("-210.00")}, "C") for code in ("01", "1T", "4T")),
        ("redeme", "01", {_M303_RESULT_CASILLA: Decimal("357.00")}, "I"),
        ("redeme", "01", {_M303_RESULT_CASILLA: Decimal("0.00")}, "N"),
        ("redeme", "1T", {_M130_RESULT_CASILLA: Decimal("-50.00")}, "B"),
    ),
    ids=(
        *(f"redeme-negative-{code}" for code in ("01", "02", "03", "12")),
        *(f"ordinary-negative-{code}" for code in ("01", "1T", "4T")),
        "redeme-positive-not-upgraded",
        "redeme-zero-not-upgraded",
        "redeme-non-m303-not-upgraded",
    ),
)
def test_resolve_modelo_result_disposition_redeme_upgrade_boundaries(
    profile_kind: str,
    period_code: str,
    casilla_values: dict[CasillaId, Decimal],
    expected: str,
) -> None:
    """REDEME standing disposition resolves only negative Modelo 303 periods to D."""
    modelo = "130" if _M130_RESULT_CASILLA in casilla_values else "303"
    assert (
        _resolve_result_disposition(
            modelo=modelo,
            casilla_values=casilla_values,
            profile=_result_disposition_profile(profile_kind),
            period=Period.from_year_and_code(2024, period_code),
        )
        == expected
    )


@pytest.mark.parametrize(
    ("modelo", "profile_kind", "period", "casilla_values", "country", "expected"),
    (
        ("303", "redeme", ("2024", "01"), {_M303_RESULT_CASILLA: Decimal("-210.00")}, None, "D"),
        ("303", "redeme", ("2024", "01"), {_M303_RESULT_CASILLA: Decimal("-210.00")}, "ES", "D"),
        ("303", "redeme", ("2024", "01"), {_M303_RESULT_CASILLA: Decimal("-210.00")}, "DE", "X"),
        ("303", "ordinary", ("2024", "1T"), {_M303_RESULT_CASILLA: Decimal("-210.00")}, "DE", "C"),
        ("303", "redeme", ("2024", "01"), {_M303_RESULT_CASILLA: Decimal("357.00")}, "DE", "I"),
        ("200", "ordinary", ("2025", "0A"), {_M200_REFUND_RESULT_CASILLA: Decimal("-1000.00")}, "BR", "X"),
        ("360", "ordinary", ("2025", "AD-HOC"), {}, "DE", "D"),
    ),
    ids=(
        "m303-refund-without-account-stays-d",
        "m303-refund-to-spanish-account-d",
        "m303-refund-to-foreign-account-x",
        "m303-carry-forward-ignores-the-account",
        "m303-ingreso-ignores-the-account",
        "m200-refund-to-foreign-account-x",
        "m360-fixed-devolucion-declares-no-x",
    ),
)
def test_a_devolucion_into_a_foreign_account_settles_as_x_where_the_modelo_declares_it(
    modelo: str,
    profile_kind: str,
    period: tuple[str, str],
    casilla_values: dict[CasillaId, Decimal],
    country: str | None,
    expected: str,
) -> None:
    """DR303 Tipo de declaración X is a devolución por transferencia al extranjero; only D changes."""
    assert (
        _resolve_result_disposition(
            modelo=modelo,
            casilla_values=casilla_values,
            profile=_result_disposition_profile(profile_kind) if modelo == "303" else _profile(),
            period=Period.from_year_and_code(int(period[0]), period[1]),
            refund_account_country=country,
        )
        == expected
    )


def test_positive_modelo_303_payment_election_resolves_i_or_u_and_refuses_g() -> None:
    """Positive M303 settlement is explicit; G is typed but unavailable."""
    period = Period.from_year_and_code(2024, "1T")
    casilla_values = {_M303_RESULT_CASILLA: Decimal("357.00")}

    assert (
        _resolve_result_disposition(
            modelo="303",
            casilla_values=casilla_values,
            profile=_result_disposition_profile("ordinary"),
            period=period,
        )
        == "I"
    )
    assert (
        _resolve_result_disposition(
            modelo="303",
            casilla_values=casilla_values,
            profile=_result_disposition_profile("ordinary"),
            period=period,
            payment_election=PaymentElection.DOMICILIACION,
        )
        == "U"
    )
    with pytest.raises(ModeloPaymentElectionCapabilityRefusedError):
        _resolve_result_disposition(
            modelo="303",
            casilla_values=casilla_values,
            profile=_result_disposition_profile("ordinary"),
            period=period,
            payment_election=PaymentElection.CUENTA_CORRIENTE,
        )


def test_incompatible_result_elections_refuse_without_changing_carry_policy() -> None:
    """Payment elections never turn a credit into carry or refund semantics."""
    positive_period = Period.from_year_and_code(2024, "1T")
    positive_values = {_M303_RESULT_CASILLA: Decimal("357.00")}
    with pytest.raises(ModeloRefundElectionNotEligibleError):
        _resolve_result_disposition(
            modelo="303",
            casilla_values=positive_values,
            profile=_result_disposition_profile("ordinary"),
            period=positive_period,
            refund_election=RefundElection.DEVOLVER,
        )

    negative_values = {_M303_RESULT_CASILLA: Decimal("-210.00")}
    with pytest.raises(ModeloPaymentElectionIncompatibleError):
        _resolve_result_disposition(
            modelo="303",
            casilla_values=negative_values,
            profile=_result_disposition_profile("ordinary"),
            period=positive_period,
            payment_election=PaymentElection.DOMICILIACION,
        )

    with pytest.raises(ModeloRefundElectionNotEligibleError):
        _resolve_result_disposition(
            modelo="303",
            casilla_values={_M303_RESULT_CASILLA: Decimal("0.00")},
            profile=_result_disposition_profile("ordinary"),
            period=positive_period,
            refund_election=RefundElection.DEVOLVER,
        )

    assert (
        _resolve_result_disposition(
            modelo="303",
            casilla_values=negative_values,
            profile=_result_disposition_profile("ordinary"),
            period=Period.from_year_and_code(2024, "4T"),
            refund_election=RefundElection.DEVOLVER,
        )
        == "D"
    )


def test_domiciliacion_follows_the_declared_codes_not_the_modelo_name() -> None:
    """Modelo 130 declares U, so a positive instalment may be domiciliado."""
    assert (
        _resolve_result_disposition(
            modelo="130",
            casilla_values={_M130_RESULT_CASILLA: Decimal("120.00")},
            profile=_profile(),
            period=Period.from_year_and_code(2024, "1T"),
            payment_election=PaymentElection.DOMICILIACION,
        )
        == "U"
    )
    with pytest.raises(ModeloPaymentElectionIncompatibleError):
        _resolve_result_disposition(
            modelo="130",
            casilla_values={_M130_RESULT_CASILLA: Decimal("-50.00")},
            profile=_profile(),
            period=Period.from_year_and_code(2024, "1T"),
            payment_election=PaymentElection.DOMICILIACION,
        )


def test_a_charge_account_outside_spain_is_capability_refused_without_account_material() -> None:
    work_unit = _result_disposition_work_unit(modelo="130", period=Period.from_year_and_code(2024, "1T"))
    require_admissible_charge_account(
        work_unit=work_unit, charge_account=ChargeAccount(iban="ES9121000418450200051332")
    )

    with pytest.raises(ModeloPaymentElectionCapabilityRefusedError) as refused:
        require_admissible_charge_account(
            work_unit=work_unit,
            charge_account=ChargeAccount(iban="DE89370400440532013000"),
        )

    assert refused.value.context == {
        "modelo": "130",
        "payment_election": "domiciliacion",
        "charge_account_country": "DE",
    }


def test_a_layout_declaring_the_header_without_a_codified_spec_refuses() -> None:
    """Modelo 216 prints Tipo de declaración but has no codified code set: no I is invented."""
    with pytest.raises(ModeloResultDispositionUncodifiedError) as refused:
        _resolve_result_disposition(
            modelo="216",
            casilla_values={},
            profile=_profile(),
            period=Period.from_year_and_code(2024, "1T"),
        )

    assert refused.value.context is not None
    assert refused.value.context["producer_key"] == "filing.result_disposition"
    assert refused.value.context["modelo"] == "216"


def test_an_absent_disposition_admits_no_election() -> None:
    period = Period.from_year_and_code(2025, "0A")
    with pytest.raises(ModeloPaymentElectionIncompatibleError):
        _resolve_result_disposition(
            modelo="390",
            casilla_values={},
            profile=_profile(),
            period=period,
            payment_election=PaymentElection.DOMICILIACION,
        )
    with pytest.raises(ModeloRefundElectionNotEligibleError):
        _resolve_result_disposition(
            modelo="390",
            casilla_values={},
            profile=_profile(),
            period=period,
            refund_election=RefundElection.DEVOLVER,
        )


def test_modelo_360_refuses_a_domiciliacion_election() -> None:
    with pytest.raises(ModeloPaymentElectionIncompatibleError):
        _resolve_result_disposition(
            modelo="360",
            casilla_values={},
            profile=_profile(),
            period=Period.from_year_and_code(2025, "AD-HOC"),
            payment_election=PaymentElection.DOMICILIACION,
        )
