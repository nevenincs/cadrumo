"""Migrate one modelo's casilla declarations from full-copy editions to delta editions.

A full-copy edition states every casilla row itself. A delta edition names a
``predecessor`` in its manifest and states only the rows that are new in it or
that differ from the row it would inherit; the loader materialises the rest.
This tool rewrites a modelo from the first shape to the second, and proves the
rewrite exact before it publishes anything.

What the migration does, edition by edition in validity order:

- **Chooses a predecessor.** The first edition stays the modelo's single root
  and declares nothing. Every later edition names the adjacent earlier edition,
  unless the two overlap in period (they may be parallel variants, not a
  sequence). A predecessor an edition already declares is kept as declared.
- **Lifts restatement.** ``casilla_source_refs`` is declared once on the
  edition when every row and constraints table states some ``source_refs`` and
  one leading run of references opens the ``source_refs`` of more rows than any
  other, and of at least two; among runs opening equally many rows the longest
  is taken, and two distinct runs of that length are a tie and declare nothing.
  Each row and constraints table stating exactly that run then drops its
  ``source_refs``, and one stating the run followed by further references
  states only those, as ``additional_source_refs``, which the loader appends
  to the default. A row or constraints table whose ``legal_refs`` equal the
  edition's ``orden_aplicabilidad`` drops them, since the loader fills that
  default already. A ``source_refs`` value the default and additions cannot
  reproduce exactly is kept whole.
- **Collapses inherited rows.** An identical row is dropped. A changed row
  becomes a recursive ``casilla_overrides`` patch against the predecessor's
  raw storage row, including explicit provenance when it is restated. New rows
  remain stated in full. Every planned patch is simulated through the same
  defaults and reference resolution before the candidate is written.
- **Reorders** the edition once, into the order the merge defines: inherited
  rows in the predecessor's materialised order, superseding rows in place, new
  rows after them in stated order.
- **Writes** the delta: the dropped rows' blocks are removed from their
  fragments, each fragment is renamed to the span it still declares, and the
  manifest gains ``predecessor`` and ``casilla_source_refs``. Existing review
  metadata is preserved byte-for-byte because storage shape is not review scope.

An edition the materialiser cannot reproduce exactly is **blocked** and stays a
full copy with its restatement lifted. The causes are closed: an overlapping
predecessor; renamed fragments that would state the new rows out of
their full-copy order, which the merge would then keep; a predecessor lineage
the successor omits without withdrawing it, through a ``retired`` evolution or
as the source of a structural succession; a predecessor row carrying no
lineage; or a planned delta the loader itself refuses to materialise, such as
a lineage carried twice or a stated row colliding with an inherited row of
another lineage, reported with the loader's own refusal. Because a modelo whose editions name predecessors admits one
key-less root only, a blocked edition other than the first needs an explicit
no-predecessor declaration. That declaration is a claim about the form, so the
tool reports the unresolved source condition and refuses application rather
than manufacturing legal continuity.

Proof and publication. The migration is written into a staging copy of the
registry and compared with the unmigrated modelo through the round-trip gate:
typed equality of every edition, casilla row order against the merge order,
locale identity, and export bytes for each edition an export scenario is given
for. The staged tree must
  preserve the edition's existing review metadata, so the carry-forward is
  decided at publication: ``--apply`` replaces the modelo in
the target registry only when source equivalence and minimality report no source
finding. Publication-readiness findings, including unchecked export bytes,
remain visible but do not block a proven source-only replacement. Without
``--apply`` nothing outside
the work directory is written by the migration; the command-line report is
written separately under the repository's ``.logs/audit-runs`` run-output
tree, which is transient: the next reclamation removes it, so promote anything
the decision rests on into durable evidence rather than citing a run directory.

Two proofs, one per starting shape. A modelo that states every row in full is
proven as above, against its own full copy. A modelo that already names
predecessors has no full copy left to prove a change against, so it is proven
against its chain instead: the staged edition is materialised through its
predecessors and must be **byte-identical** to what the edition materialises to
now, with the manifest defaults it declares inlined into the rows they fill, and
must pass the same round-trip gate. Anything short of identity refuses.

Order is part of that identity, and the order compared is the one the
declarations give. Member order in every inherited family is meaning -- casilla
rows follow the record design, and keyed families keep theirs through the merge
and declared positions -- while the order of a table's keys is serialisation and
is never compared. A partial statement's order is the merge's. An edition that
states every member of a family it also inherits is a full copy of that family
and means the order it states, but a storage baseline added beneath it makes
the merge move each member new to the baseline to the end. So before planning,
the positions that keep each such stated order are written into a copy of the
live tree and proven to move members only; that copy is what the migration
plans from and what the staged tree must equal, and each restored family is
reported. A complete statement that also declares positions for the family is
refused, because the two disagree about its order.

Because that proof compares the tree with itself, the default operation on the
chain path is **lifting in place**. On that path the tool may stop a row
restating what it can inherit from a manifest default, and may declare a default
the edition does not yet declare; it may not add, drop or reorder a member, and
the identity of every casilla row and reference-family member is compared before
and after to enforce that structurally. Predecessors, review stamps and row order
are left exactly as authored.

**Dropping restatement** (``--drop-restatement``) is the second operation the
same proof admits, and it is opt-in precisely because it removes declarations.
A successor edition states a member its predecessor already carries, byte for
byte; the union rule says it should state only what is new or divergent, so the
restatement is deleted and the loader's keyed merge puts the inherited member
back in the same position. The proof is unchanged and is what authorises the
write: a correct drop is invisible to it, because the member the edition
materialises after the drop is the member it materialised before. A drop that
was not a restatement changes the materialisation and is refused. Nothing about
:func:`_prove_chain` is relaxed to let a drop through.

What the drop will touch is decided by what the loader actually inherits, not by
what looks repetitive. A family whose members do not inherit must keep its full
copy, because omission there is deletion rather than inheritance; see
``_DROPPABLE_FAMILIES`` for the enrolled set and for every family held back and
why. Manifest scalars are never stripped: this loader has no manifest-scalar
inheritance, so an omitted ``orden_aplicabilidad`` or ``casilla_source_refs`` is
absent, not inherited. Root editions inherit nothing and are skipped whole.

Determinism and idempotency. Every choice is a function of the input tree, taken
in sorted or validity order, so two runs over the same tree write the same
bytes. Both paths report ``changed=False`` and stage nothing when planning
reproduces what the editions already state and declare, so a run over an
already-lifted tree is a clean no-op.

Where it stops:

- The full-copy conversion path authors casilla declarations; the explicit
  ``--drop-restatement`` path also accepts every keyed family enrolled by the
  canonical union, including projection endpoints and verification predicates.
  Bindings participate in the keyed union with provider-kind, data-type and
  channel identity guards. Layouts, verification expectations, workbook pins
  and the completeness manifest remain per-edition claims by policy.
- It never authors a retirement, a repurpose, or lineage; it reads them.
- Label text is not rewritten. Locale keys are edition-scoped and the loader
  gives an inherited row its origin edition's key as a fallback.
- Export scenarios come from ``dev.registry.edition_export_scenarios``. An
  edition whose export surface has no scenario there is reported unchecked by
  the gate, which blocks ``--apply``; the typed, order and locale proofs still
  run.

For an authored change, ``--accepted-modelo-dir`` adds an independent retained
casilla order comparison against an accepted source snapshot before staging or
application. Intentional identity changes require explicit ``--rename-casilla
OLD=NEW`` pairs. New and removed members are reported separately; missing
comparison coverage refuses the operation. Without a supplied snapshot, the
migration's equivalence proof covers its own rewrite of the current source.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.keyed_families import (
    CASILLAS_FAMILY,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from dev.test_runs.paths import allocate_run_directory, test_log_root

from . import edition_delta_assessment as _edition_delta_assessment
from . import edition_delta_drop as _edition_delta_drop
from . import edition_delta_drop_reporting as _edition_delta_drop_reporting
from . import edition_delta_drop_types as _edition_delta_drop_types
from . import edition_delta_equivalence as _edition_delta_equivalence
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_order_restoration as _edition_delta_order_restoration
from . import edition_delta_override_pruning as _edition_delta_override_pruning
from . import edition_delta_planning as _edition_delta_planning
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_source_publication as _edition_delta_source_publication
from . import edition_delta_types as _edition_delta_types
from . import edition_delta_workdir as _edition_delta_workdir
from . import edition_delta_writer as _edition_delta_writer
from .casilla_order_review import render_report as render_casilla_order_review
from .casilla_order_review import review_casilla_order
from .edition_export_scenarios import edition_export_scenarios
from .edition_family_delta_collapse import collapse_keyed_families
from .edition_round_trip import (
    EditionExportScenario,
    RoundTripFinding,
    RoundTripReport,
    copy_registry_tree,
    edition_round_trip_report,
)

__all__ = [
    "MigrationOutcome",
    "main",
    "migrate_modelo",
    "persist_migration_report",
    "render_outcome",
]


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    """The plan, the gate's verdict on the staged tree, and whether the modelo was published."""

    plan: _edition_delta_types.MigrationPlan
    staged_registry: Path | None
    report: RoundTripReport | None
    applied: bool
    changed: bool
    before_assessment: _edition_delta_assessment.MigrationAssessment | None = None
    after_assessment: _edition_delta_assessment.MigrationAssessment | None = None
    #: Positions written so complete statements keep the order they state.
    order_restorations: tuple[_edition_delta_order_restoration.OrderRestoration, ...] = ()
    #: Every ``(revision, family)`` whose member order those positions change.
    reordered_families: tuple[tuple[str, str], ...] = ()

    @property
    def source_findings(self) -> tuple[RoundTripFinding, ...]:
        """Findings that disprove reconstruction or effective-data identity."""
        if self.report is None:
            return ()
        return tuple(
            finding for finding in self.report.findings if _edition_delta_assessment._is_source_finding(finding)
        )

    @property
    def publication_readiness_findings(self) -> tuple[RoundTripFinding, ...]:
        """Non-source findings retained for a later authority publication."""
        if self.report is None:
            return ()
        return tuple(
            finding for finding in self.report.findings if not _edition_delta_assessment._is_source_finding(finding)
        )

    @property
    def source_status(self) -> _edition_delta_assessment.SourceMigrationStatus:
        """Return the source replacement acceptance state."""
        if self.source_findings:
            return _edition_delta_assessment.SourceMigrationStatus.REFUSED
        if self.blocked:
            return _edition_delta_assessment.SourceMigrationStatus.PARTIAL
        return (
            _edition_delta_assessment.SourceMigrationStatus.APPLIED
            if self.applied
            else _edition_delta_assessment.SourceMigrationStatus.ACCEPTED
        )

    @property
    def publication_readiness_status(self) -> _edition_delta_assessment.PublicationReadinessStatus:
        """Return the separately observed authority-readiness state."""
        return (
            _edition_delta_assessment.PublicationReadinessStatus.FAILED
            if self.publication_readiness_findings
            else _edition_delta_assessment.PublicationReadinessStatus.NOT_CHECKED
        )

    @property
    def publication_execution_status(self) -> _edition_delta_assessment.PublicationExecutionStatus:
        """Confirm that source migration did not execute publication."""
        return _edition_delta_assessment.PublicationExecutionStatus.NOT_PERFORMED

    @property
    def completed(self) -> tuple[str, ...]:
        """Return revisions whose source representation was completed."""
        return self.plan.completed()

    @property
    def unchanged(self) -> tuple[str, ...]:
        """Return revisions intentionally left unchanged."""
        return self.plan.unchanged()

    @property
    def blocked(self) -> Mapping[str, tuple[str, ...]]:
        """Return blocked revisions and their typed planning details."""
        return {
            edition.revision_id: edition.blocked_detail
            for edition in self.plan.editions
            if edition.basis is _edition_delta_types.PredecessorBasis.BLOCKED
        }

    @property
    def complete(self) -> bool:
        """Whether reconstruction, scope coverage, and minimality all pass."""
        return (
            self.equivalence_status is _edition_delta_assessment.MigrationStatus.PASSED
            and self.minimality_status is _edition_delta_assessment.MigrationStatus.PASSED
        )

    @property
    def equivalence_status(self) -> _edition_delta_assessment.MigrationStatus:
        """Return the candidate hydration-equivalence verdict."""
        return (
            _edition_delta_assessment.MigrationStatus.FAILED
            if self.source_findings
            else _edition_delta_assessment.MigrationStatus.PASSED
        )

    @property
    def compaction_status(self) -> _edition_delta_assessment.MigrationStatus:
        """Return whether physical or semantic authored storage decreased."""
        if self.before_assessment is None or self.after_assessment is None:
            return _edition_delta_assessment.MigrationStatus.INCOMPLETE
        improved = (
            self.after_assessment.physical_bytes < self.before_assessment.physical_bytes
            or self.after_assessment.authored_payload_fields < self.before_assessment.authored_payload_fields
        )
        return (
            _edition_delta_assessment.MigrationStatus.COMPLETE
            if improved
            else _edition_delta_assessment.MigrationStatus.INCOMPLETE
        )

    @property
    def minimality_status(self) -> _edition_delta_assessment.MigrationStatus:
        """Return the independent redundant-payload and coverage verdict."""
        if self.after_assessment is None:
            return (
                _edition_delta_assessment.MigrationStatus.FAILED
                if self.blocked
                else _edition_delta_assessment.MigrationStatus.INCOMPLETE
            )
        if not self.changed and self.after_assessment.minimal:
            return _edition_delta_assessment.MigrationStatus.PASSED
        return (
            _edition_delta_assessment.MigrationStatus.PASSED
            if self.after_assessment.minimal and not self.blocked
            else _edition_delta_assessment.MigrationStatus.FAILED
        )

    @property
    def application_status(self) -> _edition_delta_assessment.MigrationStatus:
        """Return whether the verified candidate is live, staged, or absent."""
        if self.applied:
            return (
                _edition_delta_assessment.MigrationStatus.APPLIED
                if self.minimality_status is _edition_delta_assessment.MigrationStatus.PASSED
                else _edition_delta_assessment.MigrationStatus.PARTIALLY_APPLIED
            )
        return (
            _edition_delta_assessment.MigrationStatus.STAGED
            if self.staged_registry is not None
            else _edition_delta_assessment.MigrationStatus.NOT_APPLIED
        )


