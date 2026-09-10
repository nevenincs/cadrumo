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
  sequence) or the successor declares a lower authority grade (it withholds by
  design and must stay full-copy). A predecessor an edition already declares is
  kept as declared.
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
- **Drops rows identical to the inherited row.** A row is dropped when the
  delta-minimality screen finds no difference between it and inheriting the
  predecessor's row of the same lineage (``restatement_differences``) *and*
  the row the loader would materialise in its place - the predecessor's raw
  row without its lineage claims, defaulted from this edition and with its
  formula and binding references resolved through lineage - equals this
  edition's row exactly. The second condition is needed because the screen
  compares normalised loaded values, and a row dropped on its word alone could
  inherit a raw shape, such as a full ``source_refs``, that materialises
  differently.
- **Keeps** every changed and new row, stated in full, and every row stating
  ``continuidad_origin`` or ``continuidad_evidence``, which an inherited row
  never carries.
- **Reorders** the edition once, into the order the merge defines: inherited
  rows in the predecessor's materialised order, superseding rows in place, new
  rows after them in stated order.
- **Writes** the delta: the dropped rows' blocks are removed from their
  fragments, each fragment is renamed to the span it still declares, and the
  manifest gains ``predecessor``, ``casilla_source_refs`` and, on a reviewed
  edition, ``reviewed_against``.

An edition the materialiser cannot reproduce exactly is **blocked** and stays a
full copy with its restatement lifted. The causes are closed: an overlapping or
lower-grade predecessor; renamed fragments that would state the new rows out of
their full-copy order, which the merge would then keep; a predecessor lineage
the successor omits without a ``retired`` evolution; a predecessor row carrying
no lineage; a lineage carried twice; or a stated row colliding with an
inherited row of another lineage. Because a modelo whose editions name predecessors admits one
key-less root only, a blocked edition other than the first needs an explicit
no-predecessor declaration. That declaration is a claim about the form, so the
tool refuses to write one unless ``--declare-blocked-roots`` is passed, and then
cites the edition's own first legal and source reference and names the cause.

Proof and publication. The migration is written into a staging copy of the
registry and compared with the unmigrated modelo through the round-trip gate:
typed equality of every edition, casilla row order against the merge order,
locale identity, and export bytes for each edition an export scenario is given
for. The staged tree must
carry ``reviewed_against`` on a reviewed delta edition or it does not load, so
the carry-forward is decided at publication: ``--apply`` replaces the modelo in
the target registry only when the gate reports nothing at all, including no
edition whose export bytes went unchecked. Without ``--apply`` nothing outside
the work directory is written.

Determinism and idempotency. Every choice is a function of the input tree, taken
in sorted or validity order, so two runs over the same tree write the same
bytes. A modelo that already names predecessors is re-planned from its
materialised editions; when the plan reproduces what is on disk the run is a
no-op, and when it would change anything the run is refused, because a
delta-authored tree has no full-copy form left to prove a further change
against.

Where it stops:

- Casilla declarations only. Formulas, bindings, layouts and every other family,
  including the completeness manifest, stay declared in full by every edition.
- It never authors a retirement, a repurpose, or lineage; it reads them.
- Label text is not rewritten. Locale keys are edition-scoped and the loader
  gives an inherited row its origin edition's key as a fallback.
- An edition whose export surface has no scenario is reported unchecked by the
  gate, which blocks ``--apply``; the typed, order and locale proofs still run.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.authority_grade import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev.registry.compiler.edition_materialisation import materialise_edition
from cadrumo.domain.calculations.registry.identifier_lineage import identifier_lineage
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.tests.test_revision_edition_round_trip import (
    EditionExportScenario,
    RoundTripReport,
    RowKey,
    copy_registry_tree,
    edition_round_trip_report,
    merge_order,
)
from dev.registry.compiler.authority import compile_validated_authority

from .analysis.delta_minimality import restatement_differences

__all__ = [
    "BlockedCause",
    "EditionPlan",
    "KeptReason",
    "LiftCounts",
    "MigrationOutcome",
    "MigrationPlan",
    "MigrationRefusedError",
    "PredecessorBasis",
    "main",
    "migrate_modelo",
    "plan_migration",
    "render_outcome",
]

_MODELOS: Final = "modelos"
_CASILLAS: Final = "casillas"
_MANIFEST: Final = "revision.toml"
_ROW_SOURCE: Final = "source_refs"
_ROW_SOURCE_ADDITIONS: Final = "additional_source_refs"
_ROW_LEGAL: Final = "legal_refs"
_LINEAGE_CLAIMS: Final = frozenset({"continuidad_origin", "continuidad_evidence"})
_CONSTRAINTS: Final = "constraints"
_LINEAGE: Final = "continuidad_id"
_REFERENCE_SECTIONS: Final[Mapping[str, str]] = {
    "formula": "formulas",
    "binding": "bindings",
    "alternate_bindings": "bindings",
}
_PENDING_REVIEW: Final = "pending_review"
_RETIRED: Final = "retired"
_REVISION_SEGMENT: Final = r'(?:"[^"\n]+"|[^".\]\n]+)'
_ROW_HEADER: Final = re.compile(rf"^\[\[revisions\.{_REVISION_SEGMENT}\.casillas\]\]\s*$")
_CONSTRAINTS_HEADER: Final = re.compile(rf"^\[revisions\.{_REVISION_SEGMENT}\.casillas\.constraints\]\s*$")
_FILENAME_SUBSTITUTIONS: Final[Mapping[str, str]] = {":": "+"}
_TOML_ESCAPES: Final[Mapping[str, str]] = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


class MigrationRefusedError(RuntimeError):
    """The modelo cannot be migrated as asked, and nothing was written outside the work directory."""


class PredecessorBasis(StrEnum):
    """How an edition's predecessor declaration was decided."""

    FIRST = "first"
    ADJACENT = "adjacent"
    DECLARED = "declared"
    DECLARED_ROOT = "declared_root"
    BLOCKED = "blocked"


