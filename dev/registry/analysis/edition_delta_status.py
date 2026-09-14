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
- ``constraints_source_refs_restated`` / ``constraints_source_refs_liftable`` /
  ``constraints_source_refs_irreducible`` / ``constraints_source_refs_order_only``
  - the same four on a row's nested ``constraints`` table, which states its own
  references and is classified by the same rules and the same helper. Counted
  apart because a row and its constraints table are separate statements and a
  sweep that reads only rows understates the surface. The claim of identical
  rules was false until the third outcome existed here: the helper took a bool
  that hardcoded the row kinds, so 81 constraint statements the default cannot
  reproduce were counted by nothing, in a family the entry described as lifted
  the same way.
- ``row_legal_refs_equal_orden`` - a row's ``legal_refs`` equal the edition's
  ``orden_aplicabilidad``, which the loader fills as a default already.
- ``edition_default_undeclared`` - an edition whose rows admit a derivable
  ``casilla_source_refs`` but which declares none, so its restatement is
  unlifted.
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
  every other inheritable family are measured here. Full-copy and per-edition
  families are explicitly outside this union rather than silently counted.

  It partitions set-exactly into four sub-kinds, and the four sum to the
  headline: that identity is the invariant, and it is pinned by a test rather
  than by a count quoted here, because a count quoted in prose is wrong from the
  next edition onward. THREE OF THE FOUR ARE REASONS NOT TO DROP, so the headline
  is not a drop list. Listed in the order the if/elif chain ASSIGNS them, which
  is the order that decides what a member with two applicable reasons is counted
  as:

  - ``member_restated_pinned`` - the member states a lineage claim a merge cannot
    reproduce, or its family inherits only conditionally. Undroppable, and tested
    first, so a pinned member is never reported as anything else.
  - ``member_restated_unedged`` - the edge is not declared, so it is not
    drop-path work yet. Tested before both grounding buckets, so an unedged
    member whose references would lift is counted here and not as droppable.
  - ``member_restated_payload_equal`` - the references LIFT to the edition
    default, so the merge can genuinely supply it. The only droppable bucket.
  - ``member_restated_grounding`` - the RESIDUAL, assigned by the ``else`` and
    not by a positive test: edged, unpinned, and ``_grounding_lifts`` returned
    False. Re-grounding on this edition's own references is the common cause but
    not the only one, so a member here is proven undroppable on this edge
    WITHOUT proving why.

  ``member_restated_dispositioned`` and
  ``member_restated_family_declared`` count members excluded by an authored
  family disposition or a ``restated_families`` declaration, kept apart so an
  exemption is visible as a quantity rather than a silent exclusion.
- ``attestation_at_risk_on_edge`` / ``attestation_at_risk_rooted`` - a member
  payload-identical to what it would inherit while stating an attestation field
  the inherited member does not state identically, split on whether the drop tool
  can reach it today. Two populations, not one: 3,887 where the inherited member
  carries nothing so a drop DESTROYS the attestation, and 399 where both carry it
  and the values differ so a drop DOWNGRADES it. They need different guards, and
  all five on-edge rows are downgrades.
- ``family_default_undeclared`` - a family whose members admit a derivable
  shared ``source_refs`` run, by the migration tool's own rule, in an edition
  whose manifest declares no default for that family. Two exclusions narrow it,
  and the count is the surface only after both: ``casillas`` is gated
  separately a few lines above, and a family declaring no source-default key at
  all cannot be measured here in the first place. The pairing is read from
  ``_family_default_keys()``, which now names
  every KEYED family missing its key as a run limitation -- a keyed family
  without one reports nothing and must not be read as having nothing to lift.
- ``root_demotion_verdict_unconsulted`` - a signed demotion verdict on an edge
  that is NOT a demotion candidate, so ``_edge_verdict`` never answers for it and
  no tally counts it. NOT a defect by default: the harness logs a verdict for every
  edge it measures, so a verdict agreeing with a root whose reason still holds is
  concordant and correctly unread. Read it as "no edge asks this question". The
  verdict value shown is the LOADED one, which the staleness downgrade may have
  rewritten. Measured only for editions the scan read, since the verdicts file is
  global while a scan may be scoped.
- ``family_without_identity`` - a family with members whose element model
  declares no identity field, so it cannot join the union until it has one.
- ``identifier_is_address`` - a member identifier carrying a ``.NNN-NNN.``
  byte-span segment. An identifier names a slot; its position lives on the
  provider (``offset``, ``length``) and moves between editions, so an
  identifier that embeds it changes when nothing about the slot did, and
  id-keyed inheritance then keeps two members for one field. Every such
  identifier blocks its family from the union until the generator emits names.

Per-edition claims are never measured as restated: ``workbook_parity_refs``
pins evidence to one official workbook, ``export_layouts`` is generated per
edition from the pinned record design, and ``verification_expectations`` is a
claim about that edition's own checks. The completeness manifest is not a
schema family and never enters the typed census. Bindings enter the typed
census under their reviewed provider/value identity policy.

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
  nor retires through a ``retired`` casilla continuity evolution. Reported ONLY
  where the successor roots, because a successor that declares a predecessor
  states just its delta and every inherited lineage it does not restate would
  look withdrawn -- eight such edges were verified false at ~1,601 boxes present
  in the compiled successors. So 51 of the corpus's 85 edges cannot raise this
  cause at all, and its absence on one of them is an unasked question rather
  than a clean edge. The three that carry it are all roots: 165 2016-2022 (15),
  490 2022-1t (116), 345 2024 (1).
- ``ambiguous_lineage`` - a lineage carried by two rows of one edition.
- ``undeclared_repurpose`` - a successor row whose id matches a predecessor row
  of a different lineage.
- ``export_scenario_missing`` - the successor has an export surface but no
  scenario in ``dev.registry.edition_export_scenarios``, so the tool cannot
  compare its bytes and refuses to apply.
- ``export_scenario_unrendered`` - a scenario IS declared and no render has been
  observed for that edition in ``export_scenario_renders.toml``. Declaring a
  scenario silenced ``export_scenario_missing`` without proving anything, so the
  two facts are held apart: one says a scenario exists, the other says it ran.
  44 edges.
- ``whole_modelo_declaration_required`` - every edition of the modelo is silent
  on its predecessor, so no single edge is a unit of work: two of three silent
  editions must be declared in one pass and exactly one may stay keyless as the
  chain's root. 7 edges.
- ``reviewed_against_required`` - a reviewed delta successor that does not state
  ``reviewed_against``. It is a reviewer's claim about what was examined, so
  nobody migrating the edge may invent it. Refused on an edition declaring an
  explicit no-predecessor, where the schema forbids the field -- demanding it
  there asks for a declaration that cannot be written, which was 23 of 29 early
  findings. 7 edges.

One cause the tool can report is not decidable here: ``row_order``, which needs
the merge order the compiler defines. A ``ready`` edge is therefore one the
tool has no raw-tree reason to refuse, and its dry run is the final word.

The remaining kinds, documented here because a catalogue that names three in four
still misleads -- 22 of this screen's 56 declared kinds were absent from it:

- ``edition_without_manifest`` - an edition directory with no ``revision.toml``.
  A half-authored directory presented as the campaign's next job.
- ``predecessor_forest_violation`` - more than one edition silent on its
  predecessor while some edition of the modelo has declared one. The forest rule
  refuses it, so declaring one edge of such a modelo turns a valid tree invalid:
  the declarations must land together.
- ``root_kind_by_wording`` - a root carrying no structured ``cause``, so its kind
  was classified from the reason TEXT. 17 of the corpus's 28 roots, because the
  migration tool writes the cause into prose and never into the field.
- ``default_carried_from_predecessor`` - see the function's own docstring before
  reading the number as work: it cannot separate a successor grounded on an older
  design from one sharing a design that governs both periods, because the design's
  devengo window is not read here. A family default identical to the
  predecessor edition's, on an edition that declares a predecessor. The merge
  would supply it.
- ``member_refs_inline`` - members restating their family default inline as their
  own ``source_refs`` instead of leaning on it.
- ``foreign_edition_token`` / ``year_token_as_content`` - the two outcomes of one
  test on an identifier carrying ANOTHER edition's token. It is a stale REFERENCE
  when a sibling of the same family spells the same stem without it, and CONTENT
  when nothing else spells that concept. The sibling is sought across every
  edition of the modelo, not only the declaring one.
- ``casillas_unmeasured`` - emitted once per EDGE, not per casilla, carrying the
  count this screen hands to :mod:`delta_minimality`.
- ``row_missing_lineage_on_projected_edge`` - an overlay on the lineage scoping
  rather than a fourth scope: the same rows again where the edition is a
  projection source.

Coverage kinds not described above: ``promised_year_projected`` (a year no edition
admits, with a covered year strictly below it, so the newest revision below could
be carried forward IF projection shipped -- it has not, which is why the kind is
deliberately NOT dispositionable), ``awaiting_ejercicio_orden`` and
``pending_orden_declaration_stale`` (AEAT has not published the ejercicio's orden,
or the declaration that it had not has gone stale), and
``disposition_kind_mismatched`` / ``disposition_coordinate_served`` (a signed
disposition whose coordinate now fails as a DIFFERENT kind the loader would
accept, or which an edition now serves -- both are signatures the corpus has
falsified and both are repairable in place),
``disposition_kind_superseded`` (the coordinate now fails as a kind the loader
REFUSES to sign, so no rewrite can make the entry apply: the reason may still be
true and the kind field is what expired, and the remedy is to re-home the
reasoning rather than to edit the kind), and
``disposition_coordinate_unreachable`` (a signed disposition naming a modelo no
manifest declares, or a filing year outside the promise -- the two cases the
served pass must skip before it can judge them, so without this they are
invisible). Reachability is tested by MODELO and YEAR only, never by period: a
period absent from a modelo's denominator is legitimate and permanent, which is
why 303's four ``0A`` entries are correct and silent.

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
- ``row_source_refs_order_only`` - the sub-population of the next kind that holds
  the whole default but not as a prefix, so the prefix test sends it to
  irreducible although default-plus-additions would reproduce it in another
  order. Measured, never reclassified: both fire for such a row. Order IS
  semantic -- the lift tool requires the lifted form to reconstruct the authored
  sequence exactly -- so these are correctly irreducible and the measurement
  exists to price a set-semantics change, which would alter what materialises for
  every already-lifted row and not only for these.
- ``row_source_refs_irreducible`` - a ``source_refs`` value the edition default
  plus additions cannot reproduce exactly. Kept whole by design.
- ``row_identical_unchained`` - a casilla row identical, after lifting, to the
  predecessor's row of the same casilla identifier, but carrying no lineage on
  either side, so the union cannot yet prove it is the same box. This is the
  lineage workload in rows: each becomes ``member_restated`` the moment its
  chain is stated.

  The emission does NOT require an explicit root, and an earlier wording here
  said it did. Measured: 5,172 of the 5,202 sit under one, and 30 do not --
  036/2025-02-03-y-siguientes declares neither a predecessor nor a root, so its
  edge is derived from edition order. For those the remediation this entry used
  to give, "inheritable the moment the root is replaced by a predecessor", has
  no subject: there is no root to replace, and the edition has to declare
  something before that question arises.

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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from ..source_default_rule import edition_source_default
from .coverage_dispositions import (
    DISPOSABLE_KINDS,
    CoverageCoordinate,
    CoverageDisposition,
    load_coverage_dispositions,
)

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


@cache
def _keyed_families() -> Any:
    """The canonical family policy module, imported on first use.

    Deferred rather than read at module scope so this screen can walk the
    bundled registry tree without the domain package importable. The screen
    exists to say what state the corpus is in; a screen that cannot be
    imported while the domain is mid-refactor goes quiet exactly when that
    question is being asked.
    """
    from cadrumo.domain.calculations.registry import keyed_families

    return keyed_families


def _family_spec(name: str) -> Any:
    """The canonical policy for ``name``, or ``None`` where none is enrolled."""
    return _keyed_families().family_spec(name)


@cache
def _inheritance() -> Any:
    """The canonical family inheritance mode enumeration."""
    return _keyed_families().FamilyInheritanceMode


@cache
def _family_default_keys() -> Mapping[str, str]:
    """The manifest key carrying each family's shared ``source_refs`` default.

    The pairing is part of the same domain policy vocabulary as inheritance;
    a family is enrolled according to its canonical policy.

    A family declaring no such key drops out of the mapping and every default
    measurement on it goes silent -- no finding, no zero, nothing. For a
    per-edition family that is correct, because it is never measured as restated
    anyway. For a KEYED family it is a blind spot, so each one is named as a
    limitation on every run: a reader comparing a keyed family reporting nothing
    against another reporting a count would otherwise read the silence as a clean
    bill. Withholding the key may well be deliberate -- ``deadline_windows``
    inherits only conditionally and says so in its own holdback reason -- but a
    deliberate exclusion still has to be visible as one.
    """
    specs = _keyed_families().CANONICAL_FAMILY_SPECS
    if keyless := sorted(
        spec.section
        for spec in specs
        if spec.source_default_key is None and spec.inheritance is not _inheritance().PER_EDITION
    ):
        _note_limitation(
            "family_default_unmeasurable: "
            f"{', '.join(keyless)} are keyed but declare no source-default key, "
            "so no default finding can be reported for them"
        )
    return {spec.section: spec.source_default_key for spec in specs if spec.source_default_key is not None}


#: Stands in for an absent ``valid_to``. Sorts above any ISO date, so an
#: edition with no declared end overlaps everything that starts after it --
#: which is what open-ended means, and is not the same as a window that
#: happens to end.
_OPEN_ENDED: Final = "9999-12-31"

#: The migration tool's own wording for a root it declared for want of lineage.
_ROOT_PENDING_LINEAGE_MARK: Final = "predecessor row without lineage"
#: The causes that make a root TERMINAL. The tool writes one sentence with a
#: varying parenthetical cause, and which cause it names is the whole question:
#: a parallel scheme variant, a successor declaring a lower grade, and two
#: editions overlapping in period are all facts about the forms, and no work of
#: ours moves them. Every other cause is work. Reading only the lineage mark and
#: calling the rest law filed two recoverable edges as terminal -- an unretired
#: withdrawal, which a `retired` continuity evolution discharges, and a row
#: order, which is the one cause this screen cannot decide from the raw tree
#: because it needs the compiler's merge order.
#: Matched case-insensitively, and as stems rather than whole phrases: the
#: corpus writes "parallel scheme variants" while a hand-authored root writes
#: "parallel scheme variant", and a classifier that read only one of those
#: spellings would file a terminal root as work. The stem is the shortest form
#: that cannot match a different cause.
_ROOT_CAUSES_BY_LAW: Final = ("parallel scheme variant", "overlapping predecessor")

#: The declared cause codes, which are the AUTHORITY on a root's kind. Matching
#: prose was the wrong mechanism, not merely the wrong word list: a reason a
#: person writes citing a norm is exactly what a substring list cannot
#: anticipate, and it misfiled a by-law root as work AND an evidence deficit as
#: law, in the same pass and in opposite directions.
_ROOT_KIND_BY_CAUSE: Final[Mapping[str, str]] = {
    # Recoverable in the two-way sense, but kept as its OWN kind: the pending
    # count is pinned as a campaign delta, and folding it into recoverable
    # would move a number nobody changed.
    "predecessor_row_without_lineage": "root_pending_lineage",
    "lower_grade": "root_recoverable",
    "unretired_withdrawal": "root_recoverable",
    # Facts about the forms, which no work of ours moves. official_structure
    # _differs covers a successor whose official record design genuinely differs
    # -- a reordering, or a byte shift -- so the predecessor cannot materialise
    # it however well the chain is stated.
    "parallel_scheme_variants": "root_by_law",
    "overlapping_predecessor": "root_by_law",
    "forbidden_by_norm": "root_by_law",
    "official_structure_differs": "root_by_law",
}


