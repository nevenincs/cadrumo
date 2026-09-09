"""Registry-backed loader for LIVA art. 161 recargo de equivalencia rates.

Closes the recargo de equivalencia rate gap in the IVA substrate:
the four LIVA art. 161 rate values (general 5.2 %, reduced 1.4 %,
super-reduced 0.5 %, tobacco 1.75 %) live in
``registry/aeat/legal/iva-recargo-equivalencia.toml`` under
``[parameters."liva-art-161:*"]`` entries with explicit BOE
citations and review metadata, and Python consumers import them
from this module.

The loader exposes a frozen pydantic record loaded once at module import time, with an explicit
:func:`recargo_rate_for_applied_rate` lookup that answers from the rate a
line actually carried and the date it carried it.
The ``LIVA_ART_161_RECARGO`` accessor is the canonical source for
recargo de equivalencia rates across the codebase.

The recargo de equivalencia regime (LIVA arts. 148-163) applies to
comerciantes minoristas (retailers) with limited annual revenue who
buy stock for resale; their suppliers charge them an additional
recargo on top of the regular IVA rate. The four rates align with
the four IVA tiers per LIVA art. 161:

* General (21 % IVA) → 5.2 % recargo (art. 161 1.º).
* Reduced (10 % IVA, art. 91 uno) → 1.4 % recargo (art. 161 2.º).
* Super-reduced (4 % IVA, art. 91 dos) → 0.5 % recargo (art. 161 3.º).
* Tobacco-specific → 1.75 % recargo (art. 161 4.º).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, model_validator

from ...core.decimal.coercion import coerce_decimal_strict
from ...core.external_constants import UTF_8_ENCODING
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.paths import path_stat_fingerprint
from ...core.resources.bundled_data import bundled_path
from ...core.revision_review import RevisionReviewStatus
from ...core.type_guards import is_object_list
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    MappingFactEntry,
    MappingFactPayload,
)
from ..calculations.registry.loader_cache import toml_file_fingerprint
from ..calculations.registry.loader_fingerprints import RegistryPathFingerprints
from ..calculations.registry.schema_base import DateAxis
from ._grounding import verify_table_legal_refs
from .errors import IvaCatalogueError, IvaValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

IVA_RECARGO_FACT_ID = "iva-recargo-by-applied-rate"


class RecargoRateRecord(BaseModel):
    """One recargo de equivalencia rate, paired with the IVA rate it accompanies.

    Keyed on the accompanying IVA rate rather than on its tier. LIVA art. 161
    pairs each recargo with a tier, and that was a sufficient key only while a
    tier had exactly one rate. Between 2023-01-01 and 2024-09-30 the reduced
    tier carried both its ordinary 10 % and the transitional 5 %, with different
    recargos, so the tier no longer identifies the pairing and the rate does.

    Attributes:
        iva_rate: The IVA rate this recargo accompanies, as a fraction.
        recargo_rate: The recargo rate itself, as a fraction. Zero is a
            legitimate value and means a rate of zero, not an absent one.
        effective_from: First date the pairing applies.
        effective_until: Last date it applies, or ``None`` for open-ended.
        legal_refs: Registry legal-reference identities establishing the value.
        notes: Authoring note; carries no runtime meaning.
    """

    model_config = STRICT_FROZEN_CONFIG

    iva_rate: UnitProportion
    recargo_rate: Decimal = Field(ge=Decimal("0"), lt=Decimal("1"))
    effective_from: date
    effective_until: date | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _validate_window(self) -> RecargoRateRecord:
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise IvaValidationError(
                f"RecargoRateRecord[iva_rate={self.iva_rate}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}",
            )
        return self

    def covers(self, on_date: date) -> bool:
        """Report whether this record's window contains ``on_date``."""
        if on_date < self.effective_from:
            return False
        return self.effective_until is None or on_date <= self.effective_until


def load_recargo_rate_table(path: Path | None = None) -> tuple[RecargoRateRecord, ...]:
    """Load the windowed recargo de equivalencia rate table from the registry.

    Resolves the bundled path on every call so ``bundled_path`` stays the single
    resolution surface, mirroring the IVA rate table loader.

    Returns:
        Every :class:`RecargoRateRecord` in the committed table.

    Raises:
        IvaCatalogueError: If the table cannot be read.
        IvaValidationError: If a record is malformed, or if two records claim
            the same IVA rate over overlapping windows.
    """
    target = path if path is not None else bundled_path("registry", "aeat", "iva", "recargo-rates.toml")
    resolved = target.resolve()
    try:
        fingerprint = path_stat_fingerprint(resolved)
    except OSError as exc:
        raise IvaCatalogueError(f"{resolved}: cannot stat recargo rate registry: {exc}") from exc
    return _load_recargo_rate_table_cached(*fingerprint)


