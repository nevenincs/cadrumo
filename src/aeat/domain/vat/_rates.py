"""Read-only VAT rate registry."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from pydantic import ValidationError

from ...core.paths import PROJECT_ROOT
from ._schema import EUMemberState, VATRate, VATRateKind
from .errors import VatCatalogueError, VatRateOverlapError

_DEFAULT_RATE_REGISTRY = PROJECT_ROOT / "registry" / "aeat" / "vat" / "rates.toml"


def load_vat_rate_table(path: Path = _DEFAULT_RATE_REGISTRY) -> Mapping[EUMemberState, tuple[VATRate, ...]]:
    """Load VAT rates from the committed registry file."""

    try:
        with path.open("rb") as fh:
            payload = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise VatCatalogueError(f"{path}: invalid VAT rate TOML: {exc}") from exc
    except OSError as exc:
        raise VatCatalogueError(f"{path}: cannot read VAT rate registry: {exc}") from exc

    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, list) or not raw_rates:
        raise VatCatalogueError(f"{path}: missing [[rates]] entries")

    by_member_state: dict[EUMemberState, list[VATRate]] = {}
    for index, raw_rate in enumerate(raw_rates, start=1):
        if not isinstance(raw_rate, dict):
            raise VatCatalogueError(f"{path}: rates[{index}] must be a table")
        try:
            rate = _parse_rate(cast("Mapping[str, Any]", raw_rate))
        except (ValidationError, ValueError) as exc:
            raise VatCatalogueError(f"{path}: invalid rates[{index}]: {exc}") from exc
        by_member_state.setdefault(rate.member_state, []).append(rate)

    missing = sorted(member_state.value for member_state in set(EUMemberState) - set(by_member_state))
    if missing:
        raise VatCatalogueError(f"{path}: VAT rate registry missing member states: {missing}")

    immutable: dict[EUMemberState, tuple[VATRate, ...]] = {}
    for member_state, rates in by_member_state.items():
        partition = tuple(sorted(rates, key=lambda rate: (rate.kind.value, rate.effective_from)))
        _assert_no_overlap(member_state, partition)
        immutable[member_state] = partition
    return MappingProxyType(immutable)


def _parse_rate(raw_rate: Mapping[str, Any]) -> VATRate:
    try:
        member_state = EUMemberState(str(raw_rate.get("member_state")))
        kind = VATRateKind(str(raw_rate.get("kind")))
        pct = Decimal(str(raw_rate.get("pct")))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid VAT rate key or pct: {raw_rate!r}") from exc
    return VATRate.model_validate(
        {
            "member_state": member_state,
            "kind": kind,
            "pct": pct,
            "effective_from": raw_rate.get("effective_from"),
            "effective_until": raw_rate.get("effective_until"),
            "boe_or_directive_reference": raw_rate.get("reference"),
        }
    )


def _assert_no_overlap(
    member_state: EUMemberState,
    rates: Iterable[VATRate],
) -> None:
    """Raise on any same-kind date-window overlap."""

    by_kind: dict[VATRateKind, list[VATRate]] = {}
    for rate in rates:
        by_kind.setdefault(rate.kind, []).append(rate)
    for kind, partition in by_kind.items():
        ordered = sorted(partition, key=lambda rate: rate.effective_from)
        for idx in range(1, len(ordered)):
            previous = ordered[idx - 1]
            current = ordered[idx]
            previous_end = previous.effective_until or date.max
            if previous_end >= current.effective_from:
                raise VatRateOverlapError(
                    f"VAT rate registry has overlapping windows for "
                    f"member_state={member_state.value!r} kind={kind.value!r}: "
                    f"{previous.effective_from}/{previous.effective_until} vs. "
                    f"{current.effective_from}/{current.effective_until}"
                )


VAT_RATE_TABLE: Mapping[EUMemberState, tuple[VATRate, ...]] = load_vat_rate_table()

__all__ = ["VAT_RATE_TABLE", "load_vat_rate_table"]