@cache
def _per_edition_families() -> frozenset[str]:
    """Families whose members are per-edition claims, not inheritable declarations.

    They are never counted as restated.
    """
    per_edition = _inheritance().PER_EDITION
    return frozenset(
        spec.section for spec in _keyed_families().CANONICAL_FAMILY_SPECS if spec.inheritance is per_edition
    )


#: Keys stripped before two members are compared for restatement.
_RESTATEMENT_KEYS: Final = frozenset({"source_refs", "legal_refs", "additional_source_refs", *_LINEAGE_CLAIMS})


@cache
def _undroppable_families() -> frozenset[str]:
    """Families a merge cannot reliably supply even when a member looks identical.

    ``deadline_windows`` inherits only where the successor selector covers the
    member's own filing period, so its drop operation remains held back.
    """
    return frozenset(
        spec.section for spec in _keyed_families().CANONICAL_FAMILY_SPECS if spec.inherited and not spec.drop_eligible
    )


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
    "disposition_coordinate_served",
    "disposition_coordinate_unreachable",
    "disposition_kind_mismatched",
    "disposition_kind_superseded",
    "promised_year_projected",
    "awaiting_ejercicio_orden",
    "pending_orden_declaration_stale",
)

#: The measurement's version. Bump on any change to what the conditions COUNT,
#: so a lane diffing two runs can separate corpus movement from instrument
#: movement rather than having to recall which changed.
_SIGNAL_SCHEMA: Final = 34

#: Every condition this screen can report, declared once and used at each
#: emission site below, so the set cannot be misread off the source.
CONDITIONS: Final[tuple[str, ...]] = (
    "derived_field_authored",
    "unknown_authoring_key",
    "edition_without_manifest",
    "predecessor_forest_violation",
    "root_kind_by_wording",
    "default_carried_from_predecessor",
    "row_source_refs_restated",
    "row_source_refs_liftable",
    "constraints_source_refs_restated",
    "constraints_source_refs_liftable",
    "constraints_source_refs_irreducible",
    "constraints_source_refs_order_only",
    "row_legal_refs_equal_orden",
    "edition_default_undeclared",
    "edition_keyed_identifier",
    "foreign_edition_token",
    "row_missing_lineage",
    "row_missing_lineage_on_edge",
    "member_restated",
    "member_restated_payload_equal",
    "member_restated_grounding",
    "member_restated_pinned",
    "family_default_undeclared",
    "family_without_identity",
    "identifier_is_address",
    *COVERAGE_CONDITIONS,
)

#: Measured alongside the conditions and never counted as findings.
MEASUREMENTS: Final[tuple[str, ...]] = (
    "year_token_as_content",
    "member_restated_dispositioned",
    "member_restated_family_declared",
    "member_refs_inline",
    "attestation_at_risk_on_edge",
    "attestation_at_risk_rooted",
    "member_restated_unedged",
    "casillas_unmeasured",
    "row_pinned_by_lineage_claim",
    "row_source_refs_irreducible",
    "row_source_refs_order_only",
    "row_identical_unchained",
    "row_missing_lineage_terminal",
    "row_missing_lineage_unedged",
    "row_missing_lineage_on_projected_edge",
    "root_demotion_verdict_unconsulted",
)


#: Every limitation this screen can record, declared so the set is checkable in both
#: directions like ``CONDITIONS`` and ``MEASUREMENTS``. Limitations were the third
#: category and the only one with no inventory: each name existed solely as an f-string
#: literal at its emit site, so a limitation that silently STOPPED being emitted --
#: because a guard moved or a code path was restructured -- was caught by nothing. That
#: is the most expensive absence to lose, because a limitation is the screen saying what
#: it could NOT measure, and losing it turns an unmeasured axis into an apparently clean
#: one.
LIMITATIONS: Final[tuple[str, ...]] = (
    "export_scenarios_unavailable",
    "family_default_unmeasurable",
    "lineage_ledger_unreadable",
    "lineage_totality_unavailable",
    "promise_absent",
    "promise_bounds_inverted",
    "promise_bounds_unparsable",
    "render_evidence_unreadable",
    "root_demotion_verdicts_unreadable",
    "schema_unavailable",
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

    def load() -> frozenset[str] | None:
        try:
            from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
        except Exception as exc:
            _note_limitation(f"schema_unavailable: {type(exc).__name__}")
            return None
        return frozenset(CasillaDefinition.model_fields)

    # Bounded for the same reason `ledger_totality` is. An import is not a fast
    # operation here: importing the schema pulls the registry package, whose
    # module-scope work has reached into the authority artefact, and a
    # non-reentrant lock held elsewhere turns that import into a hang rather
    # than an error. A guard that only catches exceptions catches nothing then.
    return _within_bound(load, "schema_vocabulary")


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
        policy = _family_spec(name)
        identity = (
            policy.identity
            if policy is not None and policy.schema_family
            else _LINEAGE
            if name == _CASILLAS
            else "id"
            if has_id
            else None
        )
        families.append((name, identity))
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
        (
            section,
            _family_spec(section).identity
            if _family_spec(section) is not None and _family_spec(section).schema_family
            else _LINEAGE
            if section == _CASILLAS
            else "id"
            if with_id[section] == members[section]
            else None,
        )
        for section in sorted(members)
    )


def _bundled_registry_root() -> Path:
    """Return the shipped AEAT registry tree root."""
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


_YEAR_RANGE: Final = re.compile(r"(?<![0-9])(\d{4})-(\d{4})(?![0-9])")
_ADDRESS_SPAN: Final = re.compile(r"\.\d+-\d+(?=\.)")


def _span_is_address(segment: str, entry: Mapping[str, Any]) -> bool:
    """Return whether a ``NNN-NNN`` identifier segment is a byte address rather than data.

    The provider is the arbiter, as it is for the rename tool: a segment equal
    to the provider's own ``record`` code (``714-02`` is a page record, not a
    span) is data, and a provider carrying ``offset``/``length`` names an
    address only when the segment equals ``offset-(offset+length-1)``. Without a
    provider to consult the segment keeps its address reading.
    """
    provider = entry.get("provider")
    if not isinstance(provider, Mapping):
        return True
    if provider.get("record") == segment:
        return False
    offset, length = provider.get("offset"), provider.get("length")
    if isinstance(offset, int) and isinstance(length, int) and not isinstance(offset, bool):
        return segment == f"{offset}-{offset + length - 1}"
    return True


_BARE_OFFSET: Final = re.compile(r"[.-](\d+)$")


def _bare_offset_in_identifier(identifier: str, entry: Mapping[str, Any]) -> int | None:
    """Return the provider offset an identifier carries as a bare trailing number, else ``None``.

    A replay that re-spells ``…290-302…`` as ``…-290`` still binds the id to
    its byte address; the dot-bounded span test cannot see it, so the trailing
    segment is compared with the provider's own ``offset``.
    """
    provider = entry.get("provider")
    if not isinstance(provider, Mapping):
        return None
    offset = provider.get("offset")
    if not isinstance(offset, int) or isinstance(offset, bool):
        return None
    tail = _BARE_OFFSET.search(identifier)
    return offset if tail is not None and int(tail.group(1)) == offset else None


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


def _declared_families(value: object) -> frozenset[str]:
    """The family names a per-family disposition table declares.

    The value is a table keyed by family name; anything else is not a
    declaration and names nothing, which is the safe reading -- a malformed
    disposition must not silently excuse a family.
    """
    if not isinstance(value, dict):
        return frozenset[str]()
    return frozenset(str(name) for name in value)


def _restated_family_causes(value: object) -> dict[str, str]:
    """The families an edition declares it states in full, mapped to the declared cause.

    A LIST of tables, each naming a family and a cause -- unlike the per-family
    disposition tables, which are keyed BY family. The two are different claims
    and must not be pooled: a disposition says the family is empty by
    construction, a restatement says the family is stated end to end here and
    the merge does not inherit it on this edge. An entry naming no family
    declares nothing and is skipped rather than counted, so a malformed
    declaration never excuses a family.
    """
    if not isinstance(value, list):
        return {}
    causes: dict[str, str] = {}
    for entry in value:
        if not isinstance(entry, dict):
            continue
        family = entry.get("family")
        if isinstance(family, str) and family:
            causes[family] = str(entry.get("cause", ""))
    return causes


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
    root_cause: str = ""
    has_manifest: bool = True
    export_surface: bool = False
    members: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    rows_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Typed for shape only.  This raw screen has not run the compiler's
    # membership/evidence validation, so consumers must still check the exact
    # predecessor edge and the materialised identity before using a sidecar.
    lineage_attestations: tuple[LineageAttestation, ...] = ()
    lineage_attestation_refusals: int = 0
    stated_keys: tuple[RowKey, ...] = ()
    retired_lineages: frozenset[str] = frozenset()
    #: Generic keyed-family retirements from ``identifier_evolutions``.  The
    #: compiler uses the same section to discharge inherited members; keeping
    #: it on the status object lets its materialisation projection agree.
    retired_family_members: dict[str, frozenset[str]] = field(default_factory=dict)
    family_defaults: dict[str, tuple[str, ...]] = field(default_factory=dict)
    family_dispositions: frozenset[str] = frozenset()
    restated_families: dict[str, str] = field(default_factory=dict)
    declared_default: tuple[str, ...] = ()
    effective_default: tuple[str, ...] = ()
    orden: tuple[str, ...] = ()
    valid_from: str = ""
    valid_to: str = ""
    authority_grade: str = ""
    review_status: str = ""
    reviewed_against: str = ""
    selector_years: tuple[int, ...] = ()
    selector_year_from: int | None = None
    selector_year_to: int | None = None
    periods: tuple[str, ...] = ()
    period_overrides: tuple[tuple[int, tuple[str, ...]], ...] = ()
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
    roots_for_want_of_lineage: bool = False
    successor_is_reviewed_without_scope: bool = False
    restated_members: tuple[tuple[str, int], ...] = ()
    chained_both_sides: int = 0
    successor_rows: int = 0
    successor_rows_without_lineage: int = 0

    @property
    def rooted_pending_lineage(self) -> bool:
        """Whether this edge is an explicit root declared only for want of lineage."""
        return self.state == "dispositioned" and self.root_kind == "root_pending_lineage"

    @property
    def rooted_recoverable(self) -> bool:
        """Whether this edge roots away for a cause that is work rather than law."""
        return self.state == "dispositioned" and self.root_kind == "root_recoverable"

    @property
    def retraction_needs_attestation(self) -> bool:
        """Whether retracting this root would require a review scope nobody can invent.

        An ``agent_reviewed`` edition that gains an inherited basis must declare
        the predecessor its rows were reviewed against, and the loader refuses
        without it: the edition would compile carrying rows its reviewer never
        read. Retracting a root turns a root edition into exactly that, so a
        candidate that is otherwise free still stops at a human attestation.

        Reported apart because those edges are the CHEAPEST work on the board
        and read as blocked-on-nothing without it -- 308/2016-2018 and
        490/2022-1t both materialise byte-identically from their predecessors
        and are one authored line from done.
        """
        return self.root_reason_resolved and self.successor_is_reviewed_without_scope

    @property
    def root_reason_resolved(self) -> bool:
        """Whether this root's stated want-of-lineage reason no longer holds.

        A root declared because the predecessor carried rows with no lineage is
        a statement about the corpus at the moment it was written. Seeding those
        rows makes the statement false, and nothing retracts it: the edition
        still declares an explicit no-predecessor, so the edge stays
        ``dispositioned``, its rows stay out of the migration queue, and the
        completed chaining work is invisible. It is the continuity-side twin of
        a signed coverage disposition whose coordinate an edition now serves.

        Deliberately narrow. Only a root whose REASON cites want of lineage
        qualifies -- a root declared for a lower authority grade or a diverging
        member is not made stale by lineage arriving, and sweeping those in
        would tell the campaign to retire roots that are still correct. Two live
        roots (131 and 165) are exactly that case.
        """
        return self.roots_for_want_of_lineage and not self.predecessor_rows_without_lineage

    @property
    def root_is_open(self) -> bool:
        """Whether this root is recoverable at all, by either route."""
        return self.rooted_pending_lineage or self.rooted_recoverable

    @property
    def chain_reach(self) -> float:
        """The share of the predecessor's rows a chain already reaches, 0.0 to 1.0.

        An edge is not chained or unchained; it is chained to a degree, and the
        degree is what a burn-down needs. Reported beside the raw counts rather
        than instead of them, because a ratio alone hides whether 0.9 means nine
        rows or nine hundred.
        """
        return 0.0 if not self.predecessor_rows else 1 - self.predecessor_rows_without_lineage / self.predecessor_rows


def _roots_for_want_of_lineage(status: EditionStatus) -> bool:
    """Whether an edition's root declaration gives want of lineage as its reason.

    Reads the declared cause first and the wording only as a fallback, matching
    ``_root_kind``: the cause is a code the tool writes, the wording is prose it
    also writes, and a corpus carries both. Checked rather than inferred from
    ``root_kind`` because that classification pools several causes into
    ``root_pending_lineage``, and only this one is retracted by seeding.
    """
    if status.root_cause:
        return status.root_cause == "predecessor_row_without_lineage"
    return _ROOT_PENDING_LINEAGE_MARK in status.root_reason.lower()


def _root_kind(reason: str, cause: str = "") -> str:
    """Classify an explicit no-predecessor root by the cause the tool named.

    An unrecognised cause falls to ``root_recoverable`` rather than to law. A
    root is a declaration that this edition states itself in full, and the only
    reasons that make it permanent are facts about the forms; a wording this
    screen has not seen is far more likely to be a new cause the tool learned to
    report than a new way for the law to forbid inheritance. Defaulting the
    other way is what hid the last two.
    """
    # A DECLARED cause is the authority and ends the question. An unrecognised
    # code still falls to recoverable, but it is a code somebody wrote, so it
    # can be looked up rather than guessed at.
    if cause:
        return _ROOT_KIND_BY_CAUSE.get(cause, "root_recoverable")
    spelled = reason.casefold()
    if _ROOT_PENDING_LINEAGE_MARK in spelled:
        return "root_pending_lineage"
    if any(known in spelled for known in _ROOT_CAUSES_BY_LAW):
        return "root_by_law"
    return "root_recoverable"


#: The fields that ARE the lineage attestation, per the campaign's ruling on the
#: referent: the three continuidad fields and nothing else. `source_refs` and
#: `reviewed_by` are deliberately NOT here -- they are provenance about the row,
#: not the record that its chain was established -- so a row differing in
#: `source_refs` is a different row rather than the same row with a different
#: attestation.
_ATTESTATION_FIELDS: Final = frozenset({"continuidad_id", "continuidad_origin", "continuidad_evidence"})


def _drop_would_lose_attestation(inherited: Mapping[str, Any], stated: Mapping[str, Any]) -> bool:
    """Whether dropping this restated member would destroy a lineage attestation.

    Payload equality here is STRICTER than ``_comparable``. That comparator
    strips ``source_refs``, ``legal_refs`` and the lineage claims before
    comparing, because a row whose references lift to an edition default is
    still droppable for restatement purposes. For this question that is too
    loose: a row differing in ``source_refs`` is a different row, not the same
    row wearing a different attestation, and counting it here would inflate the
    population by rows whose drop loses something other than an attestation.

    So payload is everything except the three attestation fields, and the
    condition is payload equality PLUS an attestation field the inherited member
    does not state IDENTICALLY. That is two populations, not one, and an earlier
    wording of this claimed only the first:

    - the inherited member does not carry the field at all, so a drop DESTROYS
      the attestation. 3,887 rows, and the larger half.
    - both carry it and the values differ, so a drop DOWNGRADES it -- typically
      a ``grounded`` origin with evidence replaced by the predecessor's
      ``seeded``. 399 rows, of which 229 differ in both origin and evidence, 94
      in evidence alone and 76 in origin alone.

    The old wording said a row whose attestation the predecessor also states
    "loses nothing when it goes", which is false for those 399: the weaker
    inherited attestation survives the drop and the stronger stated one does
    not. Both populations need a guard and they are not the same guard -- the
    first must keep the row, the second must decide whether the inherited
    attestation suffices.
    """

    def payload(member: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in member.items() if key not in _ATTESTATION_FIELDS}

    if payload(inherited) != payload(stated):
        return False
    return any(key in stated and stated.get(key) != inherited.get(key) for key in _ATTESTATION_FIELDS)