@lru_cache(maxsize=16)
def _load_recargo_rate_table_cached(path: str, byte_count: int, modified_ns: int) -> tuple[RecargoRateRecord, ...]:
    del byte_count, modified_ns
    target = Path(path)
    try:
        payload = tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read recargo rate registry: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaValidationError(f"{target}: malformed recargo rate registry: {exc}") from exc

    rows = payload.get("recargo_rates", ())
    try:
        records = tuple(RecargoRateRecord.model_validate(_hydrate_row(row)) for row in rows)
    except (ValueError, TypeError) as exc:
        raise IvaValidationError(f"{target}: invalid recargo rate record: {exc}") from exc
    _reject_overlapping_windows(records)
    verify_table_legal_refs(
        str(target),
        [(f"{record.iva_rate}/{record.effective_from.isoformat()}", record.legal_refs) for record in records],
    )
    return records


def _hydrate_row(row: Mapping[str, object]) -> dict[str, object]:
    """Widen TOML scalars to the strict model's types at the load boundary.

    The record model is strict, so the authoring tree's strings stay strings
    until here. Rates are authored as strings rather than TOML floats because a
    float cannot represent 0.0062 exactly and a recargo is money-bearing.
    """
    hydrated = dict(row)
    for field in ("iva_rate", "recargo_rate"):
        raw = hydrated.get(field)
        if isinstance(raw, str):
            # DECIMAL-TEXT-RATIONALE-RECARGO-TOML-RATE: authored TOML scalar, not
            # operator text -- the separator convention is Python/TOML decimal-point
            # literal syntax, fixed by the authoring format rather than chosen by a
            # human typist, so there is no European/American thousands ambiguity here.
            hydrated[field] = coerce_decimal_strict(raw)
    raw_refs = hydrated.get("legal_refs")
    if is_object_list(raw_refs):
        hydrated["legal_refs"] = _coerce_legal_refs(raw_refs)
    return hydrated


def _coerce_legal_refs(refs: list[object]) -> tuple[str, ...]:
    """Validate and widen a raw TOML ``legal_refs`` array to ``tuple[str, ...]``."""
    coerced: list[str] = []
    for ref in refs:
        if not isinstance(ref, str):
            raise IvaValidationError(f"legal_refs entries must be strings, got {type(ref)!r}")
        coerced.append(ref)
    return tuple(coerced)


def _reject_overlapping_windows(records: tuple[RecargoRateRecord, ...]) -> None:
    """Refuse two records claiming one IVA rate over overlapping windows.

    Without this a lookup would silently answer with whichever record happened
    to be first, which is the failure mode that made the tier-keyed shape
    unsafe in the first place -- an ambiguous key resolving to a plausible
    answer rather than to a refusal.
    """
    open_ended = date.max
    by_rate: dict[Decimal, list[RecargoRateRecord]] = {}
    for record in records:
        by_rate.setdefault(record.iva_rate, []).append(record)
    for iva_rate, group in by_rate.items():
        for index, first in enumerate(group):
            for second in group[index + 1 :]:
                first_end = first.effective_until or open_ended
                second_end = second.effective_until or open_ended
                if first.effective_from <= second_end and second.effective_from <= first_end:
                    raise IvaValidationError(
                        f"recargo rate registry: IVA rate {iva_rate} has overlapping windows "
                        f"({first.effective_from}..{first.effective_until}) and "
                        f"({second.effective_from}..{second.effective_until})",
                    )


