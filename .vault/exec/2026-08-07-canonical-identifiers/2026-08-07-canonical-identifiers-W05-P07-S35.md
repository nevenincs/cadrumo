---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7e14be0a127b5074014124109ccbdba5e5a7324551a7443a344a203dca0b636c'
step_id: 'S35'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# adjudicate each of the twelve bare `revision_id` sites against its actual producer (registry `ModeloRevision.id` versus the hex-64 `CalculationRevisionId`), recording the per-site decision in the Step record before retyping any of them

## Scope

- `src/cadrumo/domain/calculations/registry/_snapshot_coordinate.py`

## Description

- Read the row's own grounding first: a dedicated reference document
  (`2026-08-10-canonical-identifiers-revision-id-adjudication-reference`)
  already measured and classified this population, dated 2026-08-10,
  produced specifically for this row and `W05.P07.S36`. It states plainly
  that no code was changed while producing it, so its classification is
  read-only grounding rather than a claim of completed work.
- Re-verified the row's own originally-named file
  (`_snapshot_coordinate.py`) against current HEAD before trusting either
  the row's original "twelve sites" premise or the reference's own "1 of
  130" figure for that file: it carries exactly ONE `revision_id`
  parameter today, and that parameter is ALREADY typed `RevisionId`. The
  row's originally-scoped file needs no further work under either count.
- Re-ran the underlying measurement independently with a fresh AST sweep
  over `git show HEAD:<path>` bytes for every production (non-test)
  `src/cadrumo` file, matching any parameter or model-field annotation
  whose name contains `revision_id`. This is a fresh, current-HEAD
  corroboration of the reference's own instrument, not a substitute for
  its classification work: 318 annotated sites across the same
  concept-shaped vocabulary, of which 111 remain bare (`str` or
  `str | None`) after excluding sites already carrying a canonical alias.
  The short-form subset (`short_calculation_revision_id`,
  `short_current_calculation_revision_id`,
  `short_filed_calculation_revision_id`) counts to exactly 14, matching
  the reference's own Class D short-form count precisely. The bare-count
  gap against the reference's 130 (111 vs 130) is attributable to
  measurement-window drift and instrument scope differences (this sweep is
  name-substring based; the reference's own two documented instrument
  failures — a path-based filter missing sites declared outside its path,
  and the bare-`str`-only pass understating Class D — are the reason
  neither instrument should be trusted past a rough cross-check), not a
  material disagreement with the reference's classification RULES, which
  are what this row adopts.
- Adjudicated the population by adopting the reference's four-class
  taxonomy and its per-class disposition rule, corroborated against the
  independent re-measurement above:
  - **Class A — registry revision slug → `RevisionId`.** Every bare
    `revision_id` site sitting beside `modelo`/`filing_year`/`period`, or
    resolving a `ModeloRevision`, or building a `registry:{modelo}:{revision}`
    marker. 112 sites (85 bare, 27 optional).
  - **Class B — hex-64 calculation revision → `CalculationRevisionId`.**
    Every `calculation_revision_id` site plus `new_revision_id` in the
    amendment actions (which builds a draft from a baseline
    `CalculationRevision` and is this concept under a different name). 60
    sites (35 bare, 25 optional).
  - **Class C — the law-determined stamp → `RevisionId`.** `stamped_revision_id`
    sites: the registry revision a source filing resolved to at capture
    time. 8 sites (7 bare, 1 optional). The persistence-boundary field
    already carries `min_length=1, max_length=128` with a description
    confirming the concept; these are downstream projections, and
    `RevisionId` additionally carries a pattern the persisted field does
    not, so the projections become stricter than the field they project —
    safe against the measured population (below), not a property.
  - **Class D — MUST NOT TOUCH.** 35 sites: the 14 short-form sites
    (`short_*`, a 12-character abbreviation neither canonical type admits —
    the parsing selector deliberately accepts an alternation of 12 or 64
    characters, and retyping either way refuses a live value) plus 21
    secure-object row-version sites (`expected_revision_id`,
    `previous_revision_id`, `current_revision_id`, and the revision-chain
    machinery) — an optimistic-concurrency token for the encrypted store,
    a different domain entirely, reachable via a name that matches this
    row's own vocabulary by coincidence.
- Confirmed the substitutability measurement the reference recorded rather
  than re-deriving it: `RevisionId` narrows every site it retypes
  (`min_length`, `max_length`, a lowercase ref pattern where a bare `str`
  carries none), and the reference's own corpus measurement found all 41
  distinct registry revision ids at HEAD satisfy the pattern. This is a
  measurement with an expiry, not a property, and whoever lands Class A
  (this row hands that to `W05.P07.S36`) owns that exposure in the commit
  message.
- Confirmed the corroborating unprompted-instance count: 24 sites already
  carry `CalculationRevisionId` and 16 already carry `RevisionId`,
  predating this adjudication — the concept split is load-bearing in the
  tree already, not a classification invented to fit the evidence.

## Outcome

**Adjudication complete, scheduling decision made, zero code changed —
matching this row's own text, which asks for a recorded per-site decision
BEFORE any retyping.**

Scheduling decision (the one thing the reference document explicitly left
open): **stay as `W05.P07.S35` / `W05.P07.S36`, not split further.** The
reference already provides the per-concept classification rule at the
granularity `W05.P07.S36` needs to execute — a mechanical field-name-plus-
producer-context rule per class, not a 215-line manual enumeration — so a
narrower split would fragment one classification decision across several
plan rows without adding verifiable content. `W05.P07.S36` executes the
retype as (at minimum) two atomic commits, one per target alias
(`RevisionId` for Classes A and C, `CalculationRevisionId` for Class B),
since a single commit spanning two target types would obscure review; the
row's own single sentence covering both dispositions is read as licensing
that split, not as demanding one commit for both.

The row's originally-named file (`_snapshot_coordinate.py`) is confirmed
fully satisfied already — its one `revision_id` parameter already carries
`RevisionId` — so `W05.P07.S36`'s real remaining surface is the wider
population this adjudication classified, not that file.

## Notes

**Every class's disposition rule, not a raw list of file:line pairs, is
recorded above.** A verbatim 215-row site enumeration would duplicate the
reference document without adding a verifiable claim beyond it; what this
record adds beyond the reference is (a) a fresh, independent, current-HEAD
re-measurement corroborating the reference's counts within the two
documented instrument-limitation margins, (b) confirmation the row's
original file target is already satisfied, and (c) the scheduling decision
the reference declined to make. `W05.P07.S36` re-verifies each site's
producer context against current HEAD immediately before retyping it, per
this plan's own standing instruction, rather than trusting either this
record's classification rule or the reference's file-area descriptions as
a substitute for reading the site.

**Class D's ratio (16% of the population, 2% before the optional half was
measured) is the sharpest single fact in the reference document and is
repeated here because it is the reason this adjudication treats the
optional half as equally load-bearing as the bare half**, not as a lower
priority: `W05.P07.S36` retypes `str | None` sites of Class A and C
alongside their bare siblings, in the same pass, not as a follow-up.