def _comparable(member: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in member.items() if key not in _RESTATEMENT_KEYS}


def _grounding_lifts(
    inherited: Mapping[str, Any],
    stated: Mapping[str, Any],
    default: tuple[str, ...],
    predecessor_default: tuple[str, ...] = (),
) -> bool:
    """Whether two members' references agree, or the successor's lift to a declared default.

    Payload equality is not droppability. A successor that re-grounds an
    otherwise identical member on its OWN edition's design states something the
    predecessor did not, and a merge cannot supply it -- the drop path found
    zero droppable members on eleven modelos for exactly this reason, because
    the restatement census sets the reference fields aside before comparing.

    References agree when they are equal outright, or when the successor's
    source_refs are the edition's declared family default (optionally followed
    by its own additions), because the lift removes them and what remains is
    equal. Anything else is a genuine per-edition statement.
    """
    for key in ("source_refs", "legal_refs"):
        before, after = _as_refs(inherited.get(key)), _as_refs(stated.get(key))
        if before == after:
            continue
        # The loader compares with the source defaults applied only when BOTH
        # editions declare one; where either side has none, both sides are
        # compared raw. Keying liftability off the successor's default alone
        # agrees with it today and parts on any edge where one side lacks a
        # default, so the same condition is required here.
        if key == "source_refs" and default and predecessor_default and after[: len(default)] == default:
            continue
        return False
    return True


def _materialised_members(
    edition: EditionStatus, by_edition: Mapping[str, EditionStatus], family: str
) -> dict[str, dict[str, Any]]:
    """The members an edition holds for a family once its declared chain is walked.

    The merge follows the canonical family policy: casillas merge by lineage,
    while keyed families supersede by identity in predecessor order, append new
    declarations, and apply identifier retirements. Per-edition/full-copy
    families return exactly what the edition states.
    """
    policy = _family_spec(family)
    if policy is None or not policy.inherited:
        return dict(edition.members.get(family, {}))
    chain: list[EditionStatus] = []
    seen: set[str] = set()
    current: EditionStatus | None = edition
    while current is not None and current.edition not in seen:
        chain.append(current)
        seen.add(current.edition)
        current = by_edition.get(current.predecessor_id) if current.predecessor_id is not None else None
    if policy.inheritance is _inheritance().CASILLA:
        merged: dict[str, dict[str, Any]] = {}
        for member in reversed(chain):
            merged = {key: row for key, row in merged.items() if key not in member.retired_lineages}
            merged.update(member.members.get(_CASILLAS, {}))
        return merged

    merged: dict[str, dict[str, Any]] = {}
    for position, member in enumerate(reversed(chain)):
        stated = member.members.get(family, {})
        if position == 0:
            merged.update(stated)
            continue
        retired = member.retired_family_members.get(family, frozenset())
        next_members: dict[str, dict[str, Any]] = {}
        superseded: set[str] = set()
        for identity, inherited in merged.items():
            if identity in retired:
                continue
            if policy.period_scoped and not _selector_covers_status(member, inherited):
                continue
            replacement = stated.get(identity)
            if replacement is not None:
                next_members[identity] = replacement
                superseded.add(identity)
            else:
                next_members[identity] = inherited
        for identity, replacement in stated.items():
            if identity not in superseded and identity not in next_members:
                next_members[identity] = replacement
        merged = next_members
    return merged


def _selector_covers_status(edition: EditionStatus, member: Mapping[str, Any]) -> bool:
    """Mirror the loader's period-selector test for status-only materialisation."""
    year = member.get("filing_year")
    if isinstance(year, int):
        if edition.selector_years and year not in edition.selector_years:
            return False
        if edition.selector_year_from is not None and year < edition.selector_year_from:
            return False
        if edition.selector_year_to is not None and year > edition.selector_year_to:
            return False
    period = member.get("period")
    token = period.split()[-1].upper() if isinstance(period, str) and period.strip() else None
    periods = edition.periods
    for override_year, override_periods in edition.period_overrides:
        if override_year == year:
            periods = override_periods
            break
    covered = {value.split()[-1].upper() for value in periods if isinstance(value, str) and value.strip()}
    return token is None or not covered or token in covered


def _attestation_risk(
    predecessor: EditionStatus,
    successor: EditionStatus,
    by_edition: Mapping[str, EditionStatus],
) -> None:
    """Name every member whose drop would destroy a lineage attestation.

    Deliberately its OWN pass rather than a branch inside the restatement loop,
    because that loop skips casillas entirely when the successor declares a
    predecessor -- restatement of those belongs to delta_minimality, judged
    through the compiled authority. Sharing the loop meant the on-edge half of
    this measure could never fire for casillas, and every one of the 2,641 rows
    at risk is a casilla. The count would have read zero forever, on a figure
    the campaign had adopted as its floor, with nothing to say it was structural
    rather than earned.

    The attestation question is answerable from the raw tree and is not the
    restatement question, so it does not inherit that handoff.
    """
    for family, key in _schema_families():
        policy = _family_spec(family)
        if key is None or policy is None or not policy.inherited:
            continue
        inherited = _materialised_members(predecessor, by_edition, family)
        for identity, member in successor.members.get(family, {}).items():
            before = inherited.get(identity)
            if before is None or not _drop_would_lose_attestation(before, member):
                continue
            # Split on whether the drop tool can reach the row TODAY. A
            # successor declaring its predecessor inherits now, so the risk is
            # live and that half is the wave's countdown. A none-root inherits
            # nothing, so its rows are at risk only if the root is later
            # retracted -- which is why a retraction must not be followed by an
            # identical-member drop before a lineage-only stub rule exists.
            successor._add(
                "attestation_at_risk_on_edge" if successor.declares_predecessor else "attestation_at_risk_rooted",
                f"{family}/{identity}",
                f"identical to {predecessor.edition} except its lineage attestation "
                "(continuidad_id, continuidad_origin, continuidad_evidence, matched on "
                "continuidad_id against the materialised inherited row); an identical-member "
                "drop would destroy the attestation",
            )


def _restated_members(
    predecessor: EditionStatus,
    successor: EditionStatus,
    by_edition: Mapping[str, EditionStatus],
) -> tuple[tuple[str, int], ...]:
    """Count, per family, the successor's stated members identical to what it would inherit.

    Casillas under a successor that names a predecessor are left to the
    minimality screen. Other keyed families are measured from the canonical
    union; full-copy and per-edition families are not treated as restatement
    debt because omission would not inherit them.
    """
    counts: list[tuple[str, int]] = []
    # Only a DECLARED edge is drop-path work. On an edge whose successor roots
    # away, an identical member is an observation about adjacency, not a member
    # a merge would supply, and putting it in the headline offered work the tool
    # refuses. Counted apart rather than dropped so nothing disappears.
    declared_edge = successor.declares_predecessor
    if declared_edge and successor.members.get(_CASILLAS):
        # Casillas on a declared edge belong to the minimality screen, which
        # decides them through the compiled authority's materialised view. That
        # handoff was silent, so this screen reported ZERO restated casillas for
        # a modelo the loader proves has hundreds -- and while the authority is
        # unavailable, as it has been for most of today, neither screen judges
        # them. A zero is indistinguishable from a measurement that never ran.
        # Stating the handoff as a quantity fixes that without duplicating a
        # rule that would diverge: matching there is by continuidad_id only,
        # with no fallback, and reproducing it here would part from the loader
        # the moment seeding lands.
        # One finding per EDGE carrying the count, not one per member. The ask
        # was a count, and a per-member emission would add roughly ten thousand
        # rows to the persisted findings file on every run -- a measurement
        # nobody reads at that granularity, and large enough to bury the
        # findings that are actionable.
        successor._add(
            "casillas_unmeasured",
            "<edition>",
            f"{len(successor.members[_CASILLAS])} casillas on a declared edge: "
            "restatement is delta_minimality's to judge through the compiled authority",
        )
    for family, key in _schema_families():
        if key is None or family in _per_edition_families() or (family == _CASILLAS and successor.declares_predecessor):
            continue
        policy = _family_spec(family)
        if policy is None or not policy.inherited:
            continue
        if policy.inheritance is _inheritance().CASILLA and successor.declares_predecessor:
            continue
        inherited = _materialised_members(predecessor, by_edition, family)
        # A family the successor declares as stated in full, or empty, by
        # construction is not restatement debt: the corpus has said why it
        # looks that way. Counted apart so the disposition is visible as a
        # quantity rather than disappearing into a silent exclusion.
        dispositioned = family in successor.family_dispositions
        # A second, DIFFERENT exemption. `family_dispositions` says the family is
        # empty by construction; `restated_families` says this edition states the
        # family end to end and the merge does not inherit it here. Neither can
        # express the other -- a none-root would root the whole edition, and a
        # disposition means empty -- so the causes stay apart and the declared
        # cause is carried into the finding rather than flattened.
        restated_family_cause = successor.restated_families.get(family)
        restated = 0
        for identity, member in successor.members.get(family, {}).items():
            before = inherited.get(identity)
            if before is not None and _comparable(before) == _comparable(member):
                restated += 1
                locus = f"{family}/{identity}"
                if dispositioned:
                    successor._add(
                        "member_restated_dispositioned",
                        locus,
                        f"identical to {predecessor.edition}, family stated in full by declaration",
                    )
                    continue
                if restated_family_cause is not None:
                    successor._add(
                        "member_restated_family_declared",
                        locus,
                        f"identical to {predecessor.edition}, but this edition declares {family!r} restated "
                        f"in full (cause {restated_family_cause or 'unstated'}), so the merge does not "
                        "inherit it on this edge",
                    )
                    continue
                successor._add("member_restated", locus, f"identical to {predecessor.edition}")
                # A row stating its own lineage claim is unreproducible by a
                # merge: an inherited row never carries one, so dropping it
                # destroys the claim silently, and the claim is filing-grade.
                # Orthogonal to grounding -- a row can be payload-equal AND
                # references-liftable and still be undroppable for this reason.
                if _LINEAGE_CLAIMS & set(member):
                    successor._add(
                        "member_restated_pinned", locus, f"identical to {predecessor.edition}, states a lineage claim"
                    )
                elif family in _undroppable_families():
                    successor._add(
                        "member_restated_pinned",
                        locus,
                        f"identical to {predecessor.edition}, family inherits conditionally",
                    )
                elif not declared_edge:
                    successor._add(
                        "member_restated_unedged", locus, f"identical to {predecessor.edition}, edge not declared"
                    )
                elif _grounding_lifts(
                    before,
                    member,
                    successor.family_defaults.get(family, ()),
                    predecessor.family_defaults.get(family, ()),
                ):
                    successor._add(
                        "member_restated_payload_equal", locus, f"identical to {predecessor.edition}, refs lift"
                    )
                else:
                    successor._add(
                        "member_restated_grounding",
                        locus,
                        f"identical to {predecessor.edition} but re-grounded on this edition's own references",
                    )
        if restated and not dispositioned and restated_family_cause is None:
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


