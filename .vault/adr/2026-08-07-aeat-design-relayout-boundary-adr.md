---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8266492c913d97659a49b8b1a34f6c270711d7399284a2d09b29acb4ca659fae'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-research]]"
---

# `aeat-design-relayout-boundary` adr: `a registry revision must not span an AEAT design re-layout` | (**status:** `proposed`)

## Problem Statement

A registry revision carries exactly one export layout, but two revisions today
claim filing years on both sides of an AEAT record-design re-layout: Modelo 303's
`2009-y-siguientes` and `2023-y-siguientes`, and Modelo 390's single
`2010-y-siguientes`. Every such revision writes at least one of its claimed
years at the wrong byte offsets. This is live: `2023-y-siguientes` already
covers Q1/Q2 2026, both of which have closed as of this record's date, with
Modelo 303's 2026 AEAT design measured and bundled
(`2026-08-07-aeat-design-relayout-boundary-research`). A structural gate
enforcing "no revision spans a re-layout" is already landed and deliberately
red, naming the violations as its own specification
(`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`).
This record ratifies the property that gate enforces, rules on the three
questions its existence does not answer by itself, and authorizes the
registry-split implementation as follow-on plan work. It makes no registry
edit itself.

## Considerations

- The gate is generic across modelos and keyed on design-to-design agreement,
  not a casilla-to-box mapping, because that mapping barely exists for some
  modelos (Modelo 390's casillas are semantic ids) — see the research's "gate
  already exists" finding. A decision narrower than the gate it governs cannot
  itself govern that gate.
- `revision-resolution-is-law-determined` (project rule): "which revision
  applies" is a derived fact from `(modelo, filing_year, period)`, not an
  injectable one. A revision spanning a re-layout breaks this at the root — the
  law-determined answer for a given year is a SPECIFIC design, and the current
  registry cannot express two designs under one revision id.
- `modelo-export-mirrors-official-structure` (project rule): a structural
  divergence from the official AEAT layout is a hard failure, never a warning.
  A wrong byte offset is the most literal possible instance of "structural
  divergence."
- `no-silent-under-declaration` (project rule, generalized posture): this
  campaign's standing position is that a visible refusal beats a silent wrong
  answer on a money-bearing or byte-exact surface. A mis-offset filing is not
  an under-declaration in the rule's literal sense, but it is the same shape of
  harm — a silently wrong artifact the taxpayer would file believing it correct
  — and the posture generalizes directly.
- Modelo 123 already carries the correct shape in this same registry: two
  revisions, two distinct declared layout `source_refs`, each independently
  offset-correct against its own design
  (`2026-08-07-aeat-design-relayout-boundary-research`, "shipped pattern"
  finding). The fix this record authorizes is not a new mechanism; it is
  applying an existing, working pattern to two more modelos.
- Cost is asymmetric by era. Modelo 303's near-term boundary (2025→2026) is
  live and affects filings being made today; its older boundaries (2015-2022)
  and all five of Modelo 390's (2017-2024) are historical, affecting only
  filing years long past their statutory amendment window.

## Considered options

- **Split every revision at every named boundary, oldest to newest, uniformly.**
  Pro: total correctness, no filing year left mismodelled. Con: authors five
  full historical Modelo 390 revisions (back to 2017) and three additional
  historical Modelo 303 revisions (back to 2014) for filing years with no
  active filers — pure sunk authoring cost with no user ever exercising the
  correct path, and legal-grounding work (`legal_refs`, `source_refs`,
  `corpus_ref`) for each.
- **Split only at boundaries inside each modelo's currently-reachable filing
  window, and refuse export for filing years before the earliest split.**
  Rejected as the general rule but adopted as the DEFAULT posture (see
  Rationale) — bounds authoring cost to years the app can actually be asked to
  file, and a refusal is the correct answer for a year this registry was never
  asked to support, per `revision-resolution-is-law-determined` (a refusal
  naming the unmodelled year is a valid resolution outcome, an incorrect
  export is not).
- **Leave the revisions unsplit and downgrade the gate's assertions to
  warnings.** Rejected outright — this deletes the evidence the gate exists to
  carry (see the gate's own docstring: "weakening the assertions to land green
  would delete the evidence") and directly contradicts
  `modelo-export-mirrors-official-structure`'s "never a warning" clause.

## Constraints

- Registry TOML validates as one coherent tree at load; a partial revision
  split (some boundaries fixed, the registry not yet internally consistent)
  breaks suite collection for every concurrent agent on this shared worktree —
  the split for each modelo must land as one atomic commit, per
  `aeat-worktree-safety` discipline, not incrementally per-boundary.
- A revision split changes `revision_id` resolution for every carried
  cross-year observation stamped against the old id
  (`carried-observations-stamp-their-revision`); the implementing plan must
  re-confirm every carry path against the new ids, not assume the split is
  export-layout-only.
- The gate's boundary set is data, not a frozen constant: re-run
  `test_revision_span_matches_published_designs.py` at implementation time
  rather than copying the numbers in this record, which may already be stale
  against a newer bundled corpus.

## Implementation

For Modelo 303 and Modelo 390, split each existing revision into one revision
per AEAT design the gate's failure text names, following the Modelo 123
pattern: each new revision gets its own `revision.toml` (`valid_from`, and
`valid_to` for every non-newest one), its own `export/*.toml` fragment tree
encoding that design's own offsets (parsed from the bundled corpus, never
hand-transcribed), and its own declared `source_refs` naming the specific AEAT
`aeat-dr-<modelo>-<year>` design it encodes.

Per the "Considered options" ruling: split fully within each modelo's
currently-reachable filing window (the years an operator can actually create a
work unit for); for filing years strictly older than the earliest split
boundary, add a revision with `valid_from` at that boundary and no earlier
sibling — `select_revision` then finds no matching revision for the older year
and the existing "no revision covers this triple" refusal path fires, naming
the unmodelled year. This is a refusal, not a crash: the mechanism already
exists in the resolver and needs no new code, only the registry no longer
claiming a year it cannot correctly serve.

For Modelo 200: no implementation action. Its current two-design span is
offset-identical, and the same generic gate already covers its forward risk —
recorded here so a future author does not duplicate the mechanism when AEAT
eventually publishes a 2026 Modelo 200 design.

Land the split as one plan per modelo (Modelo 303, then Modelo 390), each its
own atomic multi-file commit, verified green against
`test_revision_span_matches_published_designs.py` and the existing per-modelo
completeness and parity gates before landing.

## Rationale

The generic gate already states the mechanism; this record's job is the three
things the gate cannot decide for itself. First, on refuse-vs-degrade for a
year with no correct layout today: refuse, because a wrong byte offset is
indistinguishable from correct output to the operator until AEAT's own reader
rejects or misreads the filed record — the harm surfaces downstream of the
point where this app could have caught it, which is exactly the shape
`no-silent-under-declaration`'s posture exists to prevent, generalized from
under-declared amounts to mis-placed bytes. Second, on how far back to model
historically: bound at the reachable window rather than author five Modelo 390
revisions and three more Modelo 303 revisions for years nobody can file today
— `2026-08-07-aeat-design-relayout-boundary-research` records that the harm
measured live (Modelo 303 2025→2026, Modelo 390's proved `export_draft`
mis-write) is entirely in the CURRENT and recent-past window, so the sunk cost
of full historical fidelity buys no correctness a real filer will ever reach.
Third, Modelo 123 already demonstrates the target shape is buildable in this
registry today, at the cost the split requires, with no new resolver or schema
work — the correct pattern is copy, not invention.

## Consequences

- Modelo 303 and Modelo 390 each gain additional revisions; every consumer
  that assumed one revision per modelo across their full history (query
  services, cross-period carry, deadline-window derivation) must be swept for
  that assumption as part of the implementing plan, not discovered after.
- Filing years older than each modelo's earliest post-split revision become an
  explicit, named refusal rather than a silent wrong export — a behavior
  change for any historical work unit still open at that old year, which the
  implementing plan must call out as a compatibility note (not a
  `no-legacy-compatibility` violation: this is refusing to keep writing wrong
  bytes for a year, not migrating an old persisted shape).
- `test_revision_span_matches_published_designs.py` goes green as a direct
  side effect of a correct split and should not be edited to pass any other
  way; a change to that file during implementation that is not itself
  reddened first by a genuine new boundary is a signal the split missed
  something.
- Modelo 200 is deliberately left unchanged in this pass; its coverage is a
  standing claim of the existing gate, not a new commitment this record makes.
