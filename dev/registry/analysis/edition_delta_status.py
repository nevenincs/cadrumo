"""Screen: how far each modelo has moved from full-copy editions to delta authoring.

A modelo's editions are authored one of two ways. In the FULL-COPY shape every
edition states every casilla row itself, and each row restates the edition it
already sits in: ``source_refs`` naming that edition's diseno, ``legal_refs``
repeating the edition's own ``orden_aplicabilidad``, and formula and binding
identifiers carrying the edition key. The containing directory already names the
edition, so those tokens carry no information; they are what stops a copied row
from being recognisable as a copy. In the DELTA shape a successor edition names
its ``predecessor``, states only the rows that are new in it or that differ from
the row it would inherit, and lets the loader materialise the rest, while the
references it shares are declared once on the edition and inherited by the rows
that state none.

This screen reports the distance between the two, per modelo and per edition,
so the remaining work is a worklist rather than an impression.

What it does NOT do. It does not judge whether a stated row is identical to the
row it would inherit -- that is :mod:`delta_minimality`, which compares LOADED
``CasillaDefinition`` values through the authority and owns the question. This
screen reads the authored corpus, and the two answer different questions: a
modelo can be perfectly minimal and still restate its references on every row.

Conditions reported, each keyed on one rule of the target shape:

- ``row_source_refs_restated`` - a row's ``source_refs`` equal the edition
  default exactly. The migration drops them.
- ``row_source_refs_liftable`` - a row's ``source_refs`` open with the edition
  default. The migration keeps only the tail, as ``additional_source_refs``.
- ``constraints_source_refs_restated`` / ``constraints_source_refs_liftable`` -
  the same two on a row's nested ``constraints`` table, which states its own
  references and is lifted by the same rules. Counted apart because a row and
  its constraints table are separate statements and a sweep that reads only
  rows understates the surface.
- ``row_legal_refs_equal_orden`` - a row's ``legal_refs`` equal the edition's
  ``orden_aplicabilidad``, which the loader fills as a default already.
- ``edition_default_undeclared`` - an edition whose rows admit a derivable
  ``casilla_source_refs`` but which declares none, so its restatement is
  unlifted.
- ``edition_default_underivable`` - the migration tool declines to declare a
  default: a row or constraints table states no ``source_refs``, no leading run
  opens two statements, or two runs tie. The derivation is the tool's own
  function, imported rather than copied, so the two cannot disagree; the
  finding carries the tool's reason. It needs a judgement rather than a sweep.
- ``derived_field_authored`` - a row carries an authored ``export_refs``. The
  loader derives that field from the export layout's own back-pointer and
  refuses an authored value, so any occurrence is a regression.
- ``edition_keyed_identifier`` - a member identifier, in any inheritable
  family, still carrying a year or the edition id as a token. A year the
  member declares as its own data (a deadline window's ``filing_year``) is
  not an edition token and does not count; nor do per-edition families the
  union never inherits (generated export layouts, workbook parity pins).
- ``row_missing_lineage`` - a row carries no ``continuidad_id``. Inheritance
  keys on lineage, so a predecessor row without one leaves the successor row
  nothing to supersede, and this is the precondition every other condition
  waits on. The flat count answers a corpus question, not a campaign one, so
  it is decomposed by whether an edge is waiting on the row:
  ``row_missing_lineage_on_edge`` is a row in an edition some edge names as
  its PREDECESSOR and is the only scope that enters the verdict;
  ``row_missing_lineage_terminal`` is a row in a modelo's last edition, which
  the next edition published will need; and ``row_missing_lineage_unedged`` is
  a row in a modelo with a single edition, where a chain asserts nothing yet.
  A campaign that counts all three alike cannot tell the work it owns from the
  work it does not yet have an edge for.
- ``unknown_authoring_key`` - a row key that is neither a typed
  ``CasillaDefinition`` field nor a known authoring-layer key.

The union rule is one rule over every declaration family whose members carry a
stable identity, so three conditions measure it family by family rather than
for casillas alone. Every ``SCHEMA_FAMILY`` collection on the revision model is
read from the authored fragments; a family keys on ``id`` where its element
model declares one, casillas key on ``continuidad_id``:

- ``member_restated`` - a successor edition states a member identical, after
  lifting the restated references and the lineage claims, to the member it
  would inherit from the edition before it. This is the union's own gap: what
  a person authors that the merge could supply. Casillas under an edition that
  names a predecessor are excluded, because :mod:`delta_minimality` owns that
  question through the compiled authority; casillas under an explicit root and
  every other family are measured here, since nothing inherits them yet.
- ``family_default_undeclared`` - a family whose members admit a derivable
  shared ``source_refs`` run, by the migration tool's own rule, in an edition
  whose manifest declares no default for that family (``casilla_source_refs``,
  ``binding_source_refs``, ``formula_source_refs``).
- ``family_without_identity`` - a family with members whose element model
  declares no identity field, so it cannot join the union until it has one.
- ``identifier_is_address`` - a member identifier carrying a ``.NNN-NNN.``
  byte-span segment. An identifier names a slot; its position lives on the
  provider (``offset``, ``length``) and moves between editions, so an
  identifier that embeds it changes when nothing about the slot did, and
  id-keyed inheritance then keeps two members for one field. Every such
  identifier blocks its family from the union until the generator emits names.

Two identifier-keyed families are per-edition claims rather than declarations
and are never measured as restated: ``workbook_parity_refs`` pins evidence to
one official workbook, and ``export_layouts`` is generated per edition by the
generator from the pinned record design. The completeness manifest is not a
schema family and never enters the census.

An explicit no-predecessor root is reported in two kinds, because they are
different facts: ``root_by_law`` when the reason is the form's (parallel
scheme variants, a successor withholding by design), and
``root_pending_lineage`` when the reason names a predecessor row without
lineage -- the tool's own wording for an edition it could not inherit because
the chain was never stated. The second is recoverable work and is counted in a
modelo's ``outstanding``; the first is terminal.

Three further conditions are about REACH rather than authoring shape, and they
exist because a corpus measured only against itself can only ever agree with
itself. The registry carries one global promise -- the
``supported_filing_years`` catalogue, whose own docstring calls it "the
registry's sole declaration of filing years the product supports" -- and every
modelo's declared reach is projected against it:

- ``promised_year_unserved`` - a promised filing year no edition of this modelo
  admits. Selection refuses it outright.
- ``promised_coordinate_unserved`` - a promised ``(year, period)`` cell no
  edition admits, where the modelo does serve the year in some other period.
  The period denominator is the union of the period tokens the modelo's own
  editions declare, which is the denominator
  :mod:`dev.registry.supported_filing_years` already uses; deriving it any
  other way would invent an obligation the registry never stated.
- ``coordinate_served_twice`` - more than one edition admits the same cell, so
  ``select_revision`` refuses it as ambiguous whenever the caller supplies no
  date to narrow it. The opposite failure to the two above, and no more usable.

These report DIVERGENCE, not fault, and they are NOT part of the authoring
verdict: a modelo's ``state`` and ``outstanding`` count are shape only, and a
coverage gap is printed beside them rather than folded in. Migration cannot
move a coverage gap, so counting one as outstanding shape work would hold the
shape signal hostage to a different campaign. A gap can be legitimate: the
product may promise a filing year corpus-wide while AEAT has published no
design for a particular modelo that year, and the promise file's own comment
records that this audit "remains advisory until the separately authorised
enforcement flip". No suppression mechanism exists here deliberately --
classifying a gap as legitimate is a judgement that belongs in a declaration a
reviewer signs, not in a screen's heuristic.

Edges. Each adjacent ``(predecessor, successor)`` edition pair is one unit of
migration work, in one of four states: ``migrated`` (the successor names a
predecessor), ``dispositioned`` (it declares an explicit grounded none),
``blocked``, or ``ready``. A successor that names a predecessor states only its
delta, so its rows are walked back along the declared chain and merged by
lineage -- supersede in place, drop retired, append new -- before it serves as
anyone's predecessor. The blockers are every cause the migration tool decides
from the raw tree without materialising through the compiler:

- ``predecessor_lineage_missing`` - a predecessor row without ``continuidad_id``
  cannot be inherited.
- ``successor_withholds_by_design`` - the successor declares a lower authority
  grade; inheriting would materialise rows it refuses to state.
- ``parallel_scheme_variants`` - the two editions overlap in period.
- ``unretired_withdrawal`` - a predecessor lineage the successor neither states
  nor retires through a ``retired`` casilla continuity evolution.
- ``ambiguous_lineage`` - a lineage carried by two rows of one edition.
- ``undeclared_repurpose`` - a successor row whose id matches a predecessor row
  of a different lineage.
- ``export_scenario_missing`` - the successor has an export surface but no
  scenario in ``dev.registry.edition_export_scenarios``, so the tool cannot
  compare its bytes and refuses to apply.

One cause the tool can report is not decidable here: ``row_order``, which needs
the merge order the compiler defines. A ``ready`` edge is therefore one the
tool has no raw-tree reason to refuse, and its dry run is the final word.

The causes are computed BEHIND a ``root_pending_lineage`` disposition as well,
and the blocker tally counts those edges. A root declared for want of lineage
is an edge the corpus can still recover, and treating its declaration as the
end of the question is what let the screen print no blocker at all while such
roots held thousands of rows no successor could inherit. A ``root_by_law``
disposition is left alone: no cause of ours is what stops it.

Two further measurements are reported apart from the conditions, because they
are properties of the corpus rather than defects in it, and counting them as
findings would overstate the worklist:

- ``row_pinned_by_lineage_claim`` - a row states ``continuidad_origin`` or
  ``continuidad_evidence``. The migration always keeps such a row stated, since
  an inherited row never carries one. It is a floor on what any delta can drop.
- ``row_source_refs_irreducible`` - a ``source_refs`` value the edition default
  plus additions cannot reproduce exactly. Kept whole by design.
- ``row_identical_unchained`` - a casilla row under an explicit root that is
  identical, after lifting, to the predecessor's row of the same casilla
  identifier, but carries no lineage on one side or the other, so the union
  cannot yet prove it is the same box. This is the lineage workload in rows:
  each one becomes ``member_restated`` the moment its chain is stated, and
  inheritable the moment the root is replaced by a predecessor.

Delta-0 for this screen is every shape condition at zero: no restated member
in any family, no undeclared family default, no edition-keyed identifier, no
row an edge is waiting on for a chain, and every edge migrated or rooted BY
LAW. A root declared for want of lineage is not a resting state and does not
satisfy it.

The authoring vocabulary is not the typed vocabulary. ``CasillaDefinition``
declares its fields with ``extra="forbid"``, and ``additional_source_refs`` is
not among them: it is an authoring-layer key the loader resolves into
``source_refs`` before typed construction. So the keys legally authorable in a
fragment are the typed field set plus the authoring-layer keys, and
``unknown_authoring_key`` is the check that nothing else has crept in.

Read from the authored TOML rather than through the compiled authority, because
the question is what a person maintains rather than what the product loads: a
restated reference and an inherited one materialise identically, so the
authority cannot see the distinction this screen exists to measure.

The screen exits 0 whatever it finds. It reports findings; it does not gate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from ..source_default_rule import edition_source_default
from .coverage_dispositions import CoverageCoordinate, CoverageDisposition, load_coverage_dispositions

__all__ = [
    "CONDITIONS",
    "COVERAGE_CONDITIONS",
    "MEASUREMENTS",
    "CoverageGap",
    "Edge",
    "EditionStatus",
    "Finding",
    "ModeloSignal",
    "Report",
    "build_report",
    "coverage_gaps",
    "edges",
    "edition_token_in_identifier",
    "family_rows",
    "modelo_signals",
    "render_report",
    "scan_edition",
    "scan_registry",
    "supported_filing_years",
]

_MODELOS: Final = "modelos"
_REVISIONS: Final = "revisions"
_MANIFEST: Final = "revision.toml"
_CASILLAS: Final = "casillas"
_ROW_SOURCE: Final = "source_refs"
_ROW_SOURCE_ADDITIONS: Final = "additional_source_refs"
_ROW_LEGAL: Final = "legal_refs"
_CONSTRAINTS: Final = "constraints"
_LINEAGE: Final = "continuidad_id"
_LINEAGE_CLAIMS: Final = frozenset({"continuidad_origin", "continuidad_evidence"})
_EDITION_SOURCE_DEFAULT: Final = "casilla_source_refs"
_EDITION_ORDEN: Final = "orden_aplicabilidad"
_PREDECESSOR: Final = "predecessor"
_EVOLUTIONS: Final = "casilla_continuidad_evolutions"
_RETIRED: Final = "retired"
_EXPORT_DIRS: Final = ("export", "export_layouts")
#: The manifest key that carries each family's shared ``source_refs`` default.
_FAMILY_DEFAULT_KEYS: Final[Mapping[str, str]] = {
    "casillas": "casilla_source_refs",
    "bindings": "binding_source_refs",
    "formulas": "formula_source_refs",
}
#: The migration tool's own wording for a root it declared for want of lineage.
_ROOT_PENDING_LINEAGE_MARK: Final = "predecessor row without lineage"
#: Families whose members are per-edition claims rather than inheritable
#: declarations: evidence pins to a specific official workbook, and generated
#: export layouts owned by the generator. They are never counted as restated.
_PER_EDITION_FAMILIES: Final = frozenset({"workbook_parity_refs", "export_layouts"})
#: Keys stripped before two members are compared for restatement.
_RESTATEMENT_KEYS: Final = frozenset({"source_refs", "legal_refs", "additional_source_refs", *_LINEAGE_CLAIMS})

#: A stated casilla row's identity for chain walking: its id and its lineage.
type RowKey = tuple[str, str | None]

#: Fields the loader derives and refuses as authored values.
_DERIVED_FIELDS: Final = ("export_refs",)

#: Keys legal in a fragment but resolved away before typed construction.
_AUTHORING_ONLY_KEYS: Final = frozenset({_ROW_SOURCE_ADDITIONS})

#: The registry's sole declaration of the filing years the product supports.
#: `SupportedFilingYearsCatalogue`'s own docstring calls it that, and it is the
#: promise every modelo's declared reach is measured against below.
_SUPPORTED_YEARS_FILE: Final = ("legal", "supported-filing-years.toml")
_SUPPORTED_YEARS_KEY: Final = "supported_filing_years"

#: Conditions about REACH rather than authoring shape: what the product promises
#: to file versus what the corpus can actually select. Declared apart because
#: they answer a different success criterion -- a modelo can be perfectly
#: delta-authored and still refuse a year the product claims to support -- and
#: folded into CONDITIONS so one worklist carries both.
COVERAGE_CONDITIONS: Final[tuple[str, ...]] = (
    "promised_year_unserved",
    "promised_coordinate_unserved",
    "coordinate_served_twice",
)

#: Every condition this screen can report, declared once and used at each
#: emission site below, so the set cannot be misread off the source.
CONDITIONS: Final[tuple[str, ...]] = (
    "derived_field_authored",
    "unknown_authoring_key",
    "row_source_refs_restated",
    "row_source_refs_liftable",
    "constraints_source_refs_restated",
    "constraints_source_refs_liftable",
    "row_legal_refs_equal_orden",
    "edition_default_undeclared",
    "edition_default_underivable",
    "edition_keyed_identifier",
    "row_missing_lineage",
    "row_missing_lineage_on_edge",
    "member_restated",
    "family_default_undeclared",
    "family_without_identity",
    "identifier_is_address",
    *COVERAGE_CONDITIONS,
)

#: Measured alongside the conditions and never counted as findings.
MEASUREMENTS: Final[tuple[str, ...]] = (
    "row_pinned_by_lineage_claim",
    "row_source_refs_irreducible",
    "row_identical_unchained",
    "row_missing_lineage_terminal",
    "row_missing_lineage_unedged",
)


#: Set when the registry domain could not be imported and the screen fell back
#: to reading families off the corpus. Printed as a ``limitation`` record so a
#: reading taken in that state is never mistaken for one taken against the schema.
_LIMITATIONS: list[str] = []


def _typed_casilla_fields() -> frozenset[str] | None:
    """Return the typed casilla vocabulary, or ``None`` when the domain cannot be imported.

    Without the model the unknown-key check cannot run; it is skipped and the
    limitation is recorded rather than every key being reported unknown.
    """
    try:
        from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
    except Exception as exc:
        _note_limitation(f"schema_unavailable: {type(exc).__name__}")
        return None
    return frozenset(CasillaDefinition.model_fields)


def _note_limitation(text: str) -> None:
    if text not in _LIMITATIONS:
        _LIMITATIONS.append(text)


@cache
def _schema_families() -> tuple[tuple[str, str | None], ...]:
    """Every ``SCHEMA_FAMILY`` collection on the revision model with its identity field.

    Read off the shipped model rather than listed here, so a family added to
    the schema is measured without this screen being edited to notice it.
    Casillas key on ``continuidad_id``; any other family keys on ``id`` when
    its element model declares one, and has no identity otherwise.

    When the registry domain cannot be imported (a broken working tree is the
    usual cause) the families are discovered from the shipped corpus instead:
    every array-of-tables section is a family, and it keys on ``id`` when
    every member carries one. The reading is then marked with a ``limitation``
    record. The chain sections are excluded by name in that mode, as the
    schema marker would exclude them.
    """
    import typing

    try:
        from cadrumo.domain.calculations.registry.schema import ModeloRevision
        from cadrumo.domain.calculations.registry.schema_base import SCHEMA_FAMILY
    except Exception as exc:
        _note_limitation(f"schema_unavailable: {type(exc).__name__}; families discovered from the corpus")
        return _discover_families(_bundled_registry_root())

    families: list[tuple[str, str | None]] = []
    for name, info in ModeloRevision.model_fields.items():
        if not any(marker is SCHEMA_FAMILY for marker in info.metadata):
            continue
        (element, *_rest) = typing.get_args(info.annotation) or (None,)
        candidates = [element] if hasattr(element, "model_fields") else list(typing.get_args(element))
        has_id = any("id" in getattr(candidate, "model_fields", {}) for candidate in candidates)
        families.append((name, _LINEAGE if name == _CASILLAS else ("id" if has_id else None)))
    return tuple(families)


_CHAIN_SECTION_SUFFIX: Final = "_evolutions"


def _discover_families(registry_root: Path) -> tuple[tuple[str, str | None], ...]:
    """Families and identity keys read off the corpus, for when the schema cannot be imported."""
    members: dict[str, int] = defaultdict(int)
    with_id: dict[str, int] = defaultdict(int)
    for path in (registry_root / _MODELOS).glob("*/revisions/*/*/*.toml"):
        revisions = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {})
        for table in revisions.values():
            if not isinstance(table, dict):
                continue
            for section, value in table.items():
                if section.endswith(_CHAIN_SECTION_SUFFIX) or not isinstance(value, list):
                    continue
                rows = [row for row in value if isinstance(row, dict)]
                if not rows:
                    continue
                members[section] += len(rows)
                with_id[section] += sum(1 for row in rows if isinstance(row.get("id"), str))
    return tuple(
        (section, _LINEAGE if section == _CASILLAS else ("id" if with_id[section] == members[section] else None))
        for section in sorted(members)
    )


def _bundled_registry_root() -> Path:
    """Return the shipped AEAT registry tree root."""
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


_YEAR_RANGE: Final = re.compile(r"(?<![0-9])(\d{4})-(\d{4})(?![0-9])")
_ADDRESS_SPAN: Final = re.compile(r"\.\d+-\d+(?=\.)")


def edition_token_in_identifier(identifier: str, edition_id: str) -> str | None:
    """Return the edition token an identifier carries, or ``None``.

    Whole-token rather than substring, and only the edition's OWN year
    segments: ``modelo-303-2025-reconciliation`` carries its edition while
    ``rd-1624-1992:art-71`` carries a norm's year, and a bare four-digit
    substring test reports both. Measured against this corpus the difference is
    the whole finding: a substring test reports 897 identifiers, almost all of
    them legal references embedded in a name, where the token test reports 6.

    Two refinements keep the detector honest on the residue the collapse
    leaves. A numeric token counts only when it is a four-digit year: the
    ``09`` of ``2024-desde-09-y-3t`` is a period, and an identifier naming
    ``dr303-09`` names a box. And a year inside a ``NNNN-NNNN`` range that is
    not the edition id itself -- ``page_02.2001-2017`` in edition ``2016-2017``
    -- is an offset or validity range carried by the box, not the edition
    restating itself, so it is not a finding.
    """
    if edition_id in identifier:
        return edition_id
    ranged = {year for pair in _YEAR_RANGE.findall(identifier) if "-".join(pair) != edition_id for year in pair}
    segments = set(identifier.replace(":", "-").replace(".", "-").split("-")) - ranged
    matches = [
        segment for segment in edition_id.split("-") if len(segment) == 4 and segment.isdigit() and segment in segments
    ]
    return max(matches, key=len) if matches else None


def _as_refs(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


@dataclass(frozen=True, slots=True)
class Finding:
    """One located departure from the target authoring shape."""

    modelo: str
    edition: str
    kind: str
    locus: str
    detail: str


@dataclass
class EditionStatus:
    """One edition's authoring shape and the findings located in it."""

    modelo: str
    edition: str
    declares_predecessor: bool = False
    declares_no_predecessor: bool = False
    predecessor_id: str | None = None
    root_reason: str = ""
    export_surface: bool = False
    members: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    rows_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    stated_keys: tuple[RowKey, ...] = ()
    retired_lineages: frozenset[str] = frozenset()
    declared_default: tuple[str, ...] = ()
    effective_default: tuple[str, ...] = ()
    orden: tuple[str, ...] = ()
    valid_from: str = ""
    authority_grade: str = ""
    selector_years: tuple[int, ...] = ()
    selector_year_from: int | None = None
    selector_year_to: int | None = None
    periods: tuple[str, ...] = ()
    rows: int = 0
    rows_stating_source_refs: int = 0
    rows_without_lineage: int = 0
    constraints_tables: int = 0
    casilla_files: int = 0
    rows_per_file: list[int] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def _add(self, kind: str, locus: str, detail: str) -> None:
        self.findings.append(Finding(self.modelo, self.edition, kind, locus, detail))

    @property
    def restatement_lifted(self) -> bool:
        """Whether this edition declares its shared casilla source references once."""
        return bool(self.declared_default)