# ── raw tree reading ────────────────────────────────────────────────────────


# ── the loader's semantics, reproduced for a delta that is not written yet ──


# ── restatement lifting ─────────────────────────────────────────────────────


# ── planning ────────────────────────────────────────────────────────────────


# ── writing ─────────────────────────────────────────────────────────────────


#: Families whose members carry ``source_refs`` and whose edition default is
#: declared on the manifest under ``<family>_source_refs``. The derivation is
#: :func:`edition_source_default`, unchanged: the status screen imports the same
#: function, so a member it counts as liftable is a member this tool will lift.
#: Only families whose manifest key already exists in the schema appear here;
#: adding one is a schema change in the bindings lane, not a change here.


# ── the chain proof ─────────────────────────────────────────────────────────

#: Manifest keys the migration may declare. They are defaults: the loader folds
#: them into the members they fill, so the chain proof inlines their effect and
#: compares the members rather than the declaration.


#: Marks a rendered date so it can never compare equal to a string that happens
#: to read the same. TOML forbids control characters in keys and strings, so no
#: declaration can produce a table that collides with this tag.


# ── declared order ──────────────────────────────────────────────────────────


# ── dropping restatement ────────────────────────────────────────────────────


#: The families a drop may touch, and the reason each one is safe.  Membership
#: and identity axes come from the domain policy table consumed by the loader;
#: this projection is only the migration tool's local value type.
#:
#: A restatement is redundant only where the family INHERITS. Omitting a member
#: of a family the loader does not carry along the predecessor chain does not
#: leave the predecessor's member in its place; it deletes the member outright.
#: A family absent from that enrolment is absent here.
#:
#: The chain proof still authorises every write: a policy error produces a
#: materialisation difference and refuses the modelo rather than silently
#: losing a member.

