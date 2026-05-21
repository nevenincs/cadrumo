"""Revision-level invariant validation helpers."""

from __future__ import annotations

from collections.abc import Iterable

from ._schema import DatedValue, ModeloDefinition, ModeloRevision
from ._validate_relation_sources import period_selectors_overlap


def validate_revision_windows(modelo: ModeloDefinition) -> list[str]:
    failures: list[str] = []
    revisions = sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
    for index, current in enumerate(revisions[1:], start=1):
        previous = revisions[index - 1]
        previous_to = previous.valid_to
        if (
            previous_to is None or previous_to >= current.valid_from
        ) and period_selectors_overlap(previous.period_selector, current.period_selector):
            failures.append(
                f"modelo {modelo.id}: revisions {previous.id!r} and {current.id!r} overlap on period selector"
            )
    return failures


def validate_informative_class_invariant(modelo: ModeloDefinition) -> list[str]:
    """Enforce that informative modelos carry no filing-grade computation artefacts."""
    if modelo.calculation_class != "informative":
        return []
    failures: list[str] = []
    for revision in modelo.revisions.values():
        prefix = f"modelo {modelo.id} revision {revision.id}"
        if revision.formulas:
            failures.append(
                f"{prefix}: informative modelo must not declare calculation formulas (got {len(revision.formulas)})"
            )
        if revision.relations:
            failures.append(
                f"{prefix}: informative modelo must not declare cross-model relations "
                f"(got {len(revision.relations)})"
            )
        for casilla in revision.casillas:
            if casilla.input_kind not in {"informational", "manual"}:
                failures.append(
                    f"{prefix}: informative modelo casilla {casilla.id!r} "
                    f"has input_kind={casilla.input_kind!r}; "
                    "only 'informational' and 'manual' are permitted"
                )
    return failures


def validate_dated_values(scope: str, parameter_id: str, values: Iterable[DatedValue]) -> list[str]:
    failures: list[str] = []
    by_axis: dict[str, list[DatedValue]] = {}
    for value in values:
        axis = value.date_axis
        by_axis.setdefault(axis, []).append(value)
    for axis, axis_values in by_axis.items():
        ordered = sorted(axis_values, key=lambda item: item.valid_from)
        for index, current in enumerate(ordered[1:], start=1):
            previous = ordered[index - 1]
            previous_to = previous.valid_to
            if previous_to is None or previous_to >= current.valid_from:
                failures.append(f"{scope}: parameter {parameter_id!r} has overlapping {axis} values")
    return failures


def validate_reconciliation_total_closure(scope: str, revision: ModeloRevision) -> list[str]:
    failures: list[str] = []
    declared: dict[str, str] = {}
    for expectation in revision.verification_expectations:
        for total_kind, casilla_id in expectation.reconciliation_totals.items():
            previous = declared.get(total_kind)
            if previous is not None and previous != casilla_id:
                failures.append(
                    f"{scope}: reconciliation total {total_kind!r} is declared by multiple casillas "
                    f"{previous!r} and {casilla_id!r}"
                )
            declared[total_kind] = casilla_id
    return failures