class BlockedCause(StrEnum):
    """Why an edition cannot be delta-authored exactly against its adjacent earlier edition."""

    OVERLAPPING_PREDECESSOR = "overlapping_predecessor"
    LOWER_GRADE = "lower_grade"
    #: Renamed fragments would state the edition's new rows out of their full-copy order.
    ROW_ORDER = "row_order"
    UNRETIRED_WITHDRAWAL = "unretired_withdrawal"
    PREDECESSOR_ROW_WITHOUT_LINEAGE = "predecessor_row_without_lineage"
    AMBIGUOUS_LINEAGE = "ambiguous_lineage"
    UNDECLARED_REPURPOSE = "undeclared_repurpose"


class KeptReason(StrEnum):
    """Why a row of a delta edition stays stated."""

    NEW_LINEAGE = "new_lineage"
    DIFFERS = "differs"
    NOT_EXACT = "screen_identical_not_exact"


type _Row = dict[str, object]
type _Declarations = Mapping[str, Mapping[str, tuple[str, ...]]]


@dataclass(frozen=True, slots=True)
class LiftCounts:
    """How many restated references an edition stops stating."""

    row_source_refs: int = 0
    constraint_source_refs: int = 0
    row_orden_legal_refs: int = 0
    constraint_orden_legal_refs: int = 0

    def total(self) -> int:
        """Return the number of lifted references of every kind."""
        return (
            self.row_source_refs
            + self.constraint_source_refs
            + self.row_orden_legal_refs
            + self.constraint_orden_legal_refs
        )


@dataclass(frozen=True, slots=True)
class EditionPlan:
    """What the migration writes for one edition, and the counts that justify it."""

    revision_id: str
    basis: PredecessorBasis
    predecessor: str | None
    blocked: tuple[BlockedCause, ...]
    source_default: tuple[str, ...] | None
    source_default_withheld: str | None
    rows_before: int
    stated_ids: tuple[str, ...]
    inherited_ids: tuple[str, ...]
    lifted: LiftCounts
    kept: Mapping[KeptReason, int]
    not_exact: tuple[str, ...]
    comments_dropped: int
    reviewed_against: str | None

    @property
    def is_delta(self) -> bool:
        """Whether the edition names a predecessor after migration."""
        return self.predecessor is not None and self.basis in {PredecessorBasis.ADJACENT, PredecessorBasis.DECLARED}


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """Every edition's plan for one modelo, in validity order."""

    modelo_id: str
    editions: tuple[EditionPlan, ...]
    already_delta_authored: bool

    def blocked_roots(self) -> tuple[str, ...]:
        """Return the editions that need an explicit no-predecessor declaration to stay full-copy."""
        return tuple(edition.revision_id for edition in self.editions if edition.basis is PredecessorBasis.BLOCKED)


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    """The plan, the gate's verdict on the staged tree, and whether the modelo was published."""

    plan: MigrationPlan
    staged_registry: Path | None
    report: RoundTripReport | None
    applied: bool
    changed: bool


# ── raw tree reading ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Block:
    """One casilla row as authored: its text, including any comment run directly above its header."""

    text: str
    row: _Row


@dataclass(frozen=True, slots=True)
class _Fragment:
    path: Path
    preamble: str
    blocks: tuple[_Block, ...]


@dataclass(frozen=True, slots=True)
class _EditionSource:
    revision_id: str
    manifest_text: str
    manifest: _Row
    fragments: tuple[_Fragment, ...]
    rows: tuple[_Row, ...]
    origins: tuple[str | None, ...]
    declarations: _Declarations
    retired: frozenset[str]

    def stated_rows(self) -> tuple[_Row, ...]:
        return tuple(block.row for fragment in self.fragments for block in fragment.blocks)


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_thaw(item) for item in value]
    return value


def _as_row(value: object) -> _Row:
    thawed = _thaw(value)
    if not isinstance(thawed, dict):
        raise MigrationRefusedError(f"expected a table, found {type(value).__name__}")
    return {str(key): item for key, item in thawed.items()}


def _split_blocks(text: str) -> tuple[str, list[str]]:
    """Split a fragment into its preamble and one text block per casilla row header."""
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    for index, line in enumerate(lines):
        if _ROW_HEADER.match(line.rstrip("\r\n")):
            start = index
            while start > 0 and lines[start - 1].lstrip().startswith("#") and (not starts or start - 1 > starts[-1]):
                start -= 1
            starts.append(start)
    if not starts:
        return text, []
    bounds = [*starts, len(lines)]
    blocks = ["".join(lines[bounds[index] : bounds[index + 1]]) for index in range(len(starts))]
    return "".join(lines[: starts[0]]), blocks


def _block_row(block: str) -> _Row:
    revisions = tomllib.loads(block).get("revisions")
    if not isinstance(revisions, dict) or len(revisions) != 1:
        raise MigrationRefusedError(f"casilla block does not declare exactly one revision:\n{block}")
    (revision,) = revisions.values()
    rows = revision.get(_CASILLAS) if isinstance(revision, dict) else None
    if not isinstance(rows, list) or len(rows) != 1:
        raise MigrationRefusedError(f"casilla block does not declare exactly one row:\n{block}")
    return _as_row(rows[0])


def _read_fragments(edition_dir: Path) -> tuple[_Fragment, ...]:
    fragments: list[_Fragment] = []
    for path in sorted((edition_dir / _CASILLAS).glob("*.toml")):
        preamble, texts = _split_blocks(path.read_text(encoding="utf-8"))
        fragments.append(_Fragment(path, preamble, tuple(_Block(text, _block_row(text)) for text in texts)))
    return tuple(fragments)


def _manifest_table(text: str, revision_id: str) -> _Row:
    revisions = tomllib.loads(text).get("revisions")
    if not isinstance(revisions, dict) or revision_id not in revisions:
        raise MigrationRefusedError(f"revision.toml does not declare [revisions.{revision_id!r}]")
    return _as_row(revisions[revision_id])


def _declarations(table: Mapping[str, object], revision_id: str) -> _Declarations:
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for section in sorted(set(_REFERENCE_SECTIONS.values())):
        by_lineage: dict[str, list[str]] = {}
        raw = table.get(section, ())
        for declaration in raw if isinstance(raw, list | tuple) else ():
            declaration_id = declaration.get("id") if isinstance(declaration, Mapping) else None
            if isinstance(declaration_id, str):
                by_lineage.setdefault(identifier_lineage(declaration_id, revision_id), []).append(declaration_id)
        result[section] = {lineage: tuple(ids) for lineage, ids in by_lineage.items()}
    return result


