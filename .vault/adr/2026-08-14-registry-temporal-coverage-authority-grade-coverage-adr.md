---
tags:
  - '#adr'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-27'
body_schema: 'body-v1'
body_hash: 'sha256:967e426d26ff367a59a20f86c8356aa64da96d6b5486ebac391f380a6cbf61e6'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
---

# `registry-temporal-coverage` adr: `grade-bound registry coverage and evidence horizons` | (**status:** `proposed`)

## Problem Statement

A registry revision declares one temporal selector and is consumed as though
that selector answered three separate questions: which filing years the form
legally applies to, which years the project holds evidence for, and which years
a runtime surface may serve. Independent measurement (four agents plus the
orchestrating session, methods and figures recorded in the campaign brief and in
`2026-08-14-registry-temporal-coverage-load-topology-reference`) established the
scale: 97 revisions across 73 modelos, 66 of them open-ended, none reviewed, a
coverage horizon flat at 64 modelos for every year from 2027 onward because
nothing terminates the selectors, and every filing snapshot currently refusing.

Measurement also changed the problem in three ways this record's earlier draft
did not account for.

First, the registry already has per-modelo schema divergence at three layers:
one modelo's private authority is a named field on the generic snapshot types
(`m303_annual_orden` at `src/cadrumo/domain/calculations/registry/_schema.py:1273`
and `:1297`, populated by a modelo branch inside generic authority construction
at `src/cadrumo/domain/calculations/registry/_authority.py:369`); roughly three
quarters of every registry load, warm or cold, is that one modelo's annual-orden
HTML being re-parsed and re-rendered uncached; and the applicability rules of 27
modelos live as Python literals, one rule per modelo, in
`src/cadrumo/domain/calculations/registry/_applicability.py` — regulatory data
the `aeat-registry-authority-flow` rule requires to live in the registry
authoring tree. The operator has ruled that no modelo may carry its own schema
divergence.

Second, validation has two load regimes. A warm load — the normal state of a
developer or operator machine — executes 3 of the package's 42 validator
modules and skips registry validation entirely via a persisted verdict token; a
rule added to a validator module measurably does not run on such a machine
unless a fingerprint changes. Any enforcement this record installs must be
placed where it demonstrably executes.

Third, the package already contains a coverage ledger with no governing
decision record: `src/cadrumo/domain/calculations/registry/_coverage.py` (754
lines) assesses each revision at exactly one representative year
(`_coverage.py:748`), so the registry-wide coverage audit never observes the
overwhelming majority of the years the corpus claims, and its `filing_gaps`
surface (`_coverage.py:107`) is empty for the entire registry by construction
because no revision is reviewed. It also duplicates the filing-eligibility
predicate the snapshot boundary owns.

This record decides the general coverage contract — what a revision declares
about its own evidence grade, how family coverage is expressed, what bounds a
supported filing history, and which facts a program may derive versus which a
human must attest — and it decides how the pre-existing divergence relates to
that contract, where enforcement lives so that it actually runs, and what
happens to the ungoverned coverage ledger.

## Considerations

- Selector, evidence and runtime availability are three axes collapsed into one
  field (`2026-08-14-registry-temporal-coverage-research`).
- The grade distinction this contract needs is already asserted as prose in 25
  `revision.toml` manifests and typed nowhere (campaign measurement; the phrase
  wraps lines, so single-literal greps undercount it).
- The generic snapshot types already carry one modelo's private authority as a
  named field, so any new schema surface added without correcting that ratifies
  divergence as precedent
  (`src/cadrumo/domain/calculations/registry/_schema.py:1273`).
- A warm load executes 3 of 42 validator modules and skips validation via a
  persisted verdict; the verdict is keyed on the registry tree fingerprint and
  package version, so data invariants certified at build remain sound for
  unchanged data, but consumption-time refusals cannot live in `_validate*`
  modules (`2026-08-14-registry-temporal-coverage-load-topology-reference`,
  campaign load traces).
- `authority._registry_validated` is `True` in both regimes; it reports
  certified state, not whether validation executed, and must not be used as a
  regime discriminator (campaign load traces).
- Informative modelos with export layouts and no formulas are consumed through
  filing snapshots today — `src/cadrumo/application/modelo/_m145_communication.py:95`
  resolves `authority.snapshot(...)`, which hardwires operator review. M145,
  M036 and M720 are this shape; a grade ladder that makes filing require an
  unconditional calculation closure leaves them no legal cell.
