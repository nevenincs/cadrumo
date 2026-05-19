"""Read-only VAT rate registry."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from ...core.resources import bundled_path
from ._schema import EUMemberState, VATRate, VATRateKind
from .errors import VatCatalogueError, VatRateOverlapError, VatValidationError

def load_vat_rate_table(path: Path | None = None) -> Mapping[EUMemberState, tuple[VATRate, ...]]:
    """Load VAT rates from the committed registry file.

    Resolves the bundled rates path on every call so the
    `bundled_path` boundary stays the single resolution surface.
    """

    target = path if path is not None else bundled_path("registry", "aeat", "vat", "rates.toml")
    resolved = target.resolve()
    stat = resolved.stat()
    return _load_vat_rate_table_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _load_vat_rate_table_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> Mapping[EUMemberState, tuple[VATRate, ...]]:
    del byte_count, modified_ns
    target = Path(path)
    try:
        with target.open("rb") as fh:
            payload = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise VatCatalogueError(f"{target}: invalid VAT rate TOML: {exc}") from exc
    except OSError as exc:
        raise VatCatalogueError(f"{target}: cannot read VAT rate registry: {exc}") from exc

    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, list) or not raw_rates:
        raise VatCatalogueError(f"{target}: missing [[rates]] entries")

    by_member_state: dict[EUMemberState, list[VATRate]] = {}
    for index, raw_rate in enumerate(raw_rates, start=1):
        if not isinstance(raw_rate, dict):
            raise VatCatalogueError(f"{target}: rates[{index}] must be a table")
        try:
            rate = _parse_rate(raw_rate)
        except (ValidationError, VatValidationError, ValueError) as exc:
            raise VatCatalogueError(f"{target}: invalid rates[{index}]: {exc}") from exc
        by_member_state.setdefault(rate.member_state, []).append(rate)

    missing = sorted(member_state.value for member_state in set(EUMemberState) - set(by_member_state))
    if missing:
        raise VatCatalogueError(f"{target}: VAT rate registry missing member states: {missing}")

    immutable: dict[EUMemberState, tuple[VATRate, ...]] = {}
    for member_state, rates in by_member_state.items():
        partition = tuple(sorted(rates, key=lambda rate: (rate.kind.value, rate.effective_from)))
        _assert_no_overlap(member_state, partition)
        immutable[member_state] = partition
    return MappingProxyType(immutable)


def _parse_rate(raw_rate: object) -> VATRate:
    if not isinstance(raw_rate, dict):
        raise VatValidationError(f"VAT rate entry must be a table, got: {type(raw_rate)!r}")
    data: dict[str, object] = {str(k): v for k, v in raw_rate.items()}
    try:
        member_state = EUMemberState(str(data.get("member_state")))
        kind = VATRateKind(str(data.get("kind")))
        pct = Decimal(str(data.get("pct")))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise VatValidationError(f"invalid VAT rate key or pct: {raw_rate!r}") from exc
    return VATRate.model_validate(
        {
            "member_state": member_state,
            "kind": kind,
            "pct": pct,
            "effective_from": data.get("effective_from"),
            "effective_until": data.get("effective_until"),
            "boe_or_directive_reference": data.get("reference"),
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


__all__ = ["load_vat_rate_table"]