def _period_overrides(declared: object) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Read a selector's per-year period overrides off the raw manifest table.

    A year an edition overrides serves THAT tuple and not the flat one, so the
    coverage projection must read it here rather than inferring a uniform
    surface the declaration never stated.
    """
    if not isinstance(declared, list):
        return ()
    overrides: list[tuple[int, tuple[str, ...]]] = []
    for entry in declared:
        if not isinstance(entry, dict):
            continue
        year, periods = entry.get("year"), entry.get("periods")
        if isinstance(year, int) and isinstance(periods, list):
            overrides.append((year, tuple(str(period) for period in periods)))
    return tuple(overrides)


def _periods_in_year(status: EditionStatus, year: int) -> tuple[str, ...]:
    """The period surface one edition serves in one filing year.

    ``PeriodSelector.periods_for_year``, reimplemented exactly: a year named by
    an override serves the override's tuple INSTEAD of the flat one, so a
    coordinate the transition year drops is served by neither this edition nor,
    unless another edition states it, any edition -- which is a reportable gap,
    never a silently covered cell.
    """
    for override_year, periods in status.period_overrides:
        if override_year == year:
            return periods
    return status.periods


def _selectors_overlap(left: EditionStatus, right: EditionStatus) -> bool:
    """Whether two editions could both be live -- the parallel-variant case.

    Mirrors ``period_selectors_overlap``: a shared year range AND at least one
    shared period token. Two editions that overlap may be parallel scheme
    variants rather than a sequence, and a predecessor edge between them would
    assert an order the law does not.

    Selectors are year-granular, so a MID-YEAR cutover looks like an overlap
    from here and is not one: 036 closes on 2025-02-02 and its successor opens
    on 2025-02-03, sharing filing year 2025 and every period token while never
    being live at the same moment. Two editions cannot be parallel variants if
    their validity dates never coincide, so the dates settle it before the
    selectors are consulted at all. Without this the screen reported a false
    `parallel_scheme_variants` on exactly the modelo whose split it could not
    see.
    """
    if _validity_windows_disjoint([left, right]):
        return False

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
    overridden = sorted({year for status in (left, right) for year, _ in status.period_overrides})
    if any(
        _admits_year(left, year)
        and _admits_year(right, year)
        and set(_periods_in_year(left, year)) & set(_periods_in_year(right, year))
        for year in overridden
    ):
        return True
    if overridden and left_end is not None and right_end is not None:
        shared = range(max(left_start, right_start), min(left_end, right_end) + 1)
        if {year for year in shared if _admits_year(left, year) and _admits_year(right, year)}.issubset(overridden):
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


#: Editions whose declared export scenario has actually been rendered. Kept in
#: its own file, read raw, because it is EVIDENCE rather than declaration: the
#: scenarios module says a scenario exists, and this says it ran. Eight editions
#: were declared in a single pass while the authority would not compile, which
#: silenced `export_scenario_missing` on every one of them without a byte being
#: emitted. Splitting the two facts makes that suppression impossible to repeat
#: by construction rather than by remembering not to.
_RENDER_EVIDENCE_FILE: Final = Path(__file__).with_name("export_scenario_renders.toml")


@cache
def _rendered_editions() -> frozenset[tuple[str, str]] | None:
    """Every ``(modelo, edition)`` pair a render has actually been observed for.

    ``None`` when the evidence file cannot be read at all, which is unknowable
    rather than empty: an unreadable file must not read as "nothing has ever
    been rendered" and convict every declared scenario.

    An entry whose ``selected_revision`` disagrees with its ``edition`` is NOT
    counted. That combination means the scenario rendered the wrong edition,
    which is a withdrawal, not a proof.
    """
    if not _RENDER_EVIDENCE_FILE.is_file():
        return frozenset()
    try:
        document = tomllib.loads(_RENDER_EVIDENCE_FILE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _note_limitation(f"render_evidence_unreadable: {type(exc).__name__}")
        return None
    rendered: set[tuple[str, str]] = set()
    for entry in document.get("render", ()):
        modelo, edition = str(entry.get("modelo", "")), str(entry.get("edition", ""))
        if not modelo or not edition:
            continue
        if str(entry.get("selected_revision", "")) != edition:
            continue
        if not entry.get("rendered_bytes"):
            continue
        rendered.add((modelo, edition))
    return frozenset(rendered)


@cache
def _scenario_editions(modelo_id: str) -> frozenset[str] | None:
    """The editions the round-trip gate can render export bytes for, or ``None`` when unknowable."""

    # The call is guarded as well as the import. The scenarios module builds its
    # scenarios eagerly from typed models, so a governed fact it depends on going
    # unregistered raises HERE rather than at import, and a guard around the
    # import alone turns an unknowable answer into a crashed screen. This screen
    # reports; it does not gate, and it must keep reporting when a neighbour is
    # mid-edit.
    def load() -> frozenset[str] | None:
        try:
            from ..edition_export_scenarios import edition_export_scenarios

            return frozenset(edition_export_scenarios(modelo_id))
        except Exception as exc:
            _note_limitation(f"export_scenarios_unavailable: {type(exc).__name__}")
            return None

    # Bounded, like the schema vocabulary. This path builds scenarios eagerly
    # from typed models, so it reaches further into the domain than the import
    # alone suggests, and a wedged authority lock makes it hang instead of
    # raise. Unknowable by timeout and unknowable by ImportError are the same
    # answer here -- `None`, a limitation, and no blocker claimed.
    return _within_bound(load, "export_scenarios")


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
    # Only meaningful against a successor that states its rows in full. A
    # successor that DECLARES a predecessor states only its delta, so every
    # inherited lineage it does not restate looks withdrawn -- and all eight
    # such edges were verified false, ~1,601 boxes present in the compiled
    # successors. The cause survives for roots, where the successor really does
    # state everything and a missing lineage really is gone.
    if withdrawn and not successor.declares_predecessor:
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
    # Two different answers that must not coincide. `None` means the scenarios
    # module could not be consulted at all -- unknowable, recorded as a
    # limitation, and no blocker is claimed. An empty set means it WAS consulted
    # and declares no scenario for this modelo, which is a real blocker: the
    # tool cannot compare the successor's bytes and will refuse to apply.
    # `reviewed_against` is required on a reviewed DELTA edition and REFUSED
    # everywhere else. Both halves matter. A reviewed edition that names a
    # predecessor must also name the predecessor its stated rows were reviewed
    # against -- a reviewer's claim about what was actually examined, which
    # nobody migrating the edge can invent, so the edge is not ready work but
    # work that goes back to a reviewer. A successor that declares an explicit
    # no-predecessor root is the refused half: it will never name a predecessor
    # on this edge, and demanding the field there asks for a declaration the
    # schema would reject. Tested the wide way first, and 23 of the 29 findings
    # were exactly that error.
    if (
        successor.review_status == _REVIEWED
        and not successor.reviewed_against
        and not successor.declares_no_predecessor
    ):
        blockers.append(f"reviewed_against_required={successor.edition}")
    scenarios = _scenario_editions(successor.modelo)
    if scenarios is None:
        pass
    elif successor.export_surface and successor.edition not in scenarios:
        # Named so the scenario pass can tick modelos off: an empty set means
        # the modelo is absent from the declared list, not that its scenario was
        # consulted and refused.
        blockers.append(f"export_scenario_missing={successor.modelo}")
    elif successor.export_surface:
        # Declared, but declaration is not proof. The edge stays blocked until a
        # render has actually been observed for THIS edition, so adding a
        # scenario entry can never clear the blocker on its own.
        rendered = _rendered_editions()
        if rendered is not None and (successor.modelo, successor.edition) not in rendered:
            blockers.append(f"export_scenario_unrendered={successor.modelo}")
    return tuple(blockers)


def carried_defaults(statuses: tuple[EditionStatus, ...]) -> None:
    """Name every family default an edition repeats from the edition it succeeds.

    The lift tool propagates a predecessor's derived default onto successors
    that inherit a family's rows without owning any, so materialisation stays
    byte-identical. The default says what the rows were grounded against, and
    carrying it forward carries that grounding with it, so the carried state must
    be countable apart from a default the edition states for itself.

    WHAT THIS CANNOT SAY is whether the carried grounding is stale. Two editions
    sharing a default have two different causes, and they are opposite: the
    successor is grounded on an OLDER design nobody re-grounded, which is
    authoring work, or the successor and its predecessor are grounded on the SAME
    design because one design governs both periods, which is not work and never
    will be. Deciding that needs the design's own devengo window, which lives in
    the source catalogue this screen does not read -- so every fire is a carried
    default and only some are debt. Modelo 210's 2023, 2024 and 2025 editions are
    the second case: one design covers devengos from 2022-06-01 to 2025-12-31 and
    there is nothing to re-ground. Read the count as a population to triage, not
    as a worklist.

    Equality is list equality and order-sensitive, because a default is a
    sequence the loader applies in order, not a set.
    """
    by_edition = {(status.modelo, status.edition): status for status in statuses}
    for status in statuses:
        if not status.declares_predecessor or status.predecessor_id is None:
            continue
        before = by_edition.get((status.modelo, status.predecessor_id))
        if before is None:
            continue
        for family, refs in sorted(status.family_defaults.items()):
            if refs and before.family_defaults.get(family) == refs:
                status._add(
                    "default_carried_from_predecessor",
                    family,
                    f"same default as {status.predecessor_id}: {json.dumps(list(refs))}",
                )


def inline_member_refs(statuses: tuple[EditionStatus, ...]) -> None:
    """Count members still stating ``source_refs`` their family default already gives.

    The member lift moves a family's shared references onto the edition's
    declared default and removes them from each member, which is a real
    convergence that NO existing measure could see: restatement counts
    cross-edition identity, so lifting refs off thousands of members left it
    unmoved and the work looked like it had not happened.

    Counted per edition and family rather than per member. A per-member emission
    would add several thousand rows to the findings file on every run, which is
    the mistake `casillas_unmeasured` was aggregated to undo. Equality is
    order-sensitive list equality, as it is everywhere a default is compared:
    a default is a sequence the loader applies in order, not a set.

    Reads 0 for a family when the lift is complete, which is what makes it a
    burn-down rather than an inventory.
    """
    for status in statuses:
        for family, default in sorted(status.family_defaults.items()):
            if not default or family in _per_edition_families():
                continue
            inline = sum(
                1 for member in status.members.get(family, {}).values() if _as_refs(member.get(_ROW_SOURCE)) == default
            )
            if inline:
                status._add(
                    "member_refs_inline",
                    family,
                    f"{inline} members restate the family default inline: {json.dumps(list(default))}",
                )


def forest_violations(statuses: tuple[EditionStatus, ...]) -> None:
    """Name every modelo whose editions mix a declared chain with silent omission.

    The forest rule is that a modelo's editions form one chain: each either
    names its predecessor or declares an explicit root. A modelo where MORE
    THAN ONE edition simply omits the key while another edition names one is
    neither -- it asserts a chain and leaves holes in it, and the migration tool
    refuses the whole modelo rather than guess which omission was meant. The
    screen showed one such modelo's edge as the cleanest on the board while the
    tool would not touch it.

    A modelo where every edition omits the key is UNDECLARED, not in violation:
    nothing has claimed a chain, so there is no chain to be inconsistent with,
    and the forest validator accepts it. 136, 182, 188, 189 and 345 are in that
    state today. The consequence is that declaring a predecessor on one of them
    is a whole-modelo change — every edition must be declared in the same
    load-verified pass, because the first declaration alone would leave the
    others keyless and turn a loading modelo into a refused one.
    """
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        if status.has_manifest:
            by_modelo[status.modelo].append(status)
    for modelo, editions in sorted(by_modelo.items()):
        silent = [
            status for status in editions if not status.declares_predecessor and not status.declares_no_predecessor
        ]
        # The rule binds once the modelo has made ANY predecessor declaration,
        # a named predecessor OR an explicit none root — not only a named one.
        # A modelo that has declared nothing may carry any number of keyless
        # editions and loads fine; it is UNDECLARED, not in violation. That
        # distinction matters because the first declaration on such a modelo is
        # a whole-modelo change: every edition must be declared in one
        # load-verified pass, or the first one turns a valid modelo invalid.
        declared_anything = any(status.declares_predecessor or status.declares_no_predecessor for status in editions)
        if len(silent) > 1 and declared_anything:
            named = ", ".join(sorted(status.edition for status in silent))
            for status in editions:
                status._add(
                    "predecessor_forest_violation",
                    "<modelo>",
                    f"{modelo}: {len(silent)} editions omit the predecessor key ({named}) while another names one",
                )
                break


#: The declared review status that makes `reviewed_against` mandatory once an
#: edition names a predecessor. Every reviewed edition in the corpus carries
#: this one value today.
_REVIEWED: Final = "agent_reviewed"


def _edges_with_unknowable_scenarios(found_edges: tuple[Edge, ...], statuses: tuple[EditionStatus, ...]) -> int:
    """Edges whose export blocker could not be decided because the scenarios module failed.

    ``_scenario_editions`` returns ``None`` when the scenarios module cannot be
    imported, and the blocker computation then claims nothing -- which is right,
    since unknowable is not absent. The cost is that every edge whose successor
    has an export surface silently loses a possible cause, and the only trace is
    a ``limitation`` line elsewhere in the output. Counting them here puts the
    caveat on the same row as the numbers it qualifies.

    Counts only edges whose SUCCESSOR has an export surface, because that is the
    exact population ``_blockers`` would have judged.
    """
    surfaces = {(status.modelo, status.edition): status.export_surface for status in statuses}
    return sum(
        1
        for edge in found_edges
        if _scenario_editions(edge.modelo) is None and surfaces.get((edge.modelo, edge.successor))
    )


def _modelo_declaration_blockers(editions: list[EditionStatus]) -> tuple[str, ...]:
    """The causes that bind every edge of a modelo rather than any one of them.

    The forest rule is not a per-edge rule. On a modelo where NO edition has
    declared anything, the editions are legally keyless and the modelo loads;
    the moment one edge declares a predecessor, every other edition but one must
    declare too, or the modelo that was loading becomes a modelo the tool
    refuses. So on such a modelo a single edge is not a unit of work at all, and
    calling one ready is how the screen three times named an edge ready that the
    modelo could not load -- most recently 189, whose declaration was applied
    and reverted at net zero.

    The count is the number of editions that must be declared in the SAME
    load-verified pass: all the silent ones but one, since exactly one may
    remain keyless as the chain's root.
    """
    declared_anything = any(status.declares_predecessor or status.declares_no_predecessor for status in editions)
    if declared_anything:
        return ()
    silent = [status for status in editions if not status.declares_predecessor and not status.declares_no_predecessor]
    if len(silent) <= 1:
        return ()
    return (f"whole_modelo_declaration_required={len(silent) - 1}",)


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
        # An edition with no manifest cannot take part in an edge: it has no
        # valid_from to order it and nothing to inherit from or to.
        if status.has_manifest:
            by_modelo[status.modelo].append(status)
    found: list[Edge] = []
    for modelo, editions in sorted(by_modelo.items()):
        by_edition = {status.edition: status for status in editions}
        modelo_blockers = _modelo_declaration_blockers(editions)
        ordered = sorted(editions, key=lambda status: (status.valid_from, status.edition))
        for predecessor, successor in pairwise(ordered):
            predecessor_keys = _materialised_keys(predecessor, by_edition)
            _attestation_risk(predecessor, successor, by_edition)
            blockers: tuple[str, ...] = ()
            root_kind = ""
            if successor.declares_predecessor:
                # A declared edge is not therefore a sound one. Declaring the
                # predecessor silences nothing the tool would still refuse, and
                # two edges reached `migrated` this way while an export scenario
                # was still missing -- the blocker simply left the signal. So
                # the causes are computed here too and a declared edge that
                # still fails one is named apart from a clean migration.
                blockers = _blockers(predecessor, successor, predecessor_keys)
                state = "migrated_unverified" if blockers else "migrated"
            elif successor.declares_no_predecessor:
                state = "dispositioned"
                root_kind = _root_kind(successor.root_reason, successor.root_cause)
                # A root declared FOR WANT OF LINEAGE is a recoverable edge
                # wearing a disposition, and reading the declaration as the end
                # of the question suppresses every cause behind it: the corpus
                # reports no blocker at all while such roots hold thousands of
                # rows no successor can inherit. The causes are computed here so
                # the disposition hides nothing. A root the LAW gives -- a
                # parallel scheme variant, a successor withholding by design --
                # is left alone, because no cause of ours is what stops it.
                if root_kind in {"root_pending_lineage", "root_recoverable"}:
                    blockers = _blockers(predecessor, successor, predecessor_keys)
            else:
                blockers = _blockers(predecessor, successor, predecessor_keys) + modelo_blockers
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
                    roots_for_want_of_lineage=_roots_for_want_of_lineage(successor),
                    successor_is_reviewed_without_scope=(
                        successor.review_status == _REVIEWED and not successor.reviewed_against
                    ),
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
    irreducible: str,
    order_only: str,
) -> None:
    """Bucket one ``source_refs`` statement against the edition default.

    Liftability is tested as a PREFIX, not as containment, because lifting
    rewrites the row to state only what the default does not already say and the
    remainder is what stays behind -- an operation defined on a sequence, not on
    a set.

    That makes one sub-population invisible, so it is measured rather than
    reclassified. A row can hold every ref the default holds and still fail the
    prefix test by listing an addition FIRST; it then reads as irreducible, while
    the catalogue says irreducible means the default plus additions cannot
    reproduce the value. For these it can, in a different order.
    The ``order_only`` kind counts them WITHOUT moving them, and the question it
    was raised to ask has since been answered: ORDER IS SEMANTIC. The lift tool's
    ``_table_lift`` tests a strict prefix and then tests that
    ``dict.fromkeys((*default, *rest))`` reconstructs the authored sequence
    exactly, so the lifted form materialises as default-then-additions in that
    order and nothing else. Lifting one of these would materialise refs in an
    order nobody authored. So the prefix rule here is not this screen's
    conservatism -- it mirrors the tool, and the measurement's value is no longer
    a pending question but a decision input: it names exactly the population that
    moving the lift to set semantics would change, which is not only these
    statements but every already-lifted row. Both the irreducible finding and this
    measurement fire for such a statement on purpose -- the bucket stays correct
    and the population stays visible.

    All four kinds are named by the caller. They were not: the third outcome used
    to be a bool that hardcoded the ROW kinds, so a row's refs reported four
    outcomes and its nested constraints table reported two. 81 constraint
    statements the default cannot reproduce were therefore counted by nothing at
    all, in a family whose catalogue entry says it is "lifted by the same rules".
    A silently discarded third outcome reads as a population that has none.
    """
    if not refs or not status.effective_default:
        return
    default = status.effective_default
    if refs == default:
        status._add(restated, locus, json.dumps(list(refs)))
    elif refs[: len(default)] == default:
        status._add(liftable, locus, json.dumps(list(refs[len(default) :])))
    else:
        status._add(irreducible, locus, json.dumps(list(refs)))
        if set(default) <= set(refs):
            status._add(
                order_only,
                locus,
                f"holds the whole default {json.dumps(list(default))} but not as a prefix",
            )


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


def _retired_family_members(edition_dir: Path, edition_id: str) -> dict[str, frozenset[str]]:
    """Return generic keyed-family identifiers withdrawn by this edition.

    The compiler applies both ``retired`` and ``replaced`` identifier
    evolutions before merging a family.  This raw projection keeps the status
    screen's chain walk aligned without importing compiler internals.
    """
    retired: dict[str, set[str]] = defaultdict(set)
    for path in sorted(edition_dir.rglob("*.toml")):
        table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
        evolutions = table.get("identifier_evolutions") if isinstance(table, dict) else None
        for evolution in evolutions if isinstance(evolutions, list) else ():
            if not isinstance(evolution, dict):
                continue
            family = evolution.get("family")
            identifier = evolution.get("identifier")
            if isinstance(family, str) and isinstance(identifier, str) and evolution.get("to_revision") == edition_id:
                retired[family].add(identifier)
    return {family: frozenset(identifiers) for family, identifiers in retired.items()}


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
    # A directory with no revision.toml is not an edition. It has no
    # valid_from to order it, no authority grade, no predecessor declaration --
    # so it sorts first, screens as `ready` with no cause, and sits at the top
    # of the worklist while the migration tool refuses it outright. That is a
    # half-authored directory being presented as the campaign's next job.
    status.has_manifest = manifest.exists()
    if not status.has_manifest:
        status._add("edition_without_manifest", "<edition>", f"{edition_dir.name} has no {_MANIFEST}")
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
            status.root_cause = str(none.get("cause", "")) if isinstance(none, dict) else ""
            if not status.root_cause:
                # Classified from prose because the declaration carries no code.
                # Reported rather than silent: a wording-classified root is a
                # guess, and two were wrong in opposite directions.
                status._add(
                    "root_kind_by_wording",
                    "<edition>",
                    f"no cause code; classified {_root_kind(status.root_reason)} from the reason text",
                )
        status.export_surface = bool(table.get("export_layouts"))
        # Per-family schema dispositions state that a family is stated in full,
        # or empty, by construction.
        status.family_dispositions = _declared_families(table.get("family_dispositions"))
        status.restated_families = _restated_family_causes(table.get("restated_families"))
        status.declared_default = _as_refs(table.get(_EDITION_SOURCE_DEFAULT))
        status.family_defaults = {
            family: refs for family, key in _family_default_keys().items() if (refs := _as_refs(table.get(key)))
        }
        status.orden = _as_refs(table.get(_EDITION_ORDEN))
        status.valid_from = str(table.get("valid_from", ""))
        status.valid_to = str(table.get("valid_to", ""))
        status.authority_grade = str(table.get("authority_grade", ""))
        status.review_status = str(table.get("review_status", ""))
        status.reviewed_against = str(table.get("reviewed_against", ""))
        raw_attestations = table.get("lineage_attestations")
        if isinstance(raw_attestations, list):
            parsed: list[LineageAttestation] = []
            for raw_attestation in raw_attestations:
                try:
                    if not isinstance(raw_attestation, dict):
                        continue
                    # Registry models are strict and expose refs as tuples;
                    # TOML necessarily supplies arrays as lists.  Apply only
                    # that representation normalization before typed parsing.
                    candidate = {
                        **raw_attestation,
                        "legal_refs": tuple(raw_attestation.get("legal_refs", ())),
                        "source_refs": tuple(raw_attestation.get("source_refs", ())),
                    }
                    parsed.append(LineageAttestation.model_validate(candidate))
                except (TypeError, ValueError):
                    # A raw diagnostic must not upgrade malformed metadata to
                    # grounded evidence.  The validating compiler owns the
                    # refusal detail; this screen simply excludes the claim.
                    status.lineage_attestation_refusals += 1
                    continue
            status.lineage_attestations = tuple(parsed)
        selector = table.get("period_selector")
        if isinstance(selector, dict):
            years = selector.get("years")
            status.selector_years = tuple(int(y) for y in years) if isinstance(years, list) else ()
            year_from, year_to = selector.get("year_from"), selector.get("year_to")
            status.selector_year_from = year_from if isinstance(year_from, int) else None
            status.selector_year_to = year_to if isinstance(year_to, int) else None
            periods = selector.get("periods")
            status.periods = tuple(str(p) for p in periods) if isinstance(periods, list) else ()
            status.period_overrides = _period_overrides(selector.get("period_overrides"))

    rows = _read_rows(edition_dir, edition_id, status)
    status.rows = len(rows)
    status.stated_keys = tuple((str(row.get("id", "<unidentified>")), _lineage_of(row)) for row in rows)
    status.rows_by_id = {str(row["id"]): row for row in rows if isinstance(row.get("id"), str)}
    status.retired_lineages = _retired_lineages(edition_dir, edition_id)
    status.retired_family_members = _retired_family_members(edition_dir, edition_id)
    status.export_surface = status.export_surface or any(
        (edition_dir / name).is_dir() and any((edition_dir / name).glob("*.toml")) for name in _EXPORT_DIRS
    )

    for row in rows:
        if _as_refs(row.get(_ROW_SOURCE)):
            status.rows_stating_source_refs += 1
        constraints = row.get(_CONSTRAINTS)
        if isinstance(constraints, dict):
            status.constraints_tables += 1
    # The tool's own derivation, over the rows as authored: for an unlifted
    # edition the authored row is the row the tool derives from.
    derived, _withheld = edition_source_default(rows) if rows else (None, None)
    status.effective_default = status.declared_default or (derived or ())
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
            irreducible="row_source_refs_irreducible",
            order_only="row_source_refs_order_only",
        )
        constraints = row.get(_CONSTRAINTS)
        if isinstance(constraints, dict):
            _classify_refs(
                status,
                f"{locus}.constraints",
                _as_refs(constraints.get(_ROW_SOURCE)),
                restated="constraints_source_refs_restated",
                liftable="constraints_source_refs_liftable",
                irreducible="constraints_source_refs_irreducible",
                order_only="constraints_source_refs_order_only",
            )
        if status.orden and _as_refs(row.get(_ROW_LEGAL)) == status.orden:
            status._add("row_legal_refs_equal_orden", locus, json.dumps(list(status.orden)))
        if not row.get(_LINEAGE):
            status.rows_without_lineage += 1
            # The finding names ONE edition; chaining the row takes two. A
            # continuation is bilateral -- the successor's claim needs the
            # predecessor row stamped with the same chain, and modelo 100/2024's
            # twelve refusals are exactly that shape: twelve `grounded` origins
            # whose 2023 rows exist and carry no continuidad_id. So a locus here
            # is not an inventory of what a write touches.
            status._add("row_missing_lineage", locus, "no continuidad_id; chaining it also stamps the paired row")
        # ONE finding per row, with the claims it states in the detail. Emitting
        # per CLAIM made this measurement count claims while every other `row_`
        # kind counts rows: 8,409 rows carry a claim, 4,477 of them carry both
        # `continuidad_origin` and `continuidad_evidence`, and the tally read
        # 12,886. A reader taking "row_pinned_by_lineage_claim" as a row count --
        # which is what the name and the rest of the prefix family promise -- was
        # over by 4,477.
        if claims := sorted(_LINEAGE_CLAIMS & set(row)):
            status._add("row_pinned_by_lineage_claim", locus, ", ".join(claims))

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
            if family != _CASILLAS and family not in _per_edition_families() and isinstance(entry.get("id"), str):
                token = edition_token_in_identifier(entry["id"], edition_id)
                if token is not None and not _token_is_member_data(token, entry):
                    status._add("edition_keyed_identifier", entry["id"], f"{family} token={token}")
                span = _ADDRESS_SPAN.search(entry["id"])
                if span is not None and _span_is_address(span.group(0).strip("."), entry):
                    status._add("identifier_is_address", entry["id"], f"{family} span={span.group(0).strip('.')}")
                elif (offset := _bare_offset_in_identifier(entry["id"], entry)) is not None:
                    status._add("identifier_is_address", entry["id"], f"{family} offset={offset}")
        status.members[family] = keyed
        default_key = _family_default_keys().get(family)
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


#: The lineage seeder's ledger, read as raw TOML rather than through its loader.
#: The loader imports the seeder, which imports the domain, and this screen must
#: keep reporting when the domain does not import.
_LEDGER_FILE: Final = Path(__file__).with_name("casilla_lineage_ledger.toml")


@dataclass(frozen=True, slots=True)
class LedgerScope:
    """How much of the campaign's unchained population the seeder's ledger accounts for.

    The ledger's contract is successor rows: for each adjacent pair the seeder
    disposes of every row of the SUCCESSOR. So the two unnamed populations are
    different things and are never pooled.

    ``unclaimed_predecessor`` is a row in a modelo's FIRST edition, which is
    never anyone's successor and therefore outside the ledger by construction.
    It is not a ledger miss. It is a predecessor row that no successor continues
    and no ``retired`` continuity evolution withdraws -- a retirement gap, owned
    by the migration drop path, where the answer is to inherit it or retire it.

    ``declared_root_not_first_edition`` is a row in an edition whose manifest declares an
    explicit no-predecessor. The seeder never judges such a revision at all --
    the domain's predecessor judgement returns none for it, and the totality
    gate skips the whole revision -- so a ledger entry written for one of these
    rows comes back as stale and fails that gate. Counting them as misses read
    as debt and would have produced exactly that bad write.

    ``unclaimed_predecessor`` splits again on whether the seeder has a ledgered
    reason to stand off the modelo. Its ``[[excluded]]`` entries name the
    modelos it will not examine and why; a row in one of those is a wait with a
    stated reason, not backlog, and hand-seeding it would fail the totality gate
    per row. A row in any other modelo is the seeder's next run. Presenting the
    two as one number offered work that cannot be taken.

    ``unnamed_successor`` is a row in a later edition the seeder does judge,
    which the ledger should have named and did not. That one is a genuine miss.

    The distinction is decided from the manifest rather than from the domain.
    This screen reads the raw tree so it keeps reporting when the domain does
    not import, and it therefore cannot call the predecessor judgement -- but it
    does not need to, because the fact that judgement reads is the declaration
    sitting in the TOML. Agreeing with the rule is enough; consulting the
    function is not required.
    """

    unchained_on_edge: int
    named: int
    unclaimed_predecessor: int
    declared_root_not_first_edition: int
    unnamed_successor: int
    unclaimed_predecessor_excluded: int = 0
    unclaimed_predecessor_seedable: int = 0


@dataclass(frozen=True, slots=True)
class LedgerTotality:
    """The lineage totality gate's own verdict, carried on the signal."""

    entries: int
    uncovered: int
    stale: int
    is_total: bool
    stale_modelos: tuple[str, ...]