- The in-flight `2026-08-10-aeat-export-fragment-generator-authority` campaign
  owns the Modelo 303 and Modelo 390 authoring trees; its S84 and S85 rows also
  scope `modelos/390/`, so tree ownership does not end at its S91 signoff row.
- That campaign's S91 attests M303 `2026-y-siguientes` as filing-grade, and
  that revision is open — no `valid_to`. Any constraint requiring filing-grade
  revisions to carry a terminated window would red an attested revision on a
  tree this record may not edit.
- The M390 epoch split (commit `f9f3f77704`) is the one worked example of a
  temporal repair: four disjoint bounded epochs, each with a real `valid_to`,
  produced because the annual designs genuinely differ.
- Revision review provenance is declared evidence and may never be derived,
  generated or asserted by an agent
  (`2026-08-14-registry-temporal-coverage-adr`, `2026-07-27-conformance-cli-adr`).
- A revision is law-selected from modelo, filing year and period; a stored id
  may only confirm that result (`2026-06-10-period-revision-resolution-adr`).
- The validated authority and immutable snapshot remain the sole production
  orchestration boundary — yet the package facade currently publishes the raw
  loader family in `__all__`, and no gate detects a production consumer taking
  that path (`2026-08-14-registry-temporal-coverage-load-topology-reference`).
- Regulatory values and their applicability belong in the registry authoring
  tree, never inlined at a call site (`aeat-registry-authority-flow`).
- The operator directed that remediation be tooling-driven: one-shot programs
  that derive, propose and apply mechanically, with humans reserved for claims
  evidence cannot settle.

## Considered options

- **Define the coverage contract on the schema as it stands and defer the
  divergence to its own campaign.** Rejected. The contract's fields
  (`ModeloRevision` is undiverged) could technically land, but the contract's
  substance could not: the `applicability` grade grades exactly the data that
  currently lives as Python literals outside the registry, so the bottom rung
  of the ladder would certify a claim whose subject matter the registry does
  not contain; and enforcement lands on the same authority-construction path
  the divergence contaminates. Deferring also leaves the operator's ruling —
  no modelo owns schema divergence — recorded but unexecuted, which the
  orchestration rules forbid treating as done.
- **Correct all divergence first, then define coverage.** Rejected as pure
  sequence: the contract definition does not touch the diverged types, and
  serialising the two roughly doubles the campaign's wall time for no
  correctness gain. The real dependency is narrower and is stated below.
- **Bound every open selector to its bundled-source years.** Rejected: it
  deletes real scheduling coverage for the thin modelos whose approving orden
  genuinely extends forward, to fix an authority leak those modelos express on
  a different axis.
- **Add a declared `coverage_through` cap beside the selector.** Rejected: a
  second declared temporal axis that can disagree with the first reproduces
  the conflation this record removes.
- **Require a terminated window (`valid_to` plus bounded selector) at
  calculation and filing grade.** Rejected — this was the earlier draft's
  position and the evidence broke it. Every modelo's frontier revision is
  legitimately open: the governing orden is in force and unamended, so no
  honest terminus exists, and S91 attests exactly such a revision. Mandatory
  termination would either red an attested revision on an unowned tree or
  force fabricated termini corpus-wide.
- **A fourth grade for informative modelos.** Rejected: it encodes one known
  exception as vocabulary. The defect is not that three grades are too few but
  that the ladder demanded unconditional family population; conditioning the
  ladder on family dispositions fixes M145, M036 and M720 and every future
  modelo of that shape without new vocabulary.
- **Grade-bound coverage with disposition-conditional requirements, derived
  evidence horizons, divergence removal in the same record, and mechanical
  migration (chosen).** Described below.

## Constraints

- A coverage contract may be defined while `m303_annual_orden` still sits on
  the snapshot types, because the contract's declared surface lives on
  `ModeloRevision` and its derived surfaces are projections — but it may not be
  *closed* over a diverged schema. Divergence removal is a co-requisite of this
  record, not a separate campaign: the enforcement flip requires all three
  layers corrected, and no new field, catalogue or projection introduced by
  this record may be modelo-named on a generic type.
- `applicability`, `calculation` and `filing` remain the complete grade
  vocabulary and form a ladder over *dispositions*, not raw population: a grade
  requires every family it enrolls to be resolved — `populated`, or
  `not_applicable` carrying a reason with legal references — and never
  `blocked_pending_evidence`. The calculation closure is required at
  `calculation` and `filing` grade only where the formula family is applicable;
  an informative revision whose formula family is honestly `not_applicable`
  reaches `filing` grade. The ladder direction is preserved: everything
  resolved at a lower grade must remain resolved at a higher one.