#: Families deliberately held back, and what holds each one back. Naming them
#: here keeps the refusal a decision on the record rather than an omission, and
#: gives ``--family`` something honest to refuse against.

#: Manifest scalars that are load-bearing per-edition defaults. This loader has
#: NO manifest-scalar inheritance: an omitted default is absent, not inherited,
#: so stripping one would silently change every member it fills. The drop never
#: touches the manifest at all; the constant records why.


# ── the migration ───────────────────────────────────────────────────────────


@dataclass
class _MigrationPreparation:
    registry_root: Path
    work_dir: Path
    modelo_id: str
    modelo_dir: Path
    definition: ModeloDefinition
    before: _edition_delta_assessment.MigrationAssessment
    restorations: tuple[_edition_delta_order_restoration.OrderRestoration, ...]
    plan: _edition_delta_types.MigrationPlan
    works: tuple[_edition_delta_source._EditionWork, ...]
    family_changes: bool


@dataclass(frozen=True)
class _StagedMigration:
    reference: Path
    declared: Path
    reordered: tuple[tuple[str, str], ...]
    staged: Path
    plan: _edition_delta_types.MigrationPlan
    report: RoundTripReport


def _prepare_migration(registry_root: Path, modelo_id: str, work_dir: Path) -> _MigrationPreparation:
    registry_root, work_dir = _edition_delta_workdir._resolve_work_directory(registry_root, work_dir)
    modelo_dir = registry_root / _edition_delta_fields._MODELOS / modelo_id
    if not modelo_dir.is_dir() or not _edition_delta_workdir._inside(modelo_dir, registry_root):
        raise _edition_delta_errors.MigrationRefusedError(f"{registry_root} holds no modelo {modelo_id!r}")
    definition = _edition_delta_workdir._load(registry_root, modelo_id)
    before = _edition_delta_assessment.assess_migration_state(modelo_dir)
    restorations = _edition_delta_order_restoration.declared_order_restorations(modelo_dir)
    plan, works = _edition_delta_planning._plan(modelo_dir, definition)
    family_changes = any(finding.get("family") != CASILLAS_FAMILY for finding in before.unresolved_duplication)
    return _MigrationPreparation(
        registry_root, work_dir, modelo_id, modelo_dir, definition, before, restorations, plan, works, family_changes
    )


