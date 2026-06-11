"""Read-only IVA rate registry."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from ...core import read_toml
from ...core.decimal import coerce_decimal
from ...core.resources import bundled_path
from ._errors import IvaCatalogueError, IvaRateOverlapError, IvaValidationError
from ._schema import EUMemberState, IvaRateKind, IvaRateRecord


def load_iva_rate_table(path: Path | None = None) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    """Load IVA rates from the committed registry file.

    Resolves the bundled rates path on every call so the
    `bundled_path` boundary stays the single resolution surface.

    Returns:
        Mapping from :class:`EUMemberState` to a tuple of :class:`IvaRateRecord` items.
    """
    target = path if path is not None else bundled_path("registry", "aeat", "iva", "rates.toml")
    resolved = target.resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise IvaCatalogueError(f"{resolved}: cannot stat IVA rate registry: {exc}") from exc
    return _load_iva_rate_table_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _load_iva_rate_table_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    del byte_count, modified_ns
    target = Path(path)
    payload = read_toml(target, error_factory=IvaCatalogueError)

    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, list) or not raw_rates:
        raise IvaCatalogueError(f"{target}: missing [[rates]] entries")

    by_member_state: dict[EUMemberState, list[IvaRateRecord]] = {}
    for index, raw_rate in enumerate(raw_rates, start=1):
        if not isinstance(raw_rate, dict):
            raise IvaCatalogueError(f"{target}: rates[{index}] must be a table")
        try:
            rate = _parse_rate(raw_rate)
        except (ValidationError, IvaValidationError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: invalid rates[{index}]: {exc}") from exc
        by_member_state.setdefault(rate.member_state, []).append(rate)

    missing = sorted(member_state.value for member_state in set(EUMemberState) - set(by_member_state))
    if missing:
        raise IvaCatalogueError(f"{target}: IVA rate registry missing member states: {missing}")

    immutable: dict[EUMemberState, tuple[IvaRateRecord, ...]] = {}
    for member_state, rates in by_member_state.items():
        partition = tuple(sorted(rates, key=lambda rate: (rate.kind.value, rate.effective_from)))
        _assert_no_overlap(member_state, partition)
        immutable[member_state] = partition
    return MappingProxyType(immutable)


def _parse_rate(raw_rate: object) -> IvaRateRecord:
    if not isinstance(raw_rate, dict):
        raise IvaValidationError(f"IVA rate entry must be a table, got: {type(raw_rate)!r}")
    data: dict[str, object] = {str(k): v for k, v in raw_rate.items()}
    try:
        member_state = EUMemberState(str(data.get("member_state")))
        kind = IvaRateKind(str(data.get("kind")))
        pct = coerce_decimal(data.get("pct"))
        if pct is None:
            raise ValueError(f"pct field could not be parsed: {data.get('pct')!r}")
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise IvaValidationError(f"invalid IVA rate key or pct: {raw_rate!r}") from exc
    return IvaRateRecord.model_validate(
        {
            "member_state": member_state,
            "kind": kind,
            "pct": pct,
            "effective_from": data.get("effective_from"),
            "effective_until": data.get("effective_until"),
            "boe_or_directive_reference": data.get("reference"),
        },
    )


def _assert_no_overlap(
    member_state: EUMemberState,
    rates: Iterable[IvaRateRecord],
) -> None:
    """Raise on any same-kind date-window overlap."""
    by_kind: dict[IvaRateKind, list[IvaRateRecord]] = {}
    for rate in rates:
        by_kind.setdefault(rate.kind, []).append(rate)
    for kind, partition in by_kind.items():
        ordered = sorted(partition, key=lambda rate: rate.effective_from)
        for idx in range(1, len(ordered)):
            previous = ordered[idx - 1]
            current = ordered[idx]
            previous_end = previous.effective_until or date.max
            if previous_end >= current.effective_from:
                raise IvaRateOverlapError(
                    f"IVA rate registry has overlapping windows for "
                    f"member_state={member_state.value!r} kind={kind.value!r}: "
                    f"{previous.effective_from}/{previous.effective_until} vs. "
                    f"{current.effective_from}/{current.effective_until}",
                )


__all__ = ["load_iva_rate_table"]