#: How long any call reaching for the compiled domain may take before the screen
#: gives up on it. Generous enough for a cold corpus compile on a busy machine,
#: short enough that a wedged instrument does not take the whole report with it.
_AUTHORITY_BOUND_SECONDS: Final = 300.0


#: Bound labels that have already overrun once. The bound protects a single
#: call; the screen makes many. `_scenario_editions` is cached PER MODELO, so a
#: corpus-wide report asks it about fifty-eight modelos, and against a wedged
#: authority each one would wait the full bound and leak its own worker --
#: turning a hang into a five-hour hang with fifty-eight leaked threads. The
#: first timeout is the answer for the rest: whatever is wedged is wedged for
#: the whole run, and asking again cannot learn anything the first ask did not.
_BOUND_EXHAUSTED: set[str] = set()


def _within_bound[T](work: Callable[[], T], what: str) -> T | None:
    """Run ``work`` under a time bound, returning ``None`` and a limitation if it overruns.

    A hung instrument says nothing, and that is worse than a refused one: a
    refusal is a fact the reader can act on, while a hang produces no line at
    all and takes every other measurement in the same process with it. Tonight a
    field validator re-entered a non-reentrant authority lock, and every caller
    that validated a revision stopped returning -- silently, including a screen
    run that exited 0 with no output whatsoever.

    The worker thread is left running rather than killed, because Python cannot
    safely kill a thread and a leaked daemon thread is a far smaller cost than a
    report that never prints. The screen's own answer is what matters here, and
    it is honest: unmeasured, with the reason named.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutureTimeout

    if what in _BOUND_EXHAUSTED:
        # Already proven unreachable this run. Returning immediately keeps one
        # wedged dependency from costing the bound once per caller.
        return None
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="delta-status-bound")
    future = executor.submit(work)
    try:
        return future.result(timeout=_AUTHORITY_BOUND_SECONDS)
    except FutureTimeout:
        _BOUND_EXHAUSTED.add(what)
        _note_limitation(
            f"{what}_timed_out: no answer within {_AUTHORITY_BOUND_SECONDS:g}s; treated as unmeasured for the whole run"
        )
        return None
    finally:
        # Never block on a wedged worker -- the whole point is that it may never
        # finish. Shutting down without waiting leaks the thread by design.
        executor.shutdown(wait=False)


def ledger_totality(registry_root: Path, ledger_path: Path | None = None) -> LedgerTotality | None:
    """The totality gate's verdict, or ``None`` when it cannot be asked.

    Computed through ``casilla_lineage_totality.lineage_totality`` rather than
    reimplemented. A second copy of this rule would be a second thing to keep in
    step with the seeder, and the screen has already been burned once by
    carrying its own copy of a rule the tool owns.

    ``None`` is deliberate and is never rendered as zeros. This is the only
    measurement on the screen that needs the compiled domain -- everything else
    reads the raw tree precisely so it keeps reporting while the authority
    refuses -- so it is the one most likely to be unavailable, and a gate that
    reported "uncovered 0, is_total False" because it could not run would be
    indistinguishable from a clean corpus.
    """

    def measure() -> tuple[int, Any]:
        from cadrumo.core.resources.bundled_data import bundled_path
        from cadrumo.domain.calculations.registry.casilla_lineage_totality import lineage_totality

        from ..compiler.authority import compile_registry_tree
        from .casilla_lineage_ledger import load_ledger_refusals

        definitions, _ = compile_registry_tree(registry_root, bundled_path())
        refusals = load_ledger_refusals() if ledger_path is None else load_ledger_refusals(ledger_path)
        return len(refusals), lineage_totality(definitions, tuple(refusals))

    def guarded() -> tuple[int, Any] | None:
        try:
            return measure()
        except Exception as exc:
            _note_limitation(f"lineage_totality_unavailable: {type(exc).__name__}; the totality gate is unmeasured")
            return None

    measured = _within_bound(guarded, "lineage_totality")
    if measured is None:
        return None
    entries, report = measured
    return LedgerTotality(
        entries=entries,
        uncovered=len(report.uncovered),
        stale=len(report.stale),
        is_total=report.is_total,
        stale_modelos=tuple(sorted({key.modelo for key in report.stale})),
    )


#: Per-family materialisation verdicts for demoting a root, written by the
#: session that runs the demotion harness. Read here rather than recomputed: a
#: second copy of that judgement would be a second thing to keep in step, and
#: the screen cannot materialise anything anyway.
_VERDICTS_FILE: Final = Path(__file__).with_name("root_demotion_verdicts.toml")

#: A verdict older than the edition it judges is not a verdict. The harness
#: measures a copy of the corpus at an instant, and editions are rewritten under
#: their own measurement -- one figure moved from 15 to 1 between being measured
#: and being reported. So a verdict whose edition has been written since reads
#: as untested rather than as its recorded outcome.
_VERDICT_UNTESTED: Final = "untested"
_VERDICT_STALE: Final = "stale"


def root_demotion_verdicts(registry_root: Path, path: Path = _VERDICTS_FILE) -> dict[tuple[str, str], str]:
    """Each judged ``(modelo, successor)`` edge mapped to its verdict.

    Returns an empty mapping when the file is absent or unreadable, recording a
    limitation, so a missing artefact never reads as "everything is untested" on
    one run and "everything is proven" on the next.

    A verdict is downgraded to ``stale`` when the successor edition's directory
    has been written since the verdict was measured. That is the whole reason
    ``measured_at`` exists: a verdict is true of the corpus at an instant, and
    treating a superseded one as current is exactly how `root_reason_resolved`
    was wrong in the first place.
    """
    if not path.is_file():
        return {}
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _note_limitation(f"root_demotion_verdicts_unreadable: {type(exc).__name__}")
        return {}
    verdicts: dict[tuple[str, str], str] = {}
    for entry in document.get("verdict", ()):
        modelo, successor = str(entry.get("modelo", "")), str(entry.get("successor", ""))
        verdict = str(entry.get("verdict", ""))
        if not modelo or not successor or not verdict:
            continue
        measured = str(entry.get("measured_at", ""))
        if _edition_written_since(registry_root, modelo, successor, measured):
            verdict = _VERDICT_STALE
        verdicts[(modelo, successor)] = verdict
    return verdicts


def _edition_written_since(registry_root: Path, modelo: str, edition: str, measured_at: str) -> bool:
    """Whether an edition's files are newer than the verdict that judged it.

    Compares real modification times, never a formatted timestamp: sorting
    time-of-day strings once reported a 22:40 file as the newest when the answer
    was 18:28. An unparseable or absent ``measured_at`` counts as superseded,
    because a verdict that will not say when it was taken cannot be shown to be
    current.
    """
    if not measured_at:
        return True
    try:
        taken = datetime.fromisoformat(measured_at).timestamp()
    except ValueError:
        return True
    directory = registry_root / _MODELOS / modelo / _REVISIONS / edition
    if not directory.is_dir():
        return False
    return any(path.stat().st_mtime > taken for path in directory.rglob("*") if path.is_file())


#: Every demotion verdict the signal prints, in a fixed order so a reader
#: pinned to a position keeps it. `untested` and `stale` are first-class: a root
#: nobody has measured and a root whose measurement has been superseded are both
#: unproven, and neither may be read as free.
_DEMOTION_VERDICTS: Final[tuple[str, ...]] = (
    "proven_free",
    "needs_attestation",
    "proven_drifts",
    "refused",
    "stale",
    "untested",
)


def _edge_verdict(edge: Edge, report: Report) -> str:
    """The demotion verdict for a root-demotion candidate, or the empty string.

    Only candidates are judged. An edge whose root reason still holds is not a
    demotion question at all, and giving it a verdict would put roots that are
    still correct into a worklist.
    """
    if not edge.root_reason_resolved:
        return ""
    return report.demotion_verdicts.get((edge.modelo, edge.successor), _VERDICT_UNTESTED)


def ledger_scope(
    statuses: tuple[EditionStatus, ...],
    found_edges: tuple[Edge, ...],
    path: Path = _LEDGER_FILE,
) -> LedgerScope | None:
    """Measure the campaign's unchained rows against the seeder ledger's coverage.

    Returns ``None`` when the ledger cannot be read, recording a limitation, so
    an unreadable ledger never renders as a ledger that accounts for nothing.
    """
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        rows = document.get("refusal", ())
        named = {(row["modelo"], row["revision"], row["casilla"]) for row in rows}
        # Read from the ledger's own declaration rather than by importing the
        # seeder, which would take the domain import this screen exists without.
        excluded = {str(entry["modelo"]) for entry in document.get("excluded", ()) if "modelo" in entry}
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        _note_limitation(f"lineage_ledger_unreadable: {type(exc).__name__}; ledger coverage is unmeasured")
        return None
    predecessors = {(edge.modelo, edge.predecessor) for edge in found_edges}
    successors = {(edge.modelo, edge.successor) for edge in found_edges}
    counted = first_edition = outside = later = 0
    excluded_rows = seedable_rows = 0
    for status in statuses:
        key = (status.modelo, status.edition)
        if key not in predecessors:
            continue
        for finding in status.findings:
            if finding.kind != "row_missing_lineage":
                continue
            counted += 1
            if (status.modelo, status.edition, finding.locus) in named:
                continue
            if key not in successors:
                first_edition += 1
                if status.modelo in excluded:
                    excluded_rows += 1
                else:
                    seedable_rows += 1
            elif status.declares_no_predecessor:
                outside += 1
            else:
                later += 1
    return LedgerScope(
        unchained_on_edge=counted,
        named=counted - first_edition - outside - later,
        unclaimed_predecessor=first_edition,
        declared_root_not_first_edition=outside,
        unnamed_successor=later,
        unclaimed_predecessor_excluded=excluded_rows,
        unclaimed_predecessor_seedable=seedable_rows,
    )


def projected_sources(
    statuses: tuple[EditionStatus, ...], promised_years: tuple[int, ...]
) -> frozenset[tuple[str, str]]:
    """Every edition a projected year would be answered from.

    The source is the revision admitting the greatest covered year strictly
    below the projected one, which is what makes the projected edge's
    PREDECESSOR side this edition. Its rows are the rows a projected resolution
    would carry forward, so a chain missing here stops asserting nothing the
    moment projection ships.
    """
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    sources: set[tuple[str, str]] = set()
    for modelo, editions in by_modelo.items():
        for year in promised_years:
            if any(_admits_year(status, year) for status in editions) or not _projects_year(editions, year):
                continue
            below = [
                (found, status)
                for status in editions
                if (found := _earliest_admitted_year(status)) is not None and found < year
            ]
            if below:
                sources.add((modelo, max(below, key=lambda pair: pair[0])[1].edition))
    return frozenset(sources)


def _identifier_stem(identifier: str, token: str) -> str:
    """The identifier with one edition token removed and the seam closed.

    Two ids share a stem when they are the same name but for that token, which
    is what makes a sibling spelling proof that the token is decoration.
    """
    for separator in ("-", ".", ":"):
        for form in (f"{separator}{token}{separator}", f"{separator}{token}"):
            if form in identifier:
                return identifier.replace(form, separator if form.endswith(separator) else "", 1)
    return identifier


def foreign_edition_tokens(statuses: tuple[EditionStatus, ...]) -> None:
    """Name every member id carrying the key of a DIFFERENT edition of its modelo.

    ``edition_keyed_identifier`` looks only for an edition's own token, so an id
    naming a sibling edition passes it silently. That case is worse, not better:
    the token carries no information the containing directory does not already
    give, AND it names the wrong edition, so id-keyed inheritance keeps two
    members for one field under a name that points somewhere else.

    Runs after the scan because an edition cannot know its siblings' keys.
    Exempt, as in the own-token detector, when the year is the member's own
    datum rather than an edition reference.
    """
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    for editions in by_modelo.values():
        keys = {status.edition for status in editions}
        # Every spelling each family carries anywhere in the modelo, so a stem
        # can be tested for a sibling that spells it without this token.
        spellings: dict[str, set[str]] = defaultdict(set)
        for status in editions:
            for family, members in status.members.items():
                spellings[family].update(members)
        for status in editions:
            foreign = keys - {status.edition}
            for family, members in status.members.items():
                if family == _CASILLAS or family in _per_edition_families():
                    continue
                for identity, member in members.items():
                    for other in sorted(foreign):
                        token = edition_token_in_identifier(identity, other)
                        if token is None or _token_is_member_data(token, member):
                            continue
                        # Structural test, not semantic. The token is an EDITION
                        # REFERENCE only when a sibling of the same family spells
                        # the same stem without it — that sibling is the proof
                        # the stem is the real name and the token decoration.
                        # With no sibling the year is CONTENT: modelo 100's
                        # `...-negativa-general-2024-aplicada-maxima` names the
                        # ejercicio the base came from, nothing else spells that
                        # concept, and there is no stale reference to fix.
                        stem = _identifier_stem(identity, token)
                        twins = sorted(
                            other_id
                            for other_id in spellings[family]
                            if other_id != identity and _identifier_stem(other_id, token) == stem
                        )
                        if twins:
                            status._add(
                                "foreign_edition_token",
                                identity,
                                f"{family} names edition {other} (token={token}); "
                                f"sibling {twins[0]} carries the same stem",
                            )
                        else:
                            status._add(
                                "year_token_as_content",
                                identity,
                                f"{family} carries {token} with no sibling spelling; the year is content",
                            )
                        break


def scope_lineage_findings(
    statuses: tuple[EditionStatus, ...],
    found_edges: tuple[Edge, ...],
    sources: frozenset[tuple[str, str]] = frozenset(),
) -> None:
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
        missing = [item for item in status.findings if item.kind == "row_missing_lineage"]
        for finding in missing:
            status._add(scope, finding.locus, finding.detail)
        if key in sources:
            for finding in missing:
                status._add("row_missing_lineage_on_projected_edge", finding.locus, finding.detail)


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
    #: Each judged ``(modelo, successor)`` root demotion mapped to its verdict,
    #: with any verdict older than the edition it judges downgraded to ``stale``.
    demotion_verdicts: Mapping[tuple[str, str], str] = field(default_factory=dict)


def unconsulted_verdicts(
    statuses: tuple[EditionStatus, ...], found_edges: tuple[Edge, ...], verdicts: Mapping[tuple[str, str], str]
) -> None:
    """Measure every signed demotion verdict that no edge will ever consult.

    ``_edge_verdict`` answers only for a CANDIDATE -- an edge whose root reason is
    resolved -- because giving a verdict to a root that still holds would put a
    correct root into a worklist. That gate is right and it is silent: a verdict
    whose edge stopped being a candidate is read by nobody, and nothing says so.
    Six of the corpus's thirteen are in that state, nearly half the file, each
    carrying a reviewer's judgement on a question no longer being asked.

    THE DOMINANT CAUSE IS CONCORDANCE, not staleness and not misfiling. The
    harness records a verdict for every edge it measures, candidate or not,
    because an unmeasured edge and a measured-then-refused edge are different
    states worth distinguishing. So a verdict saying "this edge cannot be demoted"
    sitting on a root whose reason STILL HOLDS is the verdict and the root
    agreeing: there is nothing to adjudicate, and nothing consulting it is
    correct. Five of the corpus's six are that case -- authored
    ``proven_drifts`` on editions whose ``official_structure_differs`` reason is
    permanent -- and the sixth is a ``refused`` agreeing with a root that holds.
    The file is therefore a MEASUREMENT LOG rather than a worklist, and about half
    of it will always be concordant and unread.

    Two other causes are possible and this does not distinguish them: the root
    reason held again AFTER the verdict was measured, which is staleness the
    ``measured_at`` check structurally cannot see; or the verdict was written for
    an edge that was never a candidate. So read a row here as "no edge asks this
    question", never as "this verdict is wrong".

    Judged only for editions this scan actually READ. The verdicts file is global
    while the scan may be scoped, and a verdict for an unscanned modelo has no
    edges here at all -- so including it would report the scope of the scan rather
    than the state of the corpus.
    """
    scanned = {(status.modelo, status.edition) for status in statuses}
    candidates = {(edge.modelo, edge.successor) for edge in found_edges if edge.root_reason_resolved}
    by_edition = {(status.modelo, status.edition): status for status in statuses}
    for (modelo, successor), verdict in sorted(verdicts.items()):
        if (modelo, successor) not in scanned or (modelo, successor) in candidates:
            continue
        status = by_edition[(modelo, successor)]
        # The value is the LOADED one. `root_demotion_verdicts` downgrades a
        # verdict whose edition was written since `measured_at` to `stale`, so the
        # file's own word is often different -- five of these read `stale` here
        # and `proven_drifts` in the file. Quoting the loaded value without
        # saying so attributes to the reviewer a verdict they did not write.
        status._add(
            "root_demotion_verdict_unconsulted",
            successor,
            f"verdict {verdict!r} as loaded (the file's own value may differ) stands on an edge whose "
            "root reason is not resolved, so no edge consults it",
        )


def build_report(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> Report:
    """Scan a registry root and derive its edges and coverage gaps."""
    statuses = scan_registry(registry_root, modelo_ids=modelo_ids)
    promised = supported_filing_years(registry_root)
    found_edges = edges(statuses)
    forest_violations(statuses)
    carried_defaults(statuses)
    inline_member_refs(statuses)
    foreign_edition_tokens(statuses)
    scope_lineage_findings(statuses, found_edges, projected_sources(statuses, promised))
    judged = root_demotion_verdicts(registry_root)
    unconsulted_verdicts(statuses, found_edges, judged)
    return Report(
        demotion_verdicts=judged,
        statuses=statuses,
        promised_years=promised,
        gaps=coverage_gaps(
            statuses,
            promised,
            load_coverage_dispositions(),
            pending_ejercicio_ordenes(registry_root),
            _legal_publication_years(registry_root),
            # The dispositions file is global; a scoped scan cannot judge an entry
            # naming a modelo it did not read. Only an unscoped scan of the bundled
            # tree can, so only it asks.
            whole_corpus=not modelo_ids and registry_root.resolve() == _bundled_registry_root().resolve(),
        ),
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
    # An unreadable promise must never render as a promise of nothing. With no
    # promised years `coverage_gaps` returns early and every coverage condition
    # prints zero -- a clean bill of health emitted precisely when the screen
    # could not read what it measures against. Each path says so instead, so
    # `missing` and `proven zero` stay distinguishable on the coverage line.
    if not path.is_file():
        _note_limitation("promise_absent: no supported-filing-years declaration; coverage is unmeasured")
        return ()
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(_SUPPORTED_YEARS_KEY, {})
    floor, horizon = table.get("floor"), table.get("horizon")
    if not isinstance(floor, int) or not isinstance(horizon, int):
        _note_limitation("promise_bounds_unparsable: floor and horizon are not both integers; coverage is unmeasured")
        return ()
    if horizon < floor:
        _note_limitation(f"promise_bounds_inverted: horizon {horizon} precedes floor {floor}; coverage is unmeasured")
        return ()
    return tuple(range(floor, horizon + 1))


#: A modelo's own manifest, which carries facts about the FORM rather than
#: about any one edition of it.
_MODELO_MANIFEST: Final = "manifest.toml"
_PENDING_ORDENES: Final = "pending_ejercicio_ordenes"
_LEGAL_DIR: Final = "legal"


@dataclass(frozen=True, slots=True)
class PendingOrden:
    """A declaration that a promised year has no approving Orden yet.

    An annual modelo on a per-ejercicio re-approval chain cannot answer a filing
    year until the Orden approving that ejercicio is published, which happens in
    the following spring. That is not a gap anyone can close by authoring: the
    authority does not exist yet. So the coordinate is reported as
    ``awaiting_ejercicio_orden`` and counted as disposed rather than as a hole.

    The danger is that such a declaration outlives its own reason and becomes a
    permanent excuse. ``stale`` is the guard: once the catalogue carries an
    Orden published in or after the year this declaration says to wait for, the
    wait is over, and the declaration is reported as a finding instead of
    disposing of anything.
    """

    modelo: str
    filing_year: int
    cadence: str
    rests_on: str
    expected_publication_year: int


def pending_ejercicio_ordenes(registry_root: Path) -> dict[tuple[str, int], PendingOrden]:
    """Read every ``[[modelo.pending_ejercicio_ordenes]]`` declaration, keyed by coordinate.

    Read off the raw manifest for the same reason every other fact here is: the
    screen must keep reporting when the domain cannot be imported, and the
    declaration is a TOML table before it is a typed model.
    """
    found: dict[tuple[str, int], PendingOrden] = {}
    modelos_root = registry_root / _MODELOS
    if not modelos_root.is_dir():
        return found
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        manifest = modelo_dir / _MODELO_MANIFEST
        if not manifest.is_file():
            continue
        declared = tomllib.loads(manifest.read_text(encoding="utf-8")).get("modelo", {})
        for entry in declared.get(_PENDING_ORDENES, ()) if isinstance(declared, dict) else ():
            year, expected = entry.get("filing_year"), entry.get("expected_publication_year")
            if not isinstance(year, int) or not isinstance(expected, int):
                continue
            found[(modelo_dir.name, year)] = PendingOrden(
                modelo=modelo_dir.name,
                filing_year=year,
                cadence=str(entry.get("approval_cadence", "")),
                rests_on=str(entry.get("rests_on", "")),
                expected_publication_year=expected,
            )
    return found


@cache
def _legal_publication_years(registry_root: Path) -> tuple[int, ...]:
    """Every year an Orden in the legal catalogue was published in.

    Used only to decide whether an awaited Orden has since arrived. Read raw,
    like everything else here, and cached because the catalogue is large and the
    answer does not change within a run.
    """
    years: set[int] = set()
    legal = registry_root / _LEGAL_DIR
    if not legal.is_dir():
        return ()
    for path in sorted(legal.glob("*.toml")):
        for entry in tomllib.loads(path.read_text(encoding="utf-8")).get("legal", {}).values():
            if not isinstance(entry, dict) or entry.get("kind") != "orden":
                continue
            published = entry.get("published_at")
            if hasattr(published, "year"):
                years.add(published.year)
    return tuple(sorted(years))


def _pending_orden_is_stale(pending: PendingOrden, published_years: tuple[int, ...]) -> bool:
    """Whether the Orden this declaration waits for has since been published.

    A suppression that outlives its reason is worse than no suppression, because
    it reads as adjudicated. The declaration names the year it expects the Orden
    in; once the catalogue carries an Orden from that year or later, the wait it
    describes is over and the declaration must stop disposing of anything.
    """
    return any(year >= pending.expected_publication_year for year in published_years)


def _earliest_admitted_year(status: EditionStatus) -> int | None:
    """The first filing year this edition admits, or ``None`` when it admits none.

    Used only to decide whether a modelo has coverage BELOW a year, which is the
    clause that separates a trailing-edge gap a projection can answer from a
    leading-edge gap it must refuse.
    """
    if status.selector_years:
        return min(status.selector_years)
    return status.selector_year_from


def _projects_year(editions: list[EditionStatus], year: int) -> bool:
    """Whether a modelo's declared reach projects forward into an unadmitted year.

    The predicate, forward only: the year is inside the promised span, no
    revision admits it, and at least one covered year lies STRICTLY BELOW it, so
    the newest revision below can be carried forward. A gap with no coverage
    beneath it is a leading-edge gap -- the modelo had not started -- and
    applying a later design to an earlier period would be wrong as law, so
    projection refuses it rather than reaching backwards. There is no backward
    mode and ties cannot arise, because the source is a strict maximum below.
    """
    earliest = [found for status in editions if (found := _earliest_admitted_year(status)) is not None]
    return bool(earliest) and min(earliest) < year


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


#: The classifications that CLOSE a coordinate rather than describing it,
#: mirrored from the declaration's own vocabulary so the two cannot disagree.
_CLOSING_CLASSIFICATIONS: Final = frozenset({"inception"})

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
    classification: str = ""

    @property
    def classified(self) -> bool:
        """Whether a signed declaration says what this gap IS."""
        return bool(self.classification)

    @property
    def disposed(self) -> bool:
        """Whether a declaration CLOSES this gap, rather than merely naming it.

        An ``awaiting_ejercicio_orden`` coordinate closes on its own kind: the
        Orden approving that ejercicio does not exist, so no authoring reaches
        it and no signature is needed to say so. A declaration whose Orden has
        since been published closes nothing -- it is the finding.

        A gap can be legitimate -- a modelo that did not legally exist in a
        promised filing year has a gap no authoring will ever serve -- and only
        that kind closes. A gap classified ``unauthored`` is the opposite: the
        modelo existed and nobody wrote the revision, so naming it is progress
        and closing it would report the corpus's own debt as resolved. The two
        refuse identically in the corpus, which is exactly why the screen must
        not pool them.
        """
        return self.kind == "awaiting_ejercicio_orden" or self.classification in _CLOSING_CLASSIFICATIONS


def _validity_windows_disjoint(editions: list[EditionStatus]) -> bool:
    """Whether every one of these editions is valid over a period none of the others covers.

    Two editions admitting one filing year is NOT double service when their
    validity DATES do not overlap. A mid-year cutover is exactly that shape:
    036 closes on 2025-02-02 and its successor opens on 2025-02-03, so filing
    year 2025 is admitted by both selectors and served by whichever edition
    covers the event's date. Selection resolves it on a reference date, and
    narrowing the predecessor's `year_to` to make the screen quiet would
    silently misroute the 33 days of censal events that fall before the
    cutover -- so the registry is right and this rule is what was wrong.

    An edition with no `valid_to` is open-ended and overlaps everything after
    its start, which is why absence is treated as unbounded rather than as a
    window that happens to end.
    """
    windows: list[tuple[str, str]] = []
    for edition in editions:
        if not edition.valid_from:
            # Without a start there is no window to compare, and guessing one
            # would manufacture a disjointness nobody declared.
            return False
        windows.append((edition.valid_from, edition.valid_to or _OPEN_ENDED))
    windows.sort()
    return all(earlier[1] < later[0] for earlier, later in pairwise(windows))


#: Coverage kinds that describe a DISPOSITION rather than a coverage failure.
#: Nobody signs for one, so one can never be the kind a signature mismatches
#: against, and a pass that compared them would report its sibling's findings.
#: Kinds that describe a DISPOSITION rather than a coordinate. They travel in
#: ``Report.gaps`` because they are found by the same passes, but they are not
#: coverage: a coordinate can carry one of these while being perfectly served,
#: and counting one as classified or unclassified debt attributes a reviewer's
#: stale paperwork to the authoring backlog.
_SYNTHETIC_COVERAGE_KINDS: Final = frozenset(
    {
        "disposition_coordinate_served",
        "disposition_kind_mismatched",
        "disposition_kind_superseded",
        "disposition_coordinate_unreachable",
    }
)


def _mismatched_dispositions(
    dispositions: Mapping[CoverageCoordinate, CoverageDisposition] | None,
    gaps: list[CoverageGap],
) -> list[CoverageGap]:
    """Name every signed disposition whose coordinate is still a gap of a DIFFERENT kind.

    A disposition names the kind it disposes of, so an entry written for an
    unserved year cannot silently absorb the opposite failure if the corpus
    later serves that cell twice. That check is right, and its consequence is
    silent: the entry simply stops applying, the coordinate reads unclassified,
    and the signature sits in the file describing a failure that is no longer
    the one occurring.

    That is the same species as a disposition whose coordinate is now served --
    a signed statement the corpus has falsified -- but it is invisible to that
    measure, because the coordinate IS still a gap. It just is not the gap
    somebody signed for.

    Two outcomes, and pooling them prices the remedy wrong. Where the new kind is
    one the loader accepts, the signature is REPAIRABLE: rewrite ``kind`` and the
    entry applies again. Where the new kind is one the loader refuses --
    ``promised_year_projected``, ``awaiting_ejercicio_orden`` and
    ``pending_orden_declaration_stale``, excluded there by an explicit ruling --
    no value of ``kind`` can ever make the entry apply, so the signature is
    SUPERSEDED rather than falsified. Its reason may well still be true; what has
    gone is the kind field, because the screen learned a better classification
    for the coordinate than the one that existed when somebody signed it. The
    remedy is to re-home the reasoning and retire the entry, never to rewrite a
    kind into a shape the loader will reject.
    """
    if not dispositions:
        return []
    outstanding = {(gap.modelo, gap.filing_year, gap.period): gap.kind for gap in gaps}
    found: list[CoverageGap] = []
    for coordinate, disposition in sorted(dispositions.items()):
        kind = outstanding.get(coordinate)
        if kind is None or kind == disposition.kind or kind in _SYNTHETIC_COVERAGE_KINDS:
            continue
        repairable = kind in DISPOSABLE_KINDS
        detail = (
            f"but this coordinate now fails as {kind}, so the signature does not apply"
            if repairable
            else f"but this coordinate now fails as {kind}, which no disposition may sign, "
            "so no rewrite makes the signature apply"
        )
        found.append(
            CoverageGap(
                coordinate[0],
                "disposition_kind_mismatched" if repairable else "disposition_kind_superseded",
                coordinate[1],
                coordinate[2],
                (),
                f"signed {disposition.classification} for {disposition.kind}, {detail}",
            )
        )
    return found


def _served_dispositions(
    statuses: tuple[EditionStatus, ...],
    promised_years: tuple[int, ...],
    dispositions: Mapping[CoverageCoordinate, CoverageDisposition] | None,
) -> list[CoverageGap]:
    """Name every signed disposition whose coordinate an edition now serves.

    A disposition says a coordinate is legitimately unserved. Authoring an
    edition that serves it does not remove the signature, and nothing linked the
    two: 036/2023 and 036/2024 sat signed `unauthored` beside the edition
    serving them until somebody read both files by hand. That is a stale
    declaration asserting a gap the corpus has closed, and it is worse than an
    unclassified gap because it carries a reviewer's name.

    Derived by subtraction: a disposed coordinate inside the promise that is NOT
    Servedness is asked of the EDITIONS directly, never derived by subtracting
    the gaps this run found. Subtraction was the first implementation and it was
    wrong: a period nothing declares never enters the period denominator, so no
    gap is emitted for it, and "no gap" then read as "served". That convicted
    four true 303 dispositions -- 0A signed for 2022, 2023, 2024 and 2026 --
    when no 303 edition admits 0A in any year. Absence of a gap is not evidence
    of coverage.

    A disposition naming a period is served only when an edition admits THAT
    period in that year; ``*`` covers a whole year and is served when any
    edition admits the year at all.
    """
    if not dispositions:
        return []
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        if status.has_manifest:
            by_modelo[status.modelo].append(status)
    found: list[CoverageGap] = []
    for coordinate, disposition in sorted(dispositions.items()):
        modelo, year, period = coordinate
        editions = by_modelo.get(modelo)
        if not editions or year not in promised_years:
            continue
        admitting = [edition for edition in editions if _admits_year(edition, year)]
        if period == "*":
            served = bool(admitting)
        else:
            served = any(period in _periods_in_year(edition, year) for edition in admitting)
        if not served:
            continue
        found.append(
            CoverageGap(
                modelo,
                "disposition_coordinate_served",
                year,
                period,
                (),
                f"signed {disposition.classification} for {disposition.kind}, but an edition now serves it",
            )
        )
    return found


def _unreachable_dispositions(
    statuses: tuple[EditionStatus, ...],
    promised_years: tuple[int, ...],
    dispositions: Mapping[CoverageCoordinate, CoverageDisposition] | None,
    *,
    whole_corpus: bool,
) -> list[CoverageGap]:
    """Name every signed disposition whose coordinate this screen cannot even ask about.

    ``_served_dispositions`` drops two cases on the floor before it can judge
    them: a disposition naming a modelo with no manifest, and one naming a
    filing year outside the promise. Both are invisible -- the entry loads, the
    loader accepts it, and no pass ever reaches it -- so a mistyped modelo
    directory or a year the promise has since moved past leaves a reviewer's
    signature governing nothing, forever, silently.

    ONLY ANSWERABLE ON A WHOLE-CORPUS SCAN, which is why the caller must say so.
    The dispositions file is global while a scan may be scoped to one modelo or
    run against a copied subtree, and then "no modelo of that id carries a
    manifest" is true of every other modelo in the file and says nothing about
    the entry. Scoped to modelo 100, an ungated check reported all 41 other
    signatures as unreachable; against a fixture tree with its own promise it
    also convicted every year outside that promise. A question the caller cannot
    answer must not be asked, so the default is silence.

    Only the MODELO and the YEAR are tested, never the period. A period absent
    from a modelo's denominator is legitimate and permanent: 303 is signed at
    ``0A`` for four years because no 303 edition admits ``0A`` in any year, and
    the entries are correct. Testing reachability by period would convict them
    and would re-introduce exactly the subtraction error
    ``_served_dispositions`` documents.
    """
    if not dispositions or not whole_corpus:
        return []
    known = {status.modelo for status in statuses if status.has_manifest}
    promised = set(promised_years)
    found: list[CoverageGap] = []
    for coordinate, disposition in sorted(dispositions.items()):
        modelo, year, period = coordinate
        if modelo not in known:
            cause = "no modelo of that id carries a manifest"
        elif year not in promised:
            cause = f"filing year outside the promise {min(promised)}-{max(promised)}" if promised else "no promise"
        else:
            continue
        found.append(
            CoverageGap(
                modelo,
                "disposition_coordinate_unreachable",
                year,
                period,
                (),
                f"signed {disposition.classification} for {disposition.kind}, but {cause}",
            )
        )
    return found


def coverage_gaps(
    statuses: tuple[EditionStatus, ...],
    promised_years: tuple[int, ...],
    dispositions: Mapping[CoverageCoordinate, CoverageDisposition] | None = None,
    pending: Mapping[tuple[str, int], PendingOrden] | None = None,
    published_years: tuple[int, ...] = (),
    *,
    whole_corpus: bool = False,
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

    def _disposition(modelo: str, kind: str, year: int, period: str) -> tuple[str, str]:
        """The signed reason and classification for this coordinate, when one classifies this KIND.

        The kind is checked as well as the coordinate: an entry written for an
        unserved year must not silently absorb the opposite failure should the
        corpus later serve that cell twice.
        """
        entry = signed.get((modelo, year, period))
        return (entry.reason, entry.classification) if entry is not None and entry.kind == kind else ("", "")

    gaps: list[CoverageGap] = []
    for modelo, editions in sorted(by_modelo.items()):
        periods = sorted(
            {period for edition in editions for period in edition.periods}
            | {period for edition in editions for _, override in edition.period_overrides for period in override}
        )
        if not periods:
            continue
        for year in promised_years:
            admitting = [edition for edition in editions if _admits_year(edition, year)]
            if not admitting:
                # A year no revision admits is not automatically unserved. Where
                # the modelo has coverage below it, the newest revision carries
                # forward and the year is ANSWERABLE; counting that as a gap
                # would report work nobody owes. The two are reported as
                # separate conditions and never pooled, because one is a
                # resolution mode and the other is a hole.
                # Three ways a year no revision admits can fail to be a hole,
                # and they are decided in this order because each is stronger
                # than the next. An Orden that does not exist yet cannot be
                # authored around, so it wins outright -- unless the Orden has
                # since been published, in which case the declaration is the
                # finding. Otherwise a year with coverage below it carries
                # forward. Only what survives both is unserved.
                waiting = (pending or {}).get((modelo, year))
                if waiting is not None and _pending_orden_is_stale(waiting, published_years):
                    kind = "pending_orden_declaration_stale"
                elif waiting is not None:
                    kind = "awaiting_ejercicio_orden"
                elif _projects_year(editions, year):
                    kind = "promised_year_projected"
                else:
                    kind = "promised_year_unserved"
                gaps.append(CoverageGap(modelo, kind, year, "*", (), *_disposition(modelo, kind, year, "*")))
                continue
            for period in periods:
                serving = tuple(edition.edition for edition in admitting if period in _periods_in_year(edition, year))
                if not serving:
                    kind = "promised_coordinate_unserved"
                    gaps.append(CoverageGap(modelo, kind, year, period, (), *_disposition(modelo, kind, year, period)))
                elif len(serving) > 1 and not _validity_windows_disjoint(
                    [edition for edition in admitting if edition.edition in serving]
                ):
                    kind = "coordinate_served_twice"
                    gaps.append(
                        CoverageGap(modelo, kind, year, period, serving, *_disposition(modelo, kind, year, period))
                    )
    # Order matters and the mismatch pass must NOT see the served ones. Both
    # passes append synthetic gaps describing a disposition rather than a
    # coverage failure, and a served coordinate's synthetic kind
    # (`disposition_coordinate_served`) differs from the kind somebody signed --
    # so running the mismatch pass over the extended list reports every served
    # disposition a second time as kind-mismatched. Judged against the real
    # coverage gaps only.
    mismatched = _mismatched_dispositions(dispositions, gaps)
    gaps.extend(_served_dispositions(statuses, promised_years, dispositions))
    gaps.extend(_unreachable_dispositions(statuses, promised_years, dispositions, whole_corpus=whole_corpus))
    gaps.extend(mismatched)
    return tuple(gaps)


#: The shape actions this screen's findings resolve to, in campaign order:
#: restatement lifting is independent and can start at once; lineage and export
#: scenarios each unblock edges; migration is what they unblock. Coverage is
#: printed for orientation and is another campaign's action.
_ACTIONS: Final[tuple[str, ...]] = (
    "lift_restatement",
    "seed_lineage",
    "inherit_member_above_floor",
    "declare_export_scenario",
    "render_export_scenario",
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
    "export_scenario_unrendered",
    "whole_modelo_declaration_required",
    "reviewed_against_required",
)

#: Edge states, in the order the signal always prints them.
_EDGE_STATES: Final[tuple[str, ...]] = (
    "migrated",
    "migrated_unverified",
    "ready",
    "blocked",
    "dispositioned",
)


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
    edges_rooted_recoverable: int = 0

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
            + self.edges_rooted_recoverable
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
        rooted_recoverable = sum(1 for edge in edges_by_modelo[modelo] if edge.rooted_recoverable)
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
                edges_rooted_recoverable=rooted_recoverable,
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
                "edges_rooted_recoverable": signal.edges_rooted_recoverable,
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
        if edge.state == "blocked" or edge.root_is_open
        for blocker in edge.blockers
    )
    lines = [
        # The measurement's own version, bumped whenever a condition is added,
        # split, renamed, or has its population changed. A reader diffing two
        # runs can then tell a CORPUS change from a MEASUREMENT change without
        # remembering which is which: if this line moved, the instrument moved,
        # and a value that shifted alongside it may have shifted for that reason
        # alone. Three metrics were misread as progress or decay today for want
        # of exactly this.
        f"# edition_delta_status schema={_SIGNAL_SCHEMA} conditions={len(CONDITIONS)} measurements={len(MEASUREMENTS)}",
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
                f"modelos_uncovered={len({gap.modelo for gap in report.gaps})}",
                # Appended after the fields that were here first. A reader
                # pinned to a position must keep it across a field being added.
                f"disposed={sum(1 for gap in report.gaps if gap.disposed)}",
                f"undisposed={sum(1 for gap in report.gaps if not gap.disposed)}",
            ]
        ),
        " ".join(
            [
                "edge",
                *(f"{state}={edge_states.get(state, 0)}" for state in _EDGE_STATES),
                f"rooted_pending_lineage={sum(1 for edge in found_edges if edge.rooted_pending_lineage)}",
                f"total={len(found_edges)}",
                # Appended: roots the tool gave a recoverable cause for, which
                # `root_by_law` absorbed until it learned to read the cause.
                f"rooted_recoverable={sum(1 for edge in found_edges if edge.rooted_recoverable)}",
                # Roots whose own stated reason the corpus has since falsified.
                # They stay `dispositioned`, so their rows stay out of the
                # migration queue and the chaining work that resolved them is
                # invisible -- the continuity twin of a signed coverage
                # disposition whose coordinate is now served.
                # NOT an action, deliberately. A discharged reason says the root
                # is no longer JUSTIFIED; it does not say the edition can be
                # materialised from its predecessor, which is the separate fact
                # that decides. Of the first eight, six drift or refuse on
                # grounds this screen cannot see, so presenting them as a
                # worklist would send somebody to write six bad retractions.
                f"root_reason_resolved={sum(1 for edge in found_edges if edge.root_reason_resolved)}",
                f"retraction_needs_attestation={sum(1 for edge in found_edges if edge.retraction_needs_attestation)}",
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
                # The movable remainder. `inherit_member` cannot reach zero
                # while the merge replaces a stated row wholesale and never
                # fills payload, because every at-risk row must keep stating its
                # own continuity origin. Showing the difference stops the
                # headline reading as though the whole population were work,
                # and it moves on its own when either side changes rather than
                # needing a floor written down.
                #
                # Only the ON-EDGE half is subtracted. The rooted half is not a
                # floor on current work at all: the drop tool cannot reach a
                # none-root's rows, because nothing is inherited there until
                # somebody retracts the root. Subtracting both would understate
                # the movable remainder by the whole rooted population.
                #
                # One asymmetry remains and is NOT reconciled here: the
                # `member_restated` side counts rooted-edge members too, so the
                # difference mixes populations at its edges. Naming it beats
                # quietly narrowing one side to match the other, which would
                # change a figure two lanes are tracking without saying so.
                f"inherit_member_above_floor="
                f"{max(census['member_restated'] - census['attestation_at_risk_on_edge'], 0)}",
                f"declare_export_scenario={blockers.get('export_scenario_missing', 0)}",
                f"render_export_scenario={blockers.get('export_scenario_unrendered', 0)}",
                f"migrate_edge={edge_states.get('ready', 0)}",
                f"close_coverage={len({gap.modelo for gap in report.gaps})}",
            ]
        ),
        " ".join(
            [
                "blocker",
                *(f"{cause}={blockers.get(cause, 0)}" for cause in _BLOCKER_CAUSES),
                # How many edges this line is understating. When the scenarios
                # module cannot be consulted at all, no export cause is claimed
                # for any modelo -- correctly, since unknowable is not absent --
                # and every edge with an export surface silently loses a
                # potential blocker. That fact was reachable only by noticing a
                # `limitation` line above, which is prose in a block readers
                # skim, and the suppression widened `migrated` by 34 edges
                # before anyone spotted it. Carried on the row itself so a
                # pinned figure brings its own caveat. Reads 0 when healthy,
                # which makes it a live assertion rather than a comment.
                f"blockers_understated={_edges_with_unknowable_scenarios(found_edges, statuses)}",
            ]
        ),
        # The root-demotion candidates split by what a per-family
        # materialisation harness actually found, rather than presented as one
        # undifferentiated worklist. `untested` and `stale` are deliberately
        # distinct from `proven_free`: a verdict whose edition has been written
        # since is not evidence, and five of the first eleven were superseded
        # within sixteen minutes of being measured.
        " ".join(
            [
                "root_demotion",
                *(
                    f"{verdict}={sum(1 for edge in found_edges if _edge_verdict(edge, report) == verdict)}"
                    for verdict in _DEMOTION_VERDICTS
                ),
            ]
        ),
        " ".join(["clean", *(kind for kind in CONDITIONS if census[kind] == 0)]) or "clean none",
    ]
    lines += [f"condition {kind}={census[kind]}" for kind in CONDITIONS if census[kind]]
    lines += [f"measurement {kind}={census[kind]}" for kind in MEASUREMENTS]
    scope = ledger_scope(statuses, found_edges)
    if scope is not None:
        lines.append(
            f"ledger unchained_on_edge={scope.unchained_on_edge} named={scope.named} "
            f"unclaimed_predecessor={scope.unclaimed_predecessor} unnamed_successor={scope.unnamed_successor} "
            f"declared_root_not_first_edition={scope.declared_root_not_first_edition} "
            f"unclaimed_predecessor_excluded={scope.unclaimed_predecessor_excluded} "
            f"unclaimed_predecessor_seedable={scope.unclaimed_predecessor_seedable}"
        )
    lines += _family_lines(report)
    lines += [
        f"modelo {signal.modelo} state={signal.state} editions={signal.editions} rows={signal.rows} "
        f"ready={signal.edges_ready} blocked={signal.edges_blocked} migrated={signal.edges_migrated} "
        f"unlifted={signal.unlifted_editions} lineage_gap={signal.lineage_gap} "
        f"restated={signal.restated_refs} liftable={signal.liftable_refs} "
        f"rooted={signal.edges_rooted_pending_lineage} restated_members={signal.restated_members} "
        f"uncovered={signal.coverage_gaps} outstanding={signal.outstanding} "
        # Appended, never inserted: every field above holds the position it
        # held before these two existed.
        f"lineage_on_edge={signal.lineage_gap_on_edge} "
        f"undisposed={signal.coverage_gaps_undisposed} "
        f"rooted_recoverable={signal.edges_rooted_recoverable}"
        for signal in signals
    ]
    lines += [
        f"uncovered {gap.modelo} {gap.filing_year} {gap.period} {gap.kind}"
        + (f" editions={','.join(gap.editions)}" if gap.editions else "")
        # Last, so it follows the optional `editions=` suffix rather than
        # displacing it on the gaps that carry one.
        + f" disposed={'yes' if gap.disposed else 'no'}"
        + f" classification={gap.classification or 'none'}"
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
        f" kind={edge.root_kind} successor_rows={edge.successor_rows}"
        for edge in found_edges
        if edge.rooted_pending_lineage
    ]
    # Recoverable roots get their own record rather than joining `rooted`, whose
    # population is pinned to the lineage kind by consumers already.
    lines += [
        f"rooted_recoverable {edge.modelo} {edge.predecessor} -> {edge.successor} "
        f"predecessor_rows={edge.predecessor_rows} unchained={edge.predecessor_rows_without_lineage} "
        f"shared_chains={edge.chained_both_sides} causes={','.join(edge.blockers) or 'none'}"
        for edge in found_edges
        if edge.rooted_recoverable
    ]
    return lines


def _fmt(value: int) -> str:
    return f"{value:,}"


_TEXT_COLUMNS: Final = frozenset(
    {"modelo", "predecessor", "successor", "family", "identity", "state", "cause", "kind", "locus", "edition"}
)


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
        if edge.state == "blocked" or edge.root_is_open
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
        f"(rooted pending lineage {rooted_pending}, rooted recoverable "
        f"{sum(1 for edge in found_edges if edge.rooted_recoverable)})   total {len(found_edges)}",
        "",
        "ACTIONS",
        f"  lift restatement      {_fmt(unlifted_total):>8}   editions x families",
        f"  seed lineage          {_fmt(_edges_awaiting_lineage(found_edges)):>8}   edges",
        f"  inherit member        {_fmt(census['member_restated']):>8}   members a merge would supply",
        f"  export scenario       {_fmt(blockers.get('export_scenario_missing', 0)):>8}   edges",
        f"  scenario unrendered   {_fmt(blockers.get('export_scenario_unrendered', 0)):>8}   edges",
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

    scope = ledger_scope(statuses, found_edges)
    if scope is not None:
        out += [
            "LEDGER  (what the lineage seeder's closed list accounts for)",
            f"  {'unchained rows on an edge':<32} {_fmt(scope.unchained_on_edge):>8}",
            f"  {'named by the ledger':<32} {_fmt(scope.named):>8}",
            f"  {'unclaimed predecessor (retire/inherit)':<38} {_fmt(scope.unclaimed_predecessor):>8}",
            f"  {'  ledgered wait (excluded modelo)':<38} {_fmt(scope.unclaimed_predecessor_excluded):>8}",
            f"  {'  seedable on the next run':<38} {_fmt(scope.unclaimed_predecessor_seedable):>8}",
            f"  {'declared root, not first edition':<38} {_fmt(scope.declared_root_not_first_edition):>8}",
            f"  {'unnamed successor (ledger miss)':<38} {_fmt(scope.unnamed_successor):>8}",
            "",
        ]

    singles = [
        finding
        for status in statuses
        for finding in status.findings
        if finding.kind
        in {
            "edition_keyed_identifier",
            "foreign_edition_token",
            "row_source_refs_liftable",
        }
    ]
    if singles:
        out.append("NAMED SINGLETONS  (conditions small enough to read here)")
        out += _table(
            ("modelo", "edition", "kind", "locus"),
            [(f.modelo, f.edition, f.kind, f.locus) for f in singles[:20]],
        )
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
    #
    # The worklist counts COORDINATES, so the synthetic kinds are excluded from
    # every line of it. Those describe a disposition whose subject has moved, and
    # pooling them in reported 18 pieces of a reviewer's stale paperwork as
    # unauthored authoring debt. They get their own line instead, because a
    # falsified signature is real work -- it is just not this campaign's.
    out.append("COVERAGE (its own campaign; never folded into the shape verdict)")
    out += [f"  {kind:<38} {_fmt(census[kind]):>8}" for kind in COVERAGE_CONDITIONS]
    out.append(f"  {'modelos uncovered':<38} {_fmt(len({gap.modelo for gap in report.gaps})):>8}")
    # Two different reasons a coordinate closes, never pooled under one label:
    # a modelo that did not exist, and an Orden that does not exist yet.
    out.append(
        f"  {'closed (inception)':<38} {_fmt(sum(1 for gap in report.gaps if gap.classification == 'inception')):>8}"
    )
    out.append(
        f"  {'closed (awaiting ejercicio orden)':<38} "
        f"{_fmt(sum(1 for gap in report.gaps if gap.kind == 'awaiting_ejercicio_orden')):>8}"
    )
    coordinates = [gap for gap in report.gaps if gap.kind not in _SYNTHETIC_COVERAGE_KINDS]
    out.append(
        f"  {'classified debt (unauthored)':<38} "
        f"{_fmt(sum(1 for gap in coordinates if gap.classified and not gap.disposed)):>8}"
    )
    out.append(f"  {'unclassified':<38} {_fmt(sum(1 for gap in coordinates if not gap.classified)):>8}")
    # Broken out by AXIS because the two are read off each other constantly and are
    # not the same number. The kind tally above counts whole-YEAR cells; this counts
    # COORDINATES, which adds the single-period cells and the projected year.
    # Quoting the year figure as "what remains" silently drops the period cells, and
    # those are the ones no year-granularity rule can see -- so they are exactly the
    # population most likely to be lost that way.
    owed = [gap for gap in coordinates if not gap.disposed]
    out.append(f"  {'undisposed (still owed)':<38} {_fmt(len(owed)):>8}")
    for label, kind in (
        ("  of which whole years", "promised_year_unserved"),
        ("  of which single periods", "promised_coordinate_unserved"),
        ("  of which projected years", "promised_year_projected"),
    ):
        out.append(f"  {label:<38} {_fmt(sum(1 for gap in owed if gap.kind == kind)):>8}")
    out.append(f"  {'signatures the corpus moved past':<38} {_fmt(len(report.gaps) - len(coordinates)):>8}")
    out.append(
        f"  {'rows unchained at a projected source':<38} "
        f"{_fmt(_census(statuses)['row_missing_lineage_on_projected_edge']):>8}"
    )
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

    out.append("EDGES  (every adjacent pair, in valid_from order)")
    out += _table(
        # `succ rows` is the column that stops an edge being misread as lineage
        # work. A successor declaring far fewer rows than its predecessor has no
        # counterpart to chain TO: its unchained count cannot fall by seeding at
        # all, because the rows it would chain to were never authored. That is
        # an authoring backlog wearing a lineage number.
        ("modelo", "predecessor", "successor", "state", "kind", "rows", "succ rows", "unchained", "shared"),
        [
            (
                edge.modelo,
                edge.predecessor,
                edge.successor,
                edge.state,
                edge.root_kind or "-",
                _fmt(edge.predecessor_rows),
                _fmt(edge.successor_rows),
                _fmt(edge.predecessor_rows_without_lineage),
                _fmt(edge.chained_both_sides),
            )
            for edge in found_edges
        ],
    )
    out.append("")

    worklist = [edge for edge in found_edges if edge.state in {"ready", "blocked"} or edge.root_is_open]
    out.append("WORKLIST  (edges that are not yet unioned)")
    if worklist:
        out += _table(
            ("modelo", "predecessor", "successor", "state", "rows", "unchained", "reach", "cause"),
            [
                (
                    edge.modelo,
                    edge.predecessor,
                    edge.successor,
                    "rooted"
                    if edge.rooted_pending_lineage
                    else ("recoverable" if edge.rooted_recoverable else edge.state),
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


def _totality_line(totality: LedgerTotality | None) -> str:
    """The totality gate's record, or the word that says it could not be asked.

    ``None`` renders as ``unmeasured`` and never as zeros. A gate reporting
    "uncovered=0 is_total=false" because it could not run is indistinguishable
    from a covered corpus, and this is the one measurement on the screen that
    needs the compiled domain -- so it is the one most likely to be in that state.
    """
    if totality is None:
        return "ledger_totality unmeasured"
    return (
        f"ledger_totality entries={totality.entries} uncovered={totality.uncovered} "
        f"stale={totality.stale} is_total={str(totality.is_total).lower()} "
        f"stale_modelos={','.join(totality.stale_modelos) or 'none'}"
    )


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
    parser.add_argument(
        "--totality",
        action="store_true",
        help="also ask the lineage totality gate (compiles the tree; needs the domain)",
    )
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

    # OPT-IN, and deliberately not folded into `build_report`. It is the only
    # measurement here that needs the compiled domain, and it compiles the whole
    # tree -- so computing it on every report would put a compile into every
    # fixture-tree test and turn a refusing authority into noise on a screen whose
    # entire point is to keep reporting without one. It is still emitted as a
    # record rather than printed as prose, because a gate worth asking is worth
    # diffing: `ledger_totality` was a declared record type that nothing emitted,
    # which is the mirror of an emitted kind that nothing documents.
    if arguments.totality:
        sys.stdout.write(_totality_line(ledger_totality(registry_root)) + "\n")

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