- The grade is declared in `revision.toml` only, as an OPTIONAL scalar with a
  fail-closed default: an absent grade means ungraded, treated as
  `applicability` scope — structurally barred from filing snapshots — and
  surfaced as a visible advisory. It is never REQUIRED at load, because a
  required manifest-only field cannot land without an atomic 97-manifest edit
  spanning two trees this record may not touch. A corpus-completeness check
  (every manifest carries an explicit grade) becomes blocking only at the
  enforcement flip.
- Grade demotion and the ungraded floor are derivable; grade promotion is an
  attestation. No program, migration, generator or bulk command raises a
  revision's grade or writes `operator_reviewed` for a revision or legal
  reference. Tooling emits reviewable promotion proposals; a human applies
  them. The one sanctioned mechanical write of a grade value is transcription
  of an existing prose self-declaration into the typed field at the same
  grade, which adds no claim.
- Temporal windows: a superseded revision — one with a successor revision for
  the same modelo — MUST be a bounded epoch with a real `valid_to`, derivable
  and applied mechanically. A frontier revision MAY remain open at any grade.
  The two temporal fields must cohere: a bounded or enumerated selector with an
  open `valid_to` (7 revisions today), or a selector start disagreeing with
  `valid_from` (3 today), is a validation failure with a mechanical fix where
  the successor or the manifest itself settles it.
- Supported filing history is bundled-source-backed only and enforced per
  cell: a filing snapshot for `(modelo, filing_year, period)` is served only
  when a bundled AEAT or BOE source artefact covers that cell, regardless of
  how far the selector claims. This is a derived bound, computed from the
  enrolled source corpus, never a declared field — so it cannot drift against
  the selector. No product-window promise, no statutory-inception backfill.
- Enforcement placement follows the measured regimes. Data-shape invariants
  (grade ladder, disposition derivation, window coherence) live in registry
  validation and are legitimately certified by the verdict cache, because the
  verdict is keyed on the complete tree fingerprint. **Amended 2026-08-27:**
  the open question this bullet made the flip contingent on is now closed by
  measurement, and it closed against the original premise. The data CAN change
  without changing the verdict key, for the bundled tree, for the duration of
  its fingerprint TTL — `BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`, currently
  10 seconds, in
  `src/cadrumo/domain/calculations/registry/loader_cache.py`. The window covers
  layout changes as well as content changes, because the fingerprint walk is
  itself what would observe a layout change. The guarantee is therefore
  restated: a verdict certifies the tree **as observed no staler than the
  bundled TTL window**, not the tree as it is at the instant of the read. This
  is a deliberate policy, not a defect. Under an editable install — the routine
  development mode — "bundled" resolves to the live in-tree source directory,
  so a TTL that never re-checked would serve stale TOML to a long-running
  process indefinitely; a bounded window folds the several fingerprint
  recomputations a single calculate call triggers into one directory walk while
  still picking up a concurrent edit well within one operator interaction, and
  a genuinely read-only installed wheel is unaffected because the re-walk
  merely repeats the same answer. Mutable authoring roots are exempt: they are
  fingerprinted afresh on every load and carry no TTL. Enforcement placement is
  unchanged by this amendment — data-shape invariants remain legitimately
  certified by the verdict cache under the restated guarantee, because a
  ten-second observation lag cannot admit a data shape that validation would
  have refused; it can only delay noticing one. Consumption-time refusals (unsupported
  cell, ungraded or under-graded revision reached from a filing surface) live
  at the authority/snapshot resolution boundary, which executes on every load
  and every snapshot request in both regimes. Every gate lands with a proof
  that it bites under a WARM load, with the verdict cache present.
- Family enrollment is derived from `ModeloRevision` field metadata via
  markers, following the existing manifest-field pattern; a hand-written
  family list is forbidden. The disposition set is `populated`,
  `not_applicable` and `blocked_pending_evidence`; the last is the fail-closed
  default for a required-but-empty family, a visible worklist entry, never
  allowlistable.
- `m303_annual_orden` comes off `RegistrySnapshot` and `RegistryCatalogues`.
  The generic concept it instantiates is a per-modelo supplementary orden
  authority: it is replaced by a generic catalogue keyed by modelo, populated
  from registry data with no modelo branch in `_authority.py`, and its parse
  output is compiled once and cached under the complete tree fingerprint —
  which also removes the measured ~75% per-load re-parse cost. Whether the
  annual-orden content later migrates fully into authoring-tree TOML is left
  open; the field removal and fingerprint-keyed compilation are decided here.