#: Authority grades in increasing reach. A successor declaring a lower grade than
#: its predecessor withholds by design, and inheriting there would silently
#: materialise rows it refused to state, so such an edge stays full-copy.
_GRADE_REACH: Final[dict[str, int]] = {
    "unsupported": 0,
    "advisory": 1,
    "calculation": 2,
    "filing": 3,
}


@dataclass(frozen=True, slots=True)
class Edge:
    """One adjacent (predecessor, successor) pair: the campaign's unit of work."""

    modelo: str
    predecessor: str
    successor: str
    state: str
    blockers: tuple[str, ...]
    predecessor_rows: int
    predecessor_rows_without_lineage: int
    root_kind: str = ""
    restated_members: tuple[tuple[str, int], ...] = ()
    chained_both_sides: int = 0
    successor_rows: int = 0
    successor_rows_without_lineage: int = 0

    @property
    def rooted_pending_lineage(self) -> bool:
        """Whether this edge is an explicit root declared only for want of lineage."""
        return self.state == "dispositioned" and self.root_kind == "root_pending_lineage"

    @property
    def chain_reach(self) -> float:
        """The share of the predecessor's rows a chain already reaches, 0.0 to 1.0.

        An edge is not chained or unchained; it is chained to a degree, and the
        degree is what a burn-down needs. Reported beside the raw counts rather
        than instead of them, because a ratio alone hides whether 0.9 means nine
        rows or nine hundred.
        """
        return 0.0 if not self.predecessor_rows else 1 - self.predecessor_rows_without_lineage / self.predecessor_rows


