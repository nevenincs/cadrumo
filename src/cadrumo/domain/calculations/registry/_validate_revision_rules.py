"""Revision-level invariant validation helpers.

Validates temporal window overlap, informative-class invariants, bracket-table
coverage, and reconciliation-total closure for a :class:`ModeloRevision` within
its :class:`ModeloDefinition`.

The D3 ``orden_aplicabilidad`` gate lives in its sibling module
:mod:`cadrumo.domain.calculations.registry._validate_orden_aplicabilidad`.
"""

from __future__ import annotations

from collections.abc import Collection

from ....core import M210_TIPO_RENTA_CODE_PROJECTION
from ._deadline_coordinate import DeadlineSemanticCoordinate, deadline_window_semantic_coordinates
from .errors import RegistrySnapshotError
from ._schema import InputKind, ModeloDefinition, ModeloRevision, filing_schedule_period_kind_mismatches
from ._temporal import select_revision
from ._validate_parameter_temporal import _bracket_coverage_gaps as _bracket_coverage_gaps
from ._validate_parameter_temporal import (
    validate_bracket_table_temporal_coverage as validate_bracket_table_temporal_coverage,
)
from ._validate_parameter_temporal import validate_dated_values as validate_dated_values
from ._validate_relation_sources import period_selectors_overlap

_M210_TIPO_RENTA_CODE_PARAMETER_PREFIX = "m210-tipo-renta-code-"


def validate_revision_windows(modelo: ModeloDefinition) -> list[str]:
    failures: list[str] = []
    revisions = sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
    for index, earlier in enumerate(revisions):
        for later in revisions[index + 1 :]:
            if earlier.valid_to is not None and earlier.valid_to < later.valid_from:
                # Later revisions are ordered by valid_from, so no subsequent
                # revision can overlap this bounded earlier window either.
                break
            if period_selectors_overlap(earlier.period_selector, later.period_selector):
                failures.append(
                    f"modelo {modelo.id}: revisions {earlier.id!r} and {later.id!r} overlap on period selector",
                )
    return failures


def validate_deadline_window_uniqueness(modelo: ModeloDefinition) -> list[str]:
    """Reject deadline identities repeated anywhere in one modelo's revisions.

    Deadline rows are revision-owned law facts, so neither an authored id nor
    an atomic request coordinate may have more than one owner.  The plural
    coordinate projection deliberately expands qualifier bundles and wildcard
    scopes before this pass compares them; this makes overlaps visible without
    teaching the validator a second set of deadline matching rules.
    """
    failures: list[str] = []
    id_owner: dict[str, str] = {}
    coordinate_owner: dict[DeadlineSemanticCoordinate, tuple[str, str]] = {}
    duplicate_ids: set[str] = set()
    duplicate_coordinates: set[DeadlineSemanticCoordinate] = set()

    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            previous_revision = id_owner.get(window.id)
            if previous_revision is None:
                id_owner[window.id] = revision.id
            elif window.id not in duplicate_ids:
                failures.append(
                    f"modelo {modelo.id}: deadline window id {window.id!r} is declared more than once "
                    f"across revisions {previous_revision!r} and {revision.id!r}",
                )
                duplicate_ids.add(window.id)

            for coordinate in deadline_window_semantic_coordinates(modelo.id, window):
                previous_owner = coordinate_owner.get(coordinate)
                if previous_owner is None:
                    coordinate_owner[coordinate] = (revision.id, window.id)
                    continue
                if coordinate in duplicate_coordinates:
                    continue
                failures.append(
                    f"modelo {modelo.id}: deadline semantic coordinate {coordinate!r} is declared more than once "
                    f"by revision/window {previous_owner!r} and {(revision.id, window.id)!r}",
                )
                duplicate_coordinates.add(coordinate)

    return failures


def validate_deadline_window_ownership(modelo: ModeloDefinition) -> list[str]:
    """Require every deadline row to live beneath its law-selected revision.

    The deadline's canonical filing coordinate drives the existing temporal
    resolver.  The containing revision is only asserted against that result;
    it never participates in selection.  This keeps period-sensitive cutovers
    governed by exactly the same resolver as snapshots and other registry
    projections.
    """
    failures: list[str] = []
    for containing_revision in modelo.revisions.values():
        for window in containing_revision.deadline_windows:
            filing_year = window.period.filing_year
            period = window.period.registry_token
            try:
                selected_revision = select_revision(
                    modelo,
                    filing_year=filing_year,
                    period=period,
                )
            except RegistrySnapshotError as exc:
                failures.append(
                    f"modelo {modelo.id} revision {containing_revision.id}: deadline window "
                    f"{window.id!r} has no unique canonical owner for filing coordinate "
                    f"({filing_year}, {period!r}): {exc}",
                )
                continue
            if selected_revision.id != containing_revision.id:
                failures.append(
                    f"modelo {modelo.id} revision {containing_revision.id}: deadline window "
                    f"{window.id!r} belongs to canonically selected revision "
                    f"{selected_revision.id!r} for filing coordinate ({filing_year}, {period!r})",
                )
    return failures


def validate_deadline_window_cadence(modelo: ModeloDefinition) -> list[str]:
    """Reject deadline cadence labels that contradict their canonical period.

    Reuse the filing-schedule compatibility table so deadline rows and
    schedules interpret monthly, quarterly, instalment, and extended tokens
    through one vocabulary owner.
    """
    failures: list[str] = []
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            period = window.period.registry_token
            if filing_schedule_period_kind_mismatches(window.period_kind, (period,)):
                failures.append(
                    f"modelo {modelo.id} revision {revision.id}: deadline window {window.id!r} "
                    f"period_kind {window.period_kind!r} contradicts period {period!r}",
                )
    return failures


