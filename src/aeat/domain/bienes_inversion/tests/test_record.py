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
    other has no percentage supplied (pending the deferred prorrata-definitiva
    input). The worked good: cuota 5.000, 80→60, efectuada 4.000 − procedente 3.000
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
    assert pending_row.prorrata_anio_pct is None
