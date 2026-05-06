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

import pytest

from aeat.domain.calculations.registry._bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    validate_ledger_oss_aggregation_binding_definition,
)
from aeat.domain.calculations.registry._errors import RegistryValidationError
from aeat.domain.calculations.registry._schema import (
    DataBindingDefinition,
    ModeloRevision,
    PeriodSelector,
)
from aeat.domain.vat import (
    EUMemberState,
    InvoiceDirection,
    OssIossRegime,
    TransactionKind,
    VATRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _binding(
    *,
    id: str = "modelo-369-union-de-services-21pct",
    regime: str = "union_scheme",
    destination: str = "de",
    rate_kind: str = "general",
    direction: str = "issued",
    kinds: tuple[str, ...] = ("oss_union_services",),
    fact: str | None = None,
    aggregation: dict[str, str] | None = None,
) -> DataBindingDefinition:
    selector: dict[str, object] = {
        "regime": regime,
        "destination_member_state": destination,
        "rate_kind": rate_kind,
        "invoice_direction": direction,
        "transaction_kinds": kinds,
    }
    if fact is not None:
        selector["fact"] = fact
    return DataBindingDefinition(
        id=id,
        source="ledger_oss_aggregation",
        selector=selector,
        aggregation=aggregation if aggregation is not None else {"op": "sum"},
        legal_refs=("orden-hac-610-2021:art-1",),
        source_refs=("aeat-dr-369-2021",),
    )


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
    return ModeloRevision(
        id="esquema-union",
        valid_from=date(2021, 7, 1),
        period_selector=PeriodSelector(
            year_from=2021, periods=("UN-1T", "UN-2T", "UN-3T", "UN-4T")
        ),
        legal_refs=("orden-hac-610-2021:art-1",),
        source_refs=("aeat-dr-369-2021",),
        bindings=bindings,
    )


def test_validate_accepts_canonical_oss_union_binding() -> None:
    binding = _binding()
    validate_ledger_oss_aggregation_binding_definition(binding)


def test_validate_rejects_unknown_regime() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(regime="bogus"))


def test_validate_rejects_unknown_destination_member_state() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(destination="zz"))


def test_validate_rejects_unknown_rate_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(rate_kind="medium"))


def test_validate_rejects_unknown_invoice_direction() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(direction="sideways"))


def test_validate_rejects_unknown_transaction_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(kinds=("ill-defined",)))


def test_validate_rejects_empty_transaction_kinds() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(kinds=()))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_oss_aggregation_binding_definition(
            _binding(aggregation={"op": "max"})
        )


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_binding(fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = DataBindingDefinition(
        id="x",
        source="invoice",
        selector={"regime": "union_scheme"},
        legal_refs=("orden-hac-610-2021:art-1",),
        source_refs=("aeat-dr-369-2021",),
    )
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
    revision = _revision_with_bindings(
        _binding(kinds=("oss_union_services", "oss_union_goods_distance_sale"))
    )
    observations = [
        _observation(kind=TransactionKind.OSS_UNION_SERVICES, iva=Decimal("10")),
        _observation(kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE, iva=Decimal("20")),
        _observation(kind=TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED, iva=Decimal("99")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("30")}


def test_resolve_returns_zero_when_no_observations_match() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [_observation(destination=EUMemberState.FR, iva=Decimal("100"))]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("0")}


def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = _revision_with_bindings(_binding(fact="base_amount_sum"))
    observations = [
        _observation(base=Decimal("100"), iva=Decimal("19")),
        _observation(base=Decimal("200"), iva=Decimal("38")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("300")}


def test_resolve_handles_multiple_bindings_independently() -> None:
    de_services = _binding(
        id="m369-union-de-services",
        destination="de",
        kinds=("oss_union_services",),
    )
    fr_services = _binding(
        id="m369-union-fr-services",
        destination="fr",
        kinds=("oss_union_services",),
    )
    revision = _revision_with_bindings(de_services, fr_services)
    observations = [
        _observation(destination=EUMemberState.DE, iva=Decimal("19")),
        _observation(destination=EUMemberState.FR, iva=Decimal("23")),
        _observation(destination=EUMemberState.DE, iva=Decimal("21")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {
        "m369-union-de-services": Decimal("40"),
        "m369-union-fr-services": Decimal("23"),
    }


def test_resolve_ignores_non_oss_bindings_on_the_revision() -> None:
    """Other binding source kinds on the same revision must not be resolved
    by the OSS aggregator."""
    other = DataBindingDefinition(
        id="some-manual-input",
        source="manual_input",
        selector={"casilla": "01"},
        legal_refs=("orden-hac-610-2021:art-1",),
        source_refs=("aeat-dr-369-2021",),
    )
    revision = _revision_with_bindings(_binding(), other)
    observations = [_observation(iva=Decimal("19"))]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}
    assert "some-manual-input" not in result


def test_oss_iross_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(Exception):  # noqa: PT011 — pydantic ValidationError on frozen mutation
        obs.iva_amount = Decimal("999")  # type: ignore[misc]
