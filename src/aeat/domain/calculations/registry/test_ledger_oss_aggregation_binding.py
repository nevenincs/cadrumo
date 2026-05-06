"""Tests for the ledger_oss_aggregation binding source kind.

Covers ADR Decision 8 from the Modelo 369 VAT centralization ADR:
the binding declares a regime + destination Member State + rate
tier + invoice direction selector, and the runtime resolver
aggregates substrate-classified ledger lines that match the
selector. This is the precondition unblock for Modelo 369 registry
slices.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest
from pydantic import ValidationError

from aeat.core.paths import PROJECT_ROOT
from aeat.domain.calculations.registry import load_registry_tree
from aeat.domain.calculations.registry._bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    validate_ledger_oss_aggregation_binding_definition,
)
from aeat.domain.calculations.registry._errors import RegistryValidationError
from aeat.domain.calculations.registry._schema import DataBindingDefinition, ModeloRevision
from aeat.domain.vat import (
    EUMemberState,
    InvoiceDirection,
    OssIossRegime,
    TransactionKind,
    VATRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@lru_cache(maxsize=1)
def _modelo_369_union_revision() -> ModeloRevision:
    modelos, _catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "369")
    return modelo.revisions["esquema-union"]


def _binding(binding_id: str = "modelo-369-union-de-services-21pct") -> DataBindingDefinition:
    return next(item for item in _modelo_369_union_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**binding.selector, **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: str) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": {"op": op}})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    regime: OssIossRegime = OssIossRegime.UNION_SCHEME,
    destination: EUMemberState = EUMemberState.DE,
    rate_kind: VATRateKind = VATRateKind.GENERAL,
    direction: InvoiceDirection = InvoiceDirection.ISSUED,
    kind: TransactionKind = TransactionKind.OSS_UNION_SERVICES,
    base: Decimal = Decimal("100"),
    iva: Decimal = Decimal("19"),
) -> OssIossLedgerObservation:
    return OssIossLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        regime=regime,
        destination_member_state=destination,
        rate_kind=rate_kind,
        invoice_direction=direction,
        transaction_kind=kind,
        base_amount=base,
        iva_amount=iva,
    )


def _revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_369_union_revision().model_copy(update={"bindings": bindings})


def test_validate_accepts_canonical_oss_union_binding() -> None:
    binding = _binding()
    validate_ledger_oss_aggregation_binding_definition(binding)


def test_validate_rejects_unknown_regime() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), regime="bogus"))


def test_validate_rejects_unknown_destination_member_state() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), destination_member_state="zz"))


def test_validate_rejects_unknown_rate_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), rate_kind="medium"))


def test_validate_rejects_unknown_invoice_direction() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), invoice_direction="sideways"))


def test_validate_rejects_unknown_transaction_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(
            _with_selector(_binding(), transaction_kinds=("ill-defined",))
        )


def test_validate_rejects_empty_transaction_kinds() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), transaction_kinds=()))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_oss_aggregation_binding_definition(_with_aggregation(_binding(), "max"))


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "invoice"})
    with pytest.raises(RegistryValidationError, match="not a ledger_oss_aggregation"):
        validate_ledger_oss_aggregation_binding_definition(binding)


def test_resolve_aggregates_iva_amount_for_matching_observations() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(ledger_id="a", iva=Decimal("19")),
        _observation(ledger_id="b", iva=Decimal("21")),
        _observation(ledger_id="c", iva=Decimal("38")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("78")}


def test_resolve_filters_observations_by_destination_member_state() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(destination=EUMemberState.DE, iva=Decimal("19")),
        _observation(destination=EUMemberState.FR, iva=Decimal("20")),
        _observation(destination=EUMemberState.IT, iva=Decimal("22")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}


def test_resolve_filters_observations_by_regime() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(regime=OssIossRegime.UNION_SCHEME, iva=Decimal("19")),
        _observation(regime=OssIossRegime.IMPORT_SCHEME, iva=Decimal("100")),
        _observation(regime=OssIossRegime.EXTERNAL_SCHEME, iva=Decimal("200")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}


def test_resolve_filters_observations_by_rate_kind() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(rate_kind=VATRateKind.GENERAL, iva=Decimal("19")),
        _observation(rate_kind=VATRateKind.REDUCED, iva=Decimal("100")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}


def test_resolve_filters_observations_by_invoice_direction() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(direction=InvoiceDirection.ISSUED, iva=Decimal("19")),
        _observation(direction=InvoiceDirection.RECEIVED, iva=Decimal("100")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}


def test_resolve_filters_observations_by_transaction_kind_set() -> None:
    revision = _revision_with_bindings(_binding("modelo-369-union-de-goods-distance-21pct"))
    observations = [
        _observation(kind=TransactionKind.OSS_UNION_SERVICES, iva=Decimal("10")),
        _observation(kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE, iva=Decimal("20")),
        _observation(kind=TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED, iva=Decimal("99")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-goods-distance-21pct": Decimal("119")}


def test_resolve_returns_zero_when_no_observations_match() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [_observation(destination=EUMemberState.FR, iva=Decimal("100"))]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("0")}


def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = _revision_with_bindings(_with_selector(_binding(), fact="base_amount_sum"))
    observations = [
        _observation(base=Decimal("100"), iva=Decimal("19")),
        _observation(base=Decimal("200"), iva=Decimal("38")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("300")}


def test_resolve_handles_multiple_bindings_independently() -> None:
    revision = _revision_with_bindings(
        _binding("modelo-369-union-de-services-21pct"),
        _binding("modelo-369-union-fr-services-21pct"),
    )
    observations = [
        _observation(destination=EUMemberState.DE, iva=Decimal("19")),
        _observation(destination=EUMemberState.FR, iva=Decimal("23")),
        _observation(destination=EUMemberState.DE, iva=Decimal("21")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-369-union-de-services-21pct": Decimal("40"),
        "modelo-369-union-fr-services-21pct": Decimal("23"),
    }


def test_resolve_ignores_non_oss_bindings_on_the_revision() -> None:
    """Other binding source kinds on the same revision must not be resolved
    by the OSS aggregator."""
    other = _binding("modelo-369-union-fr-services-21pct").model_copy(update={"source": "manual_input"})
    revision = _revision_with_bindings(_binding(), other)
    observations = [_observation(iva=Decimal("19"))]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}
    assert "modelo-369-union-fr-services-21pct" not in result


def test_oss_iross_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError):
        obs.iva_amount = Decimal("999")  # type: ignore[misc]
