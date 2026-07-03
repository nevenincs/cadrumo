"""Tests for the central per-modelo aggregation service."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind, Period
from ....core.errors import get_registered_error_code
from ....core.resources import resources
from ....domain.calculations.registry import (
    resolve_counterpart_binding_values,
    resolve_foreign_asset_binding_row_values,
)
from ... import aggregation
from .. import (
    ACCEPTED_SOURCE_KINDS,
    AggregationErrorCodes,
    AggregationUnsupportedModeloError,
    CounterpartAggregation,
    CounterpartObservation,
    ForeignAssetClass,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationLogFields,
    PerModeloAggregationResult,
    RetencionesAggregation,
    RetencionObservation,
    RetencionScheme,
    aggregate_per_modelo,
    declarable_asset_classes_720,
    declarable_counterparty_nifs_347,
    get_per_modelo_aggregation_contract,
)
from .._counterpart import (
    CounterpartAggregationSourceResolver,
    CounterpartSourceKind,
    OperationKind347,
    OperationKind349,
    _m349_declarante_summary_union,
    _registry_observations_from_counterpart_aggregation,
    aggregate_counterpart_349,
)
from .._foreign_assets import (
    ForeignAssetsAggregationSourceResolver,
    _registry_observations_from_foreign_assets_aggregation,
    aggregate_foreign_assets_720,
)
from .._source_mesh import CalculationSourceContext

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
    name: str = "Cliente Counterpart",
    source_kind: CounterpartSourceKind = BindingSourceKind.LEDGER_TRANSACTION,
    source_id: str | None = None,
    operation_kind: str = OperationKind347.DELIVERY.value,
    country: str = "ES",
    invoice_total: str = "2000.00",
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=source_kind,
        source_object_id=source_id or f"{source_kind}-ctr-1",
        counterparty_nif=nif,
        counterparty_name=name,
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
    source_id: str | None = None,
    asset_class: ForeignAssetClass = ForeignAssetClass.ACCOUNT,
    asset_external_id: str | None = None,
    country: str = "AD",
    valuation: str = "50000.01",
    acquisition_date: str = "2023-01-15",
) -> ForeignAssetIngestObservation:
    return ForeignAssetIngestObservation(
        source_kind=source_kind,
        source_object_id=source_id or f"{source_kind}-asset-1",
        asset_class=asset_class,
        asset_external_id=asset_external_id or f"{source_kind}-account",
        country=country,
        valuation_eur=Decimal(valuation),
        acquisition_date=acquisition_date,
    )


def test_contract_maps_supported_modelos_to_application_aggregation_owner() -> None:
    contract = get_per_modelo_aggregation_contract()

    assert contract.service_owner == "aeat.application.aggregation"
    assert contract.accepted_source_kinds == ACCEPTED_SOURCE_KINDS
    assert contract.error_codes == AggregationErrorCodes
    by_provider = {provider.provider: provider for provider in contract.providers}
    assert by_provider[PerModeloAggregationContributor.RETENCIONES].modelos == (
        "111",
        "115",
        "123",
        "180",
        "190",
        "193",
    )
    assert by_provider[PerModeloAggregationContributor.COUNTERPART].modelos == ("347", "349")
    assert by_provider[PerModeloAggregationContributor.FOREIGN_ASSETS].modelos == ("720",)
    assert all(provider.service_owner == "aeat.application.aggregation" for provider in contract.providers)


def test_command_contract_is_strict_and_immutable() -> None:
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        retencion_observations=(_retencion_obs(),),
    )

    assert command.provider is PerModeloAggregationContributor.RETENCIONES
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


def test_period_boundary_accepts_period_dict_for_roundtrip() -> None:
    command = PerModeloAggregationCommand.model_validate(
        {"modelo": "111", "period": {"filing_year": 2025, "code": "1T"}},
    )
    log_fields = PerModeloAggregationLogFields.model_validate(
        {
            "modelo": "111",
            "period": command.model_dump()["period"],
            "provider": PerModeloAggregationContributor.RETENCIONES,
            "observation_count": 0,
            "source_kind_count": 0,
            "result_row_count": 0,
        },
    )

    assert command.period == _P_2025_Q1
    assert log_fields.period == _P_2025_Q1


def test_period_boundary_rejects_combined_period_string() -> None:
    with pytest.raises(ValidationError) as command_exc:
        PerModeloAggregationCommand.model_validate({"modelo": "111", "period": "2026Q1"})
    with pytest.raises(ValidationError) as log_fields_exc:
        PerModeloAggregationLogFields.model_validate(
            {
                "modelo": "111",
                "period": "2026Q1",
                "provider": PerModeloAggregationContributor.RETENCIONES,
                "observation_count": 0,
                "source_kind_count": 0,
                "result_row_count": 0,
            },
        )

    assert command_exc.value.errors()[0]["loc"] == ("period",)
    assert log_fields_exc.value.errors()[0]["loc"] == ("period",)


def test_service_routes_retenciones_modelos_to_retenciones_aggregation() -> None:
    command = PerModeloAggregationCommand(
        modelo="111",
        period=_P_2025_Q1,
        retencion_observations=(_retencion_obs(source_kind="ledger_transaction"),),
    )

    result = aggregate_per_modelo(command)

    assert result.provider is PerModeloAggregationContributor.RETENCIONES
    assert isinstance(result.aggregation, RetencionesAggregation)
    assert result.aggregation.total_retencion == Decimal("150.00")
    assert result.source_kinds == (BindingSourceKind.LEDGER_TRANSACTION,)
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
        _counterpart_obs(source_kind=BindingSourceKind.LEDGER_TRANSACTION, invoice_total="1500.00"),
        _counterpart_obs(source_kind=BindingSourceKind.PAYABLE_INVOICE, invoice_total="1505.07"),
    )
    command = PerModeloAggregationCommand(
        modelo="347",
        period=_P_2025_ANNUAL,
        counterpart_observations=observations,
    )

    result = aggregate_per_modelo(command)

    assert result.provider is PerModeloAggregationContributor.COUNTERPART
    assert isinstance(result.aggregation, CounterpartAggregation)
    assert result.source_kinds == (
        BindingSourceKind.LEDGER_TRANSACTION,
        BindingSourceKind.PAYABLE_INVOICE,
    )
    assert declarable_counterparty_nifs_347(result.aggregation) == frozenset({"B00000001"})


def test_counterpart_m349_mesh_resolution_matches_prior_aggregate_exactly() -> None:
    observations = (
        _counterpart_obs(
            nif="DE123456789",
            name="Kunde GmbH",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
            source_id="sale-de",
            operation_kind=OperationKind349.INTRA_DELIVERY.value,
            country="DE",
            invoice_total="1000.00",
        ),
        _counterpart_obs(
            nif="IT12345678901",
            name="Servizi SRL",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            source_id="purchase-it",
            operation_kind=OperationKind349.INTRA_SERVICE_IN.value,
            country="IT",
            invoice_total="3000.00",
        ),
        _counterpart_obs(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_id="domestic-347-control",
            operation_kind=OperationKind347.DELIVERY.value,
            invoice_total="999.00",
        ),
    )
    expected_aggregation = aggregate_counterpart_349(observations, period=_P_2025_Q1)
    service_result = aggregate_per_modelo(
        PerModeloAggregationCommand(
            modelo="349",
            period=_P_2025_Q1,
            counterpart_observations=observations,
        ),
    )
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2025, period="1T")
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="349",
        filing_year=2025,
        period=_P_2025_Q1,
        revision=snapshot.revision,
    )
    expected_values = resolve_counterpart_binding_values(
        snapshot.revision,
        _registry_observations_from_counterpart_aggregation(expected_aggregation),
    )
    expected_values = _m349_declarante_summary_union(context=context, binding_values=expected_values)

    resolution = CounterpartAggregationSourceResolver(observations=observations).resolve(context)

    assert service_result.aggregation == expected_aggregation
    assert dict(resolution.binding_values) == expected_values
    assert {item.source_ref for item in resolution.provenance} == {
        "collectible_invoice:sale-de",
        "payable_invoice:purchase-it",
    }
    assert resolution.source_transaction_ids == ()


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

    assert result.provider is PerModeloAggregationContributor.FOREIGN_ASSETS
    assert isinstance(result.aggregation, ForeignAssetsAggregation)
    assert result.source_kinds == (
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
    )
    assert declarable_asset_classes_720(result.aggregation) == frozenset({ForeignAssetClass.ACCOUNT})


def test_foreign_assets_m720_registry_rows_match_prior_aggregate_exactly() -> None:
    observations = (
        _asset_obs(
            source_kind="ledger_transaction",
            source_id="tx-account-ad",
            asset_external_id="AD-ACCOUNT-001",
            country="AD",
            valuation="40000.00",
            acquisition_date="2020-01-15",
        ),
        _asset_obs(
            source_kind="payable_invoice",
            source_id="payable-account-ch",
            asset_external_id="CH-ACCOUNT-002",
            country="CH",
            valuation="15000.00",
            acquisition_date="2021-02-20",
        ),
        _asset_obs(
            source_kind="collectible_invoice",
            source_id="small-security",
            asset_class=ForeignAssetClass.SECURITY,
            asset_external_id="LI-SECURITY-001",
            country="LI",
            valuation="1000.00",
            acquisition_date="2022-03-25",
        ),
    )
    expected_aggregation = aggregate_foreign_assets_720(observations, period=_P_2025_ANNUAL)
    service_result = aggregate_per_modelo(
        PerModeloAggregationCommand(
            modelo="720",
            period=_P_2025_ANNUAL,
            foreign_asset_observations=observations,
        ),
    )
    snapshot = resources().modelos.authority.snapshot("720", filing_year=2025, period="0A")
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="720",
        filing_year=2025,
        period=_P_2025_ANNUAL,
        revision=snapshot.revision,
    )
    row_observations = _registry_observations_from_foreign_assets_aggregation(
        expected_aggregation,
        observations,
    )
    expected_row_values = resolve_foreign_asset_binding_row_values(snapshot.revision, row_observations)

    resolution = ForeignAssetsAggregationSourceResolver(observations=observations).resolve(context)

    assert service_result.aggregation == expected_aggregation
    assert expected_row_values == {
        ("modelo-720-asset-row-class", 1): "C",
        ("modelo-720-asset-row-country", 1): "AD",
        ("modelo-720-asset-row-currency", 1): "EUR",
        ("modelo-720-asset-row-identifier", 1): "AD-ACCOUNT-001",
        ("modelo-720-asset-row-valuation", 1): Decimal("40000.00"),
        ("modelo-720-asset-row-acquisition-date", 1): "2020-01-15",
        ("modelo-720-asset-row-class", 2): "C",
        ("modelo-720-asset-row-country", 2): "CH",
        ("modelo-720-asset-row-currency", 2): "EUR",
        ("modelo-720-asset-row-identifier", 2): "CH-ACCOUNT-002",
        ("modelo-720-asset-row-valuation", 2): Decimal("15000.00"),
        ("modelo-720-asset-row-acquisition-date", 2): "2021-02-20",
    }
    assert resolution.binding_values == {}
    assert resolution.source_transaction_ids == ("tx-account-ad",)
    assert {item.source_ref for item in resolution.provenance} == {
        "ledger_transaction:tx-account-ad",
        "payable_invoice:payable-account-ch",
    }


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
            provider=PerModeloAggregationContributor.COUNTERPART,
            aggregation=aggregation_payload,
            source_kinds=(BindingSourceKind.LEDGER_TRANSACTION,),
            log_fields=PerModeloAggregationLogFields(
                modelo="349",
                period=_P_2025_ANNUAL,
                provider=PerModeloAggregationContributor.COUNTERPART,
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
            provider=PerModeloAggregationContributor.COUNTERPART,
            aggregation=aggregation_payload,
            source_kinds=(BindingSourceKind.LEDGER_TRANSACTION,),
            log_fields=PerModeloAggregationLogFields(
                modelo="111",
                period=_P_2025_Q1,
                provider=PerModeloAggregationContributor.COUNTERPART,
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
