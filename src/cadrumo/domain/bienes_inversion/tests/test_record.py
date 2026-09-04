"""BienInversionIvaRecord / register structural invariants and window predicate."""

from __future__ import annotations

from datetime import date
from datetime import date as _date
from decimal import Decimal

import pydantic
import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....domain.calculations.registry.schema_base import ThresholdComparison
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ...calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ..register import (
    BienesInversionIvaRegister,
    BienesInversionSectorContribution,
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
    BienInversionValidationError,
    RegularizacionDireccion,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
    validate_investment_asset_reciprocity,
)
from ..regularizacion_parameters import (
    BienesInversionParameterProvenance,
    BienesInversionRegularizacionParameters,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: An explicit bundle, supplied rather than resolved: these are unit tests of the
#: art-109/110 PROCEDURE, and the procedure is what they prove. Whether the
#: figures below are the ones the law states is a separate question, answered
#: against the registry itself by the modelo 303 parameter gates. Supplying them
#: here as inputs keeps a legal value out of this file's assertions.
_PARAMS = BienesInversionRegularizacionParameters(
    ventana_anos_mueble=4,
    ventana_anos_inmueble=9,
    divisor_mueble=Decimal("5"),
    divisor_inmueble=Decimal("10"),
    umbral_puntos=Decimal("10"),
    umbral_comparison=ThresholdComparison.EXCLUSIVE,
    provenance=BienesInversionParameterProvenance(
        modelo_id="303",
        revision_id="2025",
        parameter_ids=(
            "m303-bien-inversion-ventana-anos-mueble",
            "m303-bien-inversion-ventana-anos-inmueble",
            "m303-bien-inversion-divisor-mueble",
            "m303-bien-inversion-divisor-inmueble",
            "m303-bien-inversion-regularizacion-umbral-puntos",
        ),
        resolved_on=date(2025, 6, 1),
    ),
)


def _params_for(year: int) -> BienesInversionRegularizacionParameters:
    """The bundle, resolved for ``year``.

    The projection now refuses a bundle resolved for a different filing year, so
    a fixture cannot carry one fixed year and be applied to another.
    """
    return _PARAMS.model_copy(
        update={"provenance": _PARAMS.provenance.model_copy(update={"resolved_on": _date(year, 12, 31)})}
    )


def _record(identifier: str = "bi-2022-furgoneta", **overrides: object) -> BienInversionIvaRecord:
    base: dict[str, object] = {
        "identifier": identifier,
        "description": "Furgoneta de reparto afecta a la actividad",
        "acquisition_year": 2022,
        "cuota_soportada": Decimal("4200.00"),
        "prorrata_inicial_pct": Decimal("80"),
        "kind": BienInversionKind.MUEBLE,
        "acquisition_ledger_id": f"ledger-{identifier}",
    }
    base.update(overrides)
    return BienInversionIvaRecord.model_validate(base)


def test_deduccion_efectuada_is_cuota_times_initial_prorrata() -> None:
    """The acquisition-year deduction is cuota × prorrata inicial, to cents."""
    record = _record(cuota_soportada=Decimal("4200.00"), prorrata_inicial_pct=Decimal("80"))
    assert record.deduccion_efectuada == Decimal("3360.00")


def test_movable_window_spans_four_following_years() -> None:
    """A mueble acquired in 2022 regularises 2023-2026, not 2022 or 2027."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.is_within_regularization_window(2022, parameters=_PARAMS) is False  # acquisition year excluded
    assert record.is_within_regularization_window(2023, parameters=_PARAMS) is True
    assert record.is_within_regularization_window(2026, parameters=_PARAMS) is True
    assert record.is_within_regularization_window(2027, parameters=_PARAMS) is False


def test_real_estate_window_spans_nine_following_years() -> None:
    """An inmueble acquired in 2022 regularises 2023-2031, not 2032."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.INMUEBLE)
    assert record.is_within_regularization_window(2031, parameters=_PARAMS) is True
    assert record.is_within_regularization_window(2032, parameters=_PARAMS) is False


def test_disposal_before_acquisition_is_refused() -> None:
    """A disposal year preceding acquisition is a structural error."""
    with pytest.raises(pydantic.ValidationError, match="disposal year"):
        _record(
            acquisition_year=2022,
            disposal=BienInversionDisposal(year=2021, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
        )


def test_remaining_regularization_years_mid_window_disposal() -> None:
    """A mueble (2022, window 2023-2026) disposed of in 2024 has 3 years left (2024-2026)."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2024, parameters=_PARAMS) == 3


def test_remaining_regularization_years_disposal_in_acquisition_year_counts_full_window() -> None:
    """A disposal in the acquisition year itself still owes the full following window."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2022, parameters=_PARAMS) == 4


def test_remaining_regularization_years_disposal_in_last_window_year() -> None:
    """A disposal in the final window year leaves exactly that one year."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2026, parameters=_PARAMS) == 1


def test_remaining_regularization_years_disposal_outside_window_is_zero() -> None:
    """A disposal after window expiry leaves nothing to regularise."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2027, parameters=_PARAMS) == 0


def test_register_rejects_duplicate_identifiers() -> None:
    """Two records with the same identifier fail register validation."""
    with pytest.raises(pydantic.ValidationError, match="duplicate record identifiers"):
        BienesInversionIvaRegister(records=(_record("dup"), _record("dup")))


def test_register_rejects_duplicate_acquisition_ledger_ids() -> None:
    """Each capital good owns one distinct acquisition ledger identity."""
    with pytest.raises(pydantic.ValidationError, match="duplicate acquisition_ledger_id values"):
        BienesInversionIvaRegister(
            records=(
                _record("first", acquisition_ledger_id="ledger-shared"),
                _record("second", acquisition_ledger_id="ledger-shared"),
            )
        )


def test_in_window_records_filters_by_eligibility_and_window() -> None:
    """``in_window_records`` returns only art-108-eligible, in-window goods."""
    in_window = _record("in-window", acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    out_of_window = _record("old", acquisition_year=2015, kind=BienInversionKind.MUEBLE)
    ineligible = _record("cheap", acquisition_year=2022, art108_elegible=False)
    register = BienesInversionIvaRegister(records=(in_window, out_of_window, ineligible))
    result = register.in_window_records(2024, parameters=_PARAMS)
    assert tuple(r.identifier for r in result) == ("in-window",)


def test_registro_projection_folds_computed_importes_and_reports_pending() -> None:
    """The register projection sums computed importes and flags pending goods.

    Two in-window mueble goods: one has a supplied 2024 definitive percentage (a
    20-point drop from 80 to 60 → the art-109 quotient folds into casilla 43), the
    other has no percentage supplied (pending the prorrata-definitiva input). The
    worked good: cuota 5.000, 80→60, efectuada 4.000 − procedente 3.000
    = 1.000, ÷5 = 200,00 → ingreso.
    """
    computed = _record(
        "bi-computed",
        acquisition_year=2022,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.MUEBLE,
        prorrata_sector_id="sector-services",
    )
    pending = _record(
        "bi-pending",
        acquisition_year=2023,
        cuota_soportada=Decimal("9000.00"),
        prorrata_inicial_pct=Decimal("50"),
        kind=BienInversionKind.MUEBLE,
        prorrata_sector_id="sector-rentals",
    )
    register = BienesInversionIvaRegister(records=(computed, pending))
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={"bi-computed": Decimal("60")},
        parameters=_params_for(2024),
    )
    assert projection.computed_count == 1
    assert projection.pending_percentage_count == 1
    assert projection.proposed_casilla_43 == Decimal("200.00")
    assert projection.sector_contributions == (
        BienesInversionSectorContribution(
            asset_id="bi-computed",
            prorrata_sector_id="sector-services",
            amount=Decimal("200.00"),
        ),
    )
    computed_row = next(row for row in projection.rows if row.identifier == "bi-computed")
    assert computed_row.prorrata_sector_id == "sector-services"
    assert computed_row.result is not None
    assert computed_row.result.direccion is RegularizacionDireccion.INGRESO
    pending_row = next(row for row in projection.rows if row.identifier == "bi-pending")
    assert pending_row.result is None


def test_in_window_records_excludes_a_good_disposed_at_or_before_the_year() -> None:
    """A disposed good is routed to art-110, not the ordinary annual art-109 path.

    Art. 110.Uno's single regularización supersedes the annual comparison from the
    disposal year onward, so ``in_window_records`` must exclude it.
    """
    disposed_same_year = _record(
        "disposed-same-year",
        acquisition_year=2022,
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    disposed_earlier_year = _record(
        "disposed-earlier-year",
        acquisition_year=2022,
        disposal=BienInversionDisposal(year=2023, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    disposed_later_year = _record(
        "disposed-later-year",
        acquisition_year=2022,
        disposal=BienInversionDisposal(year=2025, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    never_disposed = _record("never-disposed", acquisition_year=2022)
    register = BienesInversionIvaRegister(
        records=(disposed_same_year, disposed_earlier_year, disposed_later_year, never_disposed)
    )
    result = register.in_window_records(2024, parameters=_PARAMS)
    assert tuple(r.identifier for r in result) == ("disposed-later-year", "never-disposed")


def test_disposed_records_filters_by_disposal_year_and_remaining_window() -> None:
    """``disposed_records`` returns only a good disposed of in that exact year with window time left."""
    in_scope = _record(
        "in-scope",
        acquisition_year=2022,
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    different_year = _record(
        "different-year",
        acquisition_year=2022,
        disposal=BienInversionDisposal(year=2023, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    no_disposal = _record("no-disposal", acquisition_year=2022)
    register = BienesInversionIvaRegister(records=(in_scope, different_year, no_disposal))
    result = register.disposed_records(2024, parameters=_PARAMS)
    assert tuple(r.identifier for r in result) == ("in-scope",)


def test_registro_transmisiones_folds_disposed_goods_into_casilla_43() -> None:
    """The register-wide transmisión projection sums every disposed good's importe.

    Two goods disposed of in 2024: a mueble under regla 1.ª (uncapped, worked in
    ``test_transmision.py``: cuota 10.000, prorrata inicial 60 %, acquired 2022,
    window 2023-2026 → 3 remaining years (2024-2026) → −2.400,00) and an inmueble
    under regla 2.ª (cuota 31.500, prorrata inicial 65 %, acquired 2021, window
    2022-2030 → 7 remaining years (2024-2030) → efectuada 20.475,00 − imputada 0
    = 20.475,00 × 7 ÷ 10 = 14.332,50). Total = −2.400,00 + 14.332,50 = 11.932,50.
    """
    regla_primera = _record(
        "bi-regla-1",
        acquisition_year=2022,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.MUEBLE,
        prorrata_sector_id="sector-muebles",
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    regla_segunda = _record(
        "bi-regla-2",
        acquisition_year=2021,
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        kind=BienInversionKind.INMUEBLE,
        prorrata_sector_id="sector-inmuebles",
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.EXENTA_O_NO_SUJETA),
    )
    register = BienesInversionIvaRegister(records=(regla_primera, regla_segunda))
    projection = compute_registro_transmisiones(register, disposal_year=2024, parameters=_params_for(2024))
    assert projection.computed_count == 2
    assert projection.proposed_casilla_43 == Decimal("11932.50")
    assert projection.sector_contributions == (
        BienesInversionSectorContribution(
            asset_id="bi-regla-1",
            prorrata_sector_id="sector-muebles",
            amount=Decimal("-2400.00"),
        ),
        BienesInversionSectorContribution(
            asset_id="bi-regla-2",
            prorrata_sector_id="sector-inmuebles",
            amount=Decimal("14332.50"),
        ),
    )
    row_1 = next(r for r in projection.rows if r.identifier == "bi-regla-1")
    assert row_1.result.anos_restantes == 3
    assert row_1.result.importe == Decimal("-2400.00")
    row_2 = next(r for r in projection.rows if r.identifier == "bi-regla-2")
    assert row_2.result.anos_restantes == 7
    assert row_2.result.importe == Decimal("14332.50")


def test_registro_transmisiones_applies_the_supplied_cap_per_identifier() -> None:
    """``cuota_devengada_entrega_by_identifier`` caps only the named good's regla-1.ª quotient."""
    regla_primera = _record(
        "bi-capped",
        acquisition_year=2022,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.MUEBLE,
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    register = BienesInversionIvaRegister(records=(regla_primera,))
    projection = compute_registro_transmisiones(
        register,
        disposal_year=2024,
        cuota_devengada_entrega_by_identifier={"bi-capped": Decimal("1500.00")},
        parameters=_params_for(2024),
    )
    assert projection.proposed_casilla_43 == Decimal("-1500.00")
    row = projection.rows[0]
    assert row.result.capped is True
    assert row.result.importe == Decimal("-1500.00")


def test_registro_transmisiones_excludes_a_disposal_with_no_window_time_remaining() -> None:
    """A disposal recorded outside the regularisation window contributes nothing."""
    out_of_window_disposal = _record(
        "no-window-left",
        acquisition_year=2018,
        disposal=BienInversionDisposal(year=2027, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    register = BienesInversionIvaRegister(records=(out_of_window_disposal,))
    projection = compute_registro_transmisiones(register, disposal_year=2027, parameters=_params_for(2027))
    assert projection.computed_count == 0
    assert projection.rows == ()
    assert projection.proposed_casilla_43 == Decimal("0.00")


def _investment_observation(
    *,
    ledger_id: str = "ledger-asset-machine",
    asset_id: str = "asset-machine",
    transaction_date: date = date(2024, 5, 7),
    prorrata_sector_id: str | None = "sector-services",
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        applied_rate=Decimal("0.21"),
        prorrata_sector_id=prorrata_sector_id,
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_INVESTMENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator="invoice:asset-machine",
            evidence_digest="a" * 64,
        ),
        investment_asset_id=asset_id,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_investment_asset_reciprocity_accepts_one_real_matching_observation() -> None:
    """The ledger acquisition, asset identity, profile, year, and sector agree."""
    register = BienesInversionIvaRegister(
        records=(
            _record(
                "asset-machine",
                acquisition_year=2024,
                acquisition_ledger_id="ledger-asset-machine",
                prorrata_sector_id="sector-services",
            ),
        )
    )

    validate_investment_asset_reciprocity(
        observations=(_investment_observation(),),
        register=register,
        ledger_profile_id="profile-a",
        asset_profile_id="profile-a",
        filing_year=2024,
    )


@pytest.mark.parametrize(
    ("observation", "ledger_profile_id", "asset_profile_id", "filing_year", "message"),
    (
        (_investment_observation(ledger_id="ledger-wrong"), "profile-a", "profile-a", 2024, "not reciprocal"),
        (
            _investment_observation(transaction_date=date(2025, 1, 8)),
            "profile-a",
            "profile-a",
            2024,
            "share the filing year",
        ),
        (
            _investment_observation(prorrata_sector_id="sector-rentals"),
            "profile-a",
            "profile-a",
            2024,
            "share the prorrata sector",
        ),
        (_investment_observation(), "profile-a", "profile-b", 2024, "share a secure profile"),
    ),
)
def test_investment_asset_reciprocity_refuses_mismatched_edges(
    observation: IvaLedgerObservation,
    ledger_profile_id: str,
    asset_profile_id: str,
    filing_year: int,
    message: str,
) -> None:
    """Every stored cross-boundary edge is exact; no identifier is inferred."""
    register = BienesInversionIvaRegister(
        records=(
            _record(
                "asset-machine",
                acquisition_year=2024,
                acquisition_ledger_id="ledger-asset-machine",
                prorrata_sector_id="sector-services",
            ),
        )
    )

    with pytest.raises(BienInversionValidationError, match=message):
        validate_investment_asset_reciprocity(
            observations=(observation,),
            register=register,
            ledger_profile_id=ledger_profile_id,
            asset_profile_id=asset_profile_id,
            filing_year=filing_year,
        )