def recargo_rate_for_applied_rate(applied_rate: Decimal, on_date: date) -> Decimal | None:
    """Return the recargo rate paired with ``applied_rate`` on ``on_date``.

    This is the lookup that can express the 2023-2024 transitional rates. Asked
    for 10 % inside that window it answers 1.4 %; asked for 5 % on the same date
    it answers 0.62 %. A tier-keyed lookup cannot separate those, because both
    rates sat on the reduced tier at once.

    Args:
        applied_rate: The IVA rate the line actually carried, as a fraction.
        on_date: The operation date, which selects among windowed pairings.

    Returns:
        The paired recargo rate, which may legitimately be zero. ``None`` when
        the table models no pairing for that rate on that date -- an unmodelled
        combination, which callers must not read as "no recargo applies".

    The tobacco 1.75 % rate of art. 161 4.o is not reachable here: it attaches
    to a product rather than to an accompanying IVA rate, and is read from
    ``LIVA_ART_161_RECARGO.tabaco_rate``.
    """
    if not _recargo_fact_candidate_exists(applied_rate, on_date):
        return None
    return recargo_rate_record_from_fact(resolve_recargo_rate_for_applied_rate(applied_rate, on_date)).recargo_rate


def resolve_recargo_rate_for_applied_rate(
    applied_rate: Decimal,
    on_date: date,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedMappingFact:
    """Resolve the dated recargo pairing with its complete governed-fact provenance."""
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RECARGO_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(FactSelector(name="applied_rate", value=applied_rate),),
        ),
    )
    return cast("ResolvedMappingFact", resolved)


def _recargo_fact_candidate_exists(
    applied_rate: Decimal,
    on_date: date,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return false only for an unmodelled applied-rate/date pairing.

    A candidate still resolves through the authority afterwards, so any overlap
    or other invalid exact selection remains a loud fail-closed error rather
    than being mistaken for the public ``None`` sentinel.
    """
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    authority.validate_registry()
    fact = authority.catalogues.facts.facts.get(IVA_RECARGO_FACT_ID)
    if fact is None:
        return False
    return any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors}.get("applied_rate") == applied_rate
        for variant in fact.variants
    )


def compile_iva_recargo_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project the legacy applied-rate schedule into governed facts."""
    records = load_recargo_rate_table(registry_root.resolve() / "iva" / "recargo-rates.toml")
    return (
        GovernedFact(
            fact_id=IVA_RECARGO_FACT_ID,
            family=GovernedFactFamily.MAPPING,
            variants=tuple(_recargo_fact_variant(record) for record in records),
        ),
    )


def collect_iva_recargo_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Fingerprint the exact recargo schedule owned by the IVA provider.

    An absent schedule contributes NO fingerprint rather than raising, for the
    reason the sibling rate collector states: a partial registry carries only
    what its subject needs, and there is no content to invalidate on.
    """
    path = (registry_root.resolve() / "iva" / "recargo-rates.toml").resolve()
    if not path.is_file():
        return ()
    return (toml_file_fingerprint(path),)


def reset_iva_recargo_fact_provider() -> None:
    """Clear the recargo parser cache under the authority reset barrier."""
    _load_recargo_rate_table_cached.cache_clear()


def recargo_rate_record_from_fact(resolved: ResolvedMappingFact) -> RecargoRateRecord:
    """Project a provenance-bearing authority result onto the retained public record."""
    selectors = {selector.name: selector.value for selector in resolved.matched_selectors}
    payload = {str(entry.key): entry.value for entry in resolved.payload.entries}
    return RecargoRateRecord(
        iva_rate=Decimal(str(selectors["applied_rate"])),
        recargo_rate=Decimal(str(payload["recargo_rate"])),
        effective_from=resolved.valid_from,
        effective_until=resolved.valid_to,
        legal_refs=resolved.legal_refs,
        notes=str(payload["notes"]),
    )


def _recargo_fact_variant(record: RecargoRateRecord) -> GovernedFactVariant:
    return GovernedFactVariant(
        variant_id=f"iva-recargo.{record.iva_rate}.{record.effective_from}",
        selectors=(FactSelector(name="applied_rate", value=record.iva_rate),),
        date_axis=DateAxis.DEVENGO_DATE,
        valid_from=record.effective_from,
        valid_to=record.effective_until,
        payload=MappingFactPayload(
            entries=(
                MappingFactEntry(key="recargo_rate", value=record.recargo_rate),
                MappingFactEntry(key="notes", value=record.notes),
            ),
        ),
        legal_refs=record.legal_refs,
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        ownership=FactOwnership.GENERATED,
    )


__all__ = [
    "IVA_RECARGO_FACT_ID",
    "RecargoRateRecord",
    "collect_iva_recargo_fact_fingerprints",
    "compile_iva_recargo_facts",
    "load_recargo_rate_table",
    "recargo_rate_for_applied_rate",
    "recargo_rate_record_from_fact",
    "reset_iva_recargo_fact_provider",
    "resolve_recargo_rate_for_applied_rate",
]
