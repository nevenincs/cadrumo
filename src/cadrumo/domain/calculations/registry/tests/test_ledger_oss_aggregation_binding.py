"""Tests for the ledger_oss_aggregation binding source kind.

The binding declares a regime, destination Member State, rate tier, and
invoice direction selector. The runtime resolver aggregates
substrate-classified ledger lines that match the selector.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from ....iva.classification import InvoiceKind, TransactionKind
from ....iva.oss import OssIossRegime
from ....iva.schema import EUMemberState, IvaRateKind
from ..binding_selector_utils import selector_as_dict
from ..errors import RegistryValidationError
from ..ledger_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    unsupported_ledger_oss_observations,
    validate_ledger_oss_aggregation_binding_definition,
)
from ..schema import DataBindingDefinition, ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_369_union_revision() -> ModeloRevision:
    modelo, _catalogues = _committed_modelo("369")
    return modelo.revisions["esquema-union"]


def _binding(binding_id: str = "modelo-369-union-de-services-21pct") -> DataBindingDefinition:
    return next(item for item in _modelo_369_union_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**selector_as_dict(binding), **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: BindingAggregationOp) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": BindingAggregation(op=op)})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    regime: OssIossRegime = OssIossRegime.UNION_SCHEME,
    destination: EUMemberState = EUMemberState.DE,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    direction: InvoiceKind = InvoiceKind.ISSUED,
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
    assert binding.selector, "binding must declare a selector for validation to be meaningful"
    result = validate_ledger_oss_aggregation_binding_definition(binding)
    assert result is None


@pytest.mark.parametrize(
    "selector_updates",
    (
        pytest.param({"regime": "bogus"}, id="regime"),
        pytest.param({"destination_member_state": "zz"}, id="destination-member-state"),
        pytest.param({"rate_kind": "medium"}, id="rate-kind"),
        pytest.param({"invoice_direction": "sideways"}, id="invoice-direction"),
        pytest.param({"transaction_kinds": ("ill-defined",)}, id="transaction-kind"),
        pytest.param({"transaction_kinds": ()}, id="empty-transaction-kinds"),
    ),
)
def test_validate_rejects_malformed_selector_values(selector_updates: dict[str, object]) -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), **selector_updates))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_oss_aggregation_binding_definition(_with_aggregation(_binding(), BindingAggregationOp.COPY))


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_oss_aggregation_binding_definition(_with_selector(_binding(), fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "manual_input"})
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


def test_unsupported_oss_flags_observation_routed_to_no_binding() -> None:
    """A non-zero OSS line whose classification matches no binding is surfaced.

    The revision binds only DE-destination union services; an FR-destination
    line reaches no binding and would silently vanish from the M369 cuota, so
    the fail-closed screen MUST report it (no-silent-under-declaration).
    """
    revision = _revision_with_bindings(_binding())
    routed = _observation(ledger_id="de-line", destination=EUMemberState.DE, iva=Decimal("19"))
    unrouted = _observation(ledger_id="fr-line", destination=EUMemberState.FR, iva=Decimal("20"))

    result = unsupported_ledger_oss_observations(revision, (routed, unrouted))
    assert result == (unrouted,)


def test_unsupported_oss_does_not_flag_zero_base_and_zero_iva() -> None:
    """An OSS line with zero base and zero IVA routed to no binding must NOT false-fire.

    A line carrying no declarable base or cuota contributes nothing whether or
    not it is routed, so the false-fire guard excludes it.
    """
    revision = _revision_with_bindings(_binding())
    zero_unrouted = _observation(
        ledger_id="fr-zero",
        destination=EUMemberState.FR,
        base=Decimal("0"),
        iva=Decimal("0"),
    )

    result = unsupported_ledger_oss_observations(revision, (zero_unrouted,))
    assert result == ()


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
        _observation(rate_kind=IvaRateKind.GENERAL, iva=Decimal("19")),
        _observation(rate_kind=IvaRateKind.REDUCED, iva=Decimal("100")),
    ]
    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {"modelo-369-union-de-services-21pct": Decimal("19")}


def test_resolve_filters_observations_by_invoice_direction() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(direction=InvoiceKind.ISSUED, iva=Decimal("19")),
        _observation(direction=InvoiceKind.RECEIVED, iva=Decimal("100")),
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
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        obs.iva_amount = Decimal("999")