def validate_periodic_deadline_completeness(
    modelo: ModeloDefinition,
    *,
    supported_filing_years: Collection[int],
) -> list[str]:
    """Require every selected periodic schedule coordinate to own a window.

    The supported-year horizon is supplied by the registry-wide catalogue.
    Candidate tokens come only from authored filing schedules, and
    :func:`select_revision` decides which revision governs each coordinate.
    The shared filing-schedule cadence compatibility gate validates the period
    vocabulary; it is not replaced by a deadline-specific parser or table.
    """
    candidate_periods = sorted(
        {
            period
            for revision in modelo.revisions.values()
            for schedule in revision.filing_schedules
            if schedule.is_periodic
            for period in schedule.periods
        },
    )
    failures: list[str] = []
    for filing_year in supported_filing_years:
        for period in candidate_periods:
            try:
                selected = select_revision(modelo, filing_year=filing_year, period=period)
            except RegistrySnapshotError:
                continue
            selected_schedules = tuple(
                schedule
                for schedule in selected.filing_schedules
                if schedule.is_periodic and period in schedule.periods
            )
            if not selected_schedules:
                continue
            if any(
                window.filing_year == filing_year
                and window.period.registry_token == period
                and not filing_schedule_period_kind_mismatches(window.period_kind, (period,))
                for window in selected.deadline_windows
            ):
                continue
            failures.append(
                f"modelo {modelo.id} revision {selected.id}: periodic filing schedule coordinate "
                f"({filing_year}, {period!r}) has no deadline window",
            )
    return failures


def validate_informative_class_invariant(modelo: ModeloDefinition) -> list[str]:
    """Enforce that informative modelos carry no filing-grade computation artefacts.

    Args:
        modelo: The :class:`ModeloDefinition` to validate against the informative-class invariant.
    """
    if modelo.calculation_class != "informative":
        return []
    failures: list[str] = []
    for revision in modelo.revisions.values():
        prefix = f"modelo {modelo.id} revision {revision.id}"
        if revision.formulas:
            failures.append(
                f"{prefix}: informative modelo must not declare calculation formulas (got {len(revision.formulas)})",
            )
        if revision.relations:
            failures.append(
                f"{prefix}: informative modelo must not declare cross-model relations (got {len(revision.relations)})",
            )
        for casilla in revision.casillas:
            if casilla.input_kind not in {InputKind.INFORMATIONAL, InputKind.MANUAL}:
                failures.append(
                    f"{prefix}: informative modelo casilla {casilla.id!r} "
                    f"has input_kind={casilla.input_kind!r}; "
                    "only 'informational' and 'manual' are permitted",
                )
    return failures


def validate_m210_tipo_renta_code_projection_parity(
    modelo: ModeloDefinition,
    *,
    projected_codes: Collection[str] | None = None,
) -> list[str]:
    """Enforce bidirectional parity between the registry code set and the core projection.

    The official Modelo 210 tipo-de-renta code axis is declared in two places
    that MUST agree: the registry parameter ``m210-tipo-renta-code-<year>``
    (which codes the revision accepts, carrying the registry legal-grounding)
    and the core :data:`~cadrumo.core.M210_TIPO_RENTA_CODE_PROJECTION` (each code's
    :class:`~cadrumo.core.TipoRentaIrnr` rate concept). This gate fails the
    registry build in BOTH directions: a code declared in the registry with no
    core projection, and a code the core projects that the registry does not
    declare. It keeps the two axes from drifting so no declared code resolves to
    a fabricated rate and no projected code silently lacks a grounded home.

    Args:
        modelo: The :class:`ModeloDefinition` to check. Only revisions carrying
            an ``m210-tipo-renta-code-`` parameter are inspected; every other
            modelo is a no-op.
        projected_codes: Optional code set used for the comparison. When omitted,
            the shipped core projection is used.
    """
    failures: list[str] = []
    projected = set(M210_TIPO_RENTA_CODE_PROJECTION if projected_codes is None else projected_codes)
    for revision in modelo.revisions.values():
        for parameter in revision.parameters:
            if not parameter.id.startswith(_M210_TIPO_RENTA_CODE_PARAMETER_PREFIX):
                continue
            declared = {row.key for row in parameter.keyed_brackets}
            prefix = f"modelo {modelo.id} revision {revision.id} parameter {parameter.id!r}"
            for code in sorted(declared - projected):
                failures.append(
                    f"{prefix}: declared tipo-de-renta code {code!r} has no core "
                    "TipoRentaIrnr projection (add it to OFFICIAL_M210_TIPO_RENTA_CODES "
                    "or remove the declaration)",
                )
            for code in sorted(projected - declared):
                failures.append(
                    f"{prefix}: core-projected tipo-de-renta code {code!r} is not "
                    "declared in the registry code set (declare it here or remove it "
                    "from OFFICIAL_M210_TIPO_RENTA_CODES)",
                )
    return failures


def validate_reconciliation_total_closure(scope: str, revision: ModeloRevision) -> list[str]:
    failures: list[str] = []
    declared: dict[str, str] = {}
    for expectation in revision.verification_expectations:
        for total_kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            previous = declared.get(total_kind)
            if previous is not None and previous != casilla_id:
                failures.append(
                    f"{scope}: reconciliation total {total_kind!r} is declared by multiple casillas "
                    f"{previous!r} and {casilla_id!r}",
                )
            declared[total_kind] = casilla_id
    return failures