def _needs_staging(preparation: _MigrationPreparation) -> bool:
    return bool(
        _casilla_changes(preparation.plan, preparation.before) or preparation.family_changes or preparation.restorations
    )


def _write_migration_works(
    preparation: _MigrationPreparation,
    staged: Path,
    plan: _edition_delta_types.MigrationPlan,
    works: Sequence[_edition_delta_source._EditionWork],
) -> None:
    casilla_changes = _casilla_changes(plan, preparation.before)
    for work in works:
        if casilla_changes and _edition_delta_writer._edition_changes(work):
            _edition_delta_writer._write_edition(
                staged / _edition_delta_fields._MODELOS / preparation.modelo_id / "revisions" / work.plan.revision_id,
                work,
            )


def _stage_migration(
    preparation: _MigrationPreparation,
    export_scenarios: Mapping[str, EditionExportScenario] | None,
) -> _StagedMigration:
    reference = copy_registry_tree(
        preparation.registry_root,
        _edition_delta_workdir._scratch_path(preparation.work_dir, "reference", "registry", "aeat"),
        modelo_id=preparation.modelo_id,
    )
    declared, reordered = _edition_delta_order_restoration._stage_declared_order(
        registry_root=preparation.registry_root,
        modelo_id=preparation.modelo_id,
        work_dir=preparation.work_dir,
        reference=reference,
        restorations=preparation.restorations,
    )
    plan, works = preparation.plan, preparation.works
    if preparation.restorations:
        declared_modelo = declared / _edition_delta_fields._MODELOS / preparation.modelo_id
        plan, works = _edition_delta_planning._plan(
            declared_modelo, _edition_delta_workdir._load(declared, preparation.modelo_id)
        )
    staged = copy_registry_tree(
        declared,
        _edition_delta_workdir._scratch_path(preparation.work_dir, "migrated", "registry", "aeat"),
        modelo_id=preparation.modelo_id,
    )
    _write_migration_works(preparation, staged, plan, works)
    staged_modelo = staged / _edition_delta_fields._MODELOS / preparation.modelo_id
    collapse_keyed_families(declared / _edition_delta_fields._MODELOS / preparation.modelo_id, staged_modelo)
    _edition_delta_override_pruning.prune_redundant_override_leaves(staged_modelo)
    report = edition_round_trip_report(
        live_registry_root=staged,
        reference_registry_root=declared,
        modelo_id=preparation.modelo_id,
        export_scenarios=export_scenarios or {},
    )
    if plan.already_delta_authored:
        report = _edition_delta_equivalence._prove_chain(
            reference_modelo_dir=declared / _edition_delta_fields._MODELOS / preparation.modelo_id,
            staged_modelo_dir=staged_modelo,
            revision_ids=tuple(edition.revision_id for edition in plan.editions),
            report=report,
        )
    return _StagedMigration(reference, declared, reordered, staged, plan, report)


