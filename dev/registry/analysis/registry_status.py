"""Read-only status facts for the complete bundled registry lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority_descriptor_path,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.validate_below_floor_export_refs import declared_supported_filing_years_floor
from ..compiler.validate_bindings import informational_binding_ids, unreferenced_binding_advisories
from ..compiler.validate_export_field_placement import (
    binding_export_spans,
    export_record_placement_advisories,
    record_placed_spans,
    validate_export_record_field_placement,
)
from ..conformance.cli import load_bundled_runtime_authority, validate_registry
from ..maintenance_support import OracleEnvironment
from ..parity.maintenance import audit_registry_oracles
from ..pipeline.authority_publication import AuthorityDatabaseCurrencyStatus, authority_database_currency
from ..pipeline.generated_tree_dispositions import (
    GeneratedTreeBelowPublicationGradeDisposition,
    GeneratedTreeBelowSupportedFilingYearsDisposition,
    GeneratedTreeRecordDriftDisposition,
    GeneratedTreeRenderRefusalDisposition,
    GeneratedTreeTypeColumnContradictionDisposition,
    below_floor_dispositions,
    below_publication_grade_dispositions,
    disposition_ledger_from_path,
    record_drift_dispositions,
)

if TYPE_CHECKING:
    from .generated_tree_state import GeneratedTreeState

type GeneratedTreeDispositionRow = (
    GeneratedTreeBelowPublicationGradeDisposition
    | GeneratedTreeBelowSupportedFilingYearsDisposition
    | GeneratedTreeRecordDriftDisposition
    | GeneratedTreeRenderRefusalDisposition
    | GeneratedTreeTypeColumnContradictionDisposition
)

_TARGET_STATE_NAMES: Final[tuple[str, ...]] = (
    "current",
    "explained",
    "stale",
    "drifted",
    "never-committed",
    "unreadable",
)

#: Generated-tree states whose difference from a fresh render a ledger row may explain.
_EXPLAINABLE_TREE_STATES: Final[frozenset[str]] = frozenset({"record_drift", "manifest_only_stale"})

#: Manifest members whose movement means the official design changed under a row.
_SOURCE_PIN_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset({"source_ref", "source_sha256"})

#: What the placement census counted, named wherever its numbers are shown.
#:
#: Every other lane here walks files, and its record and field figures are file
#: figures. This one does not, and the three ways it differs are exactly the
#: three ways a reader would otherwise mis-compare it: it counts MATERIALISED
#: records (declaration fragments already merged by the loader, so a record
#: split across four files is one record), PER REVISION (the same record id in
#: two revisions is two records), and from BOTH SITES (inline export fields plus
#: the fixed export selectors of the bindings naming the record). A raw file
#: walk of the same corpus reads several hundred more "records" and far fewer
#: placed positions; neither figure is wrong, and they are not comparable.
EXPORT_PLACEMENT_POPULATION: Final[str] = "materialised, per revision, both sites"


@dataclass(frozen=True, slots=True)
class ExportPlacementCensus:
    """What the fixed-width placement check observed across every export record.

    Carries the denominators beside the findings on purpose. ``overlaps = 0`` on
    its own cannot be told apart from a check that walked nothing, and the two
    readings call for opposite actions; ``records`` and ``fields`` are what make
    a silent result legible as coverage rather than as absence.
    """

    overlaps: int = 0
    """Positions two fields both claim. A refusal at registry build, so a
    validated registry carries none and a non-zero count here means the census
    ran over an authority the validator had already rejected."""
    gaps: int = 0
    """Spans of positions no field writes, including a record whose first field
    does not begin at position 1. Advisory while the authored envelope-header
    and page records still carry the population the compiler-owned check
    measures, which is why it is reported here rather than refused there."""
    records: int = 0
    """Export records walked, across every layout of every revision."""
    fields: int = 0
    """Fields declaring both an offset and a length, across those records."""
    by_modelo: tuple[tuple[str, int], ...] = ()
    """Per-modelo finding count, overlaps and gaps together, modelos with none
    omitted. The split between the two lives in the scalar totals above."""


@dataclass(frozen=True, slots=True)
class RegistryStatus:
    """All lifecycle axes observed by the report; collecting it never mutates data."""

    valid: bool
    oracles: bool
    targets: tuple[tuple[str, int], ...]
    target_findings: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]
    authority: str
    authority_recorded_digest: str | None
    authority_candidate_digest: str | None
    loadable: bool
    unreferenced_bindings: tuple[tuple[str, int], ...]
    """Per-modelo count of bindings no typed consumer names.

    An advisory axis, not a lifecycle failure: the authored corpus still
    carries such rows, and the compiler deliberately reports rather than
    refuses them. Surfacing the count per modelo is what keeps the residue
    measurable instead of invisible -- an advisory nothing prints is
    indistinguishable from an advisory nothing raises.
    """
    informational_bindings: tuple[tuple[str, int], ...]
    """Per-modelo count of bindings declaring a non-calculation disposition.

    The dispositioned counterpart of :attr:`unreferenced_bindings`: a row the
    author classed as informational leaves the advisory and arrives here, so the
    disposition is a move between two reported lines rather than a way to make a
    binding stop being counted at all.
    """
    details: tuple[str, ...]
    export_placement: ExportPlacementCensus = ExportPlacementCensus()
    """Fixed-width placement census over every export record.

    Defaulted so a caller assembling a status for one other axis need not
    fabricate a census it did not take; the default reads as "walked nothing",
    which its own denominators make visible.
    """
    target_census_failed: bool = False
    """Whether the generated-target census refused to produce an answer.

    Distinct from any target state, because "the measurement did not happen" is
    not a property of a target. ``unreadable`` carries the targets the
    generated-state owner legitimately excluded, and those are advisory; a
    census that raised has excluded everything and knows nothing, so it blocks.
    Without this the two are the same count and a crash reports as a clean run.
    """


@dataclass(frozen=True, slots=True)
class TargetDriftExplanation:
    """Whether one ledger row explains one drifting target, and why or why not.

    ``honoured`` is False whenever the row's recorded evidence no longer
    describes the observed drift. The target then stays a currentness failure,
    and ``detail`` names the evidence that stopped matching.
    """

    subject: str
    kind: str
    honoured: bool
    detail: str


def explain_target_drift(
    state: GeneratedTreeState,
    dispositions: Iterable[GeneratedTreeDispositionRow],
    *,
    declared_floor: int,
    revision_filing_years: tuple[int, ...],
    revision_authority_grade: RegistryAuthorityGrade | None,
) -> TargetDriftExplanation | None:
    """Judge whether the ledger row keyed to exactly this target explains its drift.

    Returns ``None`` when no row names the target, or the target is in a state no
    row can explain, so the target keeps the verdict it already had.

    Three classes explain a difference from a fresh render, matching how the
    reproduction gate and the publisher read them:

    - ``below_floor``: republication is unreachable because every filing year
      the revision declares lies below the supported-filing-years floor.
      Honoured only while the row's recorded floor equals the floor the legal
      tree declares, and the revision's own newest filing year still equals the
      row's and lies below that floor.
    - ``below_publication_grade``: republication is refused because the
      revision's declared grade lies below the static-publication floor.
      Honoured only for manifest-only staleness, and only while the revision
      still declares exactly the grade the row records.
    - ``record_drift``: honoured only for record drift, and only while the
      number of differing records equals the count the row states.

    Every row is honoured only while its design pin equals the source the
    committed tree attests and the fresh render did not move that pin: a
    reissued design is a different drift from the one the row was written for.
    ``render_refusal`` rows describe trees that never reach the comparison and
    ``type_column_contradiction`` rows describe trees that reproduce, so neither
    explains a drift here.

    Args:
        state: The classified target, carrying the observed comparison evidence.
        dispositions: Ledger rows loaded through the canonical ledger loader.
        declared_floor: The supported-filing-years floor the legal tree declares.
        revision_filing_years: Every filing year the target revision declares.
        revision_authority_grade: The grade the target revision declares, or
            ``None`` when it declares none.
    """
    if state.state not in _EXPLAINABLE_TREE_STATES:
        return None
    subject = f"{state.modelo}/{state.revision}"
    row = next(
        (
            item
            for item in dispositions
            if item.subject == subject
            and isinstance(
                item,
                GeneratedTreeBelowPublicationGradeDisposition
                | GeneratedTreeBelowSupportedFilingYearsDisposition
                | GeneratedTreeRecordDriftDisposition,
            )
        ),
        None,
    )
    if row is None:
        return None

    def refused(reason: str) -> TargetDriftExplanation:
        return TargetDriftExplanation(subject=subject, kind=row.kind, honoured=False, detail=reason)

    pin = (row.source_ref, row.source_sha256)
    if state.committed_source != pin:
        attested = "no loadable manifest" if state.committed_source is None else "@".join(state.committed_source)
        return refused(f"{row.kind} row pins design {'@'.join(pin)}, the committed tree attests {attested}")
    moved_pin = sorted(_SOURCE_PIN_MANIFEST_FIELDS.intersection(state.provenance_fields))
    if moved_pin:
        return refused(f"{row.kind} row pins design {row.source_ref}, the fresh render moved {', '.join(moved_pin)}")

    if isinstance(row, GeneratedTreeBelowSupportedFilingYearsDisposition):
        if row.supported_filing_years_floor != declared_floor:
            return refused(
                f"below_floor row pins floor {row.supported_filing_years_floor}, "
                f"the registry declares {declared_floor}",
            )
        newest = max(revision_filing_years, default=None)
        if newest is None or newest != row.revision_last_filing_year or newest >= declared_floor:
            return refused(
                f"below_floor row pins newest filing year {row.revision_last_filing_year}, the revision declares "
                f"{list(revision_filing_years)} against floor {declared_floor}",
            )
        return TargetDriftExplanation(
            subject=subject,
            kind=row.kind,
            honoured=True,
            detail=(
                f"explained by below_floor disposition: filing years through {newest} lie below the "
                f"supported floor {declared_floor}; {state.detail}"
            ),
        )

    if isinstance(row, GeneratedTreeBelowPublicationGradeDisposition):
        if state.state != "manifest_only_stale":
            return refused(
                "below_publication_grade row explains manifest-only staleness, the comparison reports record drift"
            )
        if revision_authority_grade is not row.authority_grade:
            declared = "no grade" if revision_authority_grade is None else repr(revision_authority_grade.value)
            return refused(
                f"below_publication_grade row pins grade {row.authority_grade.value!r}, the revision declares "
                f"{declared}",
            )
        return TargetDriftExplanation(
            subject=subject,
            kind=row.kind,
            honoured=True,
            detail=(
                f"explained by below_publication_grade disposition: {row.authority_grade.value!r} authority "
                f"lies below the static-publication grade; {state.detail}"
            ),
        )

    if state.state != "record_drift":
        return refused("record_drift row stands but only the generation manifest differs")
    observed = len(state.record_differing)
    if observed != row.differing_records:
        return refused(
            f"record_drift row explains {row.differing_records} record(s), the comparison reports {observed}"
        )
    return TargetDriftExplanation(
        subject=subject,
        kind=row.kind,
        honoured=True,
        detail=f"explained by record_drift disposition (remedy={row.remedy}); {state.detail}",
    )


def _explaining_dispositions(ledger_path: Path | None) -> tuple[GeneratedTreeDispositionRow, ...]:
    """Load the ledger rows through the canonical loader; the live ledger by default."""
    if ledger_path is None:
        return (*below_floor_dispositions(), *below_publication_grade_dispositions(), *record_drift_dispositions())
    return disposition_ledger_from_path(ledger_path)


@dataclass(frozen=True, slots=True)
class ProjectedTargets:
    """Generated-target states projected onto the report's target buckets."""

    counts: tuple[tuple[str, int], ...]
    findings: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]
    details: tuple[str, ...]


