"""Tests for the central per-modelo aggregation service."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.errors import get_registered_error_code
from ... import aggregation
from .. import (
    ACCEPTED_SOURCE_KINDS,
    AggregationErrorCodes,
    AggregationSourceKind,
    AggregationUnsupportedModeloError,
    CounterpartAggregation,
    CounterpartObservation,
    ForeignAssetClass,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    PerModeloAggregationCommand,
    PerModeloAggregationLogFields,
    PerModeloAggregationProvider,
    PerModeloAggregationResult,
    RetencionesAggregation,
    RetencionObservation,
    RetencionScheme,
    aggregate_per_modelo,
    declarable_asset_classes_720,
    declarable_counterparty_nifs_347,
    get_per_modelo_aggregation_contract,
)
from .._counterpart import CounterpartSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_Q1 = Period.from_year_and_code(2025, "1T")
_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")


def _retencion_obs(*, source_kind: str = "ledger_transaction") -> RetencionObservation:
    return RetencionObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind}-ret-1",
        perceptor_nif="B00000001",
        perceptor_name="Proveedor Retencion",
        scheme=RetencionScheme.WORK_INCOME,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2025-03-01",
    )


def _counterpart_obs(
    *,
    nif: str = "B00000001",
    source_kind: CounterpartSourceKind = AggregationSourceKind.LEDGER_TRANSACTION,
    operation_kind: str = "entregas_y_prestaciones",
    country: str = "ES",
    invoice_total: str = "2000.00",
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind}-ctr-1",
        counterparty_nif=nif,
        counterparty_name="Cliente Counterpart",
        counterparty_country=country,
        operation_kind=operation_kind,
        operation_period="2025",
        taxable_base=Decimal(invoice_total),
        invoice_total=Decimal(invoice_total),
        accrued_on="2025-03-01",
        groi_verified=True,
        nif_iva_verified=True,
    )


def _asset_obs(
    *,
    source_kind: str = "purchase_invoice_evidence",
    valuation: str = "50000.01",
) -> ForeignAssetIngestObservation:
    return ForeignAssetIngestObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind}-asset-1",
        asset_class=ForeignAssetClass.ACCOUNT,
        asset_external_id=f"{source_kind}-account",
        country="AD",
        valuation_eur=Decimal(valuation),
        acquisition_date="2023-01-15",
    )


def test_contract_maps_supported_modelos_to_application_aggregation_owner() -> None:
    contract = get_per_modelo_aggregation_contract()

    assert contract.service_owner == "aeat.application.aggregation"
    assert contract.accepted_source_kinds == ACCEPTED_SOURCE_KINDS
    assert contract.error_codes == AggregationErrorCodes
    by_provider = {provider.provider: provider for provider in contract.providers}
    assert by_provider[PerModeloAggregationProvider.RETENCIONES].modelos == ("111", "115", "123", "180", "190", "193")
    assert by_provider[PerModeloAggregationProvider.COUNTERPART].modelos == ("347", "349")
    assert by_provider[PerModeloAggregationProvider.FOREIGN_ASSETS].modelos == ("720",)
    assert all(provider.service_owner == "aeat.application.aggregation" for provider in contract.providers)


def test_command_contract_is_strict_and_immutable() -> None:
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        retencion_observations=(_retencion_obs(),),
    )

    assert command.provider is PerModeloAggregationProvider.RETENCIONES
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PerModeloAggregationCommand.model_validate(
            {
                "modelo": "111",
                "period": _P_2025_Q1,
                "retencion_observations": (_retencion_obs(),),
                "unexpected": "field",
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        command.period = Period.from_year_and_code(2025, "2T")


def test_service_routes_retenciones_modelos_to_retenciones_aggregation() -> None:
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        retencion_observations=(_retencion_obs(source_kind="ledger_transaction"),),
    )

    result = aggregate_per_modelo(command)

    assert result.provider is PerModeloAggregationProvider.RETENCIONES
    assert isinstance(result.aggregation, RetencionesAggregation)
    assert result.aggregation.total_retencion == Decimal("150.00")
    assert result.source_kinds == (AggregationSourceKind.LEDGER_TRANSACTION,)
    assert result.log_fields.as_extra() == {
        "service_name": "per_modelo_aggregation",
        "modelo": "111",
        "period": "1T",
        "provider": "retenciones",
        "observation_count": 1,
        "source_kind_count": 1,
        "result_row_count": 1,
    }


def test_service_routes_counterpart_modelos_and_preserves_threshold_semantics() -> None:
    observations = (
        _counterpart_obs(source_kind=AggregationSourceKind.LEDGER_TRANSACTION, invoice_total="1500.00"),
        _counterpart_obs(source_kind=AggregationSourceKind.PAYABLE_INVOICE, invoice_total="1505.07"),
    )
    command = PerModeloAggregationCommand(
        modelo="347",
        period=_P_2025_ANNUAL,
        counterpart_observations=observations,
    )

    result = aggregate_per_modelo(command)

    assert result.provider is PerModeloAggregationProvider.COUNTERPART
    assert isinstance(result.aggregation, CounterpartAggregation)
    assert result.source_kinds == (
        AggregationSourceKind.LEDGER_TRANSACTION,
        AggregationSourceKind.PAYABLE_INVOICE,
    )
    assert declarable_counterparty_nifs_347(result.aggregation) == frozenset({"B00000001"})


def test_service_routes_foreign_asset_modelos_and_preserves_threshold_semantics() -> None:
    observations = (
        _asset_obs(source_kind="purchase_invoice_evidence", valuation="25000.00"),
        _asset_obs(source_kind="payable_invoice", valuation="25000.01"),
    )
    command = PerModeloAggregationCommand(
        modelo="720",
        period=_P_2025_ANNUAL,
        foreign_asset_observations=observations,
    )

    result = aggregate_per_modelo(command)

    assert result.provider is PerModeloAggregationProvider.FOREIGN_ASSETS
    assert isinstance(result.aggregation, ForeignAssetsAggregation)
    assert result.source_kinds == (
        AggregationSourceKind.PAYABLE_INVOICE,
        AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
    )
    assert declarable_asset_classes_720(result.aggregation) == frozenset({ForeignAssetClass.ACCOUNT})


def test_command_rejects_observations_from_non_selected_provider_family() -> None:
    with pytest.raises(ValidationError, match="foreign_assets"):
        PerModeloAggregationCommand(
            modelo="111",
            period=_P_2025_Q1,
            foreign_asset_observations=(_asset_obs(),),
        )


def test_unsupported_modelo_uses_registered_aggregation_error() -> None:
    with pytest.raises(AggregationUnsupportedModeloError, match="unsupported_modelo") as exc_info:
        PerModeloAggregationCommand(modelo="999", period=_P_2025_ANNUAL)

    error = exc_info.value
    assert error.suggestion == "use one of 111, 115, 123, 180, 190, 193, 347, 349, 720"
    assert get_registered_error_code(error).code == "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"


def test_modelo_whitespace_is_rejected_before_dispatch() -> None:
    with pytest.raises(AggregationUnsupportedModeloError, match="unsupported_modelo") as exc_info:
        PerModeloAggregationCommand(
            modelo=" 347 ",
            period=_P_2025_ANNUAL,
            counterpart_observations=(_counterpart_obs(),),
        )

    assert exc_info.value.context == {"modelo": " 347 "}


def test_result_contract_rejects_incoherent_envelope_payload() -> None:
    aggregation_payload = aggregate_per_modelo(
        PerModeloAggregationCommand(
            modelo="347",
            period=_P_2025_ANNUAL,
            counterpart_observations=(_counterpart_obs(),),
        ),
    ).aggregation

    with pytest.raises(ValidationError, match="does not match result modelo"):
        PerModeloAggregationResult(
            modelo="349",
            period=_P_2025_ANNUAL,
            provider=PerModeloAggregationProvider.COUNTERPART,
            aggregation=aggregation_payload,
            source_kinds=(AggregationSourceKind.LEDGER_TRANSACTION,),
            log_fields=PerModeloAggregationLogFields(
                modelo="349",
                period=_P_2025_ANNUAL,
                provider=PerModeloAggregationProvider.COUNTERPART,
                observation_count=1,
                source_kind_count=1,
                result_row_count=1,
            ),
        )


def test_result_contract_rejects_provider_payload_mismatch() -> None:
    aggregation_payload = aggregate_per_modelo(
        PerModeloAggregationCommand(
            modelo="111",
            period=_P_2025_Q1,
            retencion_observations=(_retencion_obs(),),
        ),
    ).aggregation

    with pytest.raises(ValidationError, match="does not match aggregation payload"):
        PerModeloAggregationResult(
            modelo="111",
            period=_P_2025_Q1,
            provider=PerModeloAggregationProvider.COUNTERPART,
            aggregation=aggregation_payload,
            source_kinds=(AggregationSourceKind.LEDGER_TRANSACTION,),
            log_fields=PerModeloAggregationLogFields(
                modelo="111",
                period=_P_2025_Q1,
                provider=PerModeloAggregationProvider.COUNTERPART,
                observation_count=1,
                source_kind_count=1,
                result_row_count=1,
            ),
        )


def test_service_surface_has_no_cli_dependency() -> None:
    source = "\n".join(
        [
            inspect.getsource(aggregation._service),
            inspect.getsource(aggregation.PerModeloAggregationCommand),
            inspect.getsource(aggregation.PerModeloAggregationResult),
        ],
    )

    assert "typer" not in source.lower()
    assert "entrypoints.cli" not in source