def _publish_clean_migration(preparation: _MigrationPreparation, staged: _StagedMigration, apply: bool) -> bool:
    has_source_findings = any(
        _edition_delta_assessment._is_source_finding(finding) for finding in staged.report.findings
    )
    if not apply or has_source_findings:
        return False
    _edition_delta_source_publication._assert_proof_inputs_unchanged(
        live_root=preparation.registry_root, captured_root=staged.reference, modelo_id=preparation.modelo_id
    )
    _edition_delta_source_publication._apply_proven_modelo(
        target=preparation.modelo_dir.resolve(),
        staged=staged.staged / _edition_delta_fields._MODELOS / preparation.modelo_id,
        original=staged.reference / _edition_delta_fields._MODELOS / preparation.modelo_id,
    )
    return True


def _unchanged_migration(preparation: _MigrationPreparation) -> MigrationOutcome:
    return MigrationOutcome(
        plan=preparation.plan,
        staged_registry=None,
        report=None,
        applied=False,
        changed=False,
        before_assessment=preparation.before,
        after_assessment=preparation.before,
    )


def migrate_modelo(
    *,
    registry_root: Path,
    modelo_id: str,
    work_dir: Path,
    export_scenarios: Mapping[str, EditionExportScenario] | None = None,
    apply: bool = False,
) -> MigrationOutcome:
    """Plan, stage and prove one modelo's migration; publish it only when the gate reports nothing.

    ``work_dir`` must not exist and must be outside both ``registry_root`` and
    the production ``src`` tree. The unmigrated reference, staged migration,
    and any displaced target are written beneath it and left for inspection.

    A modelo that already names predecessors is lifted in place and proven
    against its chain: the staged tree must materialise to the same bytes, and
    hold the same members in the same order, as the tree it was planned from.
    That tree is the live one in the order its declarations give: where an
    edition states every member of a family it also inherits, the positions
    keeping that stated order are written first and proven to move members
    only (:func:`declared_order_restorations`).

    Raises:
        MigrationRefusedError: When the migration cannot be planned or written,
            or a lift in place does not materialise identically.
    """
    preparation = _prepare_migration(registry_root, modelo_id, work_dir)
    if not _needs_staging(preparation):
        return _unchanged_migration(preparation)
    staged = _stage_migration(preparation, export_scenarios)
    applied = _publish_clean_migration(preparation, staged, apply)
    assessed_dir = preparation.modelo_dir if applied else staged.staged / _edition_delta_fields._MODELOS / modelo_id
    changed = (
        preparation.before.fingerprint != _edition_delta_assessment.assess_migration_state(assessed_dir).fingerprint
    )
    return MigrationOutcome(
        plan=staged.plan,
        staged_registry=staged.staged,
        report=staged.report,
        applied=applied,
        changed=changed,
        before_assessment=preparation.before,
        after_assessment=_edition_delta_assessment.assess_migration_state(assessed_dir),
        order_restorations=preparation.restorations,
        reordered_families=staged.reordered,
    )