_REPORTED_TREE_STATES: Final[dict[str, str]] = {
    "reproducible": "current",
    "manifest_only_stale": "stale",
    "record_drift": "drifted",
    "never_committed": "never-committed",
}


def project_target_states(
    states: Iterable[GeneratedTreeState],
    excluded: Iterable[tuple[str, str, str]],
    *,
    dispositions: tuple[GeneratedTreeDispositionRow, ...],
    declared_floor: Callable[[], int],
    revision_filing_years: Callable[[str, str], tuple[int, ...]],
    revision_authority_grade: Callable[[str, str], RegistryAuthorityGrade | None],
    excluded_count: int,
) -> ProjectedTargets:
    """Bucket each classified target, moving a drift its ledger row explains to ``explained``.

    A target whose row is not honoured stays in its drifting bucket and the
    refusal is named in its detail and in the report details. ``declared_floor``
    is read only when some row names a classified target.
    """
    grouped: dict[str, list[tuple[str, str, str]]] = {
        "explained": [],
        "stale": [],
        "drifted": [],
        "never-committed": [],
        "unreadable": list(excluded),
    }
    counts: Counter[str] = Counter()
    details: list[str] = []
    floor: int | None = None
    for item in states:
        bucket = _REPORTED_TREE_STATES[item.state]
        detail = item.detail
        if any(row.subject == f"{item.modelo}/{item.revision}" for row in dispositions):
            if floor is None:
                floor = declared_floor()
            explanation = explain_target_drift(
                item,
                dispositions,
                declared_floor=floor,
                revision_filing_years=revision_filing_years(item.modelo, item.revision),
                revision_authority_grade=revision_authority_grade(item.modelo, item.revision),
            )
            if explanation is not None and explanation.honoured:
                bucket = "explained"
                detail = explanation.detail
            elif explanation is not None:
                detail = f"{item.detail}; disposition not honoured: {explanation.detail}"
                details.append(f"TARGETS: {explanation.subject}: disposition not honoured: {explanation.detail}")
        counts[bucket] += 1
        if bucket in grouped:
            grouped[bucket].append((item.modelo, item.revision, detail))
    counts["unreadable"] = excluded_count
    return ProjectedTargets(
        counts=tuple((state, counts[state]) for state in _TARGET_STATE_NAMES),
        findings=tuple((state, tuple(findings)) for state, findings in grouped.items()),
        details=tuple(details),
    )