def _root_kind(reason: str) -> str:
    return "root_pending_lineage" if _ROOT_PENDING_LINEAGE_MARK in reason else "root_by_law"


def _comparable(member: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in member.items() if key not in _RESTATEMENT_KEYS}


def _materialised_members(
    edition: EditionStatus, by_edition: Mapping[str, EditionStatus], family: str
) -> dict[str, dict[str, Any]]:
    """The members an edition holds for a family once its declared chain is walked.

    Only casillas inherit today, so every other family returns exactly what the
    edition states; casillas merge by lineage along the chain, dropping the
    lineages each edition retires, as the loader does.
    """
    if family != _CASILLAS:
        return dict(edition.members.get(family, {}))
    chain: list[EditionStatus] = []
    seen: set[str] = set()
    current: EditionStatus | None = edition
    while current is not None and current.edition not in seen:
        chain.append(current)
        seen.add(current.edition)
        current = by_edition.get(current.predecessor_id) if current.predecessor_id is not None else None
    merged: dict[str, dict[str, Any]] = {}
    for member in reversed(chain):
        merged = {key: row for key, row in merged.items() if key not in member.retired_lineages}
        merged.update(member.members.get(_CASILLAS, {}))
    return merged


def _restated_members(
    predecessor: EditionStatus,
    successor: EditionStatus,
    by_edition: Mapping[str, EditionStatus],
) -> tuple[tuple[str, int], ...]:
    """Count, per family, the successor's stated members identical to what it would inherit.

    Casillas under a successor that names a predecessor are left to the
    minimality screen; everything else is measured, because nothing inherits it
    yet and the count is exactly what the union would remove.
    """
    counts: list[tuple[str, int]] = []
    for family, key in _schema_families():
        if key is None or family in _PER_EDITION_FAMILIES or (family == _CASILLAS and successor.declares_predecessor):
            continue
        inherited = _materialised_members(predecessor, by_edition, family)
        restated = 0
        for identity, member in successor.members.get(family, {}).items():
            before = inherited.get(identity)
            if before is not None and _comparable(before) == _comparable(member):
                restated += 1
                successor._add("member_restated", f"{family}/{identity}", f"identical to {predecessor.edition}")
        if restated:
            counts.append((family, restated))
        if family == _CASILLAS:
            _measure_unchained(predecessor, successor)
    return tuple(counts)


def _measure_unchained(predecessor: EditionStatus, successor: EditionStatus) -> None:
    """Count successor casilla rows identical to a predecessor row by casilla id but not chained by lineage."""
    before_by_id = {row_id: row for row_id, row in predecessor.rows_by_id.items()}
    for row_id, row in successor.rows_by_id.items():
        before = before_by_id.get(row_id)
        if before is None or _comparable(before) != _comparable(row):
            continue
        if _lineage_of(before) is None or _lineage_of(row) is None or _lineage_of(before) != _lineage_of(row):
            successor._add(
                "row_identical_unchained", row_id, f"identical to {predecessor.edition} by id, no shared lineage"
            )


def _selectors_overlap(left: EditionStatus, right: EditionStatus) -> bool:
    """Whether two editions could both be live -- the parallel-variant case.

    Mirrors ``period_selectors_overlap``: a shared year range AND at least one
    shared period token. Two editions that overlap may be parallel scheme
    variants rather than a sequence, and a predecessor edge between them would
    assert an order the law does not.
    """

    def bounds(edition: EditionStatus) -> tuple[int, int | None]:
        if edition.selector_years:
            return min(edition.selector_years), max(edition.selector_years)
        if edition.selector_year_from is None:
            return 0, None
        return edition.selector_year_from, edition.selector_year_to

    left_start, left_end = bounds(left)
    right_start, right_end = bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    return bool(set(left.periods) & set(right.periods))


def _materialised_keys(edition: EditionStatus, by_edition: Mapping[str, EditionStatus]) -> tuple[RowKey, ...]:
    """The rows an edition holds once its declared chain is walked, as the loader merges them.

    Inherited rows in the predecessor's order, a stated row superseding the
    inherited row of the same lineage in place, retired lineages dropped, and
    genuinely new rows appended in stated order. A full-copy edition holds
    exactly what it states. A chain that leaves the modelo, or loops, stops
    at the edition that breaks it: the forest validator owns that refusal.
    """
    chain: list[EditionStatus] = []
    seen: set[str] = set()
    current: EditionStatus | None = edition
    while current is not None and current.edition not in seen:
        chain.append(current)
        seen.add(current.edition)
        current = by_edition.get(current.predecessor_id) if current.predecessor_id is not None else None
    rows: list[RowKey] = []
    for member in reversed(chain):
        stated_by_lineage = {lineage: key for key in member.stated_keys if (lineage := key[1]) is not None}
        merged: list[RowKey] = []
        superseded: set[str] = set()
        for key in rows:
            lineage = key[1]
            if lineage is not None and lineage in member.retired_lineages:
                continue
            if lineage is not None and lineage in stated_by_lineage:
                merged.append(stated_by_lineage[lineage])
                superseded.add(lineage)
                continue
            merged.append(key)
        merged.extend(key for key in member.stated_keys if key[1] is None or key[1] not in superseded)
        rows = merged
    return tuple(rows)


@cache
def _scenario_editions(modelo_id: str) -> frozenset[str] | None:
    """The editions the round-trip gate can render export bytes for, or ``None`` when unknowable."""
    try:
        from ..edition_export_scenarios import edition_export_scenarios
    except Exception as exc:
        _note_limitation(f"export_scenarios_unavailable: {type(exc).__name__}")
        return None
    return frozenset(edition_export_scenarios(modelo_id))