def _retired_lineages(table: Mapping[str, object], revision_id: str) -> frozenset[str]:
    raw = table.get("casilla_continuidad_evolutions", ())
    return frozenset(
        str(evolution[_LINEAGE])
        for evolution in (raw if isinstance(raw, list | tuple) else ())
        if isinstance(evolution, Mapping)
        and evolution.get("evolution_kind") == _RETIRED
        and evolution.get("to_revision") == revision_id
        and isinstance(evolution.get(_LINEAGE), str)
    )


def _read_edition(modelo_dir: Path, revision_id: str) -> _EditionSource:
    edition_dir = modelo_dir / "revisions" / revision_id
    manifest_text = (edition_dir / _MANIFEST).read_text(encoding="utf-8")
    materialised = materialise_edition(modelo_dir, revision_id)
    raw_rows = materialised.table.get(_CASILLAS, ())
    rows = tuple(_as_row(row) for row in (raw_rows if isinstance(raw_rows, list | tuple) else ()))
    origins = materialised.label_origins or tuple(None for _ in rows)
    return _EditionSource(
        revision_id=revision_id,
        manifest_text=manifest_text,
        manifest=_manifest_table(manifest_text, revision_id),
        fragments=_read_fragments(edition_dir),
        rows=rows,
        origins=origins,
        declarations=_declarations(materialised.table, revision_id),
        retired=_retired_lineages(materialised.table, revision_id),
    )


# ── the loader's semantics, reproduced for a delta that is not written yet ──


@dataclass(frozen=True, slots=True)
class _Defaults:
    source_refs: tuple[str, ...] | None
    orden: tuple[str, ...]


def _manifest_defaults(manifest: Mapping[str, object]) -> _Defaults:
    source = manifest.get("casilla_source_refs")
    orden = manifest.get("orden_aplicabilidad", ())
    return _Defaults(
        source_refs=tuple(str(item) for item in source) if isinstance(source, list) and source else None,
        orden=tuple(str(item) for item in orden) if isinstance(orden, list) else (),
    )


def _defaulted(table: _Row, defaults: _Defaults) -> _Row:
    filled = dict(table)
    additions = filled.pop(_ROW_SOURCE_ADDITIONS, None)
    if additions is not None:
        if not defaults.source_refs or _ROW_SOURCE in filled or not isinstance(additions, list) or not additions:
            raise MigrationRefusedError(f"casilla {table.get('id')!r} states additions the loader would refuse")
        filled[_ROW_SOURCE] = list(dict.fromkeys((*defaults.source_refs, *(str(item) for item in additions))))
    elif defaults.source_refs and _ROW_SOURCE not in filled:
        filled[_ROW_SOURCE] = list(defaults.source_refs)
    if defaults.orden and _ROW_LEGAL not in filled:
        filled[_ROW_LEGAL] = list(defaults.orden)
    return filled


def _without_lineage_claims(row: _Row) -> _Row:
    """The row as an inheriting edition holds it: its claims about its predecessor never travel."""
    return {key: value for key, value in row.items() if key not in _LINEAGE_CLAIMS}


def _effective(
    row: _Row,
    *,
    origin: str | None,
    revision_id: str,
    defaults: _Defaults,
    declarations: _Declarations,
) -> _Row | None:
    """The row the loader builds typed construction from, or ``None`` when a reference cannot resolve.

    Defaults fill the row and its constraints table exactly as the loader's
    reference-default pass does; an inherited row's formula and binding
    references are resolved to this edition's declaration of the same lineage.
    """
    effective = _defaulted(row, defaults)
    constraints = effective.get(_CONSTRAINTS)
    if isinstance(constraints, dict):
        effective[_CONSTRAINTS] = _defaulted(constraints, defaults)
    if origin is None or origin == revision_id:
        return effective
    for name, section in _REFERENCE_SECTIONS.items():
        value = effective.get(name)
        if isinstance(value, str):
            resolved = _resolve(value, origin=origin, candidates=declarations.get(section, {}))
            if resolved is None:
                return None
            effective[name] = resolved
        elif isinstance(value, list):
            items: list[object] = []
            for item in value:
                resolved = (
                    _resolve(item, origin=origin, candidates=declarations.get(section, {}))
                    if isinstance(item, str)
                    else item
                )
                if resolved is None:
                    return None
                items.append(resolved)
            effective[name] = items
    return effective


def _resolve(reference: str, *, origin: str, candidates: Mapping[str, tuple[str, ...]]) -> str | None:
    found = candidates.get(identifier_lineage(reference, origin), ())
    return found[0] if len(found) == 1 else None


def _lineage(row: Mapping[str, object]) -> str | None:
    value = row.get(_LINEAGE)
    return value if isinstance(value, str) else None


def _row_id(row: Mapping[str, object]) -> str:
    return str(row["id"])


def _row_keys(rows: Sequence[Mapping[str, object]]) -> tuple[RowKey, ...]:
    return tuple((_row_id(row), _lineage(row)) for row in rows)


@dataclass(frozen=True, slots=True)
class _Placed:
    """One materialised row, the raw row the loader holds for it, and the edition that stated it."""

    row: _Row
    origin: str


