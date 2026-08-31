"""Application result-disposition resolver tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.result_disposition import ResultDisposition
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.hierarchy import CoreValidationError
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.registry_observations import registry_grounded_observations
from .._result_disposition_resolution import resolve_modelo_result_disposition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_BUCKET_ID = "915b0469-91b1-4787-a650-9aad55564dd3"  # was 'result-disposition-resolution-test'
_M200_PRINTED_RESULT_NUMBER: CasillaId = validated_casilla_id(
    "00599",
    surface="_M200_PRINTED_RESULT_NUMBER",
)
_M200_REFUND_RESULT_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00599",
    surface="_M200_REFUND_RESULT_CASILLA",
)
_M200_AMBIGUOUS_PRINTED_NUMBER: CasillaId = validated_casilla_id(
    "00562",
    surface="_M200_AMBIGUOUS_PRINTED_NUMBER",
)
_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200010:00562",
    surface="_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA",
)
_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00562",
    surface="_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA",
)


def _work_unit(*, modelo: str, filing_year: int, period_code: str, revision_id: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period.registry_token}",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _verified_revision(work_unit: WorkUnit, values: dict[CasillaId, Decimal]) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=values,
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _revision_with_casilla_values(work_unit: WorkUnit, values: dict[CasillaId, Decimal]) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        casilla_values=values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-58-2003:art-120",),
                source_refs=("aeat-modelo-disposition-fixture",),
            )
            for casilla_id, value in values.items()
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _registry_work_unit(*, modelo: str, filing_year: int, period_code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    snapshot = bundled_authority().snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
    )
    return _work_unit(
        modelo=modelo,
        filing_year=filing_year,
        period_code=period_code,
        revision_id=snapshot.revision.id,
    )


@pytest.mark.parametrize(
    ("filing_year", "period_code", "revision_id", "result_casilla"),
    (
        (2023, "4T", "2019-2023", validated_casilla_id("08", surface="result-disposition resolver test casilla id")),
        (
            2026,
            "1T",
            "2024-y-siguientes",
            validated_casilla_id("14", surface="result-disposition resolver test casilla id"),
        ),
    ),
)
def test_m123_result_disposition_uses_revision_specific_canonical_result_casilla(
    filing_year: int,
    period_code: str,
    revision_id: str,
    result_casilla: CasillaId,
) -> None:
    work_unit = _work_unit(
        modelo="123",
        filing_year=filing_year,
        period_code=period_code,
        revision_id=revision_id,
    )
    revision = _verified_revision(work_unit, {result_casilla: Decimal("223.44")})
    profile = TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)

    disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=profile,
        period=work_unit.period,
    )

    assert disposition is ResultDisposition.INGRESO


def test_resolve_modelo_result_disposition_rejects_printed_number_metadata_token() -> None:
    """A registry metadata token must not silently drive result disposition."""
    work_unit = _registry_work_unit(modelo="200", filing_year=2025, period_code="0A")
    revision = _revision_with_casilla_values(
        work_unit,
        {_M200_PRINTED_RESULT_NUMBER: Decimal("5000.00")},
    )

    with pytest.raises(CoreValidationError) as exc_info:
        resolve_modelo_result_disposition(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL),
            period=work_unit.period,
        )

    assert f"{_M200_PRINTED_RESULT_NUMBER!r} -> {_M200_REFUND_RESULT_CASILLA}" in str(exc_info.value)


def test_resolve_modelo_result_disposition_rejects_ambiguous_printed_number_metadata_token() -> None:
    """A reused printed number must fail before result casilla filtering."""
    work_unit = _registry_work_unit(modelo="200", filing_year=2025, period_code="0A")
    revision = _revision_with_casilla_values(
        work_unit,
        {_M200_AMBIGUOUS_PRINTED_NUMBER: Decimal("5000.00")},
    )

    with pytest.raises(CoreValidationError) as exc_info:
        resolve_modelo_result_disposition(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL),
            period=work_unit.period,
        )

    assert (
        f"{_M200_AMBIGUOUS_PRINTED_NUMBER!r} is ambiguous; candidate casilla.id values: "
        f"{_M200_ECPN_REUSED_PRINTED_NUMBER_CASILLA}, {_M200_LIQUIDACION_REUSED_PRINTED_NUMBER_CASILLA}"
    ) in str(exc_info.value)
