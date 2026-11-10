"""BienInversionIvaRecord / register structural invariants and window predicate."""

from __future__ import annotations
from ...calculations.registry.tests.authored_editions import filing_year_envelope

from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from functools import partial

import pydantic
import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ...iva.deduction_facts import IvaDeductionClassificationProvenance
from ...iva.flow import IvaFlowDirection
from ...iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..register import (
    BienesInversionIvaRegister,
    BienesInversionSectorContribution,
    BienInversionDisposal,
    BienInversionIvaRecord,
    BienInversionValidationError,
    RegularizacionDireccion,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
    validate_investment_asset_reciprocity,
)
from ..vocabulary import BienInversionDisposalRegime, BienInversionKind
from .explicit_parameters import EXPLICIT_PARAMS, params_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ACQ = filing_year_envelope().floor
#: A year two after acquisition, inside every window the explicit parameters declare.
_MID = _ACQ + 2


@pytest.fixture(scope="module", autouse=True)
def _governed_fact_scope() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _record(identifier: str = "bi-2022-furgoneta", **overrides: object) -> BienInversionIvaRecord:
    base: dict[str, object] = {
        "identifier": identifier,
        "description": "Furgoneta de reparto afecta a la actividad",
        "acquisition_year": _ACQ,
        "cuota_soportada": Decimal("4200.00"),
        "prorrata_inicial_pct": Decimal("80"),
        "kind": BienInversionKind.from_registry("mueble"),
        "acquisition_ledger_id": f"ledger-{identifier}",
    }
    base.update(overrides)
    return BienInversionIvaRecord.model_validate(base)


def test_deduccion_efectuada_is_cuota_times_initial_prorrata() -> None:
    """The acquisition-year deduction is cuota × prorrata inicial, to cents."""
    record = _record(cuota_soportada=Decimal("4200.00"), prorrata_inicial_pct=Decimal("80"))
    assert record.deduccion_efectuada == Decimal("3360.00")


def test_movable_window_spans_four_following_years() -> None:
    """A mueble regularises the ventana_anos_mueble years after its acquisition, not the acquisition year or the year past the window."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    assert (
        record.is_within_regularization_window(_ACQ, parameters=EXPLICIT_PARAMS) is False
    )  # acquisition year excluded
    assert record.is_within_regularization_window(_ACQ + 1, parameters=EXPLICIT_PARAMS) is True
    assert (
        record.is_within_regularization_window(_ACQ + EXPLICIT_PARAMS.ventana_anos_mueble, parameters=EXPLICIT_PARAMS)
        is True
    )
    assert (
        record.is_within_regularization_window(
            _ACQ + EXPLICIT_PARAMS.ventana_anos_mueble + 1, parameters=EXPLICIT_PARAMS
        )
        is False
    )


def test_real_estate_window_spans_nine_following_years() -> None:
    """An inmueble regularises the ventana_anos_inmueble years after its acquisition, not the year past the window."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("inmueble"))
    assert (
        record.is_within_regularization_window(_ACQ + EXPLICIT_PARAMS.ventana_anos_inmueble, parameters=EXPLICIT_PARAMS)
        is True
    )
    assert (
        record.is_within_regularization_window(
            _ACQ + EXPLICIT_PARAMS.ventana_anos_inmueble + 1, parameters=EXPLICIT_PARAMS
        )
        is False
    )


def test_disposal_before_acquisition_is_refused() -> None:
    """A disposal year preceding acquisition is a structural error."""
    with pytest.raises(pydantic.ValidationError, match="disposal year"):
        _record(
            acquisition_year=_ACQ,
            disposal=BienInversionDisposal(
                year=_ACQ - 1, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")
            ),
        )


def test_remaining_regularization_years_mid_window_disposal() -> None:
    """A mueble disposed of two years after acquisition, in a four-year window, has 3 years left (the disposal year included)."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    assert record.remaining_regularization_years(_MID, parameters=EXPLICIT_PARAMS) == 3


def test_remaining_regularization_years_disposal_in_acquisition_year_counts_full_window() -> None:
    """A disposal in the acquisition year itself still owes the full following window."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    assert record.remaining_regularization_years(_ACQ, parameters=EXPLICIT_PARAMS) == 4