def collect_registry_status(
    *,
    registry_root: Path | None = None,
    source_root: Path | None = None,
    authority_descriptor: Path | None = None,
    disposition_ledger: Path | None = None,
) -> RegistryStatus:
    """Delegate each status axis to its owning validator or currency primitive."""
    resolved_registry_root = registry_root or bundled_path("registry", "aeat")
    resolved_source_root = source_root or bundled_path()
    resolved_descriptor = authority_descriptor or bundled_authority_descriptor_path()
    details: list[str] = []

    authority = None
    try:
        authority = validate_registry(registry_root=resolved_registry_root, source_root=resolved_source_root)
        valid = True
    except Exception as error:
        valid = False
        details.append(f"VALID: {type(error).__name__}: {error}")

    try:
        oracle_report = audit_registry_oracles(
            resolved_registry_root,
            environment=OracleEnvironment.PRODUCTION,
        )
        oracles = not oracle_report.failures
        if not oracles:
            details.append(f"ORACLES: {', '.join(oracle_report.failures)}")
    except Exception as error:
        oracles = False
        details.append(f"ORACLES: {type(error).__name__}: {error}")

    target_census_failed = False
    if authority is None:
        target_census_failed = True
        targets = Counter({"unreadable": 1})
        target_findings = (("unreadable", (("unknown", "unknown", "whole-registry validity failed"),)),)
        details.append("TARGETS: unavailable because whole-registry validity failed")
    else:
        try:
            from .generated_tree_state import generated_state_inventory

            # Walked one modelo at a time so a single unrenderable one cannot
            # blind the census of every other. Asking for the whole corpus in
            # one call meant modelo 360's literal-field defect aborted all 58,
            # and the caller then could not say whether the defect was one
            # field or the first of thousands. A modelo that raises is recorded
            # and blocks; the rest are still counted.
            states = []
            excluded = []
            unrenderable: list[str] = []
            for modelo in authority.modelos:
                try:
                    modelo_states, modelo_excluded = generated_state_inventory(authority, (str(modelo.id),))
                except Exception as modelo_error:
                    unrenderable.append(str(modelo.id))
                    details.append(f"TARGETS: modelo {modelo.id}: {type(modelo_error).__name__}: {modelo_error}")
                    continue
                states.extend(modelo_states)
                excluded.extend(modelo_excluded)
            if unrenderable:
                target_census_failed = True
                joined = ", ".join(unrenderable)
                details.append(f"TARGETS: {len(unrenderable)} modelo(s) could not be censused: {joined}")
            expected_target_count = sum(len(modelo.revisions) for modelo in authority.modelos)
            excluded_target_count = max(0, expected_target_count - len(states))
            if excluded_target_count:
                details.append(f"TARGETS: {excluded_target_count} target(s) were excluded by the generated-state owner")
            validated_authority = authority
            projected = project_target_states(
                states,
                excluded,
                dispositions=_explaining_dispositions(disposition_ledger),
                declared_floor=lambda: declared_supported_filing_years_floor(registry_root=resolved_registry_root),
                revision_filing_years=lambda modelo_id, revision_id: next(
                    tuple(revision.period_selector.years)
                    for candidate_id, revision in validated_authority.modelo(modelo_id).revisions.items()
                    if str(candidate_id) == revision_id
                ),
                revision_authority_grade=lambda modelo_id, revision_id: next(
                    revision.effective_authority_grade if revision.is_graded else None
                    for candidate_id, revision in validated_authority.modelo(modelo_id).revisions.items()
                    if str(candidate_id) == revision_id
                ),
                excluded_count=excluded_target_count,
            )
            details.extend(projected.details)
            targets = Counter(dict(projected.counts))
            target_findings = projected.findings
        except Exception as error:
            target_census_failed = True
            targets = Counter({"unreadable": 1})
            target_findings = (("unreadable", (("unknown", "unknown", str(error)),)),)
            details.append(f"TARGETS: {type(error).__name__}: {error}")

    recorded_digest: str | None = None
    candidate_digest: str | None = None
    try:
        currency = authority_database_currency(
            resolved_descriptor,
            registry_root=resolved_registry_root,
            source_root=resolved_source_root,
        )
        authority_status = currency.status.value
        recorded_digest = currency.recorded_identity_digest
        candidate_digest = currency.candidate_identity_digest
        if currency.status is not AuthorityDatabaseCurrencyStatus.CURRENT:
            details.append(f"AUTHORITY: {currency.detail}")
    except Exception as error:
        authority_status = AuthorityDatabaseCurrencyStatus.UNREADABLE.value
        details.append(f"AUTHORITY: {type(error).__name__}: {error}")

    try:
        runtime_authority = load_bundled_runtime_authority()
        runtime_authority.close()
        loadable = True
    except Exception as error:
        loadable = False
        details.append(f"LOADABLE: {type(error).__name__}: {error}")

    unreferenced_bindings = _unreferenced_binding_counts(authority)
    if unreferenced_bindings:
        total = sum(count for _, count in unreferenced_bindings)
        modelos = ", ".join(f"{modelo}={count}" for modelo, count in unreferenced_bindings)
        details.append(f"UNREFERENCED-BINDINGS: {total} binding(s) named by no typed consumer ({modelos})")

    informational_bindings = _informational_binding_counts(authority)
    if informational_bindings:
        informational_total = sum(count for _, count in informational_bindings)
        informational_modelos = ", ".join(f"{modelo}={count}" for modelo, count in informational_bindings)
        details.append(
            f"INFORMATIONAL-BINDINGS: {informational_total} binding(s) declaring a non-calculation "
            f"disposition ({informational_modelos})"
        )

    export_placement = _export_placement_census(authority)
    if export_placement.overlaps or export_placement.gaps:
        placement_modelos = ", ".join(f"{modelo}={count}" for modelo, count in export_placement.by_modelo)
        details.append(
            f"EXPORT-PLACEMENT ({EXPORT_PLACEMENT_POPULATION}): {export_placement.overlaps} overlap(s) and "
            f"{export_placement.gaps} gap(s) across {export_placement.records} record(s) and "
            f"{export_placement.fields} placed field(s) "
            f"({placement_modelos})"
        )

    return RegistryStatus(
        valid=valid,
        oracles=oracles,
        targets=tuple((state, targets[state]) for state in _TARGET_STATE_NAMES),
        target_findings=target_findings,
        target_census_failed=target_census_failed,
        authority=authority_status,
        authority_recorded_digest=recorded_digest,
        authority_candidate_digest=candidate_digest,
        loadable=loadable,
        unreferenced_bindings=unreferenced_bindings,
        informational_bindings=informational_bindings,
        details=tuple(details),
        export_placement=export_placement,
    )


