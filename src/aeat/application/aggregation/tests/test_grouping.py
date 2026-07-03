"""Pin behavioural invariants of the shared group_and_collect_names helper."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import BindingSourceKind
from ....core.aggregation import RetencionScheme
from .._grouping import group_and_collect_names
from .._retenciones import RetencionObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_SOURCE_LEDGER = BindingSourceKind.LEDGER_TRANSACTION
_SOURCE_INVOICE = BindingSourceKind.COLLECTIBLE_INVOICE
_SCHEME_WORK = RetencionScheme.WORK_INCOME
_SCHEME_RENT = RetencionScheme.URBAN_RENTAL


def _observation(
    source_kind: BindingSourceKind,
    perceptor_nif: str,
    scheme: RetencionScheme,
    perceptor_name: str = "",
) -> RetencionObservation:
    return RetencionObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind.value}:{perceptor_nif}:{scheme.value}:{perceptor_name or 'empty'}",
        perceptor_nif=perceptor_nif,
        perceptor_name=perceptor_name,
        scheme=scheme,
        taxable_base=Decimal("1.00"),
        retencion_amount=Decimal("0.15"),
        accrued_on="2026-01-01",
    )


def _name(obs: RetencionObservation) -> str | None:
    return obs.perceptor_name or None


def _group_key(obs: RetencionObservation) -> tuple[BindingSourceKind, str, RetencionScheme]:
    return (BindingSourceKind(obs.source_kind), obs.perceptor_nif, obs.scheme)


def _identity_key(obs: RetencionObservation) -> tuple[BindingSourceKind, str]:
    return (BindingSourceKind(obs.source_kind), obs.perceptor_nif)


def test_group_and_collect_names_buckets_by_composite_key() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_RENT, "Alpha"),
        _observation(_SOURCE_LEDGER, "B", _SCHEME_WORK, "Beta"),
    )
    grouped, _ = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert set(grouped.keys()) == {
        (_SOURCE_LEDGER, "A", _SCHEME_WORK),
        (_SOURCE_LEDGER, "A", _SCHEME_RENT),
        (_SOURCE_LEDGER, "B", _SCHEME_WORK),
    }
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)]) == 2
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_RENT)]) == 1
    assert len(grouped[(_SOURCE_LEDGER, "B", _SCHEME_WORK)]) == 1


def test_group_and_collect_names_preserves_iteration_order_within_bucket() -> None:
    first = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha")
    second = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha-2nd")
    third = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha-3rd")
    grouped, _ = group_and_collect_names(
        (first, second, third),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)] == [first, second, third]


def test_group_and_collect_names_first_non_empty_name_wins() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "First Real Name"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Later Name"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "First Real Name"


def test_group_and_collect_names_skips_empty_names_without_clearing_prior_win() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Real Name"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, ""),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "Real Name"


def test_group_and_collect_names_separate_identities_get_separate_names() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "B", _SCHEME_WORK, "Beta"),
        _observation(_SOURCE_INVOICE, "A", _SCHEME_WORK, "Alpha-Invoice"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names == {
        (_SOURCE_LEDGER, "A"): "Alpha",
        (_SOURCE_LEDGER, "B"): "Beta",
        (_SOURCE_INVOICE, "A"): "Alpha-Invoice",
    }


def test_group_and_collect_names_empty_iterable_returns_empty_maps() -> None:
    grouped, names = group_and_collect_names(
        (),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped == {}
    assert names == {}


def test_group_and_collect_names_identity_subset_of_group_key_is_consistent() -> None:
    # When two different group keys share the same identity key (e.g.
    # same (source, nif) but different kind), the name cache must be
    # consistent — first non-empty name wins regardless of which group
    # observed it.
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_RENT, "Name From K2"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Name From K1"),
    )
    grouped, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "Name From K2"
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)]) == 2
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_RENT)]) == 1