def _casilla_changes(
    plan: _edition_delta_types.MigrationPlan, assessment: _edition_delta_assessment.MigrationAssessment
) -> bool:
    """Whether the casilla pass has anything to write: a lift, or restated casilla payload."""
    return any(edition.lifted.total() for edition in plan.editions) or any(
        finding.get("family") == CASILLAS_FAMILY for finding in assessment.unresolved_duplication
    )


# ── reporting ───────────────────────────────────────────────────────────────


def _measurement_line(
    before: _edition_delta_assessment.MigrationAssessment,
    after: _edition_delta_assessment.MigrationAssessment,
) -> str:
    return (
        f"measurement before_fingerprint={before.fingerprint} after_fingerprint={after.fingerprint} "
        f"physical_bytes={before.physical_bytes}->{after.physical_bytes} "
        f"authored_payload_fields={before.authored_payload_fields}->{after.authored_payload_fields} "
        f"inherited_payload_fields={before.inherited_payload_fields}->{after.inherited_payload_fields} "
        f"genuine_overrides={after.genuine_overrides} redundant_overrides={after.redundant_overrides} "
        f"additions={after.additions} removals={after.removals} structural_overhead={after.structural_overhead} "
        f"unresolved_duplication={len(after.unresolved_duplication)} blocked_work={len(after.blocked_work)}"
    )


def _edition_lines(outcome: MigrationOutcome) -> list[str]:
    lines: list[str] = []
    for edition in outcome.plan.editions:
        kept = " ".join(f"{reason}={count}" for reason, count in edition.kept.items())
        lines.append(
            f"edition modelo={outcome.plan.modelo_id} revision={edition.revision_id} basis={edition.basis} "
            f"predecessor={edition.predecessor} dependencies={','.join(edition.dependencies) or '-'} "
            f"blocked={','.join(edition.blocked) or '-'} blocked_detail={json.dumps(edition.blocked_detail)} "
            f"rows_before={edition.rows_before} stated_after={len(edition.stated_ids)} "
            f"inherited={len(edition.inherited_ids)} lifted_row_source_refs={edition.lifted.row_source_refs} "
            f"lifted_constraint_source_refs={edition.lifted.constraint_source_refs} "
            f"lifted_row_orden_legal_refs={edition.lifted.row_orden_legal_refs} "
            f"lifted_constraint_orden_legal_refs={edition.lifted.constraint_orden_legal_refs} "
            f"source_default={json.dumps(list(edition.source_default) if edition.source_default else None)} "
            f"reviewed_against={edition.reviewed_against} comments_dropped={edition.comments_dropped} {kept}".rstrip()
        )
        lines.extend(f"not_exact revision={edition.revision_id} {detail}" for detail in edition.not_exact)
    return lines


