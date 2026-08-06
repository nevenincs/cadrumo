"""BienInversionIvaRecord / register structural invariants and window predicate."""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest

from .. import (
    BienesInversionIvaRegister,
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
    RegularizacionDireccion,
    compute_registro_regularizacion,
    compute_registro_transmisiones,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _record(identifier: str = "bi-2022-furgoneta", **overrides: object) -> BienInversionIvaRecord:
    base: dict[str, object] = {
        "identifier": identifier,
        "description": "Furgoneta de reparto afecta a la actividad",
        "acquisition_year": 2022,
        "cuota_soportada": Decimal("4200.00"),
        "prorrata_inicial_pct": Decimal("80"),
        "kind": BienInversionKind.MUEBLE,
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
    assert record.is_within_regularization_window(2022) is False  # acquisition year excluded
    assert record.is_within_regularization_window(2023) is True
    assert record.is_within_regularization_window(2026) is True
    assert record.is_within_regularization_window(2027) is False


def test_real_estate_window_spans_nine_following_years() -> None:
    """An inmueble acquired in 2022 regularises 2023-2031, not 2032."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.INMUEBLE)
    assert record.is_within_regularization_window(2031) is True
    assert record.is_within_regularization_window(2032) is False


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
    assert record.remaining_regularization_years(2024) == 3


def test_remaining_regularization_years_disposal_in_acquisition_year_counts_full_window() -> None:
    """A disposal in the acquisition year itself still owes the full following window."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2022) == 4


def test_remaining_regularization_years_disposal_in_last_window_year() -> None:
    """A disposal in the final window year leaves exactly that one year."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2026) == 1


def test_remaining_regularization_years_disposal_outside_window_is_zero() -> None:
    """A disposal after window expiry leaves nothing to regularise."""
    record = _record(acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    assert record.remaining_regularization_years(2027) == 0


def test_register_rejects_duplicate_identifiers() -> None:
    """Two records with the same identifier fail register validation."""
    with pytest.raises(pydantic.ValidationError, match="duplicate record identifiers"):
        BienesInversionIvaRegister(records=(_record("dup"), _record("dup")))


def test_in_window_records_filters_by_eligibility_and_window() -> None:
    """``in_window_records`` returns only art-108-eligible, in-window goods."""
    in_window = _record("in-window", acquisition_year=2022, kind=BienInversionKind.MUEBLE)
    out_of_window = _record("old", acquisition_year=2015, kind=BienInversionKind.MUEBLE)
    ineligible = _record("cheap", acquisition_year=2022, art108_elegible=False)
    register = BienesInversionIvaRegister(records=(in_window, out_of_window, ineligible))
    result = register.in_window_records(2024)
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
    )
    pending = _record(
        "bi-pending",
        acquisition_year=2023,
        cuota_soportada=Decimal("9000.00"),
        prorrata_inicial_pct=Decimal("50"),
        kind=BienInversionKind.MUEBLE,
    )
    register = BienesInversionIvaRegister(records=(computed, pending))
    projection = compute_registro_regularizacion(
        register,
        regularizacion_year=2024,
        prorrata_definitiva_by_identifier={"bi-computed": Decimal("60")},
    )
    assert projection.computed_count == 1
    assert projection.pending_percentage_count == 1
    assert projection.proposed_casilla_43 == Decimal("200.00")
    computed_row = next(row for row in projection.rows if row.identifier == "bi-computed")
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
    result = register.in_window_records(2024)
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
    result = register.disposed_records(2024)
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
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.SUJETA_NO_EXENTA),
    )
    regla_segunda = _record(
        "bi-regla-2",
        acquisition_year=2021,
        cuota_soportada=Decimal("31500.00"),
        prorrata_inicial_pct=Decimal("65"),
        kind=BienInversionKind.INMUEBLE,
        disposal=BienInversionDisposal(year=2024, regime=BienInversionDisposalRegime.EXENTA_O_NO_SUJETA),
    )
    register = BienesInversionIvaRegister(records=(regla_primera, regla_segunda))
    projection = compute_registro_transmisiones(register, disposal_year=2024)
    assert projection.computed_count == 2
    assert projection.proposed_casilla_43 == Decimal("11932.50")
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
    projection = compute_registro_transmisiones(register, disposal_year=2027)
    assert projection.computed_count == 0
    assert projection.rows == ()
    assert projection.proposed_casilla_43 == Decimal("0.00")
