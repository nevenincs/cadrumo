"""Real-behavior tests for AggregationConfigError registry and composition paths.

Covers contract: assert AggregationConfigError is in ERROR_REGISTRY, round-trips
through build_error_envelope, and is raised by each replaced service-composition
invariant site.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.aggregation import AggregationSourceKind as CoreAggregationSourceKind
from ....core.errors import ERROR_REGISTRY, build_error_envelope, get_registered_error_code
from .._errors import AggregationConfigError
from .._service import (
    ACCEPTED_SOURCE_KINDS,
    AggregationSourceKind,
    PerModeloAggregationContract,
    PerModeloAggregationLogFields,
    PerModeloAggregationProvider,
    PerModeloAggregationProviderContract,
    PerModeloAggregationResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_Q1 = Period.from_year_and_code(2025, "1T")
_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")
_P_2024_ANNUAL = Period.from_year_and_code(2024, "0A")


# ---------------------------------------------------------------------------
# Registry and envelope round-trip (contract primary gate)
# ---------------------------------------------------------------------------


def test_aggregation_config_error_is_in_error_registry() -> None:
    # ERROR_REGISTRY is keyed by error code string (e.g. "ERROR_AGGREGATION_CONFIG")
    assert "ERROR_AGGREGATION_CONFIG" in ERROR_REGISTRY, (
        "AggregationConfigError must be bound in ERROR_REGISTRY under code 'ERROR_AGGREGATION_CONFIG'"
    )
    code = ERROR_REGISTRY["ERROR_AGGREGATION_CONFIG"]
    assert code.message_key == "errors.error.error_aggregation_config"


def test_aggregation_config_error_registered_code_accessible_from_instance() -> None:
    exc = AggregationConfigError("provider modelos must be unique")
    registered = get_registered_error_code(exc)
    assert registered.code == "ERROR_AGGREGATION_CONFIG"


def test_aggregation_config_error_round_trips_through_build_error_envelope() -> None:
    exc = AggregationConfigError("per-modelo aggregation providers must be unique")
    envelope = build_error_envelope(exc)
    assert envelope.code == "ERROR_AGGREGATION_CONFIG"
    assert envelope.category == "ERROR"


# ---------------------------------------------------------------------------
# Composition-invariant raise sites (one test per replaced site)
# ---------------------------------------------------------------------------


def _retenciones_contract() -> PerModeloAggregationProviderContract:
    return PerModeloAggregationProviderContract(
        provider=PerModeloAggregationProvider.RETENCIONES,
        modelos=("111", "115", "123", "180", "190", "193"),
        service_owner="aeat.application.aggregation",
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
    )


def _counterpart_contract() -> PerModeloAggregationProviderContract:
    return PerModeloAggregationProviderContract(
        provider=PerModeloAggregationProvider.COUNTERPART,
        modelos=("347", "349"),
        service_owner="aeat.application.aggregation",
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
    )


def _foreign_assets_contract() -> PerModeloAggregationProviderContract:
    return PerModeloAggregationProviderContract(
        provider=PerModeloAggregationProvider.FOREIGN_ASSETS,
        modelos=("720",),
        service_owner="aeat.application.aggregation",
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
    )


def test_site1_provider_contract_rejects_duplicate_modelos() -> None:
    """PerModeloAggregationProviderContract._modelos_are_unique raises AggregationConfigError."""
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationProviderContract(
            provider=PerModeloAggregationProvider.RETENCIONES,
            modelos=("111", "111"),  # duplicate
            service_owner="aeat.application.aggregation",
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes), (
        "Expected AggregationConfigError inside ValidationError causes"
    )


def test_site2_contract_rejects_duplicate_providers() -> None:
    """PerModeloAggregationContract._providers_are_unique raises AggregationConfigError."""
    retenciones_dup = PerModeloAggregationProviderContract(
        provider=PerModeloAggregationProvider.RETENCIONES,
        modelos=("193",),
        service_owner="aeat.application.aggregation",
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
    )
    retenciones_base = _retenciones_contract()
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationContract(
            providers=(retenciones_base, retenciones_dup),
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
            error_codes=("ERROR_FINANCIAL_AGGREGATION",),
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site3_contract_rejects_modelo_owned_by_multiple_providers() -> None:
    """PerModeloAggregationContract._providers_are_unique raises AggregationConfigError for modelo collision."""
    # Two distinct providers that claim the same modelo
    counterpart_with_extra = PerModeloAggregationProviderContract(
        provider=PerModeloAggregationProvider.COUNTERPART,
        modelos=("347", "349", "111"),  # 111 also claimed by retenciones
        service_owner="aeat.application.aggregation",
        accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationContract(
            providers=(_retenciones_contract(), counterpart_with_extra, _foreign_assets_contract()),
            accepted_source_kinds=ACCEPTED_SOURCE_KINDS,
            error_codes=("ERROR_FINANCIAL_AGGREGATION",),
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site4_contract_rejects_wrong_source_kind_taxonomy() -> None:
    """PerModeloAggregationContract._source_kinds_are_exact raises AggregationConfigError."""
    wrong_kinds = (AggregationSourceKind.LEDGER_TRANSACTION,)  # incomplete taxonomy
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationContract(
            providers=(_retenciones_contract(), _counterpart_contract(), _foreign_assets_contract()),
            accepted_source_kinds=wrong_kinds,
            error_codes=("ERROR_FINANCIAL_AGGREGATION",),
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site5_command_rejects_cross_family_observations() -> None:
    """PerModeloAggregationCommand._only_matching_observation_family_is_populated raises AggregationConfigError."""
    from .._foreign_assets import ForeignAssetClass, ForeignAssetIngestObservation
    from .._service import PerModeloAggregationCommand

    obs = ForeignAssetIngestObservation(
        source_kind="purchase_invoice_evidence",
        source_object_id="test-asset-1",
        asset_class=ForeignAssetClass.ACCOUNT,
        asset_external_id="test-account",
        country="AD",
        valuation_eur=Decimal("50000.01"),
        acquisition_date="2023-01-15",
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationCommand(
            modelo="111",
            period=_P_2025_Q1,
            foreign_asset_observations=(obs,),
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site6_result_rejects_duplicate_source_kinds() -> None:
    """PerModeloAggregationResult._source_kinds_are_unique raises AggregationConfigError."""
    from .._retenciones import RetencionObservation, RetencionScheme
    from .._service import PerModeloAggregationCommand, aggregate_per_modelo

    obs = RetencionObservation(
        source_kind=CoreAggregationSourceKind.LEDGER_TRANSACTION,
        source_object_id="ret-1",
        perceptor_nif="B00000001",
        perceptor_name="Proveedor",
        scheme=RetencionScheme.WORK_INCOME,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2025-03-01",
    )
    cmd = PerModeloAggregationCommand(modelo="111", period=_P_2025_Q1, retencion_observations=(obs,))
    agg = aggregate_per_modelo(cmd).aggregation
    log = PerModeloAggregationLogFields(
        modelo="111",
        period=_P_2025_Q1,
        provider=PerModeloAggregationProvider.RETENCIONES,
        observation_count=1,
        source_kind_count=1,
        result_row_count=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationResult(
            modelo="111",
            period=_P_2025_Q1,
            provider=PerModeloAggregationProvider.RETENCIONES,
            aggregation=agg,
            source_kinds=(
                AggregationSourceKind.LEDGER_TRANSACTION,
                AggregationSourceKind.LEDGER_TRANSACTION,  # duplicate
            ),
            log_fields=log,
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site7_result_rejects_modelo_mismatch() -> None:
    """PerModeloAggregationResult._envelope_matches_payload raises AggregationConfigError for modelo mismatch."""
    from .._counterpart import CounterpartObservation
    from .._service import PerModeloAggregationCommand, aggregate_per_modelo

    obs = CounterpartObservation(
        source_kind=CoreAggregationSourceKind.LEDGER_TRANSACTION,
        source_object_id="ctr-1",
        counterparty_nif="B00000001",
        counterparty_name="Cliente",
        counterparty_country="ES",
        operation_kind="entregas_y_prestaciones",
        operation_period="2025",
        taxable_base=Decimal("2000.00"),
        invoice_total=Decimal("2000.00"),
        accrued_on="2025-03-01",
        groi_verified=True,
        nif_iva_verified=True,
    )
    cmd = PerModeloAggregationCommand(modelo="347", period=_P_2025_ANNUAL, counterpart_observations=(obs,))
    agg = aggregate_per_modelo(cmd).aggregation  # modelo=347
    log = PerModeloAggregationLogFields(
        modelo="349",
        period=_P_2025_ANNUAL,
        provider=PerModeloAggregationProvider.COUNTERPART,
        observation_count=1,
        source_kind_count=1,
        result_row_count=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationResult(
            modelo="349",  # mismatch: aggregation says 347
            period=_P_2025_ANNUAL,
            provider=PerModeloAggregationProvider.COUNTERPART,
            aggregation=agg,
            source_kinds=(AggregationSourceKind.LEDGER_TRANSACTION,),
            log_fields=log,
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site8_result_rejects_period_mismatch() -> None:
    """PerModeloAggregationResult._envelope_matches_payload raises AggregationConfigError for period mismatch."""
    from .._counterpart import CounterpartObservation
    from .._service import PerModeloAggregationCommand, aggregate_per_modelo

    obs = CounterpartObservation(
        source_kind=CoreAggregationSourceKind.LEDGER_TRANSACTION,
        source_object_id="ctr-2",
        counterparty_nif="B00000002",
        counterparty_name="Cliente B",
        counterparty_country="ES",
        operation_kind="entregas_y_prestaciones",
        operation_period="2025",
        taxable_base=Decimal("5000.00"),
        invoice_total=Decimal("5000.00"),
        accrued_on="2025-06-01",
        groi_verified=True,
        nif_iva_verified=True,
    )
    cmd = PerModeloAggregationCommand(modelo="347", period=_P_2025_ANNUAL, counterpart_observations=(obs,))
    agg = aggregate_per_modelo(cmd).aggregation  # period=2025
    log = PerModeloAggregationLogFields(
        modelo="347",
        period=_P_2024_ANNUAL,
        provider=PerModeloAggregationProvider.COUNTERPART,
        observation_count=1,
        source_kind_count=1,
        result_row_count=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationResult(
            modelo="347",
            period=_P_2024_ANNUAL,  # mismatch: aggregation says 2025
            provider=PerModeloAggregationProvider.COUNTERPART,
            aggregation=agg,
            source_kinds=(AggregationSourceKind.LEDGER_TRANSACTION,),
            log_fields=log,
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


def test_site9_result_rejects_provider_payload_type_mismatch() -> None:
    """``PerModeloAggregationResult._envelope_matches_payload`` raises ``AggregationConfigError``.

    Triggered by a provider / payload type mismatch.
    """
    from .._retenciones import RetencionObservation, RetencionScheme
    from .._service import PerModeloAggregationCommand, aggregate_per_modelo

    obs = RetencionObservation(
        source_kind="ledger_transaction",
        source_object_id="ret-2",
        perceptor_nif="B00000001",
        perceptor_name="Proveedor",
        scheme=RetencionScheme.WORK_INCOME,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2025-03-01",
    )
    cmd = PerModeloAggregationCommand(modelo="111", period=_P_2025_Q1, retencion_observations=(obs,))
    agg = aggregate_per_modelo(cmd).aggregation  # RetencionesAggregation
    log = PerModeloAggregationLogFields(
        modelo="111",
        period=_P_2025_Q1,
        provider=PerModeloAggregationProvider.COUNTERPART,
        observation_count=1,
        source_kind_count=1,
        result_row_count=1,
    )
    with pytest.raises(ValidationError) as exc_info:
        PerModeloAggregationResult(
            modelo="111",
            period=_P_2025_Q1,
            provider=PerModeloAggregationProvider.COUNTERPART,  # wrong provider for RetencionesAggregation
            aggregation=agg,
            source_kinds=(AggregationSourceKind.LEDGER_TRANSACTION,),
            log_fields=log,
        )
    causes = [e.get("ctx", {}).get("error") for e in exc_info.value.errors()]
    assert any(isinstance(c, AggregationConfigError) for c in causes)


# ---------------------------------------------------------------------------
# contract: StrEnum surface coverage — every source-kind constant uses AggregationSourceKind
# ---------------------------------------------------------------------------


def test_accepted_source_kinds_are_enum_members() -> None:
    """ACCEPTED_SOURCE_KINDS must be a tuple of AggregationSourceKind, not raw strings."""
    assert len(ACCEPTED_SOURCE_KINDS) == 4
    for kind in ACCEPTED_SOURCE_KINDS:
        assert isinstance(kind, AggregationSourceKind), (
            f"ACCEPTED_SOURCE_KINDS entry {kind!r} is {type(kind).__name__}, expected AggregationSourceKind"
        )


def test_accepted_source_kinds_covers_all_four_members() -> None:
    """ACCEPTED_SOURCE_KINDS must contain exactly the four canonical aggregation kinds.

    The retired bare ``INVOICE`` alias must not participate at this boundary.
    """
    expected = frozenset(
        {
            AggregationSourceKind.PAYABLE_INVOICE,
            AggregationSourceKind.COLLECTIBLE_INVOICE,
            AggregationSourceKind.LEDGER_TRANSACTION,
            AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
        },
    )
    actual = frozenset(ACCEPTED_SOURCE_KINDS)
    assert actual == expected, f"ACCEPTED_SOURCE_KINDS {actual} != canonical four {expected}"


def test_counterpart_canonical_source_kinds_are_enum_members() -> None:
    """_counterpart._CANONICAL_SOURCE_KINDS must contain AggregationSourceKind members."""
    from .._counterpart import _CANONICAL_SOURCE_KINDS as counterpart_kinds

    assert len(counterpart_kinds) == 4
    for kind in counterpart_kinds:
        assert isinstance(kind, AggregationSourceKind), (
            f"_counterpart._CANONICAL_SOURCE_KINDS entry {kind!r} is {type(kind).__name__}"
        )


def test_retenciones_canonical_source_kinds_are_enum_members() -> None:
    """_retenciones._CANONICAL_SOURCE_KINDS must contain AggregationSourceKind members."""
    from .._retenciones import _CANONICAL_SOURCE_KINDS as retenciones_kinds

    assert len(retenciones_kinds) == 4
    for kind in retenciones_kinds:
        assert isinstance(kind, AggregationSourceKind), (
            f"_retenciones._CANONICAL_SOURCE_KINDS entry {kind!r} is {type(kind).__name__}"
        )


def test_foreign_assets_canonical_source_kinds_are_enum_members() -> None:
    """_foreign_assets._CANONICAL_SOURCE_KINDS must contain AggregationSourceKind members."""
    from .._foreign_assets import _CANONICAL_SOURCE_KINDS as foreign_kinds

    assert len(foreign_kinds) == 4
    for kind in foreign_kinds:
        assert isinstance(kind, AggregationSourceKind), (
            f"_foreign_assets._CANONICAL_SOURCE_KINDS entry {kind!r} is {type(kind).__name__}"
        )


def test_registry_provider_counterpart_binding_source_kinds_are_enum_members() -> None:
    """_registry_provider._COUNTERPART_BINDING_SOURCE_KINDS must contain AggregationSourceKind members."""
    from .._registry_provider import _COUNTERPART_BINDING_SOURCE_KINDS

    assert len(_COUNTERPART_BINDING_SOURCE_KINDS) == 4
    for kind in _COUNTERPART_BINDING_SOURCE_KINDS:
        assert isinstance(kind, AggregationSourceKind), (
            f"_registry_provider._COUNTERPART_BINDING_SOURCE_KINDS entry {kind!r} is {type(kind).__name__}"
        )


def test_operator_accepted_kind_map_uses_enum_keys_for_aggregation_source_kinds() -> None:
    """_operator._ACCEPTED_KIND_TO_INTERNAL must use AggregationSourceKind for the four aggregation kinds."""
    from ...review._operator import _ACCEPTED_KIND_TO_INTERNAL

    aggregation_keys = {
        AggregationSourceKind.LEDGER_TRANSACTION,
        AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE,
        AggregationSourceKind.PAYABLE_INVOICE,
        AggregationSourceKind.COLLECTIBLE_INVOICE,
    }
    for key in aggregation_keys:
        assert key in _ACCEPTED_KIND_TO_INTERNAL, (
            f"AggregationSourceKind.{key.name} ({key!r}) not found as key in _ACCEPTED_KIND_TO_INTERNAL"
        )
        # StrEnum members compare equal to their string values, but isinstance confirms the type
        assert isinstance(key, AggregationSourceKind)


def test_aggregation_source_kind_values_are_stable() -> None:
    """AggregationSourceKind string values must remain stable."""
    assert AggregationSourceKind.LEDGER_TRANSACTION == "ledger_transaction"
    assert AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE == "purchase_invoice_evidence"
    assert AggregationSourceKind.PAYABLE_INVOICE == "payable_invoice"
    assert AggregationSourceKind.COLLECTIBLE_INVOICE == "collectible_invoice"
