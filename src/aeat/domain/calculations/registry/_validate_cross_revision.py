"""Cross-revision drift validation for registry casillas."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ._errors import RegistryValidationError
from ._schema import (
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
)

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
)

__all__ = (
    "CrossRevisionCasillaDivergence",
    "CrossRevisionCasillaDriftSummary",
    "summarize_non_overlapping_cross_revision_casilla_drift",
    "validate_cross_revision_casilla_consistency",
)


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDivergence:
    """One field-level difference for a repeated casilla id."""

    modelo_id: str
    casilla_id: str
    left_revision_id: str
    right_revision_id: str
    field: str
    left_value: object
    right_value: object
    revisions_overlap: bool
    left_continuidad_id: str | None = None
    right_continuidad_id: str | None = None
    evolution_id: str | None = None
    evolution_kind: str | None = None
    evolution_covers_field: bool = False


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDriftSummary:
    """Grouped advisory drift inventory for non-overlapping revisions."""

    modelo_id: str
    left_revision_id: str
    right_revision_id: str
    field: str
    drift_count: int
    example_casilla_ids: tuple[str, ...]
    continuidad_ids: tuple[str, ...] = ()
    evolution_kinds: tuple[str, ...] = ()
    covered_by_evolution_count: int = 0
    uncovered_count: int = 0


def _cross_revision_signature(casilla: CasillaDefinition) -> tuple[object, ...]:
    """Return the stable cross-revision fingerprint for a casilla."""

    return tuple(getattr(casilla, field) for field in _CROSS_REVISION_CASILLA_FIELDS)


def _period_selector_year_bounds(selector: PeriodSelector) -> tuple[int, int | None]:
    if selector.years:
        return min(selector.years), max(selector.years)
    if selector.year_from is None:
        return 0, None
    return selector.year_from, selector.year_to


def _period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    left_start, left_end = _period_selector_year_bounds(left)
    right_start, right_end = _period_selector_year_bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    return bool(set(left.periods).intersection(right.periods))


def _revisions_overlap(left: object, right: object) -> bool:
    left_selector = getattr(left, "period_selector", None)
    right_selector = getattr(right, "period_selector", None)
    if not isinstance(left_selector, PeriodSelector) or not isinstance(right_selector, PeriodSelector):
        return True
    return _period_selectors_overlap(left_selector, right_selector)


def validate_cross_revision_casilla_consistency(modelos: Iterable[ModeloDefinition]) -> None:
    """Raise when a repeated casilla id drifts across revisions."""

    failures = _validate_cross_revision_casilla_consistency(modelos)
    if failures:
        raise RegistryValidationError(
            "cross-revision casilla drift detected:\n" + "\n".join(f" - {failure}" for failure in failures)
        )


def _validate_cross_revision_casilla_consistency(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce that casillas sharing an id across revisions of a modelo agree.

    Per the AEAT registry design contract, a casilla id is a stable
    handle for a single legal concept within a modelo. Two
    declarations of casilla `0700` in two overlapping revisions
    must declare the same label, section, data_type, role, and
    legal references. Divergence is an authoring or repurposing event
    that needs explicit handling (either deprecate-and-rename or
    reconcile-to-canonical-form), never silent acceptance.
    """

    failures: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in _iter_cross_revision_casilla_divergences(modelos):
        if not divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.casilla_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
        )
        failures[key].append(divergence)
    return tuple(
        _format_cross_revision_failure(modelo_id, casilla_id, left_revision_id, divergences)
        for (
            modelo_id,
            casilla_id,
            left_revision_id,
            _right_revision_id,
        ), divergences in failures.items()
    )


def _validate_strict_cross_revision_casilla_continuity(
    modelos: Iterable[ModeloDefinition],
) -> tuple[str, ...]:
    """Enforce explicit continuity decisions for opted-in revision pairs."""

    failures: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for modelo in modelos:
        for divergence in _iter_cross_revision_casilla_divergences((modelo,)):
            if divergence.revisions_overlap:
                continue
            left_revision = modelo.revisions[divergence.left_revision_id]
            right_revision = modelo.revisions[divergence.right_revision_id]
            if (
                left_revision.continuidad_validation != "strict"
                and right_revision.continuidad_validation != "strict"
            ):
                continue
            if divergence.evolution_covers_field:
                continue
            key = (
                divergence.modelo_id,
                divergence.casilla_id,
                divergence.left_revision_id,
                divergence.right_revision_id,
            )
            failures[key].append(divergence)
    return tuple(
        _format_strict_continuity_failure(modelo_id, casilla_id, left_revision_id, right_revision_id, divergences)
        for (
            modelo_id,
            casilla_id,
            left_revision_id,
            right_revision_id,
        ), divergences in failures.items()
    )


def _format_strict_continuity_failure(
    modelo_id: str,
    casilla_id: str,
    left_revision_id: str,
    right_revision_id: str,
    divergences: Iterable[CrossRevisionCasillaDivergence],
) -> str:
    divergence_tuples = tuple(
        (
            item.field,
            (item.left_value, item.right_value),
            (item.left_continuidad_id, item.right_continuidad_id),
            item.evolution_kind,
        )
        for item in divergences
    )
    return (
        f"strict continuity drift: modelo {modelo_id} casilla {casilla_id!r} "
        f"revisions {left_revision_id!r}->{right_revision_id!r} "
        f"uncovered divergences {divergence_tuples!r}"
    )


def _format_cross_revision_failure(
    modelo_id: str,
    casilla_id: str,
    left_revision_id: str,
    divergences: Iterable[CrossRevisionCasillaDivergence],
) -> str:
    divergence_tuples = tuple(
        (item.right_revision_id, item.field, (item.left_value, item.right_value))
        for item in divergences
    )
    return (
        f"cross-revision drift: modelo {modelo_id} casilla "
        f"{casilla_id!r} canonical revision {left_revision_id!r} "
        f"divergences {divergence_tuples!r}"
    )