def _report_summary_line(outcome: MigrationOutcome) -> str:
    report = outcome.report
    if report is None:
        raise RuntimeError("a gate summary requires a report")
    compared = ",".join(report.byte_compared_revisions) or "-"
    return (
        f"summary changed={outcome.changed} gate_findings={len(report.findings)} "
        f"byte_compared={compared} applied={outcome.applied} complete={outcome.complete} "
        f"equivalence_status={outcome.equivalence_status} compaction_status={outcome.compaction_status} "
        f"minimality_status={outcome.minimality_status} application_status={outcome.application_status} "
        f"source_status={outcome.source_status} "
        f"publication_readiness_status={outcome.publication_readiness_status} "
        f"publication_execution_status={outcome.publication_execution_status} "
        f"completed={','.join(outcome.completed) or '-'} unchanged={','.join(outcome.unchanged) or '-'} "
        f"blocked={','.join(outcome.blocked) or '-'} staged={outcome.staged_registry}"
    )


def _unchanged_summary_line(outcome: MigrationOutcome) -> str:
    return (
        f"summary changed={outcome.changed} applied={outcome.applied} complete={outcome.complete} "
        f"equivalence_status={outcome.equivalence_status} compaction_status={outcome.compaction_status} "
        f"minimality_status={outcome.minimality_status} application_status={outcome.application_status} "
        f"source_status={outcome.source_status} "
        f"publication_readiness_status={outcome.publication_readiness_status} "
        f"publication_execution_status={outcome.publication_execution_status} "
        f"completed={','.join(outcome.completed) or '-'} unchanged={','.join(outcome.unchanged) or '-'} "
        f"blocked={','.join(outcome.blocked) or '-'}"
    )


def render_outcome(outcome: MigrationOutcome) -> str:
    """Return one greppable line per edition, one per gate finding, and a closing summary."""
    lines: list[str] = []
    if outcome.before_assessment is not None and outcome.after_assessment is not None:
        lines.append(_measurement_line(outcome.before_assessment, outcome.after_assessment))
    lines.extend(_edition_lines(outcome))
    lines.extend(
        _edition_delta_order_restoration._order_lines(
            outcome.plan.modelo_id, outcome.order_restorations, outcome.reordered_families
        )
    )
    if outcome.report is not None:
        lines.extend(
            f"gate kind={finding.kind} revision={finding.revision_id} detail={finding.detail!r}"
            for finding in outcome.report.findings
        )
        lines.append(_report_summary_line(outcome))
    else:
        lines.append(_unchanged_summary_line(outcome))
    return "\n".join(lines) + "\n"


def _render(outcome: MigrationOutcome | _edition_delta_drop_types.DropOutcome) -> str:
    """Render whichever outcome the invoked operation produced."""
    return (
        _edition_delta_drop_reporting.render_drop_outcome(outcome)
        if isinstance(outcome, _edition_delta_drop_types.DropOutcome)
        else render_outcome(outcome)
    )