def _export_placement_census(authority: ValidatedRegistryAuthority | None) -> ExportPlacementCensus:
    """Census the placement of every export record the validated authority carries.

    Returns an empty census when the registry failed validity: an authority that
    did not load has no records to speak about, which is not the same as having
    none misplaced.
    """
    if authority is None:
        return ExportPlacementCensus()
    return export_placement_census(authority.modelos)


def export_placement_census(modelos: Iterable[ModeloDefinition]) -> ExportPlacementCensus:
    """Census the fixed-width placement of every export record, per modelo.

    Grouping: one census entry per compiled ``ExportRecordDefinition``, which is
    per layout record of each revision AFTER the loader has merged that record's
    declaration fragments into a single field list. A record declared across
    several files is one record here, not several, and its contiguity is judged
    over the whole merged list.

    Read through the compiler-owned
    :func:`~dev.registry.compiler.validate_export_field_placement.validate_export_record_field_placement`
    and its advisory sibling for the same reason the binding counts read through
    theirs: the report must not hold a second opinion about what a gap or an
    overlap is. Walks already-loaded definitions, so the census adds no second
    read of the registry tree and mutates nothing.

    Args:
        modelos: Loaded modelo definitions whose export layouts are walked.
    """
    overlaps = 0
    gaps = 0
    records = 0
    fields = 0
    counts: list[tuple[str, int]] = []
    for modelo in modelos:
        modelo_findings = 0
        for revision_id, revision in modelo.revisions.items():
            prefix = f"modelo {modelo.id} revision {revision_id}"
            spans = binding_export_spans(revision)
            for layout in revision.export_layouts:
                for record in layout.records:
                    records += 1
                    fields += len(record_placed_spans(record, spans))
                    record_overlaps = len(
                        validate_export_record_field_placement(prefix=prefix, record=record, binding_spans=spans),
                    )
                    record_gaps = len(
                        export_record_placement_advisories(prefix=prefix, record=record, binding_spans=spans),
                    )
                    overlaps += record_overlaps
                    gaps += record_gaps
                    modelo_findings += record_overlaps + record_gaps
        if modelo_findings:
            counts.append((str(modelo.id), modelo_findings))
    return ExportPlacementCensus(
        overlaps=overlaps,
        gaps=gaps,
        records=records,
        fields=fields,
        by_modelo=tuple(sorted(counts)),
    )