def _merge(
    inherited: Sequence[_Placed],
    stated: Sequence[_Row],
    *,
    revision_id: str,
    retired: frozenset[str],
) -> tuple[list[_Placed], BlockedCause | None]:
    """Reproduce the loader's casilla merge; return the rows, or the cause it would refuse with."""
    stated_by_lineage: dict[str, _Row] = {}
    for row in stated:
        lineage = _lineage(row)
        if lineage is None:
            continue
        if lineage in stated_by_lineage or lineage in retired:
            return [], BlockedCause.AMBIGUOUS_LINEAGE
        stated_by_lineage[lineage] = row
    inherited_counts = Counter(lineage for placed in inherited if (lineage := _lineage(placed.row)) is not None)
    if any(inherited_counts[lineage] > 1 for lineage in stated_by_lineage):
        return [], BlockedCause.AMBIGUOUS_LINEAGE
    merged: list[_Placed] = []
    kept_ids: dict[str, str | None] = {}
    superseded: set[str] = set()
    for placed in inherited:
        lineage = _lineage(placed.row)
        if lineage is not None and lineage in retired:
            continue
        if lineage is not None and lineage in stated_by_lineage:
            merged.append(_Placed(stated_by_lineage[lineage], revision_id))
            superseded.add(lineage)
            continue
        merged.append(_Placed(_without_lineage_claims(placed.row), placed.origin))
        kept_ids[_row_id(placed.row)] = lineage
    for row in stated:
        lineage = _lineage(row)
        if _row_id(row) in kept_ids:
            return [], BlockedCause.UNDECLARED_REPURPOSE
        if lineage is None or lineage not in superseded:
            merged.append(_Placed(row, revision_id))
    return merged, None


# ── restatement lifting ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _TableLift:
    """What lifting removes from one row or constraints table, and the additions it states instead."""

    removed: frozenset[str] = frozenset()
    additions: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class _Lift:
    """One row's lifted form and what the lift changes in the row and in its constraints table."""

    row: _Row
    row_lift: _TableLift
    constraint_lift: _TableLift


def _source_refs(table: Mapping[str, object]) -> tuple[str, ...] | None:
    value = table.get(_ROW_SOURCE)
    return tuple(str(item) for item in value) if isinstance(value, list) else None


def _source_default(rows: Sequence[_Row]) -> tuple[tuple[str, ...] | None, str | None]:
    """The edition's shared leading ``source_refs`` run, or ``None`` and the reason none is declared.

    A run counts for a row only when the row's references open with it and
    repeat nothing, so the default followed by the rest reproduces them exactly.
    """
    constraints = [table for row in rows if isinstance(table := row.get(_CONSTRAINTS), dict)]
    if any(_ROW_SOURCE not in table for table in [*rows, *constraints]):
        return None, "a row or constraints table states no source_refs, so a default would add references to it"
    scores: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        refs = _source_refs(row)
        if refs and len(set(refs)) == len(refs):
            scores.update(refs[:length] for length in range(1, len(refs) + 1))
    if not scores or max(scores.values()) < 2:
        return None, "no leading source_refs run is shared by two rows"
    best = max(scores.values())
    longest = max(len(run) for run, score in scores.items() if score == best)
    candidates = sorted(run for run, score in scores.items() if score == best and len(run) == longest)
    if len(candidates) > 1:
        return None, f"{len(candidates)} leading source_refs runs of length {longest} tie at {best} rows"
    return candidates[0], None


def _table_lift(
    table: Mapping[str, object], *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]
) -> _TableLift:
    removed: set[str] = set()
    additions: tuple[str, ...] | None = None
    refs = _source_refs(table)
    if source_default is not None and refs is not None and refs[: len(source_default)] == source_default:
        rest = refs[len(source_default) :]
        if tuple(dict.fromkeys((*source_default, *rest))) == refs:
            removed.add(_ROW_SOURCE)
            additions = rest or None
    if orden and table.get(_ROW_LEGAL) == list(orden):
        removed.add(_ROW_LEGAL)
    return _TableLift(frozenset(removed), additions)


def _lifted_table(table: Mapping[str, object], lift: _TableLift) -> _Row:
    lifted = {key: value for key, value in table.items() if key not in lift.removed}
    if lift.additions is not None:
        lifted[_ROW_SOURCE_ADDITIONS] = list(lift.additions)
    return lifted


def _lift(row: _Row, *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]) -> _Lift:
    row_lift = _table_lift(row, source_default=source_default, orden=orden)
    lifted = _lifted_table(row, row_lift)
    constraint_lift = _TableLift()
    constraints = row.get(_CONSTRAINTS)
    if isinstance(constraints, dict):
        constraint_lift = _table_lift(constraints, source_default=source_default, orden=orden)
        lifted[_CONSTRAINTS] = _lifted_table(constraints, constraint_lift)
    return _Lift(lifted, row_lift, constraint_lift)


# ── planning ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _EditionWork:
    """An edition's plan together with what writing it needs."""

    plan: EditionPlan
    source: _EditionSource
    lifts: Mapping[str, _Lift]
    root_declaration: _Row | None


def _grade(manifest: Mapping[str, object]) -> RegistryAuthorityGrade:
    token = manifest.get("authority_grade")
    return RegistryAuthorityGrade(token) if isinstance(token, str) else UNDECLARED_REGISTRY_AUTHORITY_GRADE


def _stem(casilla_id: str) -> str:
    for hostile, safe in _FILENAME_SUBSTITUTIONS.items():
        casilla_id = casilla_id.replace(hostile, safe)
    return casilla_id


def _fragment_name(ids: Sequence[str]) -> str:
    first, last = _stem(ids[0]), _stem(ids[-1])
    return f"c{first}.toml" if len(ids) == 1 or first == last else f"c{first}__c{last}.toml"


def _stated_layout(source: _EditionSource, stated: frozenset[str]) -> list[tuple[str, list[_Block]]]:
    """The fragments that remain once only ``stated`` rows are kept, named and ordered as the loader reads them."""
    layout: list[tuple[str, list[_Block]]] = []
    for fragment in source.fragments:
        kept = [block for block in fragment.blocks if _row_id(block.row) in stated]
        if kept:
            layout.append((_fragment_name([_row_id(block.row) for block in kept]), kept))
    names = [name for name, _ in layout]
    duplicated = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicated:
        raise MigrationRefusedError(f"edition {source.revision_id!r}: fragments would share the names {duplicated!r}")
    return sorted(layout, key=lambda item: item[0])


def _root_declaration(source: _EditionSource, causes: Sequence[BlockedCause]) -> _Row:
    legal, sources = source.manifest.get("legal_refs"), source.manifest.get("source_refs")
    if not (isinstance(legal, list) and legal and isinstance(sources, list) and sources):
        raise MigrationRefusedError(
            f"edition {source.revision_id!r} cites no legal and source reference to ground a root"
        )
    reason = (
        "Stated in full: this edition cannot be materialised exactly from the edition before it ("
        + ", ".join(cause.value.replace("_", " ") for cause in causes)
        + ")."
    )
    return {"none": {"reason": reason, "legal_refs": [str(legal[0])], "source_refs": [str(sources[0])]}}