- The `ModeloApplicabilityRule` literals, one rule per modelo across 27
  modelos, move to the registry authoring
  tree as a declared fragment family, migrated by tooling with a compiled-
  equality proof, and the literals are deleted (no bridge, per
  `no-legacy-compatibility`). The Modelo 303 and 390 rows are blocked until
  the export-fragment campaign releases those trees.
- Enumeration completeness is NOT assumed. The measurement behind this record
  covered the registry package only, computed no static import closure, and
  examined 6 of the 61 modules that execute in neither load regime; whether
  other packages carry registry-shaped drift was never measured. This record
  therefore binds drift CLASSES through derived detectors, not through a
  finding list frozen at drafting time, and requires a drift census before
  the enforcement flip: compute the static import closure from the sanctioned
  load entry points and classify its never-executed members; scan the whole
  application source, not the registry package alone, for regulatory
  literals, year sets and modelo-conditional branches outside the sanctioned
  channels; and persist the census as a vault audit in which every finding is
  either enrolled as a plan row or formally deferred with a reference — zero
  unclassified findings is the gate, and the flip is blocked until it holds.
- The applicability literals are not the only Python-resident registry data,
  so the teardown is governed by inventory, not by the one known case. Every
  modelo-specific module in the package is classified exactly once: a
  REGULATORY DATA EMBED — rates, coefficients, thresholds, year sets,
  applicability conditions, operator-facing prose — which migrates to the
  registry authoring tree (or, for prose, the locale catalogues) and is then
  deleted; MACHINERY — parsing, projection or validation code with no
  encoded regulatory values — which is kept with its justification recorded;
  or DEAD, which is deleted. `_m303_orden_constants.py` is the proven second
  case: its `SUPPORTED_EJERCICIOS` tuple, seasonal index coefficients,
  difficult-justification percentage and Lorca 2022 reduction are orden
  content encoded as Python literals. The two per-modelo formula runtimes
  are classified by the same pass rather than assumed either way. A value
  imported through the curated `core.external_constants` leaf channel is the
  one sanctioned exception the authority-flow rule already grants.
- The set of filing years production serves is a DECLARATION in the registry
  authoring tree — a single supported-filing-years catalogue, replacing every
  Python-resident year set such as `SUPPORTED_EJERCICIOS` — and the
  declaration must be proven, not trusted: registry build validation refuses
  the ENTIRE registry load when any year declared supported has any obliged
  modelo, per the registry-resident applicability data, without a
  law-resolvable revision at its required grade and evidence-backed cells
  for every period of that year. The failure enumerates every missing cell
  with modelo, period and missing prerequisite. Turning a year on is
  therefore an assertion the corpus must already satisfy: flipping 2026 or
  2027 on with a gap takes the whole registry down loudly, never partially.
  Because the declaration and the corpus are both fingerprinted registry
  data, this gate legitimately rides the validation verdict.
- The calendar rollover is the time-dependent half and therefore lives at
  the authority and snapshot resolution boundary, never in a `_validate*`
  module: when the evaluation date enters a filing year not declared
  supported, production calculation and filing consumption refuse with a
  clear failure naming the undeclared year, in both load regimes. The
  boundary takes its evaluation date from the one clock authority so the
  refusal is provable with an explicit date, not a patched clock. Deadline
  and applicability scheduling surfaces remain readable so the operator can
  see what the refusing year requires.
- The raw loader family is demoted from the package facade `__all__`; external
  consumers route through the authority or a purpose-built narrower export,
  and the import-hygiene gate is extended to red a production raw-loader
  import. `_loader.py` stays the compiler implementation detail the
  authority-flow rule says it is.
- `_coverage.py` is governed by this record. The derived
  `(modelo, filing_year, period, schema_family)` matrix supersedes the
  ledger's single-representative-year assessment; the duplicated
  filing-eligibility predicate is unified onto the snapshot-owned one; the
  by-construction-empty `filing_gaps` path is replaced by the honest derived
  worklist or deleted. No second coverage authority survives.