def _unreferenced_binding_counts(authority: ValidatedRegistryAuthority | None) -> tuple[tuple[str, int], ...]:
    """Count, per modelo, the bindings the compiler's advisory names.

    Read through the same :func:`unreferenced_binding_advisories` the compiler
    owns rather than recounted here, so the report and the validator can never
    disagree about what counts as unreferenced. Returns nothing when the
    registry failed validity: an unloadable authority has no bindings to speak
    about, which is not the same as having none unreferenced.
    """
    if authority is None:
        return ()
    counts: list[tuple[str, int]] = []
    for modelo in authority.modelos:
        advisories = tuple(
            advisory
            for revision_id, revision in modelo.revisions.items()
            for advisory in unreferenced_binding_advisories(
                prefix=f"modelo {modelo.id} revision {revision_id}",
                revision=revision,
            )
        )
        if advisories:
            counts.append((str(modelo.id), len(advisories)))
    return tuple(sorted(counts))


def _informational_binding_counts(authority: ValidatedRegistryAuthority | None) -> tuple[tuple[str, int], ...]:
    """Count, per modelo, the bindings that declare a non-calculation disposition.

    Read through the compiler-owned :func:`informational_binding_ids` for the
    same reason the unreferenced count reads through its advisory: the report
    must not hold a second opinion about what the disposition means.
    """
    if authority is None:
        return ()
    counts: list[tuple[str, int]] = []
    for modelo in authority.modelos:
        total = sum(len(informational_binding_ids(revision)) for revision in modelo.revisions.values())
        if total:
            counts.append((str(modelo.id), total))
    return tuple(sorted(counts))