def plan_migration(
    modelo_dir: Path,
    definition: ModeloDefinition,
    *,
    declare_blocked_roots: bool = False,
) -> MigrationPlan:
    """Decide every edition's predecessor, lifted defaults and stated rows, writing nothing.

    Raises:
        MigrationRefusedError: When an edition other than the first is blocked
            and ``declare_blocked_roots`` is not set.
    """
    return _plan(modelo_dir, definition, declare_blocked_roots=declare_blocked_roots)[0]


def _plan(
    modelo_dir: Path,
    definition: ModeloDefinition,
    *,
    declare_blocked_roots: bool,
) -> tuple[MigrationPlan, tuple[_EditionWork, ...]]:
    ordered = ordered_revisions(definition)
    sources = {str(revision.id): _read_edition(modelo_dir, str(revision.id)) for revision in ordered}
    already = any(
        key in source.manifest for source in sources.values() for key in ("predecessor", "casilla_source_refs")
    )
    materialised: dict[str, list[_Placed]] = {}
    work: list[_EditionWork] = []
    for position, revision in enumerate(ordered):
        revision_id = str(revision.id)
        source = sources[revision_id]
        full = [
            _effective(
                row,
                origin=origin,
                revision_id=revision_id,
                defaults=_manifest_defaults(source.manifest),
                declarations=source.declarations,
            )
            for row, origin in zip(source.rows, source.origins, strict=True)
        ]
        if any(row is None for row in full):
            raise MigrationRefusedError(f"edition {revision_id!r}: an inherited reference does not resolve on input")
        full_rows = [row for row in full if row is not None]
        source_default, withheld = _source_default(full_rows)
        orden = _manifest_defaults(source.manifest).orden
        lifts = {_row_id(row): _lift(row, source_default=source_default, orden=orden) for row in full_rows}
        new_defaults = _Defaults(source_refs=source_default, orden=orden)

        predecessor, basis, causes = _choose_predecessor(position, ordered, source)
        drops = set[str]()
        kept: Counter[KeptReason] = Counter()
        not_exact: list[str] = []
        if predecessor is not None and not causes:
            causes, drops, kept, not_exact = _choose_drops(
                definition=definition,
                revision_id=revision_id,
                predecessor=predecessor,
                inherited=materialised[predecessor],
                full_rows=full_rows,
                lifts=lifts,
                source=source,
                defaults=new_defaults,
            )
        stated_ids = frozenset(_row_id(row) for row in full_rows) - drops
        if causes:
            basis, drops, stated_ids = (
                PredecessorBasis.BLOCKED,
                set[str](),
                frozenset(_row_id(row) for row in full_rows),
            )
            kept = Counter[KeptReason]()
            not_exact = list[str]()
        if basis in {PredecessorBasis.FIRST, PredecessorBasis.DECLARED_ROOT, PredecessorBasis.BLOCKED}:
            materialised[revision_id] = [_Placed(lifts[_row_id(row)].row, revision_id) for row in full_rows]
        else:
            layout = _stated_layout(source, stated_ids)
            stated_rows = [lifts[_row_id(block.row)].row for _, blocks in layout for block in blocks]
            merged, _ = _merge(
                materialised[str(predecessor)], stated_rows, revision_id=revision_id, retired=source.retired
            )
            materialised[revision_id] = merged
        if basis is PredecessorBasis.BLOCKED and position > 0 and not declare_blocked_roots:
            raise MigrationRefusedError(
                f"edition {revision_id!r} is blocked ({', '.join(cause.value for cause in causes)}); keeping it "
                "full-copy needs an explicit no-predecessor declaration, which is a claim about the form; pass "
                "--declare-blocked-roots to write one citing the edition's own first legal and source reference",
            )
        is_delta = basis in {PredecessorBasis.ADJACENT, PredecessorBasis.DECLARED}
        review = source.manifest.get("review_status", _PENDING_REVIEW)
        plan = EditionPlan(
            revision_id=revision_id,
            basis=basis,
            predecessor=predecessor if is_delta else None,
            blocked=tuple(causes),
            source_default=source_default,
            source_default_withheld=withheld,
            rows_before=len(full_rows),
            stated_ids=tuple(_row_id(row) for row in full_rows if _row_id(row) in stated_ids),
            inherited_ids=tuple(_row_id(row) for row in full_rows if _row_id(row) not in stated_ids),
            lifted=_lift_counts(source, lifts, stated_ids),
            kept=dict(sorted(kept.items())),
            not_exact=tuple(not_exact),
            comments_dropped=sum(
                1
                for fragment in source.fragments
                for block in fragment.blocks
                if _row_id(block.row) not in stated_ids and block.text.lstrip().startswith("#")
            ),
            reviewed_against=predecessor if is_delta and review != _PENDING_REVIEW else None,
        )
        root = _root_declaration(source, causes) if basis is PredecessorBasis.BLOCKED and position > 0 else None
        work.append(_EditionWork(plan=plan, source=source, lifts=lifts, root_declaration=root))
    return (
        MigrationPlan(
            modelo_id=str(definition.id),
            editions=tuple(item.plan for item in work),
            already_delta_authored=already,
        ),
        tuple(work),
    )


def _lift_counts(source: _EditionSource, lifts: Mapping[str, _Lift], stated_ids: frozenset[str]) -> LiftCounts:
    """Count only the lifted keys the edition actually authors on the rows it keeps stating."""
    authored = {_row_id(row): row for row in source.stated_rows()}

    def count(key: str, *, constraint: bool) -> int:
        total = 0
        for row_id in stated_ids:
            row = authored.get(row_id, {})
            table = row.get(_CONSTRAINTS) if constraint else row
            keys = lifts[row_id].constraint_lift.removed if constraint else lifts[row_id].row_lift.removed
            total += key in keys and isinstance(table, dict) and key in table
        return total

    return LiftCounts(
        row_source_refs=count(_ROW_SOURCE, constraint=False),
        constraint_source_refs=count(_ROW_SOURCE, constraint=True),
        row_orden_legal_refs=count(_ROW_LEGAL, constraint=False),
        constraint_orden_legal_refs=count(_ROW_LEGAL, constraint=True),
    )


