"""Modelo 190 type-2 row grouping from active withholding observations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregation, BindingAggregationOp, RetencionClave
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..errors import RegistryValidationError
from ..schema import BindingDefinition, ModeloRevision
from ..schema_base import CasillaDataType
from ..schema_exports import ExportFieldDataType
from ..schema_references import PeriodSelector
from ..withholding_bindings import (
    WithholdingObservation,
    WithholdingProvider,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REFS = (
    "ley-35-2006:art-99",
    "orden-eha-3127-2009:art-1",
    "orden-hac-1431-2025:art-2",
)
_SOURCE_REFS = (
    "aeat-dr-190-2025",
    "aeat-modelo-190-instructions-2025",
)

_ROW_EXPORT_DATA_TYPES: dict[BindingDataType, ExportFieldDataType] = {
    BindingDataType.TEXT: CasillaDataType.TEXT,
    BindingDataType.MONEY: CasillaDataType.MONEY,
}


def _row_binding(binding_id: str, row_field: str, data_type: BindingDataType) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider=WithholdingProvider(
            fact="row_field",
            row_field=row_field,
            grouping="per_perceptor_clave",
            record="perceptor",
            data_type=_ROW_EXPORT_DATA_TYPES[data_type],
        ),
        value=BindingValueContract(
            data_type=data_type,
            channel=BindingValueChannel.ROW_SET,
            row_grouping="withholding",
        ),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _scalar_binding(
    binding_id: str, fact: str, data_type: BindingDataType, op: BindingAggregationOp
) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider=WithholdingProvider(fact=fact),
        value=BindingValueContract(
            data_type=data_type,
            channel=BindingValueChannel.INTEGER
            if data_type is BindingDataType.INTEGER
            else BindingValueChannel.DECIMAL,
        ),
        aggregation=BindingAggregation(op=op),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _revision_with(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2025-y-siguientes",
        localization_key="test.schema.revision.2025-y-siguientes.label",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(year_from=2025, periods=("0A",)),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        bindings=bindings,
    )


def _observation(
    *,
    source_id: str,
    subclave: str,
    amount: str,
    withholding: str,
    province_code: str = "28",
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id="11111111H",
        perceptor_legal_name="PERCEPTOR SINTETICO",
        transaction_date=date(2025, 6, 1),
        clave=RetencionClave.from_registry("G"),
        subclave=subclave,
        percibido_dinerario=Decimal(amount),
        retencion_practicada=Decimal(withholding),
        province_code=province_code,
        territorial_deduction_clave=0,
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal("0"),
    )


def test_m190_rows_group_active_payments_by_recipient_clave_and_subclave() -> None:
    """Two G.01 payments share one type-2 record; G.02 remains distinct."""
    count = _scalar_binding(
        "modelo-190-percepciones-anual",
        "percepcion_count",
        BindingDataType.INTEGER,
        BindingAggregationOp.COUNT_DISTINCT,
    )
    base = _scalar_binding(
        "modelo-190-111-trabajo-dinerario-importe-anual",
        "percibido_sum",
        BindingDataType.MONEY,
        BindingAggregationOp.SUM,
    )
    retention = _scalar_binding(
        "modelo-190-111-retenciones-anual",
        "retencion_sum",
        BindingDataType.MONEY,
        BindingAggregationOp.SUM,
    )
    nif = _row_binding("modelo-190-perceptor-row-nif", "perceptor_tax_id", BindingDataType.TEXT)
    clave = _row_binding("modelo-190-perceptor-row-clave", "clave", BindingDataType.TEXT)
    subclave = _row_binding("modelo-190-perceptor-row-subclave", "subclave", BindingDataType.TEXT)
    dinerario = _row_binding(
        "modelo-190-perceptor-row-percibido-dinerario",
        "percibido_dinerario",
        BindingDataType.MONEY,
    )
    practicada = _row_binding(
        "modelo-190-perceptor-row-retencion-practicada",
        "retencion_practicada",
        BindingDataType.MONEY,
    )
    province = _row_binding("modelo-190-perceptor-row-provincia", "province_code", BindingDataType.TEXT)
    revision = _revision_with(count, base, retention, nif, clave, subclave, dinerario, practicada, province)
    observations = (
        _observation(source_id="payment-1", subclave="01", amount="300.00", withholding="57.00"),
        _observation(source_id="payment-2", subclave="01", amount="200.00", withholding="38.00"),
        _observation(source_id="payment-3", subclave="02", amount="100.00", withholding="15.00"),
    )

    scalar_values = resolve_withholding_binding_values(revision, observations)
    row_values = resolve_withholding_binding_row_values(revision, observations)

    assert scalar_values == {
        count.id: Decimal("2"),
        base.id: Decimal("600.00"),
        retention.id: Decimal("110.00"),
    }
    assert row_values[(nif.id, 1)] == "11111111H"
    assert row_values[(clave.id, 1)] == "G"
    assert row_values[(subclave.id, 1)] == "01"
    assert row_values[(dinerario.id, 1)] == Decimal("500.00")
    assert row_values[(practicada.id, 1)] == Decimal("95.00")
    assert row_values[(province.id, 1)] == "28"
    assert row_values[(subclave.id, 2)] == "02"
    assert row_values[(dinerario.id, 2)] == Decimal("100.00")
    assert row_values[(practicada.id, 2)] == Decimal("15.00")
    assert {row_index for binding_id, row_index in row_values if binding_id == nif.id} == {1, 2}


def test_m190_row_group_refuses_conflicting_non_additive_detail() -> None:
    """A grouping key does not license selecting a province arbitrarily."""
    province = _row_binding("modelo-190-perceptor-row-provincia", "province_code", BindingDataType.TEXT)
    revision = _revision_with(province)
    observations = (
        _observation(source_id="payment-1", subclave="01", amount="300.00", withholding="57.00", province_code="28"),
        _observation(source_id="payment-2", subclave="01", amount="200.00", withholding="38.00", province_code="08"),
    )

    with pytest.raises(RegistryValidationError, match=r"conflicting non-additive detail.*province_code"):
        resolve_withholding_binding_row_values(revision, observations)