def summarize_non_overlapping_cross_revision_casilla_drift(
    modelos: Iterable[ModeloDefinition],
    *,
    example_limit: int = 5,
) -> tuple[CrossRevisionCasillaDriftSummary, ...]:
    """Return advisory drift summaries for repeated ids in non-overlapping revisions.

    The snapshot-build validator raises on overlapping revision windows
    because those revisions can apply to the same filing period. Annual
    non-overlapping forms, such as M100, can legally evolve or repurpose
    repeated numeric ids; this inventory keeps that drift visible without
    turning it into a load-time error before the schema has an explicit
    continuity/evolution contract.
    """

    if example_limit < 1:
        raise ValueError("example_limit must be at least 1")

    grouped: dict[tuple[str, str, str, str], list[CrossRevisionCasillaDivergence]] = defaultdict(list)
    for divergence in _iter_cross_revision_casilla_divergences(modelos):
        if divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
            divergence.field,
        )
        grouped[key].append(divergence)

    summaries: list[CrossRevisionCasillaDriftSummary] = []
    for (modelo_id, left_revision_id, right_revision_id, field), divergences in sorted(grouped.items()):
        casilla_ids = [divergence.casilla_id for divergence in divergences]
        examples = tuple(dict.fromkeys(casilla_ids[:example_limit]))
        continuidad_ids = tuple(
            sorted(
                {
                    continuidad_id
                    for divergence in divergences
                    for continuidad_id in (divergence.left_continuidad_id, divergence.right_continuidad_id)
                    if continuidad_id is not None
                }
            )
        )
        evolution_kinds = tuple(
            sorted(
                {
                    divergence.evolution_kind
                    for divergence in divergences
                    if divergence.evolution_kind is not None
                }
            )
        )
        covered_by_evolution_count = sum(1 for divergence in divergences if divergence.evolution_covers_field)
        summaries.append(
            CrossRevisionCasillaDriftSummary(
                modelo_id=modelo_id,
                left_revision_id=left_revision_id,
                right_revision_id=right_revision_id,
                field=field,
                drift_count=len(casilla_ids),
                example_casilla_ids=examples,
                continuidad_ids=continuidad_ids,
                evolution_kinds=evolution_kinds,
                covered_by_evolution_count=covered_by_evolution_count,
                uncovered_count=len(divergences) - covered_by_evolution_count,
            )
        )
    return tuple(summaries)


def _iter_cross_revision_casilla_divergences(
    modelos: Iterable[ModeloDefinition],
) -> tuple[CrossRevisionCasillaDivergence, ...]:
    divergences: list[CrossRevisionCasillaDivergence] = []
    for modelo in modelos:
        by_id: dict[str, list[tuple[ModeloRevision, CasillaDefinition]]] = defaultdict(list)
        for revision in modelo.revisions.values():
            for casilla in revision.casillas:
                by_id[casilla.id].append((revision, casilla))
        for casilla_id, occurrences in by_id.items():
            if len(occurrences) < 2:
                continue
            for index, (left_revision, left_casilla) in enumerate(occurrences[:-1]):
                left_sig = _cross_revision_signature(left_casilla)
                for right_revision, right_casilla in occurrences[index + 1 :]:
                    revisions_overlap = _revisions_overlap(left_revision, right_revision)
                    right_sig = _cross_revision_signature(right_casilla)
                    if right_sig == left_sig:
                        continue
                    evolution = _matching_evolution(left_revision, right_revision, left_casilla, right_casilla)
                    for field, left_value, right_value in zip(
                        _CROSS_REVISION_CASILLA_FIELDS,
                        left_sig,
                        right_sig,
                        strict=True,
                    ):
                        if left_value == right_value:
                            continue
                        divergences.append(
                            CrossRevisionCasillaDivergence(
                                modelo_id=modelo.id,
                                casilla_id=casilla_id,
                                left_revision_id=left_revision.id,
                                right_revision_id=right_revision.id,
                                field=field,
                                left_value=left_value,
                                right_value=right_value,
                                revisions_overlap=revisions_overlap,
                                left_continuidad_id=left_casilla.continuidad_id,
                                right_continuidad_id=right_casilla.continuidad_id,
                                evolution_id=evolution.id if evolution is not None else None,
                                evolution_kind=evolution.evolution_kind if evolution is not None else None,
                                evolution_covers_field=_evolution_covers_field(evolution, field),
                            )
                        )
    return tuple(divergences)


def _matching_evolution(
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
    left_casilla: CasillaDefinition,
    right_casilla: CasillaDefinition,
) -> CasillaContinuidadEvolutionDefinition | None:
    continuidad_ids = {left_casilla.continuidad_id, right_casilla.continuidad_id} - {None}
    if len(continuidad_ids) != 1:
        return None
    continuidad_id = next(iter(continuidad_ids))
    for revision in (left_revision, right_revision):
        for evolution in revision.casilla_continuidad_evolutions:
            if evolution.continuidad_id != continuidad_id:
                continue
            if {evolution.from_revision, evolution.to_revision} == {left_revision.id, right_revision.id}:
                return evolution
    return None


def _evolution_covers_field(evolution: CasillaContinuidadEvolutionDefinition | None, field: str) -> bool:
    if evolution is None:
        return False
    if evolution.evolution_kind == "label_evolved":
        return field == "label"
    if evolution.evolution_kind == "legal_refs_evolved":
        return field == "legal_refs"
    if evolution.evolution_kind == "label_and_legal_refs_evolved":
        return field in {"label", "legal_refs"}
    return evolution.evolution_kind == "repurposed"