- Every replacement this record decides is delete-not-bridge: the superseded
  surface, its exports and its tests are removed in the same change that lands
  the canonical one — no compatibility alias, no re-export, no dormant
  fallback. That covers the modelo-named snapshot field and its authority
  branch, the applicability literals and their carrier mechanism, the raw
  loader facade entries, the coverage ledger's single-year assessment, its
  duplicated predicate and its vacuous gap surface, the prose grade markers
  once transcribed, and the migration programs at close. The six validator
  modules measurement proved execute in neither load regime are classified by
  reachable caller and deleted where dead — a validator that cannot execute on
  any machine is not kept. The deliberate survivals are the `_m303_orden_*`
  parsing modules and their authority type, rehomed behind the generic keyed
  catalogue pending the operator's ruling on full TOML migration, and the
  post-load registry surfaces outside this record's scope.
- The parent temporal-coverage record, the resolver record and the
  authority-flow record are accepted and stable. This record narrows what
  those boundaries admit; it does not create a second selector, loader,
  snapshot service or declared temporal axis.

## Implementation

**The grade field.** A `RegistryAuthorityGrade` string enum in `core` carries
`applicability`, `calculation` and `filing`. `ModeloRevision` gains an optional
`authority_grade` of that type, hydrated from `revision.toml` at the loader
boundary and refused anywhere else in the fragment tree. Absence is the
fail-closed ungraded state: applicability scope, filing-barred, advisory-
visible. Registry validation enforces the disposition-conditional ladder; a
grade that outruns its resolved families refuses at build, so the field cannot
be aspirational.

**The coverage manifest and matrix.** A derived `RevisionCoverageManifest`
projects one row per enrolled family — identifier, disposition, populated
count, and for substantive claims a reason with legal and source references —
with enrollment read from `ModeloRevision` field markers so a new family
appears everywhere the moment it is declared. Above it, a derived
`(modelo, filing_year, period, schema_family)` matrix over the validated
authority yields per cell the owning revision, grade, disposition and backing
evidence, assessed across every claimed year rather than one representative
year. The matrix is the campaign denominator: worklists are read out of it,
never maintained beside it.

**The horizon.** No new temporal field. Superseded revisions become bounded
epochs mechanically; frontier revisions stay open; the two existing temporal
fields must cohere. The filing bound is per-cell and derived: the snapshot
boundary refuses a filing cell no bundled source covers, so an open frontier
selector confers scheduling reach, never filing reach. This resolves the S91
contradiction without editing an owned tree: M303 `2026-y-siguientes` stays
open and filing-attestable for the cells its bundled sources cover.

**Divergence removal.** The modelo-named snapshot field is replaced by the
generic modelo-keyed supplementary orden catalogue with fingerprint-keyed
compiled caching; the `Modelo.M303` branch in generic authority construction
is deleted; the applicability literals migrate to a registry fragment family
with compiled-equality proof; the raw loader family leaves the facade. A
structural gate reds any modelo-named field on a generic registry schema type
so the divergence cannot return.

**The embed teardown.** A derivation pass enumerates every modelo-specific
module mechanically (name pattern plus `Modelo` enum reference) and forces
exactly one classification per module — regulatory data embed, machinery with
recorded justification, or dead. Embeds migrate to the registry authoring
tree (prose to the locale catalogues) and are deleted; embeds whose
destination is an owned tree queue for the owned-tree sweep. The pass is
exhaustive by construction: an unclassified module in the derived set fails
the gate, so a future modelo-specific module cannot ship unclassified.

**The year gate.** The supported-filing-years declaration lands in the
registry authoring tree and replaces every Python-resident year set. Registry
build validation cross-derives, for each declared year, the obliged modelo
set from the registry-resident applicability data and refuses the whole load
on any modelo missing its required grade, resolvable revision or
evidence-backed cells for any period of that year, enumerating every gap.
The authority and snapshot boundary refuses production calculation and filing
consumption for any evaluation date whose filing year is not declared
supported, with an instructive failure naming the year and the declaration
that would admit it. Declaring next year early is supported and forces the
corpus to be complete for it before the declaration can load.

**Enforcement.** Build-time rules join registry validation and ride the
verdict; the plan first closes the open fingerprint/TTL conformance question,
since verdict legitimacy depends on it. Consumption-time refusals live at the
authority/snapshot resolution boundary. Both are landed advisory-first behind
the campaign closure, and every gate ships with a warm-regime bite proof:
verdict cache present, deliberate defect introduced from outside the tree,
gate observed red, restored.

