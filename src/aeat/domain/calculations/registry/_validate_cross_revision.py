"""Cross-revision drift validation for registry casillas."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ._errors import RegistryValidationError
from ._schema import CasillaDefinition, ModeloDefinition, ModeloRevision, PeriodSelector

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
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


@dataclass(frozen=True, slots=True)
class CrossRevisionCasillaDriftSummary:
    """Grouped advisory drift inventory for non-overlapping revisions."""

    modelo_id: str
    left_revision_id: str
    right_revision_id: str
    field: str
    drift_count: int
    example_casilla_ids: tuple[str, ...]


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

    grouped: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for divergence in _iter_cross_revision_casilla_divergences(modelos):
        if divergence.revisions_overlap:
            continue
        key = (
            divergence.modelo_id,
            divergence.left_revision_id,
            divergence.right_revision_id,
            divergence.field,
        )
        grouped[key].append(divergence.casilla_id)

    summaries: list[CrossRevisionCasillaDriftSummary] = []
    for (modelo_id, left_revision_id, right_revision_id, field), casilla_ids in sorted(grouped.items()):
        examples = tuple(dict.fromkeys(casilla_ids[:example_limit]))
        summaries.append(
            CrossRevisionCasillaDriftSummary(
                modelo_id=modelo_id,
                left_revision_id=left_revision_id,
                right_revision_id=right_revision_id,
                field=field,
                drift_count=len(casilla_ids),
                example_casilla_ids=examples,
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
                            )
                        )
    return tuple(divergences)