def _blockers(
    predecessor: EditionStatus,
    successor: EditionStatus,
    predecessor_keys: tuple[RowKey, ...],
) -> tuple[str, ...]:
    """Every raw-tree cause the migration tool would refuse this edge with."""
    blockers: list[str] = []
    without_lineage = sum(1 for _, lineage in predecessor_keys if lineage is None)
    if without_lineage:
        blockers.append(f"predecessor_lineage_missing={without_lineage}")
    left = _GRADE_REACH.get(predecessor.authority_grade, -1)
    right = _GRADE_REACH.get(successor.authority_grade, -1)
    if left >= 0 and right >= 0 and right < left:
        blockers.append("successor_withholds_by_design")
    if _selectors_overlap(predecessor, successor):
        blockers.append("parallel_scheme_variants")
    predecessor_lineages = Counter(lineage for _, lineage in predecessor_keys if lineage is not None)
    successor_lineages = Counter(lineage for _, lineage in successor.stated_keys if lineage is not None)
    withdrawn = [
        lineage
        for lineage in predecessor_lineages
        if lineage not in successor_lineages and lineage not in successor.retired_lineages
    ]
    if withdrawn:
        blockers.append(f"unretired_withdrawal={len(withdrawn)}")
    if any(count > 1 for count in predecessor_lineages.values()) or any(
        count > 1 for count in successor_lineages.values()
    ):
        blockers.append("ambiguous_lineage")
    predecessor_by_id = dict(predecessor_keys)
    repurposed = sum(
        1
        for row_id, lineage in successor.stated_keys
        if lineage is not None and predecessor_by_id.get(row_id) not in (None, lineage)
    )
    if repurposed:
        blockers.append(f"undeclared_repurpose={repurposed}")
    scenarios = _scenario_editions(successor.modelo)
    if successor.export_surface and scenarios is not None and successor.edition not in scenarios:
        blockers.append("export_scenario_missing")
    return tuple(blockers)


def edges(statuses: tuple[EditionStatus, ...]) -> tuple[Edge, ...]:
    """Return every modelo's adjacent edition pairs with its migration state.

    Ordered by ``valid_from``, as the migration tool orders them. The four
    states are distinct and must not be pooled: ``migrated`` already declares a
    predecessor; ``dispositioned`` declares an explicit reasoned
    no-predecessor, which is the recorded outcome for a parallel variant or an
    edition that withholds by design and is NOT outstanding work; ``blocked``
    names a precondition; ``ready`` names none. Blockers are computed only for
    the two outstanding states, against the predecessor's materialised rows.
    """
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    found: list[Edge] = []
    for modelo, editions in sorted(by_modelo.items()):
        by_edition = {status.edition: status for status in editions}
        ordered = sorted(editions, key=lambda status: (status.valid_from, status.edition))
        for predecessor, successor in pairwise(ordered):
            predecessor_keys = _materialised_keys(predecessor, by_edition)
            blockers: tuple[str, ...] = ()
            root_kind = ""
            if successor.declares_predecessor:
                state = "migrated"
            elif successor.declares_no_predecessor:
                state = "dispositioned"
                root_kind = _root_kind(successor.root_reason)
                # A root declared FOR WANT OF LINEAGE is a recoverable edge
                # wearing a disposition, and reading the declaration as the end
                # of the question suppresses every cause behind it: the corpus
                # reports no blocker at all while such roots hold thousands of
                # rows no successor can inherit. The causes are computed here so
                # the disposition hides nothing. A root the LAW gives -- a
                # parallel scheme variant, a successor withholding by design --
                # is left alone, because no cause of ours is what stops it.
                if root_kind == "root_pending_lineage":
                    blockers = _blockers(predecessor, successor, predecessor_keys)
            else:
                blockers = _blockers(predecessor, successor, predecessor_keys)
                state = "blocked" if blockers else "ready"
            found.append(
                Edge(
                    modelo=modelo,
                    predecessor=predecessor.edition,
                    successor=successor.edition,
                    state=state,
                    blockers=blockers,
                    predecessor_rows=len(predecessor_keys),
                    predecessor_rows_without_lineage=sum(1 for _, lineage in predecessor_keys if lineage is None),
                    root_kind=root_kind,
                    chained_both_sides=len(
                        {lineage for _, lineage in predecessor_keys if lineage is not None}
                        & {lineage for _, lineage in successor.stated_keys if lineage is not None}
                    ),
                    successor_rows=len(successor.stated_keys),
                    successor_rows_without_lineage=sum(1 for _, lineage in successor.stated_keys if lineage is None),
                    restated_members=_restated_members(predecessor, successor, by_edition),
                )
            )
    return tuple(found)


def _classify_refs(
    status: EditionStatus,
    locus: str,
    refs: tuple[str, ...],
    *,
    restated: str,
    liftable: str,
    report_irreducible: bool,
) -> None:
    """Bucket one ``source_refs`` statement against the edition default."""
    if not refs or not status.effective_default:
        return
    default = status.effective_default
    if refs == default:
        status._add(restated, locus, json.dumps(list(refs)))
    elif refs[: len(default)] == default:
        status._add(liftable, locus, json.dumps(list(refs[len(default) :])))
    elif report_irreducible:
        status._add("row_source_refs_irreducible", locus, json.dumps(list(refs)))


def _member_year_data(member: Mapping[str, Any]) -> frozenset[str]:
    """Years a member declares as its own data, which an identifier may carry without keying on the edition.

    A deadline window for filing year 2013 inside a 2013-2014 edition is named
    by that year because the year is the window's datum (``filing_year``), not
    the edition's key. Any integer field whose name ends in ``year`` counts.
    """
    return frozenset(str(value) for key, value in member.items() if key.endswith("year") and isinstance(value, int))


def _token_is_member_data(token: str, member: Mapping[str, Any]) -> bool:
    """Whether a matched edition token is really the member's own year datum.

    The token may be a bare year or a whole edition id such as ``2018-4t``; in
    both cases it is data when its leading year equals a year field the member
    declares (a deadline window's ``filing_year``).
    """
    years = _member_year_data(member)
    return token in years or token.split("-", 1)[0] in years


def _lineage_of(row: Mapping[str, Any]) -> str | None:
    value = row.get(_LINEAGE)
    return value if isinstance(value, str) and value else None


def _retired_lineages(edition_dir: Path, edition_id: str) -> frozenset[str]:
    """The lineages this edition withdraws through a ``retired`` continuity evolution.

    Evolutions may sit in the manifest or in any fragment under the edition, so
    every TOML file below the edition is read for the section.
    """
    retired: set[str] = set()
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
        evolutions = table.get(_EVOLUTIONS) if isinstance(table, dict) else None
        for evolution in evolutions if isinstance(evolutions, list) else ():
            if (
                isinstance(evolution, dict)
                and evolution.get("evolution_kind") == _RETIRED
                and evolution.get("to_revision") == edition_id
                and isinstance(evolution.get(_LINEAGE), str)
            ):
                retired.add(str(evolution[_LINEAGE]))
    return frozenset(retired)


def _read_rows(edition_dir: Path, edition_id: str, status: EditionStatus) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    casilla_dir = edition_dir / _CASILLAS
    if not casilla_dir.is_dir():
        return rows
    for fragment in sorted(casilla_dir.glob("*.toml")):
        payload = tomllib.loads(fragment.read_text(encoding="utf-8"))
        declared = payload.get(_REVISIONS, {}).get(edition_id, {}).get(_CASILLAS)
        fragment_rows = [row for row in declared if isinstance(row, dict)] if isinstance(declared, list) else []
        rows.extend(fragment_rows)
        status.casilla_files += 1
        status.rows_per_file.append(len(fragment_rows))
    return rows