def test_remaining_regularization_years_disposal_in_last_window_year() -> None:
    """A disposal in the final window year leaves exactly that one year."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    assert (
        record.remaining_regularization_years(_ACQ + EXPLICIT_PARAMS.ventana_anos_mueble, parameters=EXPLICIT_PARAMS)
        == 1
    )


def test_remaining_regularization_years_disposal_outside_window_is_zero() -> None:
    """A disposal after window expiry leaves nothing to regularise."""
    record = _record(acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    assert (
        record.remaining_regularization_years(
            _ACQ + EXPLICIT_PARAMS.ventana_anos_mueble + 1, parameters=EXPLICIT_PARAMS
        )
        == 0
    )


def test_a_stored_identifier_longer_than_the_request_bound_still_loads() -> None:
    """Only the write request bounds the identifier, so a register saved before that bound still hydrates."""
    long_identifier = "i" * 129

    register = BienesInversionIvaRegister.model_validate_json(
        BienesInversionIvaRegister(
            records=(_record(long_identifier, acquisition_ledger_id="ledger-1"),)
        ).model_dump_json(),
    )

    assert register.records[0].identifier == long_identifier


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
    in_window = _record("in-window", acquisition_year=_ACQ, kind=BienInversionKind.from_registry("mueble"))
    out_of_window = _record(
        "old",
        acquisition_year=_ACQ - 2 * EXPLICIT_PARAMS.ventana_anos_mueble,
        kind=BienInversionKind.from_registry("mueble"),
    )
    ineligible = _record("cheap", acquisition_year=_ACQ, art108_elegible=False)
    register = BienesInversionIvaRegister(records=(in_window, out_of_window, ineligible))
    result = register.in_window_records(_MID, parameters=EXPLICIT_PARAMS)
    assert tuple(r.identifier for r in result) == ("in-window",)


def test_registro_projection_folds_computed_importes_and_reports_pending() -> None:
    """The register projection sums computed importes and flags pending goods.

    Two in-window mueble goods: one has a supplied definitive percentage (a
    20-point drop from 80 to 60 → the art-109 quotient folds into casilla 43), the
    other has no percentage supplied (pending the prorrata-definitiva input). The
    worked good: cuota 5.000, 80→60, efectuada 4.000 − procedente 3.000
    = 1.000, ÷5 = 200,00 → ingreso.
    """
    computed = _record(
        "bi-computed",
        acquisition_year=_ACQ,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.from_registry("mueble"),
        prorrata_sector_id="sector-services",
    )
    pending = _record(
        "bi-pending",
        acquisition_year=_ACQ + 1,
        cuota_soportada=Decimal("9000.00"),
        prorrata_inicial_pct=Decimal("50"),
        kind=BienInversionKind.from_registry("mueble"),
        prorrata_sector_id="sector-rentals",
    )
    register = BienesInversionIvaRegister(records=(computed, pending))
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=_MID,
        prorrata_definitiva_by_identifier={"bi-computed": Decimal("60")},
        parameters=params_for(_MID),
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
        acquisition_year=_ACQ,
        disposal=BienInversionDisposal(year=_MID, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")),
    )
    disposed_earlier_year = _record(
        "disposed-earlier-year",
        acquisition_year=_ACQ,
        disposal=BienInversionDisposal(
            year=_ACQ + 1, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")
        ),
    )
    disposed_later_year = _record(
        "disposed-later-year",
        acquisition_year=_ACQ,
        disposal=BienInversionDisposal(
            year=_ACQ + 3, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")
        ),
    )
    never_disposed = _record("never-disposed", acquisition_year=_ACQ)
    register = BienesInversionIvaRegister(
        records=(disposed_same_year, disposed_earlier_year, disposed_later_year, never_disposed)
    )
    result = register.in_window_records(_MID, parameters=EXPLICIT_PARAMS)
    assert tuple(r.identifier for r in result) == ("disposed-later-year", "never-disposed")


def test_disposed_records_filters_by_disposal_year_and_remaining_window() -> None:
    """``disposed_records`` returns only a good disposed of in that exact year with window time left."""
    in_scope = _record(
        "in-scope",
        acquisition_year=_ACQ,
        disposal=BienInversionDisposal(year=_MID, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")),
    )
    different_year = _record(
        "different-year",
        acquisition_year=_ACQ,
        disposal=BienInversionDisposal(
            year=_ACQ + 1, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")
        ),
    )
    no_disposal = _record("no-disposal", acquisition_year=_ACQ)
    register = BienesInversionIvaRegister(records=(in_scope, different_year, no_disposal))
    result = register.disposed_records(_MID, parameters=EXPLICIT_PARAMS)
    assert tuple(r.identifier for r in result) == ("in-scope",)


def test_registro_transmisiones_folds_disposed_goods_into_casilla_43() -> None:
    """The register-wide transmisión projection sums every disposed good's importe.

    Two goods disposed of in the same year: a mueble under regla 1.ª (uncapped, worked in
    ``test_transmision.py``: cuota 10.000, prorrata inicial 60 %, acquired two years
    before the disposal, four-year window → 3 remaining years → −2.400,00) and an inmueble
    under regla 2.ª (cuota 31.500, prorrata inicial 65 %, acquired three years
    before the disposal, nine-year window → 7 remaining years → efectuada 20.475,00 − imputada 0
    = 20.475,00 × 7 ÷ 10 = 14.332,50). Total = −2.400,00 + 14.332,50 = 11.932,50.
    """
    regla_primera = _record(
        "bi-regla-1",
        acquisition_year=_ACQ,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.from_registry("mueble"),
        prorrata_sector_id="sector-muebles",
        disposal=BienInversionDisposal(year=_MID, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")),
    )
    regla_segunda = _record(
        "bi-regla-2",
        acquisition_year=_ACQ - 1,
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        kind=BienInversionKind.from_registry("inmueble"),
        prorrata_sector_id="sector-inmuebles",
        disposal=BienInversionDisposal(
            year=_MID, regime=BienInversionDisposalRegime.from_registry("exenta_o_no_sujeta")
        ),
    )
    register = BienesInversionIvaRegister(records=(regla_primera, regla_segunda))
    projection = compute_registro_transmisiones(register, disposal_year=_MID, parameters=params_for(_MID))
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
        acquisition_year=_ACQ,
        cuota_soportada=Decimal("10000.00"),
        prorrata_inicial_pct=Decimal("60"),
        kind=BienInversionKind.from_registry("mueble"),
        disposal=BienInversionDisposal(year=_MID, regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta")),
    )
    register = BienesInversionIvaRegister(records=(regla_primera,))
    projection = compute_registro_transmisiones(
        register,
        disposal_year=_MID,
        cuota_devengada_entrega_by_identifier={"bi-capped": Decimal("1500.00")},
        parameters=params_for(_MID),
    )
    assert projection.proposed_casilla_43 == Decimal("-1500.00")
    row = projection.rows[0]
    assert row.result.capped is True
    assert row.result.importe == Decimal("-1500.00")


def test_registro_transmisiones_excludes_a_disposal_with_no_window_time_remaining() -> None:
    """A disposal recorded outside the regularisation window contributes nothing."""
    out_of_window_disposal = _record(
        "no-window-left",
        acquisition_year=_ACQ - 2 * EXPLICIT_PARAMS.ventana_anos_mueble,
        disposal=BienInversionDisposal(
            year=_ACQ + EXPLICIT_PARAMS.ventana_anos_mueble + 1,
            regime=BienInversionDisposalRegime.from_registry("sujeta_no_exenta"),
        ),
    )
    register = BienesInversionIvaRegister(records=(out_of_window_disposal,))
    projection = compute_registro_transmisiones(
        register,
        disposal_year=_ACQ + EXPLICIT_PARAMS.ventana_anos_mueble + 1,
        parameters=params_for(_ACQ + EXPLICIT_PARAMS.ventana_anos_mueble + 1),
    )
    assert projection.computed_count == 0
    assert projection.rows == ()
    assert projection.proposed_casilla_43 == Decimal("0.00")


def _investment_observation(
    *,
    ledger_id: str = "ledger-asset-machine",
    asset_id: str = "asset-machine",
    transaction_date: date = date(_MID, 5, 7),
    prorrata_sector_id: str | None = "sector-services",
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=IvaCategory("domestic_general"),
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("soportado"),
        base_amount=Decimal("10000.00"),
        iva_amount=Decimal("2100.00"),
        applied_rate=Decimal("0.21"),
        prorrata_sector_id=prorrata_sector_id,
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_investment"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
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
                acquisition_year=_MID,
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
        filing_year=_MID,
    )


@pytest.mark.parametrize(
    ("build_observation", "ledger_profile_id", "asset_profile_id", "filing_year", "message", "expected_context"),
    (
        (
            partial(_investment_observation, ledger_id="ledger-wrong"),
            "profile-a",
            "profile-a",
            _MID,
            "not reciprocal",
            {"ledger_transaction_id": "ledger-wrong", "investment_asset_id": "asset-machine"},
        ),
        (
            partial(_investment_observation, transaction_date=date(_MID + 1, 1, 8)),
            "profile-a",
            "profile-a",
            _MID,
            "share the filing year",
            {"ledger_transaction_id": "ledger-asset-machine", "investment_asset_id": "asset-machine"},
        ),
        (
            partial(_investment_observation, prorrata_sector_id="sector-rentals"),
            "profile-a",
            "profile-a",
            _MID,
            "share the prorrata sector",
            {"ledger_transaction_id": "ledger-asset-machine", "investment_asset_id": "asset-machine"},
        ),
        (_investment_observation, "profile-a", "profile-b", _MID, "share a secure profile", None),
    ),
)
def test_investment_asset_reciprocity_refuses_mismatched_edges(
    build_observation: Callable[[], IvaLedgerObservation],
    ledger_profile_id: str,
    asset_profile_id: str,
    filing_year: int,
    message: str,
    expected_context: dict[str, str] | None,
) -> None:
    """Every stored cross-boundary edge is exact; no identifier is inferred.

    The offending ledger transaction and investment asset ids ride on the
    refusal's context wherever a specific edge -- not merely a whole-register
    profile mismatch -- was compared.
    """
    observation = build_observation()
    register = BienesInversionIvaRegister(
        records=(
            _record(
                "asset-machine",
                acquisition_year=_MID,
                acquisition_ledger_id="ledger-asset-machine",
                prorrata_sector_id="sector-services",
            ),
        )
    )

    with pytest.raises(BienInversionValidationError, match=message) as exc_info:
        validate_investment_asset_reciprocity(
            observations=(observation,),
            register=register,
            ledger_profile_id=ledger_profile_id,
            asset_profile_id=asset_profile_id,
            filing_year=filing_year,
        )
    assert exc_info.value.context == expected_context