def persist_migration_report(
    repository: Path,
    outcome: MigrationOutcome | _edition_delta_drop_types.DropOutcome,
    command: Sequence[str],
) -> Path:
    """Persist one rendered migration outcome under the canonical audit log hierarchy.

    ``allocate_run_directory`` supplies a date, process, and UUID identity;
    creating that directory without ``exist_ok`` preserves earlier evidence if
    two invocations ever receive the same generated name. The returned
    ``report.md`` is the human-readable authority; ``report.json`` carries the
    same rendered text and command for mechanical consumers. Neither path is
    derived from the caller's scratch directory.
    """
    run_dir = allocate_run_directory(
        repository.resolve(), family=_edition_delta_fields._REPORT_FAMILY, label=_edition_delta_fields._REPORT_LABEL
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    rendered = _render(outcome)
    report_path = run_dir / "report.md"
    report_path.write_text(
        f"command: {' '.join(command)}\n\n{rendered}",
        encoding="utf-8",
        newline="\n",
    )
    machine: dict[str, object] = {
        "command": list(command),
        "report": rendered,
        "source_migration": outcome.source_status,
        "publication_readiness": outcome.publication_readiness_status,
        "publication_execution": outcome.publication_execution_status,
        "order_restorations": [asdict(item) for item in outcome.order_restorations],
        "reordered_families": [list(item) for item in outcome.reordered_families],
    }
    if isinstance(outcome, MigrationOutcome):
        machine["outcomes"] = {
            "completed": list(outcome.completed),
            "unchanged": list(outcome.unchanged),
            "blocked": {revision: list(details) for revision, details in outcome.blocked.items()},
            "complete": outcome.complete,
            "applied": outcome.applied,
            "equivalence": outcome.equivalence_status,
            "compaction": outcome.compaction_status,
            "minimality": outcome.minimality_status,
            "application": outcome.application_status,
        }
        machine["measurements"] = {
            "before": asdict(outcome.before_assessment) if outcome.before_assessment is not None else None,
            "after": asdict(outcome.after_assessment) if outcome.after_assessment is not None else None,
        }
    (run_dir / "report.json").write_text(
        json.dumps(
            machine,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report_path


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, required=True, help="registry root holding modelos/")
    parser.add_argument("--modelo", required=True, help="modelo id, for example 303")
    parser.add_argument("--work-dir", type=Path, required=True, help="new directory for the reference and staging")
    parser.add_argument(
        "--drop-restatement",
        action="store_true",
        help="drop members that restate exactly what the edition inherits, instead of migrating",
    )
    parser.add_argument(
        "--family",
        action="append",
        metavar="SECTION",
        help="limit --drop-restatement to this family; repeatable, defaults to every accepted family",
    )
    parser.add_argument("--apply", action="store_true", help="publish the staged modelo when the gate is clean")
    parser.add_argument(
        "--accepted-modelo-dir",
        type=Path,
        help="accepted modelo source snapshot for an independent retained-casilla order check before staging",
    )
    parser.add_argument(
        "--rename-casilla",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="explicit one-to-one identity rename for --accepted-modelo-dir; repeatable",
    )
    return parser


def _validate_cli_scope(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> None:
    if arguments.family and not arguments.drop_restatement:
        parser.error("--family only applies to --drop-restatement")
    if arguments.rename_casilla and arguments.accepted_modelo_dir is None:
        parser.error("--rename-casilla requires --accepted-modelo-dir")


def _rename_pairs(values: Sequence[str]) -> list[tuple[str, str]]:
    renames: list[tuple[str, str]] = []
    for value in values:
        old, separator, new = value.partition("=")
        if not separator or not old or not new or "=" in new:
            raise ValueError(f"invalid casilla rename {value!r}; expected OLD=NEW")
        renames.append((old, new))
    return renames


def _review_accepted_source(arguments: argparse.Namespace) -> bool:
    if arguments.accepted_modelo_dir is None:
        return True
    try:
        order_review = review_casilla_order(
            arguments.accepted_modelo_dir,
            arguments.registry_root / _edition_delta_fields._MODELOS / arguments.modelo,
            renames=_rename_pairs(arguments.rename_casilla),
        )
    except (RegistryError, ValueError) as exc:
        sys.stderr.write(f"accepted-source order review refused: {exc}\n")
        return False
    sys.stdout.write(render_casilla_order_review(order_review) + "\n")
    if order_review.passed:
        return True
    sys.stderr.write(f"accepted-source order review refused: {order_review.status}\n")
    return False


def _execute_cli_operation(arguments: argparse.Namespace) -> MigrationOutcome | _edition_delta_drop_types.DropOutcome:
    export_scenarios = edition_export_scenarios(arguments.modelo, registry_root=arguments.registry_root)
    if arguments.drop_restatement:
        return _edition_delta_drop.drop_restatement(
            registry_root=arguments.registry_root,
            modelo_id=arguments.modelo,
            work_dir=arguments.work_dir,
            sections=arguments.family,
            export_scenarios=export_scenarios,
            apply=arguments.apply,
        )
    return migrate_modelo(
        registry_root=arguments.registry_root,
        modelo_id=arguments.modelo,
        work_dir=arguments.work_dir,
        export_scenarios=export_scenarios,
        apply=arguments.apply,
    )


def _cli_exit_code(outcome: MigrationOutcome | _edition_delta_drop_types.DropOutcome) -> int:
    if outcome.source_findings:
        return 1
    return int(isinstance(outcome, MigrationOutcome) and not outcome.complete)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the migration; exit 0 when the staged tree round-trips clean or nothing changes, 1 otherwise."""
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    _validate_cli_scope(parser, arguments)
    if not _review_accepted_source(arguments):
        return 1
    try:
        outcome = _execute_cli_operation(arguments)
    except _edition_delta_errors.MigrationRefusedError as exc:
        sys.stderr.write(f"refused: {exc}\n")
        return 1
    command = tuple(sys.argv) if argv is None else (sys.argv[0], *argv)
    report_path = persist_migration_report(test_log_root(), outcome, command)
    sys.stdout.write(_render(outcome))
    sys.stdout.write(f"report persisted to {report_path}\n")
    return _cli_exit_code(outcome)


if __name__ == "__main__":
    raise SystemExit(main())