def scan_edition(modelo_id: str, edition_dir: Path, typed_fields: frozenset[str] | None) -> EditionStatus:
    """Read one edition directory and locate every condition it carries."""
    edition_id = edition_dir.name
    status = EditionStatus(modelo=modelo_id, edition=edition_id)

    manifest = edition_dir / _MANIFEST
    manifest_table: dict[str, Any] = {}
    if manifest.exists():
        table = tomllib.loads(manifest.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
        manifest_table = table if isinstance(table, dict) else {}
        predecessor = table.get(_PREDECESSOR)
        # The schema spells three states apart deliberately: an ABSENT key, a
        # DECLARED predecessor as a bare revision id, and an EXPLICIT
        # no-predecessor as a single `[...predecessor.none]` table carrying its
        # reason. Reading a table as enrollment reports modelo 369's three
        # parallel scheme variants as migrated when nothing about them inherits.
        status.declares_predecessor = isinstance(predecessor, str)
        status.declares_no_predecessor = isinstance(predecessor, dict)
        status.predecessor_id = predecessor if isinstance(predecessor, str) else None
        if isinstance(predecessor, dict):
            none = predecessor.get("none")
            status.root_reason = str(none.get("reason", "")) if isinstance(none, dict) else ""
        status.export_surface = bool(table.get("export_layouts"))
        status.declared_default = _as_refs(table.get(_EDITION_SOURCE_DEFAULT))
        status.orden = _as_refs(table.get(_EDITION_ORDEN))
        status.valid_from = str(table.get("valid_from", ""))
        status.authority_grade = str(table.get("authority_grade", ""))
        selector = table.get("period_selector")
        if isinstance(selector, dict):
            years = selector.get("years")
            status.selector_years = tuple(int(y) for y in years) if isinstance(years, list) else ()
            year_from, year_to = selector.get("year_from"), selector.get("year_to")
            status.selector_year_from = year_from if isinstance(year_from, int) else None
            status.selector_year_to = year_to if isinstance(year_to, int) else None
            periods = selector.get("periods")
            status.periods = tuple(str(p) for p in periods) if isinstance(periods, list) else ()

    rows = _read_rows(edition_dir, edition_id, status)
    status.rows = len(rows)
    status.stated_keys = tuple((str(row.get("id", "<unidentified>")), _lineage_of(row)) for row in rows)
    status.rows_by_id = {str(row["id"]): row for row in rows if isinstance(row.get("id"), str)}
    status.retired_lineages = _retired_lineages(edition_dir, edition_id)
    status.export_surface = status.export_surface or any(
        (edition_dir / name).is_dir() and any((edition_dir / name).glob("*.toml")) for name in _EXPORT_DIRS
    )

    statements = 0
    for row in rows:
        if _as_refs(row.get(_ROW_SOURCE)):
            status.rows_stating_source_refs += 1
            statements += 1
        constraints = row.get(_CONSTRAINTS)
        if isinstance(constraints, dict):
            status.constraints_tables += 1
            if _as_refs(constraints.get(_ROW_SOURCE)):
                statements += 1
    # The tool's own derivation, over the rows as authored: for an unlifted
    # edition the authored row is the row the tool derives from.
    derived, withheld = edition_source_default(rows) if rows else (None, None)
    status.effective_default = status.declared_default or (derived or ())

    if statements and not status.effective_default and withheld is not None:
        status._add("edition_default_underivable", "<edition>", withheld)
    if status.effective_default and not status.declared_default:
        status._add("edition_default_undeclared", "<edition>", json.dumps(list(status.effective_default)))

    for row in rows:
        locus = str(row.get("id", "<unidentified>"))
        for key in row:
            if typed_fields is not None and key not in typed_fields and key not in _AUTHORING_ONLY_KEYS:
                status._add("unknown_authoring_key", locus, key)
        for derived in _DERIVED_FIELDS:
            if derived in row:
                status._add("derived_field_authored", locus, derived)
        _classify_refs(
            status,
            locus,
            _as_refs(row.get(_ROW_SOURCE)),
            restated="row_source_refs_restated",
            liftable="row_source_refs_liftable",
            report_irreducible=True,
        )
        constraints = row.get(_CONSTRAINTS)
        if isinstance(constraints, dict):
            _classify_refs(
                status,
                f"{locus}.constraints",
                _as_refs(constraints.get(_ROW_SOURCE)),
                restated="constraints_source_refs_restated",
                liftable="constraints_source_refs_liftable",
                report_irreducible=False,
            )
        if status.orden and _as_refs(row.get(_ROW_LEGAL)) == status.orden:
            status._add("row_legal_refs_equal_orden", locus, json.dumps(list(status.orden)))
        if not row.get(_LINEAGE):
            status.rows_without_lineage += 1
            status._add("row_missing_lineage", locus, "no continuidad_id")
        for claim in sorted(_LINEAGE_CLAIMS & set(row)):
            status._add("row_pinned_by_lineage_claim", locus, claim)

    families = _schema_families()
    declared_sections = _read_sections(edition_dir, edition_id, {family for family, _ in families})
    for family, key in families:
        members = [entry for entry in declared_sections.get(family, ()) if isinstance(entry, dict)]
        if not members:
            continue
        if key is None:
            status._add("family_without_identity", family, f"{len(members)} members, element model declares no id")
            continue
        keyed: dict[str, dict[str, Any]] = {}
        for entry in members:
            identity = entry.get(key)
            if isinstance(identity, str) and identity:
                keyed[identity] = entry
            if family != _CASILLAS and family not in _PER_EDITION_FAMILIES and isinstance(entry.get("id"), str):
                token = edition_token_in_identifier(entry["id"], edition_id)
                if token is not None and not _token_is_member_data(token, entry):
                    status._add("edition_keyed_identifier", entry["id"], f"{family} token={token}")
                span = _ADDRESS_SPAN.search(entry["id"])
                if span is not None:
                    status._add("identifier_is_address", entry["id"], f"{family} span={span.group(0).strip('.')}")
        status.members[family] = keyed
        default_key = _FAMILY_DEFAULT_KEYS.get(family)
        if default_key is not None and family != _CASILLAS and default_key not in manifest_table:
            derived_default, _withheld = edition_source_default(members)
            if derived_default:
                status._add("family_default_undeclared", family, json.dumps(list(derived_default)))
    return status


def _read_sections(edition_dir: Path, edition_id: str, families: set[str]) -> dict[str, list[object]]:
    """Merge every fragment below the edition into one table per family, as the loader does."""
    merged: dict[str, list[object]] = defaultdict(list)
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
        if not isinstance(table, dict):
            continue
        for family in families:
            declared = table.get(family)
            if isinstance(declared, list):
                merged[family].extend(declared)
    return merged


def scan_registry(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> tuple[EditionStatus, ...]:
    """Scan every edition of every modelo under a registry root."""
    typed_fields = _typed_casilla_fields()
    modelos_root = registry_root / _MODELOS
    statuses: list[EditionStatus] = []
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        if modelo_ids and modelo_dir.name not in modelo_ids:
            continue
        editions_dir = modelo_dir / _REVISIONS
        if not editions_dir.is_dir():
            continue
        for edition_dir in sorted(path for path in editions_dir.iterdir() if path.is_dir()):
            statuses.append(scan_edition(modelo_dir.name, edition_dir, typed_fields))
    return tuple(statuses)


#: The three obligations a missing chain can carry, told apart by whether an
#: edge is waiting on the row. Declared once so the scopes and the flat count
#: cannot drift apart at the sites that read them.
LINEAGE_SCOPES: Final[tuple[str, ...]] = (
    "row_missing_lineage_on_edge",
    "row_missing_lineage_terminal",
    "row_missing_lineage_unedged",
)


def scope_lineage_findings(statuses: tuple[EditionStatus, ...], found_edges: tuple[Edge, ...]) -> None:
    """Classify every missing chain by whether an edge is waiting on it.

    ``row_missing_lineage`` states a fact about a row and says nothing about
    what is blocked by it, and the three scopes it conflates carry three
    different obligations:

    - ``row_missing_lineage_on_edge`` -- the row sits in an edition some edge
      names as its PREDECESSOR, so a successor cannot inherit it today. This is
      the campaign's own worklist and the only scope that enters a modelo's
      outstanding count.
    - ``row_missing_lineage_terminal`` -- the row sits in a modelo's last
      edition. Nothing inherits from it yet; the next edition published will.
    - ``row_missing_lineage_unedged`` -- the modelo declares one edition, so it
      has no edge at all. A chain asserts nothing until a second edition exists.

    Added BESIDE the flat count rather than replacing it, so the corpus fact and
    the campaign's share of it are both readable and the scopes stay checkable
    against the total they decompose.

    Scoping has to happen after the edges are derived and therefore cannot
    happen in :func:`scan_edition`, which reads one edition and cannot know
    what succeeds it.
    """
    predecessors = {(edge.modelo, edge.predecessor) for edge in found_edges}
    successors = {(edge.modelo, edge.successor) for edge in found_edges}
    for status in statuses:
        key = (status.modelo, status.edition)
        if key in predecessors:
            scope = "row_missing_lineage_on_edge"
        elif key in successors:
            scope = "row_missing_lineage_terminal"
        else:
            scope = "row_missing_lineage_unedged"
        for finding in [item for item in status.findings if item.kind == "row_missing_lineage"]:
            status._add(scope, finding.locus, finding.detail)


def _edges_awaiting_lineage(found_edges: tuple[Edge, ...]) -> int:
    """Edges a chain must be stated on before they can be unioned.

    Counted over EDGES rather than summed from the blocker tally: a rooted edge
    now carries its own ``predecessor_lineage_missing`` cause, so adding the
    tally to the rooted count would report each of those edges twice.
    """
    return sum(
        1
        for edge in found_edges
        if edge.rooted_pending_lineage
        or any(blocker.startswith("predecessor_lineage_missing") for blocker in edge.blockers)
    )


@dataclass(frozen=True, slots=True)
class Report:
    """One scan: the editions read, the promise they are measured against, and what follows.

    Bound together because every reporting surface needs all three, and passing
    them separately is how a coverage figure ends up computed against a
    different promise than the one printed beside it.
    """

    statuses: tuple[EditionStatus, ...]
    promised_years: tuple[int, ...]
    gaps: tuple[CoverageGap, ...]
    edges: tuple[Edge, ...]


def build_report(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> Report:
    """Scan a registry root and derive its edges and coverage gaps."""
    statuses = scan_registry(registry_root, modelo_ids=modelo_ids)
    promised = supported_filing_years(registry_root)
    found_edges = edges(statuses)
    scope_lineage_findings(statuses, found_edges)
    return Report(
        statuses=statuses,
        promised_years=promised,
        gaps=coverage_gaps(statuses, promised, load_coverage_dispositions()),
        edges=found_edges,
    )


def _census(statuses: tuple[EditionStatus, ...], gaps: tuple[CoverageGap, ...] = ()) -> dict[str, int]:
    counts = Counter(finding.kind for status in statuses for finding in status.findings)
    counts.update(gap.kind for gap in gaps)
    return {kind: counts.get(kind, 0) for kind in (*CONDITIONS, *MEASUREMENTS)}


def supported_filing_years(registry_root: Path) -> tuple[int, ...]:
    """Return the filing years the product promises to support: ``floor`` through ``horizon``.

    One registry-wide declaration, and the only one: the catalogue's own
    docstring calls itself "the registry's sole declaration of filing years the
    product supports". It declares a hard ``floor`` and the last authored
    ``horizon``; the promise measured here is that closed range. Years above
    the horizon are projected forward by the authority rather than refused,
    so they are not part of the promise this lane measures. A modelo's
    success criterion is measured against this promise rather than against
    what its own directories happen to contain,
    because a corpus can only ever agree with itself.
    """
    path = registry_root.joinpath(*_SUPPORTED_YEARS_FILE)
    if not path.is_file():
        return ()
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(_SUPPORTED_YEARS_KEY, {})
    floor, horizon = table.get("floor"), table.get("horizon")
    if not isinstance(floor, int) or not isinstance(horizon, int) or horizon < floor:
        return ()
    return tuple(range(floor, horizon + 1))


def _admits_year(status: EditionStatus, year: int) -> bool:
    """Whether an edition's selector admits a filing year.

    ``PeriodSelector.includes_year``, reimplemented exactly: an explicit
    ``years`` tuple wins outright; otherwise ``year_from`` is REQUIRED and
    ``year_to`` optional. A selector carrying neither admits no year at all --
    which is why an absent ``valid_to`` does not, on its own, make an edition
    open-ended, and why this must not be approximated as "no bound means all
    years".
    """
    if status.selector_years:
        return year in status.selector_years
    if status.selector_year_from is None:
        return False
    return year >= status.selector_year_from and (status.selector_year_to is None or year <= status.selector_year_to)


#: An empty signed declaration, typed once so a caller passing none does not
#: widen the mapping's value type and take every reason read from it with it.
_NO_DISPOSITIONS: Final[Mapping[CoverageCoordinate, CoverageDisposition]] = dict[
    CoverageCoordinate, CoverageDisposition
]()


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """One promised filing coordinate the corpus does not serve exactly once."""

    modelo: str
    kind: str
    filing_year: int
    period: str
    editions: tuple[str, ...]
    disposition: str = ""

    @property
    def disposed(self) -> bool:
        """Whether a signed declaration classifies this gap as legitimate.

        A gap CAN be legitimate -- the product may promise a filing year that
        AEAT published no design for -- and no migration work will ever close
        one. What a screen must not do is decide which gaps those are, so the
        classification is read from a declaration a reviewer signs and every
        unclassified gap stays outstanding.
        """
        return bool(self.disposition)


def coverage_gaps(
    statuses: tuple[EditionStatus, ...],
    promised_years: tuple[int, ...],
    dispositions: Mapping[CoverageCoordinate, CoverageDisposition] | None = None,
) -> tuple[CoverageGap, ...]:
    """Project every modelo's declared reach against the promised filing years.

    The period denominator per modelo is the union of the period tokens its own
    editions declare -- the method ``dev.registry.supported_filing_years``
    already uses, kept identical so the two reconcile. Deriving it any other way
    would invent an obligation the registry never stated.

    Two failures, and they are opposite: a coordinate NO edition admits cannot
    be filed at all, and a coordinate MORE THAN ONE edition admits is refused by
    ``select_revision`` as ambiguous whenever the caller supplies no date to
    narrow it. Both are reported, because a corpus that serves a year twice is
    no more usable than one that serves it never.
    """
    if not promised_years:
        return ()
    signed = _NO_DISPOSITIONS if dispositions is None else dispositions
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)

    def _disposition(modelo: str, kind: str, year: int, period: str) -> str:
        """The signed reason for this coordinate, when one classifies this KIND.

        The kind is checked as well as the coordinate: an entry written for an
        unserved year must not silently absorb the opposite failure should the
        corpus later serve that cell twice.
        """
        entry = signed.get((modelo, year, period))
        return entry.reason if entry is not None and entry.kind == kind else ""

    gaps: list[CoverageGap] = []
    for modelo, editions in sorted(by_modelo.items()):
        periods = sorted({period for edition in editions for period in edition.periods})
        if not periods:
            continue
        for year in promised_years:
            admitting = [edition for edition in editions if _admits_year(edition, year)]
            if not admitting:
                kind = "promised_year_unserved"
                gaps.append(CoverageGap(modelo, kind, year, "*", (), _disposition(modelo, kind, year, "*")))
                continue
            for period in periods:
                serving = tuple(edition.edition for edition in admitting if period in edition.periods)
                if not serving:
                    kind = "promised_coordinate_unserved"
                    gaps.append(CoverageGap(modelo, kind, year, period, (), _disposition(modelo, kind, year, period)))
                elif len(serving) > 1:
                    kind = "coordinate_served_twice"
                    gaps.append(
                        CoverageGap(modelo, kind, year, period, serving, _disposition(modelo, kind, year, period))
                    )
    return tuple(gaps)


#: The shape actions this screen's findings resolve to, in campaign order:
#: restatement lifting is independent and can start at once; lineage and export
#: scenarios each unblock edges; migration is what they unblock. Coverage is
#: printed for orientation and is another campaign's action.
_ACTIONS: Final[tuple[str, ...]] = (
    "lift_restatement",
    "seed_lineage",
    "declare_export_scenario",
    "migrate_edge",
    "close_coverage",
)

#: Every blocker cause an edge can carry, in the order the signal prints them.
_BLOCKER_CAUSES: Final[tuple[str, ...]] = (
    "predecessor_lineage_missing",
    "successor_withholds_by_design",
    "parallel_scheme_variants",
    "unretired_withdrawal",
    "ambiguous_lineage",
    "undeclared_repurpose",
    "export_scenario_missing",
)

#: Edge states, in the order the signal always prints them.
_EDGE_STATES: Final[tuple[str, ...]] = ("migrated", "ready", "blocked", "dispositioned")


@dataclass(frozen=True, slots=True)
class ModeloSignal:
    """One modelo's actionable state, as a row a later run can be diffed against."""

    modelo: str
    state: str
    editions: int
    rows: int
    edges_total: int
    edges_migrated: int
    edges_ready: int
    edges_blocked: int
    lineage_gap: int
    unlifted_editions: int
    restated_refs: int
    liftable_refs: int
    coverage_gaps: int
    coverage_gaps_undisposed: int = 0
    edges_rooted_pending_lineage: int = 0
    restated_members: int = 0
    lineage_gap_on_edge: int = 0

    @property
    def outstanding(self) -> int:
        """Shape work left: unlifted editions, unmigrated edges, pending roots, restated members, unchained rows.

        The units are mixed deliberately -- editions, edges, members and rows --
        because the number RANKS a worklist rather than measuring one quantity,
        and a modelo whose only remaining work is 1,343 rows no successor can
        inherit must not sort below one carrying a single unlifted edition.

        The lineage term counts only rows an edge is actually waiting on. A
        revision-local chain gap, and a gap in a modelo with one edition, are
        not this campaign's debt and are measured apart.
        """
        return (
            self.unlifted_editions
            + self.edges_ready
            + self.edges_blocked
            + self.edges_rooted_pending_lineage
            + self.restated_members
            + self.lineage_gap_on_edge
        )


def _modelo_state(
    editions: int,
    migrated: int,
    ready: int,
    blocked: int,
    dispositioned: int,
    unlifted: int,
    rooted_pending: int = 0,
    restated_members: int = 0,
) -> str:
    """Name a modelo's position against the union criteria.

    ``done`` is the only terminal state and requires all of: no edition still
    restates its references, every edge migrated or rooted by law, and no
    member of any family stated identical to what it would inherit. A modelo
    whose roots were declared for want of lineage is ``rooted``: shape-valid,
    not unioned. Filing coverage is reported beside the state and never
    decides it.
    """
    total_edges = migrated + ready + blocked + dispositioned
    if total_edges == 0:
        if editions == 1 and unlifted == 0 and restated_members == 0:
            return "single_edition"
        return "single_edition_unlifted"
    if ready == 0 and blocked == 0:
        if rooted_pending:
            return "rooted"
        if unlifted:
            return "migrated_unlifted"
        return "done" if restated_members == 0 else "migrated_restating"
    if migrated or dispositioned:
        return "partial"
    return "blocked" if ready == 0 else "ready"


def modelo_signals(report: Report) -> tuple[ModeloSignal, ...]:
    """Roll every edition, edge and coverage gap up into one diffable row per modelo."""
    statuses = report.statuses
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    edges_by_modelo: dict[str, list[Edge]] = defaultdict(list)
    for edge in report.edges:
        edges_by_modelo[edge.modelo].append(edge)
    gaps_by_modelo: Counter[str] = Counter(gap.modelo for gap in report.gaps)
    undisposed_by_modelo: Counter[str] = Counter(gap.modelo for gap in report.gaps if not gap.disposed)

    signals: list[ModeloSignal] = []
    for modelo, editions in sorted(by_modelo.items()):
        states = Counter(edge.state for edge in edges_by_modelo[modelo])
        counts = Counter(finding.kind for edition in editions for finding in edition.findings)
        unlifted = counts["edition_default_undeclared"] + counts["family_default_undeclared"]
        rooted_pending = sum(1 for edge in edges_by_modelo[modelo] if edge.rooted_pending_lineage)
        restated_members = counts["member_restated"]
        signals.append(
            ModeloSignal(
                modelo=modelo,
                state=_modelo_state(
                    len(editions),
                    states["migrated"],
                    states["ready"],
                    states["blocked"],
                    states["dispositioned"],
                    unlifted,
                    rooted_pending,
                    restated_members,
                ),
                editions=len(editions),
                rows=sum(edition.rows for edition in editions),
                edges_total=sum(states.values()),
                edges_migrated=states["migrated"],
                edges_ready=states["ready"],
                edges_blocked=states["blocked"],
                lineage_gap=counts["row_missing_lineage"],
                lineage_gap_on_edge=counts["row_missing_lineage_on_edge"],
                unlifted_editions=unlifted,
                restated_refs=counts["row_source_refs_restated"] + counts["constraints_source_refs_restated"],
                liftable_refs=counts["row_source_refs_liftable"] + counts["constraints_source_refs_liftable"],
                coverage_gaps=gaps_by_modelo[modelo],
                coverage_gaps_undisposed=undisposed_by_modelo[modelo],
                edges_rooted_pending_lineage=rooted_pending,
                restated_members=restated_members,
            )
        )
    return tuple(signals)


@dataclass(frozen=True, slots=True)
class FamilyRow:
    """One schema family's union position, shared by the record and the report renderers."""

    family: str
    identity: str
    members: int
    restated: int
    default_undeclared: int
    keyed_identifiers: int
    address_identifiers: int
    identical_unchained: int | None


def family_rows(report: Report) -> tuple[FamilyRow, ...]:
    """Per schema family: members, restated members, undeclared defaults, keyed identifiers, identity key."""
    members: Counter[str] = Counter()
    for status in report.statuses:
        for family, keyed in status.members.items():
            members[family] += len(keyed)
    restated: Counter[str] = Counter()
    for edge in report.edges:
        for family, count in edge.restated_members:
            restated[family] += count
    undeclared: Counter[str] = Counter()
    without_identity: Counter[str] = Counter()
    keyed: Counter[str] = Counter()
    address: Counter[str] = Counter()
    unchained = 0
    for status in report.statuses:
        for finding in status.findings:
            if finding.kind == "family_default_undeclared":
                undeclared[finding.locus] += 1
            elif finding.kind == "family_without_identity":
                without_identity[finding.locus] += int(finding.detail.split(" ", 1)[0])
            elif finding.kind == "edition_keyed_identifier":
                keyed[finding.detail.split(" ", 1)[0]] += 1
            elif finding.kind == "identifier_is_address":
                address[finding.detail.split(" ", 1)[0]] += 1
            elif finding.kind == "row_identical_unchained":
                unchained += 1
    rows: list[FamilyRow] = []
    for family, key in _schema_families():
        total = members[family] + without_identity[family]
        if total == 0:
            continue
        rows.append(
            FamilyRow(
                family=family,
                identity="none" if key is None else key,
                members=total,
                restated=restated[family],
                default_undeclared=undeclared[family],
                keyed_identifiers=keyed[family],
                address_identifiers=address[family],
                identical_unchained=unchained if family == _CASILLAS else None,
            )
        )
    return tuple(rows)


def _family_lines(report: Report) -> list[str]:
    """One record per schema family, for the diffable form."""
    return [
        f"family {row.family} members={row.members} restated={row.restated} "
        f"default_undeclared={row.default_undeclared} keyed_identifiers={row.keyed_identifiers} "
        f"address_identifiers={row.address_identifiers} identity={row.identity}"
        + (f" identical_unchained={row.identical_unchained}" if row.identical_unchained is not None else "")
        for row in family_rows(report)
    ]


def _payload(report: Report) -> dict[str, Any]:
    statuses = report.statuses
    return {
        "conditions": list(CONDITIONS),
        "coverage_conditions": list(COVERAGE_CONDITIONS),
        "measurements": list(MEASUREMENTS),
        "promised_filing_years": list(report.promised_years),
        "census": _census(statuses, report.gaps),
        "edge_census": dict(Counter(edge.state for edge in report.edges)),
        "coverage_gaps": [
            {
                "modelo": gap.modelo,
                "kind": gap.kind,
                "filing_year": gap.filing_year,
                "period": gap.period,
                "editions": list(gap.editions),
            }
            for gap in report.gaps
        ],
        "edges": [
            {
                "modelo": edge.modelo,
                "predecessor": edge.predecessor,
                "successor": edge.successor,
                "state": edge.state,
                "blockers": list(edge.blockers),
                "predecessor_rows": edge.predecessor_rows,
                "predecessor_rows_without_lineage": edge.predecessor_rows_without_lineage,
                "root_kind": edge.root_kind,
                "restated_members": dict(edge.restated_members),
            }
            for edge in report.edges
        ],
        "modelos": [
            {
                "modelo": signal.modelo,
                "state": signal.state,
                "editions": signal.editions,
                "rows": signal.rows,
                "edges_total": signal.edges_total,
                "edges_migrated": signal.edges_migrated,
                "edges_ready": signal.edges_ready,
                "edges_blocked": signal.edges_blocked,
                "lineage_gap": signal.lineage_gap,
                "lineage_gap_on_edge": signal.lineage_gap_on_edge,
                "unlifted_editions": signal.unlifted_editions,
                "restated_refs": signal.restated_refs,
                "liftable_refs": signal.liftable_refs,
                "coverage_gaps": signal.coverage_gaps,
                "coverage_gaps_undisposed": signal.coverage_gaps_undisposed,
                "edges_rooted_pending_lineage": signal.edges_rooted_pending_lineage,
                "restated_members": signal.restated_members,
                "outstanding": signal.outstanding,
            }
            for signal in modelo_signals(report)
        ],
        "editions": [
            {
                "modelo": status.modelo,
                "edition": status.edition,
                "declares_predecessor": status.declares_predecessor,
                "restatement_lifted": status.restatement_lifted,
                "declared_default": list(status.declared_default),
                "effective_default": list(status.effective_default),
                "rows": status.rows,
                "rows_stating_source_refs": status.rows_stating_source_refs,
                "constraints_tables": status.constraints_tables,
                "casilla_files": status.casilla_files,
                "rows_per_file": status.rows_per_file,
            }
            for status in statuses
        ],
        "findings": [
            {
                "modelo": finding.modelo,
                "edition": finding.edition,
                "kind": finding.kind,
                "locus": finding.locus,
                "detail": finding.detail,
            }
            for status in statuses
            for finding in status.findings
        ],
    }


def _artifacts_dir(explicit: Path | None) -> Path | None:
    """Return where per-finding detail belongs, or ``None`` when nowhere does.

    ``CADRUMO_DEV_ARTIFACTS_DIR`` is exported by :mod:`dev.test_runs.command`,
    so a run through the owning just recipe persists its detail beside its
    ``run.json`` without the recipe naming a path. Run directly with no
    override and the detail is simply not written: a screen invoked by hand
    should print its signal and leave no files behind.
    """
    if explicit is not None:
        return explicit
    from_environment = os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
    return Path(from_environment) if from_environment else None


def _write_detail(directory: Path, report: Report) -> tuple[Path, ...]:
    """Persist the full finding population beside the run's own metadata."""
    statuses = report.statuses
    directory.mkdir(parents=True, exist_ok=True)
    findings_path = directory / "edition-delta-findings.jsonl"
    with findings_path.open("w", encoding="utf-8") as handle:
        for status in statuses:
            for finding in status.findings:
                handle.write(
                    json.dumps(
                        {
                            "modelo": finding.modelo,
                            "edition": finding.edition,
                            "kind": finding.kind,
                            "locus": finding.locus,
                            "detail": finding.detail,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        # Coverage gaps are modelo-scoped rather than edition-scoped, so they
        # carry a sentinel edition and a `<year>/<period>` locus. They share the
        # findings file because a consumer wants one population to filter, not
        # two files to join.
        for gap in report.gaps:
            handle.write(
                json.dumps(
                    {
                        "modelo": gap.modelo,
                        "edition": "<modelo>",
                        "kind": gap.kind,
                        "locus": f"{gap.filing_year}/{gap.period}",
                        "detail": ",".join(gap.editions),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    signal_path = directory / "edition-delta-signal.json"
    signal_path.write_text(json.dumps(_payload(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (signal_path, findings_path)


def _signal_lines(report: Report) -> list[str]:
    """Return the signal: sorted, sanitized records a later run diffs against.

    Every line is ``<record> <stable key> <field=value>...`` with a fixed field
    order and a deterministic sort, so ``diff`` between two runs shows movement
    and nothing else. Nothing here carries a path, a timestamp, a row
    identifier or a reference value -- those are the parts that churn without
    the campaign advancing, and a signal that churns cannot be read as a delta.
    """
    statuses = report.statuses
    found_edges = report.edges
    signals = modelo_signals(report)
    census = _census(statuses, report.gaps)
    edge_states = Counter(edge.state for edge in found_edges)
    blockers = Counter(
        blocker.split("=")[0]
        for edge in found_edges
        if edge.state == "blocked" or edge.rooted_pending_lineage
        for blocker in edge.blockers
    )
    lines = [
        "# edition_delta_status schema=1",
        *(f"limitation {text}" for text in _LIMITATIONS),
        f"corpus modelos={len({status.modelo for status in statuses})} editions={len(statuses)} "
        f"casilla_rows={sum(status.rows for status in statuses)} "
        f"casilla_files={sum(status.casilla_files for status in statuses)}",
        # The promise every modelo's reach is measured against, printed beside
        # the measurement so a reader never has to assume which years it used.
        "promise filing_years=" + (",".join(str(year) for year in report.promised_years) or "none"),
        " ".join(
            [
                "coverage",
                *(f"{kind}={census[kind]}" for kind in COVERAGE_CONDITIONS),
                f"disposed={sum(1 for gap in report.gaps if gap.disposed)}",
                f"undisposed={sum(1 for gap in report.gaps if not gap.disposed)}",
                f"modelos_uncovered={len({gap.modelo for gap in report.gaps})}",
            ]
        ),
        " ".join(
            [
                "edge",
                *(f"{state}={edge_states.get(state, 0)}" for state in _EDGE_STATES),
                f"rooted_pending_lineage={sum(1 for edge in found_edges if edge.rooted_pending_lineage)}",
                f"total={len(found_edges)}",
            ]
        ),
        # The worklist, in the campaign's own ordering: restatement lifting is
        # independent and can start now, lineage and export scenarios each
        # unblock edges, and migration is what they unblock.
        " ".join(
            [
                "action",
                f"lift_restatement={census['edition_default_undeclared'] + census['family_default_undeclared']}",
                f"seed_lineage={_edges_awaiting_lineage(found_edges)}",
                f"inherit_member={census['member_restated']}",
                f"declare_export_scenario={blockers.get('export_scenario_missing', 0)}",
                f"migrate_edge={edge_states.get('ready', 0)}",
                f"close_coverage={len({gap.modelo for gap in report.gaps})}",
            ]
        ),
        " ".join(["blocker", *(f"{cause}={blockers.get(cause, 0)}" for cause in _BLOCKER_CAUSES)]),
        " ".join(["clean", *(kind for kind in CONDITIONS if census[kind] == 0)]) or "clean none",
    ]
    lines += [f"condition {kind}={census[kind]}" for kind in CONDITIONS if census[kind]]
    lines += [f"measurement {kind}={census[kind]}" for kind in MEASUREMENTS]
    lines += _family_lines(report)
    lines += [
        f"modelo {signal.modelo} state={signal.state} editions={signal.editions} rows={signal.rows} "
        f"ready={signal.edges_ready} blocked={signal.edges_blocked} migrated={signal.edges_migrated} "
        f"unlifted={signal.unlifted_editions} lineage_gap={signal.lineage_gap} "
        f"lineage_on_edge={signal.lineage_gap_on_edge} "
        f"restated={signal.restated_refs} liftable={signal.liftable_refs} "
        f"rooted={signal.edges_rooted_pending_lineage} restated_members={signal.restated_members} "
        f"uncovered={signal.coverage_gaps} undisposed={signal.coverage_gaps_undisposed} "
        f"outstanding={signal.outstanding}"
        for signal in signals
    ]
    lines += [
        f"uncovered {gap.modelo} {gap.filing_year} {gap.period} {gap.kind} "
        f"disposed={'yes' if gap.disposed else 'no'}" + (f" editions={','.join(gap.editions)}" if gap.editions else "")
        for gap in report.gaps
    ]
    lines += [
        f"ready {edge.modelo} {edge.predecessor} -> {edge.successor} predecessor_rows={edge.predecessor_rows}"
        for edge in found_edges
        if edge.state == "ready"
    ]
    lines += [
        f"blocked {edge.modelo} {edge.predecessor} -> {edge.successor} {','.join(edge.blockers)}"
        for edge in found_edges
        if edge.state == "blocked"
    ]
    # The rooted edges are the campaign's own worklist and had no record of
    # their own: the diffable form named only `ready` and `blocked`, so a run
    # that seeded a thousand chains behind a root moved no line in the signal.
    lines += [
        f"rooted {edge.modelo} {edge.predecessor} -> {edge.successor} "
        f"predecessor_rows={edge.predecessor_rows} unchained={edge.predecessor_rows_without_lineage} "
        f"shared_chains={edge.chained_both_sides} causes={','.join(edge.blockers) or 'none'}"
        for edge in found_edges
        if edge.rooted_pending_lineage
    ]
    return lines


def _fmt(value: int) -> str:
    return f"{value:,}"


_TEXT_COLUMNS: Final = frozenset({"modelo", "predecessor", "successor", "family", "identity", "state", "cause"})


def _table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]], *, indent: str = "  ") -> list[str]:
    """Render an aligned table; count columns right-align, identifier and text columns left-align."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: tuple[str, ...], *, header: bool = False) -> str:
        parts = []
        for index, cell in enumerate(cells):
            align = cell.ljust if header or headers[index] in _TEXT_COLUMNS else cell.rjust
            parts.append(align(widths[index]))
        return indent + "  ".join(parts).rstrip()

    return [
        line(headers, header=True),
        indent + "  ".join("-" * width for width in widths),
        *(line(row) for row in rows),
    ]


def render_report(report: Report, *, totals_only: bool = False) -> str:
    """Return the signal as a grouped, aligned, human-readable report.

    The same facts as :func:`_signal_lines`, laid out for a reader rather than
    for ``diff``: corpus and promise first, then the edge and action summary,
    then the shape conditions with the clean ones named, the measurements,
    the per-family union position, the per-modelo table sorted by outstanding
    work, and finally the per-edge worklist. Coverage sits in its own block
    because it is another campaign's number.
    """
    statuses = report.statuses
    found_edges = report.edges
    census = _census(statuses, report.gaps)
    signals = modelo_signals(report)
    edge_states = Counter(edge.state for edge in found_edges)
    rooted_pending = sum(1 for edge in found_edges if edge.rooted_pending_lineage)
    blockers = Counter(
        blocker.split("=")[0]
        for edge in found_edges
        if edge.state == "blocked" or edge.rooted_pending_lineage
        for blocker in edge.blockers
    )
    excluded = {*COVERAGE_CONDITIONS, "row_missing_lineage"}
    shape_conditions = [kind for kind in CONDITIONS if kind not in excluded]
    unlifted_total = census["edition_default_undeclared"] + census["family_default_undeclared"]
    out: list[str] = []
    rule = "=" * 78

    out += [
        "EDITION DELTA STATUS",
        rule,
        *(f"  LIMITATION  {text}" for text in _LIMITATIONS),
        f"  corpus     modelos {len({s.modelo for s in statuses})}   editions {len(statuses)}   "
        f"casilla rows {_fmt(sum(s.rows for s in statuses))}   "
        f"casilla files {_fmt(sum(s.casilla_files for s in statuses))}",
        "  promise    filing years " + (", ".join(str(y) for y in report.promised_years) or "none"),
        "",
        "EDGES",
        f"  migrated {edge_states.get('migrated', 0)}   ready {edge_states.get('ready', 0)}   "
        f"blocked {edge_states.get('blocked', 0)}   dispositioned {edge_states.get('dispositioned', 0)} "
        f"(rooted pending lineage {rooted_pending})   total {len(found_edges)}",
        "",
        "ACTIONS",
        f"  lift restatement      {_fmt(unlifted_total):>8}   editions x families",
        f"  seed lineage          {_fmt(_edges_awaiting_lineage(found_edges)):>8}   edges",
        f"  inherit member        {_fmt(census['member_restated']):>8}   members a merge would supply",
        f"  export scenario       {_fmt(blockers.get('export_scenario_missing', 0)):>8}   edges",
        f"  migrate edge          {_fmt(edge_states.get('ready', 0)):>8}   edges",
        f"  close coverage        {_fmt(len({gap.modelo for gap in report.gaps if not gap.disposed})):>8}"
        "   modelos (coverage campaign)",
        f"  dispose coverage      {_fmt(sum(1 for gap in report.gaps if not gap.disposed)):>8}"
        "   coordinates unclassified",
        "",
    ]
    nonzero_blockers = [(cause, blockers[cause]) for cause in _BLOCKER_CAUSES if blockers.get(cause)]
    out.append("BLOCKERS")
    out += [f"  {cause:<32} {_fmt(count):>8}" for cause, count in nonzero_blockers] or ["  none"]
    out.append("")

    out.append("SHAPE CONDITIONS")
    active = [(kind, census[kind]) for kind in shape_conditions if census[kind]]
    out += [f"  {kind:<32} {_fmt(count):>8}" for kind, count in active] or ["  all clean"]
    clean = [kind for kind in shape_conditions if not census[kind]]
    if clean and active:
        out.append("  clean: " + ", ".join(clean))
    out.append("")

    out.append("MEASUREMENTS")
    out += [f"  {kind:<32} {_fmt(census[kind]):>8}" for kind in (*MEASUREMENTS, "row_missing_lineage")]
    out.append("")

    # Coverage sits in its own block and never enters the shape verdict:
    # migration cannot move a coverage gap, so counting one as outstanding
    # shape work would hold the shape signal hostage to a different campaign.
    # What it does carry now is its own worklist -- a gap is either classified
    # by a signed disposition or it is outstanding, and an unclassified gap is
    # not evidence of anything except that nobody has read it yet.
    out.append("COVERAGE (its own campaign; never folded into the shape verdict)")
    out += [f"  {kind:<32} {_fmt(census[kind]):>8}" for kind in COVERAGE_CONDITIONS]
    out.append(f"  {'modelos uncovered':<32} {_fmt(len({gap.modelo for gap in report.gaps})):>8}")
    out.append(f"  {'disposed (signed)':<32} {_fmt(sum(1 for gap in report.gaps if gap.disposed)):>8}")
    out.append(f"  {'undisposed (outstanding)':<32} {_fmt(sum(1 for gap in report.gaps if not gap.disposed)):>8}")
    out.append("")

    out.append("FAMILIES  (union position per declaration family)")
    rows = [
        (
            row.family,
            row.identity,
            _fmt(row.members),
            _fmt(row.restated),
            _fmt(row.default_undeclared),
            _fmt(row.keyed_identifiers),
            _fmt(row.address_identifiers),
            _fmt(row.identical_unchained) if row.identical_unchained is not None else "",
        )
        for row in family_rows(report)
    ]
    out += _table(
        (
            "family",
            "identity",
            "members",
            "restated",
            "default undeclared",
            "keyed ids",
            "address ids",
            "identical unchained",
        ),
        rows,
    )
    out.append("")

    if totals_only:
        return "\n".join(out) + "\n"

    out.append("MODELOS  (sorted by outstanding work, then id)")
    state_order = {
        "blocked": 0,
        "ready": 1,
        "partial": 2,
        "rooted": 3,
        "migrated_unlifted": 4,
        "migrated_restating": 5,
        "single_edition_unlifted": 6,
        "done": 7,
        "single_edition": 8,
    }
    ordered = sorted(signals, key=lambda sig: (-sig.outstanding, state_order.get(sig.state, 9), sig.modelo))
    out += _table(
        (
            "modelo",
            "state",
            "eds",
            "rows",
            "ready",
            "blocked",
            "migrated",
            "rooted",
            "unchained",
            "unlifted",
            "restated",
            "uncovered",
            "outstanding",
        ),
        [
            (
                sig.modelo,
                sig.state,
                _fmt(sig.editions),
                _fmt(sig.rows),
                _fmt(sig.edges_ready),
                _fmt(sig.edges_blocked),
                _fmt(sig.edges_migrated),
                _fmt(sig.edges_rooted_pending_lineage),
                _fmt(sig.lineage_gap_on_edge),
                _fmt(sig.unlifted_editions),
                _fmt(sig.restated_members),
                _fmt(sig.coverage_gaps_undisposed),
                _fmt(sig.outstanding),
            )
            for sig in ordered
        ],
    )
    out.append("")

    worklist = [edge for edge in found_edges if edge.state in {"ready", "blocked"} or edge.rooted_pending_lineage]
    out.append("WORKLIST  (edges that are not yet unioned)")
    if worklist:
        out += _table(
            ("modelo", "predecessor", "successor", "state", "rows", "unchained", "reach", "cause"),
            [
                (
                    edge.modelo,
                    edge.predecessor,
                    edge.successor,
                    "rooted" if edge.rooted_pending_lineage else edge.state,
                    _fmt(edge.predecessor_rows),
                    _fmt(edge.predecessor_rows_without_lineage),
                    f"{edge.chain_reach:.0%}",
                    ", ".join(edge.blockers) if edge.blockers else (edge.root_kind or "-"),
                )
                for edge in worklist
            ],
        )
    else:
        out.append("  none")
    out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    """Print the delta-able signal; persist the finding population. Always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, default=None, help="registry root holding modelos/")
    parser.add_argument("--modelo", action="append", default=[], help="restrict to these modelo ids")
    parser.add_argument("--artifacts-dir", type=Path, default=None, help="where to persist the finding population")
    parser.add_argument("--totals-only", action="store_true", help="print only the corpus-wide records")
    parser.add_argument("--findings", action="store_true", help="print the finding rows to stdout as well")
    parser.add_argument("--kind", action="append", default=[], help="with --findings, print only these kinds")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON instead of the signal")
    parser.add_argument("--lines", action="store_true", help="print the diffable record lines instead of the report")
    arguments = parser.parse_args()

    registry_root = (arguments.registry_root or _bundled_registry_root()).resolve()
    report = build_report(registry_root, modelo_ids=tuple(arguments.modelo))
    statuses = report.statuses

    if arguments.json:
        sys.stdout.write(json.dumps(_payload(report), indent=2, sort_keys=True) + "\n")
        return 0

    if arguments.findings:
        selected = frozenset(arguments.kind) if arguments.kind else None
        for status in statuses:
            for finding in status.findings:
                if selected is not None and finding.kind not in selected:
                    continue
                sys.stdout.write(
                    f"finding modelo={finding.modelo} edition={finding.edition} "
                    f"kind={finding.kind} locus={finding.locus} detail={finding.detail!r}\n"
                )

    if arguments.lines:
        per_modelo_records = {"modelo", "ready", "blocked", "uncovered"}
        for line in _signal_lines(report):
            if arguments.totals_only and line.split(" ", 1)[0] in per_modelo_records:
                continue
            sys.stdout.write(line + "\n")
    else:
        sys.stdout.write(render_report(report, totals_only=arguments.totals_only))

    directory = _artifacts_dir(arguments.artifacts_dir)
    if directory is not None:
        for path in _write_detail(directory, report):
            sys.stdout.write(f"detail {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