def _choose_predecessor(
    position: int,
    ordered: Sequence[ModeloRevision],
    source: _EditionSource,
) -> tuple[str | None, PredecessorBasis, list[BlockedCause]]:
    declared = source.manifest.get("predecessor")
    if isinstance(declared, str):
        return declared, PredecessorBasis.DECLARED, []
    if isinstance(declared, dict):
        return None, PredecessorBasis.DECLARED_ROOT, []
    if position == 0:
        return None, PredecessorBasis.FIRST, []
    earlier, current = ordered[position - 1], ordered[position]
    causes: list[BlockedCause] = []
    if revisions_overlap(earlier, current):
        causes.append(BlockedCause.OVERLAPPING_PREDECESSOR)
    ladder = tuple(RegistryAuthorityGrade)
    if ladder.index(_grade(source.manifest)) < ladder.index(_grade(_manifest_of(earlier))):
        causes.append(BlockedCause.LOWER_GRADE)
    return str(earlier.id), PredecessorBasis.ADJACENT, causes


def _manifest_of(revision: ModeloRevision) -> Mapping[str, object]:
    grade = revision.authority_grade
    return {} if grade is None else {"authority_grade": str(grade)}


def _choose_drops(
    *,
    definition: ModeloDefinition,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_Placed],
    full_rows: Sequence[_Row],
    lifts: Mapping[str, _Lift],
    source: _EditionSource,
    defaults: _Defaults,
) -> tuple[list[BlockedCause], set[str], Counter[KeptReason], list[str]]:
    causes: list[BlockedCause] = []
    if any(_lineage(placed.row) is None for placed in inherited):
        causes.append(BlockedCause.PREDECESSOR_ROW_WITHOUT_LINEAGE)
    stated_lineages = {_lineage(row) for row in full_rows}
    if any(
        (lineage := _lineage(placed.row)) is not None
        and lineage not in stated_lineages
        and lineage not in source.retired
        for placed in inherited
    ):
        causes.append(BlockedCause.UNRETIRED_WITHDRAWAL)
    if causes:
        return causes, set(), Counter(), []
    by_lineage: dict[str, list[_Placed]] = {}
    for placed in inherited:
        by_lineage.setdefault(str(_lineage(placed.row)), []).append(placed)
    revision = definition.revisions[revision_id]
    typed = {str(casilla.id): casilla for casilla in revision.casillas}
    predecessor_revision = definition.revisions[predecessor]
    typed_predecessor = {str(casilla.continuidad_id): casilla for casilla in predecessor_revision.casillas}
    drops = set[str]()
    kept: Counter[KeptReason] = Counter()
    not_exact: list[str] = []
    for row in full_rows:
        row_id, lineage = _row_id(row), _lineage(row)
        candidates = by_lineage.get(str(lineage), []) if lineage is not None else []
        if len(candidates) != 1 or lineage not in typed_predecessor:
            kept[KeptReason.NEW_LINEAGE] += 1
            continue
        if restatement_differences(typed[row_id], revision, typed_predecessor[lineage], predecessor_revision):
            kept[KeptReason.DIFFERS] += 1
            continue
        (candidate,) = candidates
        materialised = _effective(
            _without_lineage_claims(candidate.row),
            origin=candidate.origin,
            revision_id=revision_id,
            defaults=defaults,
            declarations=source.declarations,
        )
        if materialised != row:
            kept[KeptReason.NOT_EXACT] += 1
            differing = sorted(
                key
                for key in set(row) | set(materialised or {})
                if materialised is None or row.get(key) != materialised.get(key)
            )
            not_exact.append(f"{row_id}: {', '.join(differing) or 'unresolved reference'}")
            continue
        drops.add(row_id)
    stated = frozenset(_row_id(row) for row in full_rows) - drops
    layout = _stated_layout(source, stated)
    stated_rows = [lifts[_row_id(block.row)].row for _, blocks in layout for block in blocks]
    merged, refused = _merge(inherited, stated_rows, revision_id=revision_id, retired=source.retired)
    if refused is not None:
        return [refused], set(), Counter(), []
    expected = merge_order(_row_keys(full_rows), _row_keys([placed.row for placed in inherited]))
    if [_row_id(placed.row) for placed in merged] != [row_id for row_id, _ in expected]:
        return [BlockedCause.ROW_ORDER], set(), Counter(), []
    full_by_id = {_row_id(row): row for row in full_rows}
    for placed in merged:
        row = full_by_id[_row_id(placed.row)]
        effective = _effective(
            placed.row,
            origin=placed.origin,
            revision_id=revision_id,
            defaults=defaults,
            declarations=source.declarations,
        )
        if effective != row:
            raise MigrationRefusedError(
                f"edition {revision_id!r}: simulated casilla {_row_id(row)!r} does not reproduce the full copy",
            )
    return [], drops, kept, not_exact


# ── writing ─────────────────────────────────────────────────────────────────


def _toml_string(value: str) -> str:
    escaped = "".join(
        _TOML_ESCAPES.get(char, f"\\u{ord(char):04x}" if ord(char) < 0x20 or ord(char) == 0x7F else char)
        for char in value
    )
    return f'"{escaped}"'


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{key} = {_toml_value(item)}" for key, item in value.items()) + " }"
    raise MigrationRefusedError(f"cannot render {type(value).__name__} as a manifest value")


def _scan_depth(text: str, depth: int) -> int:
    """Return the bracket depth after ``text``, ignoring strings and comments."""
    index, quote = 0, ""
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 1
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            break
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        index += 1
    return depth


