"""Cross-revision drift validation for registry casillas."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ._errors import RegistryValidationError
from ._schema import CasillaDefinition, ModeloDefinition, ModeloRevision, PeriodSelector

_CROSS_REVISION_CASILLA_FIELDS: tuple[str, ...] = (
    "label",
    "section",
    "data_type",
    "semantic_role",
    "legal_refs",
)


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
    declarations of casilla `0700` in M100 revisions 2024 and 2025
    must declare the same label, section, data_type, role, and
    legal references. Divergence is an authoring or repurposing event
    that needs explicit handling (either deprecate-and-rename or
    reconcile-to-canonical-form), never silent acceptance.
    """

    failures: list[str] = []
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
                    if not _revisions_overlap(left_revision, right_revision):
                        continue
                    right_sig = _cross_revision_signature(right_casilla)
                    if right_sig == left_sig:
                        continue
                    divergences = tuple(
                        (right_revision.id, field, (left_value, right_value))
                        for field, left_value, right_value in zip(
                            _CROSS_REVISION_CASILLA_FIELDS,
                            left_sig,
                            right_sig,
                            strict=True,
                        )
                        if left_value != right_value
                    )
                    failures.append(
                        f"cross-revision drift: modelo {modelo.id} casilla "
                        f"{casilla_id!r} canonical revision {left_revision.id!r} "
                        f"divergences {divergences!r}"
                    )
                    continue
    return tuple(failures)
