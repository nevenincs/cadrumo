"""Development-only compilers for authored IVA schedules."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from cadrumo.core.decimal.coercion import coerce_decimal, coerce_decimal_strict
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import read_toml
from cadrumo.core.type_adapters import OBJECT_TUPLE_ADAPTER, STR_KEYED_MAPPING_ADAPTER
from cadrumo.core.type_guards import is_object_list
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    MappingFactEntry,
    MappingFactPayload,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis, SourceCitation
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.iva.compilation_catalogues import compiling_catalogues_in_scope
from cadrumo.domain.iva.errors import IvaCatalogueError, IvaRateOverlapError, IvaValidationError
from cadrumo.domain.iva.rates import IVA_RATE_FACT_ID
from cadrumo.domain.iva.recargo_equivalencia import IVA_RECARGO_FACT_ID, RecargoRateRecord
from cadrumo.domain.iva.schema import EUMemberState, IvaRateKind, IvaRateRecord
from dev.registry.compiler.loader import load_shared_catalogues

from .corpus_catalogue import verify_source_file
from .legal_grounding import legal_ref_failures
from .loader_cache import toml_file_fingerprint
from .loader_fingerprints import RegistryPathFingerprints

_RATE_REGISTRY_MEMBER_STATES = frozenset(state for state in EUMemberState if state is not EUMemberState.XI)


@lru_cache(maxsize=16)
def _load_rate_table(path: str, byte_count: int, modified_ns: int) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    del byte_count, modified_ns
    target = Path(path)
    payload = read_toml(target, error_factory=IvaCatalogueError)
    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, list) or not raw_rates:
        raise IvaCatalogueError(f"{target}: missing [[rates]] entries")
    by_state: dict[EUMemberState, list[IvaRateRecord]] = {}
    for index, raw in enumerate(OBJECT_TUPLE_ADAPTER.validate_python(raw_rates), start=1):
        if not isinstance(raw, Mapping):
            raise IvaCatalogueError(f"{target}: rates[{index}] must be a table")
        try:
            rate = _parse_rate(STR_KEYED_MAPPING_ADAPTER.validate_python(raw))
        except (ValidationError, IvaValidationError, ValueError) as exc:
            raise IvaCatalogueError(f"{target}: invalid rates[{index}]: {exc}") from exc
        by_state.setdefault(rate.member_state, []).append(rate)
    missing = sorted(state.value for state in _RATE_REGISTRY_MEMBER_STATES - set(by_state))
    if missing:
        raise IvaCatalogueError(f"{target}: IVA rate registry missing member states: {missing}")
    result: dict[EUMemberState, tuple[IvaRateRecord, ...]] = {}
    for state, rates in by_state.items():
        partition = tuple(sorted(rates, key=lambda rate: (rate.kind.value, rate.effective_from)))
        _assert_no_overlap(state, partition)
        result[state] = partition
    frozen = MappingProxyType(result)
    _verify_rate_grounding(frozen, registry_root=target.parent.parent)
    return frozen


def _parse_rate(raw: object) -> IvaRateRecord:
    if not isinstance(raw, dict):
        raise IvaValidationError(f"IVA rate entry must be a table, got: {type(raw)!r}")
    data = STR_KEYED_MAPPING_ADAPTER.validate_python(raw)
    try:
        pct = coerce_decimal(data.get("pct"))
        if pct is None:
            raise ValueError(f"pct field could not be parsed: {data.get('pct')!r}")
        member_state, kind = EUMemberState(str(data.get("member_state"))), IvaRateKind(str(data.get("kind")))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise IvaValidationError(f"invalid IVA rate key or pct: {raw!r}") from exc
    return IvaRateRecord.model_validate(
        {
            "member_state": member_state,
            "kind": kind,
            "pct": pct,
            "effective_from": data.get("effective_from"),
            "effective_until": data.get("effective_until"),
            "legal_refs": _reference_ids(data, "legal_refs"),
            "source_refs": _reference_ids(data, "source_refs"),
            "supersedes_tier_default": data.get("supersedes_tier_default", False),
        }
    )


def _reference_ids(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    raw = data.get(key, ())
    if not isinstance(raw, (list, tuple)):
        raise IvaValidationError(f"{key} must be an array")
    items = OBJECT_TUPLE_ADAPTER.validate_python(raw)
    reference_ids = tuple(item for item in items if isinstance(item, str))
    if len(reference_ids) != len(items):
        raise IvaValidationError(f"{key} must contain only registry identity strings")
    return reference_ids


def _assert_no_overlap(state: EUMemberState, rates: Iterable[IvaRateRecord]) -> None:
    by_kind: dict[IvaRateKind, list[IvaRateRecord]] = {}
    for rate in rates:
        if not rate.supersedes_tier_default:
            by_kind.setdefault(rate.kind, []).append(rate)
    for kind, partition in by_kind.items():
        ordered = sorted(partition, key=lambda rate: rate.effective_from)
        for previous, current in pairwise(ordered):
            if (previous.effective_until or date.max) >= current.effective_from:
                raise IvaRateOverlapError(
                    f"IVA rate registry has overlapping windows for member_state={state.value!r} "
                    f"kind={kind.value!r}: {previous.effective_from}/{previous.effective_until} "
                    f"vs. {current.effective_from}/{current.effective_until}"
                )


def _verify_rate_grounding(table: Mapping[EUMemberState, tuple[IvaRateRecord, ...]], *, registry_root: Path) -> None:
    # A compilation names the corpus root it validates against; a candidate
    # staged outside the package tree has no corpus beside its registry root.
    compiling = compiling_catalogues_in_scope()
    if compiling is not None:
        legal, sources, source_root = compiling
    else:
        catalogues = load_shared_catalogues(registry_root)
        legal, sources, source_root = catalogues.legal, catalogues.sources, registry_root.parents[1]
    verify_iva_rate_grounding(table, legal=legal, sources=sources, source_root=source_root)


def verify_iva_rate_grounding(
    table: Mapping[EUMemberState, tuple[IvaRateRecord, ...]],
    *,
    legal: Mapping[str, LegalReference],
    sources: Mapping[str, SourceReference],
    source_root: Path,
) -> None:
    """Refuse an IVA rate table any of whose rows is not grounded, naming every failure.

    Each row's legal refs must resolve and corpus-verify, each source ref must
    resolve and verify, and every non-Spanish row must fall inside the
    applicability window of at least one of its cited sources. Spanish rows are
    grounded by legislation, so the window rule does not apply to them.

    Raises:
        IvaCatalogueError: When any row fails; the message lists every failure.
    """
    verified_legal: set[str] = set()
    verified_sources: set[str] = set()
    failures: list[str] = []
    for rates in table.values():
        for rate in rates:
            row = f"{rate.member_state.value}/{rate.kind.value}/{rate.effective_from.isoformat()}"
            failures.extend(legal_ref_failures(row, rate.legal_refs, legal, source_root, verified_legal))
            row_sources: list[SourceReference] = []
            for ref_id in rate.source_refs:
                reference = sources.get(ref_id)
                if reference is None:
                    failures.append(f"{row}: unknown source_ref {ref_id!r}")
                else:
                    row_sources.append(reference)
                    if ref_id not in verified_sources:
                        try:
                            verify_source_file(source_root, reference)
                        except RegistryValidationError as exc:
                            failures.append(f"{row}: invalid source_ref {ref_id!r}: {exc}")
                        else:
                            verified_sources.add(ref_id)
            if rate.member_state is not EUMemberState.ES and not any(
                ref.applies_from is not None
                and ref.applies_from <= rate.effective_from
                and (
                    ref.applies_to is None
                    or (rate.effective_until is not None and rate.effective_until <= ref.applies_to)
                )
                for ref in row_sources
            ):
                failures.append(
                    f"{row}: no source_ref applicability window covers {rate.effective_from}/{rate.effective_until}"
                )
    if failures:
        raise IvaCatalogueError(
            "IVA rate grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures)
        )


def compile_iva_rate_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Compile the mutable IVA rate declaration into governed facts."""
    target = (registry_root.resolve() / "iva" / "rates.toml").resolve()
    try:
        stat = target.stat()
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot stat IVA rate registry: {exc}") from exc
    table = _load_rate_table(str(target), stat.st_size, stat.st_mtime_ns)
    return (
        GovernedFact(
            fact_id=IVA_RATE_FACT_ID,
            family=GovernedFactFamily.MAPPING,
            variants=tuple(
                _rate_fact_variant(rate)
                for state in sorted(table, key=lambda item: item.value)
                for rate in table[state]
            ),
        ),
    )