def _export_placement_lane(census: ExportPlacementCensus) -> str:
    """Project the placement census onto the report's three lane states.

    An overlap fails the lane: it is a refusal at registry build, so observing
    one here means a record that must not ship is being reported as health. A
    gap is partial, matching the compiler's own advisory posture. Neither means
    the lane passes silently on nothing walked -- the census denominators carry
    that, and a lane state cannot.
    """
    if census.overlaps:
        return "failed"
    return "partial" if census.gaps else "passed"


def _payload(status: RegistryStatus, *, blocking: bool) -> dict[str, object]:
    target_counts = dict(status.targets)
    blocking_target_count = sum(target_counts[state] for state in ("stale", "drifted", "never-committed"))
    lanes = {
        "authority_currency": (
            "passed" if status.authority == AuthorityDatabaseCurrencyStatus.CURRENT.value else "failed"
        ),
        "oracle_bindings": "passed" if status.oracles else "failed",
        "registry_validity": "passed" if status.valid else "failed",
        "runtime_loadability": "passed" if status.loadable else "failed",
        "target_currentness": "failed" if status.target_census_failed or blocking_target_count else "passed",
        "target_coverage": "partial" if target_counts["unreadable"] else "passed",
        "binding_reference_coverage": "partial" if status.unreferenced_bindings else "passed",
        "export_placement_coverage": _export_placement_lane(status.export_placement),
    }
    failed_lanes = sorted(lane for lane, state in lanes.items() if state == "failed")
    partial_lanes = sorted(lane for lane, state in lanes.items() if state == "partial")
    target_overview: dict[str, object] = {}
    for state, findings in status.target_findings:
        if not findings:
            continue
        sample_limit = 5 if state == "unreadable" else 10
        reason_counts: dict[str, int] = {}
        if state == "unreadable":
            for _, _, detail in findings:
                if "declares no export layout" in detail:
                    reason = "no_export_layout"
                elif "cites no record-design source" in detail:
                    reason = "no_record_design_source"
                elif "has no authored inputs" in detail:
                    reason = "missing_authored_inputs"
                else:
                    reason = "other"
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        target_overview[state] = {
            "count": len(findings),
            "affected_modelos": sorted({modelo for modelo, _, _ in findings}),
            "sample_targets": [
                {"modelo": modelo, "revision": revision, "detail": detail}
                for modelo, revision, detail in findings[:sample_limit]
            ],
            "targets_omitted": max(0, len(findings) - sample_limit),
            **({"reason_counts": dict(sorted(reason_counts.items()))} if reason_counts else {}),
        }
    actions: list[dict[str, object]] = []
    if status.authority != AuthorityDatabaseCurrencyStatus.CURRENT.value:
        actions.append(
            {
                "code": "authority_not_current",
                "command": "just registry-publish-authority",
                "detail": "Publish the validated authority after reviewing the authored registry changes.",
            }
        )
    action_by_state = {
        "stale": ("review_then_republish_target", "Review the generated diff, then use registry-republish-target."),
        "drifted": ("investigate_record_drift", "Investigate record-byte drift; do not republish blindly."),
        "never-committed": ("publish_target", "Review and publish the missing generated target."),
    }
    for state, findings in status.target_findings:
        if state not in action_by_state:
            continue
        code, detail = action_by_state[state]
        for modelo, revision, _ in findings:
            actions.append({"code": code, "modelo": modelo, "revision": revision, "detail": detail})
    return {
        "schema_version": 1,
        "command": "check-registry" if blocking else "report-registry-status",
        "posture": "blocking" if blocking else "advisory",
        "result": "passed" if not failed_lanes else "failed",
        "classification": "clean" if not failed_lanes else "registry_findings",
        "headline": (
            "Registry health passed across all lifecycle lanes."
            if not failed_lanes
            else f"Registry health found {len(failed_lanes)} failing lifecycle lane(s)."
        ),
        "summary": {
            "lanes_total": len(lanes),
            "lanes_passed": len(lanes) - len(failed_lanes) - len(partial_lanes),
            "lanes_failed": len(failed_lanes),
            "lanes_partial": len(partial_lanes),
            "details_total": len(status.details),
        },
        "lanes": dict(sorted(lanes.items())),
        "failed_lanes": failed_lanes,
        "partial_lanes": partial_lanes,
        "targets": target_counts,
        "target_findings": target_overview,
        "authority": {
            "status": status.authority,
            "recorded_identity_digest": status.authority_recorded_digest,
            "candidate_identity_digest": status.authority_candidate_digest,
        },
        "unreferenced_bindings": {
            "total": sum(count for _, count in status.unreferenced_bindings),
            "by_modelo": dict(status.unreferenced_bindings),
        },
        "informational_bindings": {
            "total": sum(count for _, count in status.informational_bindings),
            "by_modelo": dict(status.informational_bindings),
        },
        "export_placement": {
            "population": EXPORT_PLACEMENT_POPULATION,
            "overlaps": status.export_placement.overlaps,
            "gaps": status.export_placement.gaps,
            "records": status.export_placement.records,
            "fields": status.export_placement.fields,
            "by_modelo": dict(status.export_placement.by_modelo),
        },
        "details": list(status.details),
        "actions": actions,
    }


