"""Result-disposition resolver coverage for modelo export headers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, CasillaObservation
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime, ModeloIVAProfile
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from .._result_disposition_resolution import resolve_modelo_result_disposition
from ._export_test_support import (
    _M130_RESULT_CASILLA,
    _M200_REFUND_RESULT_CASILLA,
    _M303_RESULT_CASILLA,
    _profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
_BUCKET_ID = "6e84e19e-58f8-4241-b2d1-6ab9bcc3dd7b"


def _result_disposition_work_unit(*, modelo: str, period: Period) -> WorkUnit:
    snapshot = resources().modelos.authority.snapshot(
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
    )
    return CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("result-disposition-test",),
                source_refs=("result-disposition-test",),
            )
            for casilla_id, value in casilla_values.items()
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _resolve_result_disposition(
    *,
    modelo: str,
    casilla_values: dict[CasillaId, Decimal],
    profile: TaxpayerProfile,
    period: Period,
) -> str:
    work_unit = _result_disposition_work_unit(modelo=modelo, period=period)
    revision = _result_disposition_revision(work_unit=work_unit, casilla_values=casilla_values)
    return resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=profile,
        period=period,
    ).value


def _result_disposition_profile(kind: str) -> TaxpayerProfile:
    if kind == "redeme":
        return TaxpayerProfile(
            tax_id="redemecompany",
            iva_regime=IVARegime.GENERAL,
            iva=ModeloIVAProfile(redeme_enrolled=True),
        )
    if kind == "ordinary":
        return _profile()
    raise AssertionError(f"unknown result-disposition profile kind: {kind}")


@pytest.mark.parametrize(
    ("modelo", "casilla_values", "period", "expected"),
    (
        ("303", {_M303_RESULT_CASILLA: Decimal("357.00")}, Period.from_year_and_code(2024, "1T"), "I"),
        ("303", {_M303_RESULT_CASILLA: Decimal("-210.00")}, Period.from_year_and_code(2024, "1T"), "C"),
        ("303", {_M303_RESULT_CASILLA: Decimal("0.00")}, Period.from_year_and_code(2024, "1T"), "N"),
        ("303", {}, Period.from_year_and_code(2024, "1T"), "N"),
        ("130", {_M130_RESULT_CASILLA: Decimal("-50.00")}, Period.from_year_and_code(2024, "1T"), "B"),
        ("200", {_M200_REFUND_RESULT_CASILLA: Decimal("-1000.00")}, Period.from_year_and_code(2024, "0A"), "D"),
        ("390", {}, Period.from_year_and_code(2026, "0A"), "I"),
    ),
    ids=(
        "m303-positive-ingreso",
        "m303-negative-carry-forward",
        "m303-zero-negative",
        "m303-missing-result-defaults-zero",
        "m130-negative-deducir",
        "m200-negative-refund",
        "uncodified-modelo-provisional-ingreso",
    ),
)
def test_resolve_modelo_result_disposition_maps_result_to_disposition(
    modelo: str,
    casilla_values: dict[CasillaId, Decimal],
    period: Period,
    expected: str,
) -> None:
    """The fichero 'Tipo de declaración' is derived from the result, never hardcoded."""
    assert (
        _resolve_result_disposition(
            modelo=modelo,
            casilla_values=casilla_values,
            profile=_profile(),
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
    """REDEME monthly-refund election upgrades only negative Modelo 303 periods."""
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
