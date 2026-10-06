"""Modelo 190 type-2 row grouping from active withholding observations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, RetencionClave
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..errors import RegistryValidationError
from ..schema import BindingDefinition, ModeloRevision
from ..schema_base import CasillaDataType
from ..schema_exports import ExportFieldDataType
from ..schema_references import PeriodSelector
from ..withholding_bindings import (
    WithholdingGrouping,
    WithholdingObservation,
    WithholdingProvider,
    resolve_withholding_binding_row_values,
    resolve_withholding_binding_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_financial_asset_loss_preserves_signed_base_without_negative_withholding() -> None:
    observation = _observation(source_id="asset-loss", subclave="01", amount="0", withholding="0")
    loss = WithholdingObservation.model_validate(
        {**observation.model_dump(), "financial_asset_origin": "A", "base_retenciones": Decimal("-125.30")}
    )
    binding = _row_binding("asset-base", "base_retenciones", BindingDataType.MONEY, "per_source_allocation")
    assert resolve_withholding_binding_row_values(_revision_with(binding), (loss,)) == {
        (binding.id, 1): Decimal("-125.30")
    }
    with pytest.raises(ValidationError, match="requires zero withholding"):
        WithholdingObservation.model_validate({**loss.model_dump(), "retencion_practicada": Decimal("1")})


def test_other_withholding_records_still_reject_negative_bases() -> None:
    observation = _observation(source_id="ordinary", subclave="01", amount="0", withholding="0")
    with pytest.raises(ValidationError, match="requires a financial-asset origin"):
        WithholdingObservation.model_validate({**observation.model_dump(), "base_retenciones": Decimal("-1")})


def _signed_asset(source_id: str, base: str) -> WithholdingObservation:
    observation = _observation(source_id=source_id, subclave="01", amount="0", withholding="0")
    return WithholdingObservation.model_validate(
        {**observation.model_dump(), "financial_asset_origin": "A", "base_retenciones": Decimal(base)}
    )


def _sign_summary(
    binding_id: str, sign: str, *, count: bool, grouping: str = "per_source_allocation"
) -> BindingDefinition:
    provider = WithholdingProvider.model_validate(
        {
            "fact": "grouped_row_count" if count else "grouped_row_sum",
            "grouping": grouping,
            "base_sign": sign,
            **({} if count else {"row_field": "base_retenciones"}),
        }
    )
    prototype = _scalar_binding(
        binding_id,
        "percepcion_count" if count else "retencion_sum",
        BindingDataType.INTEGER if count else BindingDataType.MONEY,
        BindingAggregationOp.COUNT_DISTINCT if count else BindingAggregationOp.SUM,
    )
    return prototype.model_copy(update={"provider": provider})


def test_base_sign_summary_counts_records_and_keeps_zero_with_negative_group() -> None:
    bindings = (
        _sign_summary("positive-count", "positive", count=True),
        _sign_summary("positive-total", "positive", count=False),
        _sign_summary("nonpositive-count", "nonpositive", count=True),
        _sign_summary("nonpositive-total", "nonpositive", count=False),
    )
    observations = tuple(_signed_asset(str(i), amount) for i, amount in enumerate(("100.25", "24.75", "0", "-25")))
    # Every record deliberately has the same recipient: count records, not NIFs.
    expected = {
        "positive-count": Decimal("2"),
        "positive-total": Decimal("125"),
        "nonpositive-count": Decimal("2"),
        "nonpositive-total": Decimal("-25"),
    }
    revision = _revision_with(*bindings)
    assert resolve_withholding_binding_values(revision, observations) == expected
    assert resolve_withholding_binding_values(revision, reversed(observations)) == expected
    assert resolve_withholding_binding_values(revision, ()) == dict.fromkeys(expected, Decimal("0"))


def test_base_sign_selection_occurs_after_annual_record_grouping() -> None:
    bindings = (
        _sign_summary("positive", "positive", count=True, grouping="per_perceptor_clave"),
        _sign_summary("nonpositive", "nonpositive", count=True, grouping="per_perceptor_clave"),
        _sign_summary("base", "nonpositive", count=False, grouping="per_perceptor_clave"),
    )
    assert resolve_withholding_binding_values(
        _revision_with(*bindings), (_signed_asset("gain", "10"), _signed_asset("loss", "-15"))
    ) == {"positive": Decimal("0"), "nonpositive": Decimal("1"), "base": Decimal("-5")}


def test_base_sign_filter_cannot_hide_duplicate_source_evidence() -> None:
    binding = _sign_summary("positive", "positive", count=True)
    loss = _signed_asset("duplicate", "-10")
    with pytest.raises(RegistryValidationError, match="repeats its source allocation"):
        resolve_withholding_binding_values(_revision_with(binding), (loss, loss))


def test_base_sign_refuses_row_projection_and_unknown_sign() -> None:
    with pytest.raises(ValidationError):
        WithholdingProvider.model_validate(
            {"fact": "grouped_row_count", "grouping": "per_source_allocation", "base_sign": "negative"}
        )
    binding = _row_binding("base", "base_retenciones", BindingDataType.MONEY, "per_source_allocation")
    assert isinstance(binding.provider, WithholdingProvider)
    changed = binding.model_copy(update={"provider": binding.provider.model_copy(update={"base_sign": "positive"})})
    with pytest.raises(RegistryValidationError, match="requires a grouped scalar fact"):
        resolve_withholding_binding_row_values(_revision_with(changed), (_signed_asset("one", "10"),))


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_financial_asset_base_must_be_finite(value: Decimal) -> None:
    observation = _observation(source_id="asset", subclave="01", amount="0", withholding="0")
    with pytest.raises(ValidationError):
        WithholdingObservation.model_validate(
            {**observation.model_dump(), "financial_asset_origin": "A", "base_retenciones": value}
        )


@pytest.mark.parametrize("field", ["financial_asset_acquisition_value", "financial_asset_disposal_value"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("100")])
def test_pre_coupon_origin_requires_absent_values_including_explicit_zero(field: str, value: Decimal) -> None:
    observation = _observation(source_id="coupon", subclave="01", amount="0", withholding="0")
    supplied = {**observation.model_dump(), "financial_asset_origin": "D"}
    assert WithholdingObservation.model_validate(supplied).financial_asset_origin == "D"
    with pytest.raises(ValidationError, match="requires absent acquisition and disposal"):
        WithholdingObservation.model_validate({**supplied, field: value})


@pytest.mark.parametrize("field", ["financial_asset_acquisition_value", "financial_asset_disposal_value"])
def test_financial_asset_amounts_preserve_unknown_and_zero(field: str) -> None:
    observation = _observation(source_id="asset", subclave="01", amount="0", withholding="0")
    binding = _row_binding("financial-asset-value", field, BindingDataType.MONEY)
    revision = _revision_with(binding)
    assert getattr(observation, field) is None
    assert resolve_withholding_binding_row_values(revision, (observation,)) == {}
    zero = WithholdingObservation.model_validate({**observation.model_dump(), field: Decimal("0")})
    assert resolve_withholding_binding_row_values(revision, (zero,)) == {(binding.id, 1): Decimal("0")}


@pytest.mark.parametrize("field", ["financial_asset_acquisition_value", "financial_asset_disposal_value"])
@pytest.mark.parametrize("amount", [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity")])
def test_financial_asset_amounts_reject_invalid_evidence(field: str, amount: Decimal) -> None:
    observation = _observation(source_id="asset", subclave="01", amount="0", withholding="0")
    with pytest.raises(ValidationError):
        WithholdingObservation.model_validate({**observation.model_dump(), field: amount})


def test_financial_asset_values_do_not_silently_merge_different_transactions() -> None:
    observation = _observation(source_id="asset", subclave="01", amount="0", withholding="0")
    binding = _row_binding("financial-asset-value", "financial_asset_acquisition_value", BindingDataType.MONEY)
    revision = _revision_with(binding)
    observations = tuple(
        WithholdingObservation.model_validate(
            {**observation.model_dump(), "source_id": f"asset-{i}", "financial_asset_acquisition_value": Decimal(value)}
        )
        for i, value in enumerate(("1000", "2000"))
    )
    with pytest.raises(RegistryValidationError, match="conflicting non-additive detail"):
        resolve_withholding_binding_row_values(revision, observations)


@pytest.mark.parametrize(
    ("field", "value"),
    [("financial_asset_origin", "F"), ("financial_asset_origin", "a"), ("financial_asset_related_entity", "X")],
)
def test_financial_asset_classifications_reject_unknown_codes(field: str, value: str) -> None:
    observation = _observation(source_id="asset", subclave="01", amount="0", withholding="0")
    with pytest.raises(ValidationError):
        WithholdingObservation.model_validate({**observation.model_dump(), field: value})


_LEGAL_REFS = (
    "ley-35-2006:art-99",
    "orden-eha-3127-2009:art-1",
    "orden-hac-1431-2025:art-2",
)


@pytest.mark.parametrize("second_value", ["1000", "2000"])
def test_transaction_grouping_preserves_securities_operations_and_order(second_value: str) -> None:
    binding = _row_binding(
        "asset-value", "financial_asset_acquisition_value", BindingDataType.MONEY, "per_source_allocation"
    )
    revision = _revision_with(binding)
    base = _observation(source_id="statement", subclave="01", amount="0", withholding="0")
    observations = tuple(
        WithholdingObservation.model_validate(
            {
                **base.model_dump(),
                "source_allocation_id": allocation,
                "financial_asset_acquisition_value": Decimal(value),
            }
        )
        for allocation, value in (("line-b", second_value), ("line-a", "1000"))
    )
    expected = {(binding.id, 1): Decimal("1000"), (binding.id, 2): Decimal(second_value)}
    assert resolve_withholding_binding_row_values(revision, observations) == expected
    assert resolve_withholding_binding_row_values(revision, reversed(observations)) == expected


@pytest.mark.parametrize("conflicting", [False, True])
def test_transaction_grouping_refuses_duplicate_source_allocations(conflicting: bool) -> None:
    binding = _row_binding("asset-withholding", "retencion_practicada", BindingDataType.MONEY, "per_source_allocation")
    revision = _revision_with(binding)
    first = _observation(source_id="transaction", subclave="01", amount="1000", withholding="190")
    second = first.model_copy(update={"retencion_practicada": Decimal("200")}) if conflicting else first
    with pytest.raises(RegistryValidationError, match="repeats its source allocation"):
        resolve_withholding_binding_row_values(revision, (first, second))


_SOURCE_REFS = (
    "aeat-dr-190-2025",
    "aeat-modelo-190-instructions-2025",
)

_ROW_EXPORT_DATA_TYPES: dict[BindingDataType, ExportFieldDataType] = {
    BindingDataType.TEXT: CasillaDataType.TEXT,
    BindingDataType.MONEY: CasillaDataType.MONEY,
}


def _row_binding(
    binding_id: str,
    row_field: str,
    data_type: BindingDataType,
    grouping: WithholdingGrouping = "per_perceptor_clave",
) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider=WithholdingProvider(
            fact="row_field",
            row_field=row_field,
            grouping=grouping,
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
