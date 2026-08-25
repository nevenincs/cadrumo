"""Read-only IVA rate registry.

:func:`load_iva_rate_table` validates committed rate TOML into mappings from
:class:`EUMemberState` to dated :class:`IvaRateRecord` windows partitioned by
:class:`IvaRateKind`, rejecting same-kind overlaps with
:class:`IvaRateOverlapError`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER, read_toml
from ...core.decimal import coerce_decimal
from ...core.paths import path_stat_fingerprint
from ...core.resources import bundled_path
from .errors import IvaCatalogueError, IvaRateOverlapError, IvaValidationError
from ._grounding import legal_ref_failures, registry_catalogues
from ._schema import EUMemberState, IvaRateKind, IvaRateRecord

if TYPE_CHECKING:
    # Type-only: importing these at runtime would close the cycle the local
    # imports in the grounding helpers below exist to avoid.
    from cadrumo.domain.calculations.registry.schema import SourceReference


_RATE_REGISTRY_MEMBER_STATES: frozenset[EUMemberState] = frozenset(
    member_state for member_state in EUMemberState if member_state is not EUMemberState.XI
)
"""Jurisdictions that must carry rate rows.

``XI`` is a Northern Ireland IVA prefix for goods, not a state with its own IVA
rate table, so it is intentionally excluded from the rate-registry completeness
gate.
"""


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
        fingerprint = path_stat_fingerprint(resolved)
    except OSError as exc:
        raise IvaCatalogueError(f"{resolved}: cannot stat IVA rate registry: {exc}") from exc
    return _load_iva_rate_table_cached(*fingerprint)


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
    for index, raw_rate in enumerate(OBJECT_TUPLE_ADAPTER.validate_python(raw_rates), start=1):
        if not isinstance(raw_rate, Mapping):
            raise IvaCatalogueError(f"{target}: rates[{index}] must be a table")
        try:
            rate = _parse_rate(STR_KEYED_MAPPING_ADAPTER.validate_python(raw_rate))
        except (ValidationError, IvaValidationError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: invalid rates[{index}]: {exc}") from exc
        by_member_state.setdefault(rate.member_state, []).append(rate)

    missing = sorted(member_state.value for member_state in _RATE_REGISTRY_MEMBER_STATES - set(by_member_state))
    if missing:
        raise IvaCatalogueError(f"{target}: IVA rate registry missing member states: {missing}")

    immutable: dict[EUMemberState, tuple[IvaRateRecord, ...]] = {}
    for member_state, rates in by_member_state.items():
        partition = tuple(sorted(rates, key=lambda rate: (rate.kind.value, rate.effective_from)))
        _assert_no_overlap(member_state, partition)
        immutable[member_state] = partition
    result = MappingProxyType(immutable)
    _verify_rate_grounding(result)
    return result


def _parse_rate(raw_rate: object) -> IvaRateRecord:
    if not isinstance(raw_rate, dict):
        raise IvaValidationError(f"IVA rate entry must be a table, got: {type(raw_rate)!r}")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw_rate)
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
            "legal_refs": _reference_ids(data, "legal_refs"),
            "source_refs": _reference_ids(data, "source_refs"),
            # Every field the record carries must be listed here: this builds
            # the model from an explicit mapping, so a TOML key absent from it
            # is DROPPED without error and the field silently takes its default.
            "supersedes_tier_default": data.get("supersedes_tier_default", False),
        },
    )


def _reference_ids(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    """Read one TOML array shape without accepting scalar coercion."""
    if key not in data:
        return ()
    raw = data.get(key)
    if not isinstance(raw, (list, tuple)):
        raise IvaValidationError(f"{key} must be an array")
    reference_ids: list[str] = []
    for item in OBJECT_TUPLE_ADAPTER.validate_python(raw):
        if not isinstance(item, str):
            raise IvaValidationError(f"{key} must contain only registry identity strings")
        reference_ids.append(item)
    return tuple(reference_ids)


def _source_window_covers(reference: SourceReference, rate: IvaRateRecord) -> bool:
    """Report whether one source's applicability window spans the rate's whole period."""
    if reference.applies_from is None or reference.applies_from > rate.effective_from:
        return False
    if reference.applies_to is None:
        return True
    return rate.effective_until is not None and rate.effective_until <= reference.applies_to


def _source_window_failure(
    rate: IvaRateRecord,
    row: str,
    row_sources: Sequence[SourceReference],
) -> str | None:
    """Report the uncovered-applicability-window refusal for one row, or ``None``.

    Spanish rows are exempt by design: an ES rate is grounded through its
    ``legal_refs`` against the BOE catalogue rather than through a foreign
    source's applicability window, so applying the window check to ES would
    refuse every Spanish row.

    ``row_sources`` must carry EVERY resolvable source on the row, including
    ones already verified on an earlier row; see :func:`_source_ref_failures`.
    """
    if rate.member_state is EUMemberState.ES:
        return None
    if any(_source_window_covers(reference, rate) for reference in row_sources):
        return None
    return f"{row}: no source_ref applicability window covers {rate.effective_from}/{rate.effective_until}"


def _source_ref_failures(
    rate: IvaRateRecord,
    row: str,
    sources: Mapping[str, SourceReference],
    source_root: Path,
    verified_sources: set[str],
) -> tuple[list[str], list[SourceReference]]:
    """Resolve and verify one row's source refs, returning failures and the row's sources.

    Every resolvable source joins ``row_sources`` BEFORE the memoisation check,
    so a source already verified on an earlier row still counts toward THIS
    row's applicability window. Collecting after the memo check instead would
    hide repeat sources from :func:`_source_window_failure`, which would then
    refuse rows whose grounding is in fact present.
    """
    # Keep this import local: registry binding modules consume the public IVA
    # facade, while the rate loader is also part of that facade.
    from cadrumo.domain.calculations.registry.corpus_catalogue import verify_source_file
    from cadrumo.domain.calculations.registry.errors import RegistryValidationError

    failures: list[str] = []
    row_sources: list[SourceReference] = []
    for ref_id in rate.source_refs:
        reference = sources.get(ref_id)
        if reference is None:
            failures.append(f"{row}: unknown source_ref {ref_id!r}")
            continue
        row_sources.append(reference)
        if ref_id in verified_sources:
            continue
        try:
            verify_source_file(source_root, reference)
        except RegistryValidationError as exc:
            failures.append(f"{row}: invalid source_ref {ref_id!r}: {exc}")
            continue
        verified_sources.add(ref_id)
    return failures, row_sources


def _verify_rate_grounding(
    table: Mapping[EUMemberState, tuple[IvaRateRecord, ...]],
) -> None:
    """Resolve and verify every legal/source identity carried by rate rows.

    The legal half delegates to the shared IVA grounding verifier, which every
    other registry table under ``registry/aeat/iva/`` also routes through; the
    source-reference and applicability-window halves stay here because they are
    properties of a rate row rather than of a citation.
    """
    legal, sources, source_root = registry_catalogues()
    verified_legal: set[str] = set()
    verified_sources: set[str] = set()
    failures: list[str] = []

    for rates in table.values():
        for rate in rates:
            row = f"{rate.member_state.value}/{rate.kind.value}/{rate.effective_from.isoformat()}"
            failures.extend(legal_ref_failures(row, rate.legal_refs, legal, source_root, verified_legal))
            source_failures, row_sources = _source_ref_failures(rate, row, sources, source_root, verified_sources)
            failures.extend(source_failures)
            window_failure = _source_window_failure(rate, row, row_sources)
            if window_failure is not None:
                failures.append(window_failure)

    if failures:
        raise IvaCatalogueError("IVA rate grounding verification failed:\n" + "\n".join(f" - {f}" for f in failures))


def _assert_no_overlap(
    member_state: EUMemberState,
    rates: Iterable[IvaRateRecord],
) -> None:
    """Raise on any same-kind date-window overlap between TIER-DEFINING rates.

    Rates flagged ``supersedes_tier_default`` are excluded, because they exist
    precisely to overlap: a statute applied them to part of a tier's supplies
    while the rest stayed on the ordinary rate, so both are simultaneously
    correct. Including them would make the rule reject the very shape it is
    meant to permit, while excluding the ordinary records from it would let two
    genuine tier definitions collide unnoticed -- which is the ambiguity
    :func:`lookup_rate` relies on this rule to prevent.
    """
    by_kind: dict[IvaRateKind, list[IvaRateRecord]] = {}
    for rate in rates:
        if rate.supersedes_tier_default:
            continue
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