def _render_export_placement(census: ExportPlacementCensus) -> None:
    """Print the placement census beside the name of the population it counted."""
    print(
        f"export_placement({EXPORT_PLACEMENT_POPULATION}): overlaps={census.overlaps} "
        f"gaps={census.gaps} records={census.records} fields={census.fields}"
    )


def main(argv: list[str] | None = None) -> int:
    """Print lifecycle facts without publishing, repairing, or regenerating artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the status payload as JSON")
    parser.add_argument("--check", action="store_true", help="exit non-zero when any lifecycle lane fails")
    args = parser.parse_args(argv)
    status = collect_registry_status()
    payload = _payload(status, blocking=args.check)
    if args.json:
        for state, findings in status.target_findings:
            for modelo, revision, detail in findings:
                print(
                    f"TARGET_DETAIL\tstate={state}\tmodelo={modelo}\trevision={revision}\tdetail={detail}",
                    file=sys.stderr,
                )
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 1 if args.check and payload["result"] == "failed" else 0

    print("report-registry-status\tposture=report-only; exit_status=0")
    print(f"VALID\t{'pass' if status.valid else 'fail'}")
    print(f"ORACLES\t{'pass' if status.oracles else 'fail'}")
    target_values = " ".join(f"{state}={count}" for state, count in status.targets)
    print(f"TARGETS\t{target_values or 'unreadable=1'}")
    print(f"AUTHORITY\t{status.authority}")
    print(f"LOADABLE\t{'pass' if status.loadable else 'fail'}")
    _render_export_placement(status.export_placement)
    for detail in status.details:
        print(f"DETAIL\t{detail}")
    return 1 if args.check and payload["result"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXPORT_PLACEMENT_POPULATION",
    "ExportPlacementCensus",
    "GeneratedTreeDispositionRow",
    "ProjectedTargets",
    "RegistryStatus",
    "TargetDriftExplanation",
    "collect_registry_status",
    "explain_target_drift",
    "export_placement_census",
    "main",
    "project_target_states",
]