**The migration programs.** One-shot programs under `dev/`, retired at close:
a prose-marker transcriber (25 self-declared applicability manifests to the
typed field, same grade, no new claim); a grade-candidate deriver emitting a
reviewable promotion proposal per remaining revision; a bounds applier
terminating superseded epochs and repairing the 10 mechanically-boundable
selectors and the coherence mismatches evidence settles; an applicability-
literal migrator with compiled-equality proof; the embed classifier and
migrator over the modelo-specific module inventory; and a matrix reporter
emitting the residue — the claims only adjudication can settle — as a finite,
diffable worklist. A program may derive, demote, bound, transcribe and prove;
it may not promote a grade, assert applicability for an unevidenced year,
declare a filing year supported, or write any review attestation.

## Rationale

The knockout criterion is unchanged: this is the only shape under which the
corpus becomes honest without anyone asserting something they do not know. What
the measurements changed is where honesty was previously impossible. A
termination mandate at filing grade demanded a fact — the law's end date —
that does not exist for a frontier revision, so it manufactured either false
termini or an unresolvable conflict with an attested revision; deriving the
filing bound per cell from bundled sources states only facts the project holds.
A coverage contract closed over a schema that carries one modelo's private
field would grade a corpus through a type that itself violates the operator's
schema ruling, and its bottom grade would certify applicability data the
registry does not contain; folding divergence removal into the same record
makes the contract's subject matter and its substrate consistent before
anything flips blocking. And placing rules by measured execution rather than
by module naming convention is what separates a gate that bites from a gate
that decorates: the verdict cache is a sound certification for
fingerprint-covered data and a proven bypass for everything else, so the
contract puts data invariants behind the verdict and refusals at the boundary
every regime executes.

The disposition-conditional ladder is the same honesty argument applied to
families. Demanding unconditional population made three real modelos illegal
and would have invited either a fourth grade per exception or quiet
misgrading; demanding resolved dispositions makes "this family does not apply,
for this cited reason" a first-class, checkable claim, and keeps
`blocked_pending_evidence` as the visible residue automation must never clear.

The tooling boundary follows the operator's direction and the evidence's
grain: 25 grades are transcriptions, 10 bounds are mechanical, superseded
epochs and coherence repairs are derivable, and the genuinely human residue —
long-span calculation claims, concentrated in a handful of fragment-heavy
modelos — arrives as a matrix-generated worklist instead of a 653-modelo-year
guess.

## Consequences

- Family absence becomes readable, and unfinished work becomes a worklist
  generated from the authority. Ungraded revisions are visible advisories from
  day one and filing-barred at the flip.
- Scheduling-only modelos keep their forward deadline coverage and lose the
  ability to present as filing authority. Informative modelos gain a legal
  filing cell through honest `not_applicable` dispositions.
- The flat-64-forever horizon stops being a lie about filing and becomes an
  explicit scheduling claim; filing reach is exactly the bundled-source cell
  set, which is currently far smaller and honestly so.
- The snapshot types lose their modelo-named field, generic authority
  construction loses its modelo branch, and every registry consumer stops
  paying ~75% of each load for one modelo's uncached HTML parsing. Consumers
  of the removed field and the facade's raw loaders must move in the same
  changes — atomic relocations, no bridges.
- `_applicability.py` shrinks from the package's second-largest module to a
  loader-fed surface; which modelo obliges which taxpayer becomes registry
  data, versioned and validated like the rest — except the two owned modelos,
  which follow at campaign release.
- `_coverage.py` stops being an ungoverned second coverage authority; its
  audit stops being blind to all but one year per revision, and its vacuous
  gap surface is replaced by one that can actually report gaps.
- The enforcement flip is a named closure obligation anchored on the
  export-fragment campaign's full closure including S84 and S85. Until then,
  drift can accrue behind advisory notices; the flip step re-runs the full
  derivation and reds on any residue.
- Availability is deliberately traded for honesty at the year boundary: a
  declared-supported year with one missing cell keeps the entire registry
  from loading, and a calendar rollover into an undeclared year takes
  production calculation and filing down until the operator declares the
  year and the corpus proves it. That totality is the point — a partial year
  serving quietly is the failure mode this gate exists to make impossible.
- Two questions are deliberately left open for the operator: whether the
  annual-orden content itself later migrates into authoring-tree TOML beyond
  the field removal decided here — the embed inventory will classify
  `_m303_orden_constants.py` as regulatory data, making that content the
  first concrete instance of this question — and the scheduling of the human
  promotion worklist the matrix will emit. Accepting this record ratifies
  the keyed-catalogue destination, the in-scope applicability migration, the
  embed-inventory teardown and the year gate.