def load_iva_rate_table_for_publication(registry_root: Path) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    """Read one mutable IVA schedule for validation before artifact publication."""
    target = (registry_root.resolve() / "iva" / "rates.toml").resolve()
    stat = target.stat()
    return _load_rate_table(str(target), stat.st_size, stat.st_mtime_ns)


def collect_iva_rate_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Identify the IVA rate declaration used for a publication candidate."""
    target = (registry_root.resolve() / "iva" / "rates.toml").resolve()
    return () if not target.is_file() else (toml_file_fingerprint(target),)


def reset_iva_rate_fact_provider() -> None:
    """Clear the development rate-parser cache."""
    _load_rate_table.cache_clear()


def _rate_fact_variant(rate: IvaRateRecord) -> GovernedFactVariant:
    role = "ordinary" if not rate.supersedes_tier_default else f"coexisting-{rate.pct}"
    return GovernedFactVariant(
        variant_id=f"iva-rate.{rate.member_state.value}.{rate.kind.value}.{rate.effective_from}.{role}",
        selectors=(
            FactSelector(name="member_state", value=rate.member_state.value),
            FactSelector(name="kind", value=rate.kind.value),
            FactSelector(name="rate_role", value=role),
        ),
        date_axis=DateAxis.DEVENGO_DATE,
        valid_from=rate.effective_from,
        valid_to=rate.effective_until,
        payload=MappingFactPayload(
            entries=(
                MappingFactEntry(key="pct", value=rate.pct),
                MappingFactEntry(key="supersedes_tier_default", value=rate.supersedes_tier_default),
            )
        ),
        legal_refs=rate.legal_refs,
        source_refs=rate.source_refs,
        source_citations=tuple(
            SourceCitation(source_ref=ref, required_text=(str(rate.pct),)) for ref in rate.source_refs
        ),
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        ownership=FactOwnership.GENERATED,
    )


@lru_cache(maxsize=16)
def _load_recargo_table(path: str, byte_count: int, modified_ns: int) -> tuple[RecargoRateRecord, ...]:
    del byte_count, modified_ns
    target = Path(path)
    try:
        payload = tomllib.loads(target.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot read recargo rate registry: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise IvaValidationError(f"{target}: malformed recargo rate registry: {exc}") from exc
    try:
        records = tuple(
            RecargoRateRecord.model_validate(_hydrate_recargo_row(row)) for row in payload.get("recargo_rates", ())
        )
    except (ValueError, TypeError) as exc:
        raise IvaValidationError(f"{target}: invalid recargo rate record: {exc}") from exc
    _reject_recargo_overlaps(records)
    citations = [(f"{record.iva_rate}/{record.effective_from.isoformat()}", record.legal_refs) for record in records]
    compiling = compiling_catalogues_in_scope()
    if compiling is not None:
        legal, _sources, source_root = compiling
    else:
        registry_root = target.parent.parent
        legal, source_root = load_shared_catalogues(registry_root).legal, registry_root.parents[1]
    _verify_table_legal_refs(str(target), citations, legal=legal, source_root=source_root)
    return records


def _verify_table_legal_refs(
    table: str,
    citations: Sequence[tuple[str, Sequence[str]]],
    *,
    legal: Mapping[str, LegalReference],
    source_root: Path,
) -> None:
    """Corpus-verify every citation a compiled IVA table's rows carry, or refuse the table."""
    verified: set[str] = set()
    failures: list[str] = []
    for row, reference_ids in citations:
        failures.extend(legal_ref_failures(row, reference_ids, legal, source_root, verified))
    if failures:
        raise IvaCatalogueError(
            f"{table}: legal grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _hydrate_recargo_row(row: Mapping[str, object]) -> dict[str, object]:
    hydrated = dict(row)
    for field in ("iva_rate", "recargo_rate"):
        if isinstance(hydrated.get(field), str):
            hydrated[field] = coerce_decimal_strict(hydrated[field])
    refs = hydrated.get("legal_refs")
    if is_object_list(refs):
        reference_ids = tuple(ref for ref in refs if isinstance(ref, str))
        if len(reference_ids) != len(refs):
            raise IvaValidationError("legal_refs entries must be strings")
        hydrated["legal_refs"] = reference_ids
    return hydrated


def _reject_recargo_overlaps(records: tuple[RecargoRateRecord, ...]) -> None:
    by_rate: dict[Decimal, list[RecargoRateRecord]] = {}
    for record in records:
        by_rate.setdefault(record.iva_rate, []).append(record)
    for rate, group in by_rate.items():
        for index, first in enumerate(group):
            for second in group[index + 1 :]:
                if first.effective_from <= (second.effective_until or date.max) and second.effective_from <= (
                    first.effective_until or date.max
                ):
                    raise IvaValidationError(
                        f"recargo rate registry: IVA rate {rate} has overlapping windows "
                        f"({first.effective_from}..{first.effective_until}) and "
                        f"({second.effective_from}..{second.effective_until})"
                    )


def compile_iva_recargo_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Compile mutable recargo declarations into governed facts."""
    target = (registry_root.resolve() / "iva" / "recargo-rates.toml").resolve()
    try:
        stat = target.stat()
    except OSError as exc:
        raise IvaCatalogueError(f"{target}: cannot stat recargo rate registry: {exc}") from exc
    records = _load_recargo_table(str(target), stat.st_size, stat.st_mtime_ns)
    return (
        GovernedFact(
            fact_id=IVA_RECARGO_FACT_ID,
            family=GovernedFactFamily.MAPPING,
            variants=tuple(_recargo_fact_variant(record) for record in records),
        ),
    )


def collect_iva_recargo_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Identify the recargo declaration used for a publication candidate."""
    target = (registry_root.resolve() / "iva" / "recargo-rates.toml").resolve()
    return () if not target.is_file() else (toml_file_fingerprint(target),)


def reset_iva_recargo_fact_provider() -> None:
    """Clear the development recargo-parser cache."""
    _load_recargo_table.cache_clear()


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
            )
        ),
        legal_refs=record.legal_refs,
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        ownership=FactOwnership.GENERATED,
    )