def _top_level_items(inline: str) -> list[str]:
    """Split the inside of an inline table at its top-level commas, keeping each item's text."""
    items: list[str] = []
    depth, quote, start, index = 0, "", 0, 0
    while index < len(inline):
        char = inline[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 1
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(inline[start:index])
            start = index + 1
        index += 1
    items.append(inline[start:])
    return [item for item in items if item.strip()]


def _additions_assignment(additions: tuple[str, ...]) -> str:
    return f"{_ROW_SOURCE_ADDITIONS} = {_toml_value(list(additions))}"


def _lifted_inline(line: str, lift: _TableLift) -> str:
    key, _, rest = line.partition("=")
    body = rest.strip()
    if not (body.startswith("{") and body.endswith("}")):
        raise MigrationRefusedError(f"constraints are neither a table nor a one-line inline table: {line!r}")
    kept: list[str] = []
    for item in (item.strip() for item in _top_level_items(body[1:-1])):
        name = item.partition("=")[0].strip()
        if name not in lift.removed:
            kept.append(item)
        elif name == _ROW_SOURCE and lift.additions is not None:
            kept.append(_additions_assignment(lift.additions))
    return f"{key.rstrip()} = {{ {', '.join(kept)} }}\n" if kept else f"{key.rstrip()} = {{}}\n"


def _key_of(line: str) -> str | None:
    match = re.match(r"^([A-Za-z0-9_-]+)\s*=", line)
    return str(match.group(1)) if match else None


def _lifted_text(block: _Block, lift: _Lift) -> str:
    """Remove the lifted keys from a row block's text, stating additions in their place, verified by re-parsing."""
    if not lift.row_lift.removed and not lift.constraint_lift.removed:
        return block.text
    lines = block.text.splitlines(keepends=True)
    out: list[str] = []
    scope, index = "comment", 0
    while index < len(lines):
        line = lines[index]
        stripped = line.rstrip("\r\n")
        if _ROW_HEADER.match(stripped):
            scope = "row"
        elif _CONSTRAINTS_HEADER.match(stripped):
            scope = "constraints"
        elif stripped.startswith("["):
            scope = "other"
        key = _key_of(line)
        table_lift = lift.row_lift if scope == "row" else lift.constraint_lift if scope == "constraints" else None
        if table_lift is not None and key is not None and key in table_lift.removed:
            depth = _scan_depth(line.partition("=")[2], 0)
            while depth > 0 and index + 1 < len(lines):
                index += 1
                depth = _scan_depth(lines[index], depth)
            if key == _ROW_SOURCE and table_lift.additions is not None:
                out.append(_additions_assignment(table_lift.additions) + "\n")
            index += 1
            continue
        if scope == "row" and key == _CONSTRAINTS and lift.constraint_lift.removed:
            line = _lifted_inline(line, lift.constraint_lift)
        out.append(line)
        index += 1
    text = "".join(out)
    if _block_row(text) != lift.row:
        raise MigrationRefusedError(f"lifting casilla {_row_id(block.row)!r} would change more than its lifted keys")
    return text


def _write_manifest(path: Path, work: _EditionWork) -> None:
    plan = work.plan
    additions: dict[str, object] = {}
    if plan.predecessor is not None and plan.basis is PredecessorBasis.ADJACENT:
        additions["predecessor"] = plan.predecessor
    if work.root_declaration is not None:
        additions["predecessor"] = work.root_declaration
    if plan.source_default is not None and "casilla_source_refs" not in work.source.manifest:
        additions["casilla_source_refs"] = list(plan.source_default)
    if plan.reviewed_against is not None and "reviewed_against" not in work.source.manifest:
        additions["reviewed_against"] = plan.reviewed_against
    if not additions:
        return
    text = work.source.manifest_text
    header = re.compile(
        rf'^\[revisions\.(?:"{re.escape(plan.revision_id)}"|{re.escape(plan.revision_id)})\][ \t]*\r?\n',
        re.MULTILINE,
    )
    match = header.search(text)
    if match is None:
        raise MigrationRefusedError(f"{path}: no [revisions.{plan.revision_id!r}] header to declare under")
    inserted = "".join(f"{key} = {_toml_value(value)}\n" for key, value in additions.items())
    rewritten = text[: match.end()] + inserted + text[match.end() :]
    if _manifest_table(rewritten, plan.revision_id) != {**work.source.manifest, **additions}:
        raise MigrationRefusedError(f"{path}: declaring {sorted(additions)!r} would change other manifest keys")
    path.write_text(rewritten, encoding="utf-8", newline="\n")


def _write_edition(edition_dir: Path, work: _EditionWork) -> None:
    stated = frozenset(work.plan.stated_ids)
    layout = _stated_layout(work.source, stated)
    preambles = {
        _fragment_name([_row_id(block.row) for block in fragment.blocks if _row_id(block.row) in stated]): (
            fragment.preamble
        )
        for fragment in work.source.fragments
        if any(_row_id(block.row) in stated for block in fragment.blocks)
    }
    casillas = edition_dir / _CASILLAS
    rendered = {
        name: preambles[name] + "".join(_lifted_text(block, work.lifts[_row_id(block.row)]) for block in blocks)
        for name, blocks in layout
    }
    originals = {fragment.path.name: fragment.path.read_text(encoding="utf-8") for fragment in work.source.fragments}
    for name in originals:
        if name not in rendered:
            (casillas / name).unlink()
    for name, text in rendered.items():
        if Path(name).name != name or not name.startswith("c"):
            raise MigrationRefusedError(f"refusing to write fragment name {name!r}")
        if originals.get(name) == text:
            continue
        (casillas / name).write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    if not any(casillas.iterdir()):
        casillas.rmdir()
    _write_manifest(edition_dir / _MANIFEST, work)


def _edition_changes(work: _EditionWork) -> bool:
    """Whether writing this edition's plan would change any byte of it."""
    plan = work.plan
    return bool(
        plan.inherited_ids
        or plan.lifted.total()
        or plan.basis is PredecessorBasis.ADJACENT
        or work.root_declaration is not None
        or (plan.source_default is not None and "casilla_source_refs" not in work.source.manifest)
    )


def _is_fixed_point(works: Sequence[_EditionWork]) -> bool:
    """Whether planning an already delta-authored tree reproduces exactly what each edition states and declares."""
    for work in works:
        plan, source = work.plan, work.source
        if plan.basis in {PredecessorBasis.ADJACENT, PredecessorBasis.BLOCKED}:
            return False
        current = {_row_id(row): row for row in source.stated_rows()}
        planned = {row_id: work.lifts[row_id].row for row_id in plan.stated_ids}
        if current != planned:
            return False
        declared_default = source.manifest.get("casilla_source_refs")
        if (list(plan.source_default) if plan.source_default else None) != declared_default:
            return False
        if plan.reviewed_against != source.manifest.get("reviewed_against"):
            return False
    return True


# ── the migration ───────────────────────────────────────────────────────────


def _load(registry_root: Path, modelo_id: str) -> ModeloDefinition:
    return compile_validated_authority(registry_root, bundled_path()).modelo(modelo_id)


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def migrate_modelo(
    *,
    registry_root: Path,
    modelo_id: str,
    work_dir: Path,
    declare_blocked_roots: bool = False,
    export_scenarios: Mapping[str, EditionExportScenario] | None = None,
    apply: bool = False,
) -> MigrationOutcome:
    """Plan, stage and prove one modelo's migration; publish it only when the gate reports nothing.

    ``work_dir`` must not exist; the unmigrated reference and the staged
    migration are written under it and left for inspection.

    Raises:
        MigrationRefusedError: When the migration cannot be planned or written,
            or ``apply`` is asked of a tree that is already delta-authored but
            not a fixed point.
    """
    if work_dir.exists():
        raise MigrationRefusedError(f"work directory {work_dir} already exists")
    modelo_dir = registry_root / _MODELOS / modelo_id
    if not modelo_dir.is_dir() or not _inside(modelo_dir, registry_root):
        raise MigrationRefusedError(f"{registry_root} holds no modelo {modelo_id!r}")
    definition = _load(registry_root, modelo_id)
    plan, works = _plan(modelo_dir, definition, declare_blocked_roots=declare_blocked_roots)
    if plan.already_delta_authored:
        if _is_fixed_point(works):
            return MigrationOutcome(plan=plan, staged_registry=None, report=None, applied=False, changed=False)
        raise MigrationRefusedError(
            f"modelo {modelo_id} already names predecessors and re-planning it would change it; a delta-authored "
            "tree has no full-copy form to prove a further change against",
        )
    if not any(_edition_changes(work) for work in works):
        return MigrationOutcome(plan=plan, staged_registry=None, report=None, applied=False, changed=False)
    reference = copy_registry_tree(registry_root, work_dir / "reference" / "registry" / "aeat", modelo_id=modelo_id)
    staged = copy_registry_tree(registry_root, work_dir / "migrated" / "registry" / "aeat", modelo_id=modelo_id)
    for work in works:
        _write_edition(staged / _MODELOS / modelo_id / "revisions" / work.plan.revision_id, work)
    report = edition_round_trip_report(
        live_registry_root=staged,
        reference_registry_root=reference,
        modelo_id=modelo_id,
        export_scenarios=export_scenarios or {},
    )
    applied = False
    if apply and not report.findings:
        target = modelo_dir.resolve()
        displaced = work_dir / "displaced" / modelo_id
        shutil.move(target, displaced)
        try:
            shutil.copytree(staged / _MODELOS / modelo_id, target)
        except OSError:
            if target.exists():
                shutil.rmtree(target)
            shutil.move(displaced, target)
            raise
        applied = True
    return MigrationOutcome(plan=plan, staged_registry=staged, report=report, applied=applied, changed=True)


# ── reporting ───────────────────────────────────────────────────────────────


def render_outcome(outcome: MigrationOutcome) -> str:
    """Return one greppable line per edition, one per gate finding, and a closing summary."""
    lines: list[str] = []
    for edition in outcome.plan.editions:
        kept = " ".join(f"{reason}={count}" for reason, count in edition.kept.items())
        lines.append(
            f"edition modelo={outcome.plan.modelo_id} revision={edition.revision_id} basis={edition.basis} "
            f"predecessor={edition.predecessor} blocked={','.join(edition.blocked) or '-'} "
            f"rows_before={edition.rows_before} stated_after={len(edition.stated_ids)} "
            f"inherited={len(edition.inherited_ids)} lifted_row_source_refs={edition.lifted.row_source_refs} "
            f"lifted_constraint_source_refs={edition.lifted.constraint_source_refs} "
            f"lifted_row_orden_legal_refs={edition.lifted.row_orden_legal_refs} "
            f"lifted_constraint_orden_legal_refs={edition.lifted.constraint_orden_legal_refs} "
            f"source_default={json.dumps(list(edition.source_default) if edition.source_default else None)} "
            f"reviewed_against={edition.reviewed_against} comments_dropped={edition.comments_dropped} {kept}".rstrip()
        )
        lines.extend(f"not_exact revision={edition.revision_id} {detail}" for detail in edition.not_exact)
    if outcome.report is not None:
        lines.extend(
            f"gate kind={finding.kind} revision={finding.revision_id} detail={finding.detail!r}"
            for finding in outcome.report.findings
        )
        compared = ",".join(outcome.report.byte_compared_revisions) or "-"
        lines.append(
            f"summary changed={outcome.changed} gate_findings={len(outcome.report.findings)} "
            f"byte_compared={compared} applied={outcome.applied} staged={outcome.staged_registry}"
        )
    else:
        lines.append(f"summary changed={outcome.changed} applied={outcome.applied}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the migration; exit 0 when the staged tree round-trips clean or nothing changes, 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, required=True, help="registry root holding modelos/")
    parser.add_argument("--modelo", required=True, help="modelo id, for example 303")
    parser.add_argument("--work-dir", type=Path, required=True, help="new directory for the reference and staging")
    parser.add_argument("--declare-blocked-roots", action="store_true", help="keep blocked editions full-copy")
    parser.add_argument("--apply", action="store_true", help="publish the staged modelo when the gate is clean")
    arguments = parser.parse_args(argv)
    try:
        outcome = migrate_modelo(
            registry_root=arguments.registry_root,
            modelo_id=arguments.modelo,
            work_dir=arguments.work_dir,
            declare_blocked_roots=arguments.declare_blocked_roots,
            apply=arguments.apply,
        )
    except MigrationRefusedError as exc:
        sys.stderr.write(f"refused: {exc}\n")
        return 1
    sys.stdout.write(render_outcome(outcome))
    if outcome.report is not None and outcome.report.findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
