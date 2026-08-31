---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-29'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:390cd7dd15ef094ecf529fba5e13e31b33484a02bdb9dfb1279cb265c1cd49d4'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `registry-completeness-closure` audit: `gate staleness sweep`

A sweep of the registry test lanes at HEAD, taken because the lanes were red and
nobody had a current count. Baseline measured before any change: **53 failed,
6202 passed** across `domain/calculations/registry/tests` and
`application/registry/tests` (19m10s, sequential).

The registry itself is healthy. The conformance report renders 48 rows, every one
`registry_validated=true`, so the bundled authority loads and validates at HEAD.
None of the 53 failures was a registry-data defect. They fall into three classes,
and the classes matter more than the count.

## Class 1 -- a change landed without sweeping its dependents

### `design_constant` shipped its source kind but not its projection

`ce7ed9c74e` added the `design_constant` `BindingSourceKind`, its route
pseudo-owner and its Modelo 720 registry bindings. It did not update
`application/registry/source_connectivity_authority.py`, whose
`_canonical_route_source_ownership` branches only on the manual-input
pseudo-owner. The new owner fell through to the resolver branch and died on
`stage`'s `Literal`, taking **32 tests** with it -- all reading as unrelated
authority failures rather than as a missing projection.

The same commit also skipped the four locale catalogues, leaving
`docs.casilla.binding_source.design_constant` and its `flows` sibling absent in
all of `en`, `es`, `ca`, `hu`.

**Remediation applied.** A sibling `CalculationRouteDesignConstantSourceOwnership`
row model, a third branch in the canonical projection, a `design_constant` field
on the catalogue, and the locale leaves authored through `dev.locales set`.
Deliberately NOT a widening of the manual row: the route's own owner refuses that
move, and the two pseudo-owners must stay distinguishable -- a manual value
arrives from the operator, a design constant is fixed by AEAT's diseno.

**Carry forward.** Adding a `BindingSourceKind` member touches four surfaces that
nothing forces you to visit, because the registry loads clean while they are
missing. See the sibling memory note; the pair that actually bites is
`application/registry/tests/test_source_connectivity_authority*.py`.

### A reformat commit widened a deliberately narrow matcher

`57181181a3` ("style: mandate relative imports within the package and reformat",
1,168 files) changed `InventorySelector.filing_year` from `Literal[2025]` to a
bare `int`. The selector's three admitted destinations -- 0177, 0181, 0182 -- are
Modelo 100's **2025** casilla numbers, and AEAT renumbers between years, so
any-year acceptance let a 2024- or 2026-scoped binding target 2025 boxes and
resolve without complaint. The guarding test went red at that commit and stayed
red, attributed to the surrounding churn.

**Remediation applied.** The pin is restored, with the reason recorded at the
field so a later widening has to argue with it.

**Carry forward.** A mechanical commit subject buys trust its diff has not
earned. Filtering `git show <c> -U0` for `Literal|frozenset|min_length|max_length|pattern|ge=|le=|strict|extra=`
with import lines dropped surfaced this one widening out of 1,168 files, and it
was the only one.

## Class 2 -- gates that had stopped describing their own subject

Eight modules pinned something that a relocation, a rename or a withdrawal had
moved. None was a registry defect; each was a gate reporting on a state that no
longer existed.

- **The facade-import detector could not see a relative import.** It matched only
  `node.level == 0`, while every real binding in the tree is spelled
  `from ... import registry`. It therefore reported zero offenders while four
  files bound the namespace, and the paired exemption-liveness check then read
  its single entry as stale. Repaired to resolve relative imports against the
  importing module's package, and to tell a SUBMODULE import apart from a
  facade-symbol import. Proven against six shapes from outside the repo; the
  three sibling files that bind the namespace to prove its inertness are now
  enrolled with the same stated reason.
- **The `select_revision` sanction set was stale in both directions.**
  `_build_validated_snapshot` moved from `snapshot.py` into
  `_snapshot_internals.py`, so the moved call read as a brand-new *unsanctioned
  revision-id injection* -- the exact defect class `aeat-registry-authority-flow`
  bars -- while the entry left behind defended a file with no such call.
  Re-pointed, and a **liveness test added**, which immediately caught a second
  stale entry: `application/modelo/work_addressing.py` no longer injects at all,
  having moved to one `RegistryAuthorityCapture` with both axes asserted against
  it. That is strictly stronger than a narrowing argument, so the entry was
  DROPPED rather than re-pointed -- a sanction outliving its need is standing
  permission for whatever is written into that path next.
- **Modelo 200's layout withdrawal was never swept.** Both revisions now declare
  zero export layouts. That left two `_UNADJUDICATED_REPEATED_SLOTS` entries
  naming slots that no longer exist, two schema proofs dying on their FIXTURE
  rather than their subject, and a box-numbered enrolment reaching nothing. Each
  repaired by making the subject the CONDITION: the width proofs now borrow a
  genuinely shipped field by condition instead of by modelo name, and the
  envelope assertion holds when a layout is present so it returns to a real check
  the moment M200's layout is re-authored. The two unresolved M200 tax questions
  and the retired 3,427/3,427 measurement are preserved in place rather than
  deleted, because re-authoring brings both straight back.
- **`test_modelo_165_incomplete_2013_design_...` asserted a defect that was
  fixed.** The type-two hole at positions 102-103 is closed on evidence: the
  bundled correction sidecar records that the 2013 orden misprints
  `104-500 BLANCOS` where both later editions of the SAME orden print
  `102-500 BLANCOS`, surrounding rows identical. Asserting the old refusal would
  have asserted a defect back into the corpus. Restated as the stronger claim the
  test is named for: a COMPLETE design is still not layout authority until a
  layout is deliberately authored.
- **Two import-shape pins and one module path** went stale on the
  relative-imports sweep and the public-module relocations
  (`_conformance.py` -> `conformance.py`,
  `registry.parse_export_payload` -> `registry.export_parse.parse_export_payload`,
  a level-0 `SourceReference` floor).
- **Three exhaustive name-set pins** in the record-design selector gate reddened
  on `applies_across` -- the resolver's check that a design actually covers the
  requested filing year, which is grounding this gate wants MORE of. Converted to
  property-plus-floor, the correction that module had already applied to its
  import assertion and not to its three siblings.
- **The validator size ratchet was measuring documentation.**
  `_validate_export_layout_coverage.py` crossed its 1,067-line ceiling at 1,201
  lines, of which **394 were code and 807 were the comment and docstring blocks
  recording why each regex is spelled as it is**. Both ways to go green -- delete
  the reasoning, or split a cohesive validator to beat a number -- are worse than
  the problem. The metric now counts reviewable code lines; all thirteen
  baselines re-pinned to exact current values with no slack, and the ratchet
  proven to red one line over ceiling.

## Class 3 -- correctly red, and not this session's to close

These are honest declarations of incomplete work. None should be edited green.

- **`test_every_registry_revision_can_produce_a_filing_artifact`** is a standing
  worklist -- "fail with the list of revisions that cannot emit, until that list
  is empty". 35 revisions across 18 modelos, each already carrying a disposition:
  an authorable gap naming its plan owners, or a terminal refusal naming the
  authority or product-scope condition that must change. It goes green when the
  export campaign completes, not before.
- **`test_committed_registry_tree_has_required_model_law_coverage`** fails on one
  coordinate: Modelo 165 revision `2023-2025`, layout_authority coverage gap. The
  registry is RIGHT and the gate is right. Three signals -- the corpus filename,
  AEAT's own `archivos_23` URL path, and `DR_Mod_165_2023.pdf` -- suggest the
  bundled design is the 2023 one, but the revision records the adjudication
  explicitly: *"The next bundled positional artefact is headed Ejercicio 2026.
  Its filename says it was updated in 2023, but that is not an applicability
  declaration for 2023-2025"*, and the revision is `authority_grade =
  "applicability"` accordingly. Backdating the 2026 design to close this would be
  exactly the invented temporal coverage the rules forbid. Blocked on acquiring
  AEAT's actual 2023-2025 M165 design -- `registry-temporal-coverage`
  `W02.P05.S51`.

## The continuity ratchet moved, and it is arrivals

`_UNGROUNDED_BASELINE` diverged by **+3,294 across eight modelos** (6,077
observed against 2,783 recorded). The gate offers two readings and they were
distinguished before the number was touched:

At the commit that last set the mapping, modelos 165, 200, 270, 308, 309, 341,
347 and 576 carried **zero** `continuidad_id` stamps between them, and they still
carry zero. No chain in any of them could have lost a stamp, so the regression
arm is refuted outright rather than judged unlikely. Seven gained revisions to
the temporal splits (165, 308, 309 one to four; 200, 270, 341, 576 one to two).
Modelo 347 gained no revision and moved by one: its `2008-2024` revision was
re-identified as `2011-2024` and given the new contraparte-clave bindings.
Modelo 200 alone accounts for 3,173 -- its withdrawn layout plus the 2024/2025
partition -- which is why the total looks alarming and is not.

Re-recorded with that evidence beside the mapping. **Nothing was adjudicated**;
raising the baseline records that the work arrived, never that it was resolved.
The backlog remains `registry-completeness-closure` `W03.P05.S89`.

## One non-finding worth recording

The home-office suministros chain was checked for the OPPOSITE direction to the
one the apparatus watches. LIRPF art. 30.2.5.a b) grants 30 % **of the affected
floor-area proportion**, and `_ledger_expenses.py` applies the stored ratio
directly with no visible multiplier -- which would over-declare by more than 3x
if that ratio were the raw proportion. It is not: production derives
`raw_afectacion_ratio * statutory_multiplier` through `effective_usage_ratio`
before it reaches the aggregation, and the registry declares
`statutory_multiplier = "0.30"` with the BOE quote. **No defect.** The failing
test simply never supplied a ratio, and its fixture now states the law: the
ceiling case (raw afectacion 1.0), chosen because it makes the local-versus-
dwelling contrast the SMALLEST the carve-out can produce, so the gate errs
toward understating the cost of misrouting.

## `dev/registry` was examined and is sound

The generators were read against the concern that they author revisions ahead of
legal truth. They do not. `derive_result_dispositions` reads the admissible
letters out of each modelo's own diseno and proves itself against the nine
hand-authored mappings. `generate_result_disposition_fragments` explicitly
REFUSES to derive the result casilla because that fact is not derivable, rather
than encoding a modelo-to-role map. `apply_revision_temporal_bounds` closes only
the two bound classes the corpus mechanically settles and routes start-mismatches
to a worklist for an orden reading. The auxiliary-header contract is single-homed
in `record_design_schema.py`, which `dev/registry/pipeline` imports rather than
copying. `newmodelo` is a grounding checklist, not a value generator.

The damage in this sweep came from the other direction entirely: ordinary feature
and reformat commits that changed a registry surface without sweeping what
depended on it.

## Verified outcome, and the eight that remain

Re-measured over the same two lanes after the repairs: **8 failed, 6248 passed,
1 skipped** (14m08s, sequential), against the 53/6202 baseline. Every one of the
45 closed failures was a gate defect, a stale pin, or a missing sweep -- no
registry datum was changed to make a test pass.

The eight survivors are NOT gate staleness. They are the campaign's genuine open
work, and they are listed here so a later reader does not re-diagnose them.

**Correctly red by design, not to be edited green (2)**

- `test_every_registry_revision_can_produce_a_filing_artifact` -- the standing
  35-revision filing worklist described above.
- `test_committed_registry_tree_has_required_model_law_coverage` -- coverage
  gaps including M165 `2023-2025` layout_authority and M714 `2025`
  executable_parity_evidence.

**Blocked on acquiring or reading an official source (2)**

- `test_the_design_parser_reads_every_markdown_design_it_claims` -- modelo 184
  revision `2023-2024` claims 2024, but its design
  (`07-184-orden-hfp-1284-2023-boe-a-2023-24412.pdf`) yields neither box offsets
  nor page lengths, so the gate is UNMEASURED there rather than clean. Its
  silence about those years means nothing until the artefact is parseable.
- `test_every_bundled_record_design_file_is_registered_by_a_source` -- 2 of 218
  bundled files carry no registered `SourceReference`:
  `modelo_036/.../02-036-...-provisional-...xlsx` and
  `modelo_200/files/01-200-ejercicio-2025-...xlsx`. Registering either needs an
  applicability window and review status nobody has adjudicated; the 036 file
  names itself *provisional*, which is its own question.

**Real registry-truth defects, authorable, and worth prioritising (2)**

- `test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today`
  reports both shapes the temporal splits left behind. **HOLES:** modelo 194 has
  no revision resolving 2020, 2021, 2022 or 2025; modelo 270 and modelo 721 none
  for 2025 -- the application cannot even attempt those years.
  **OVERLAP, and this is the sharper one:** modelo 308 filing year 2011 resolves
  through BOTH `2009-2011-junio` and `2011-julio-2015` for period token
  `AD-HOC`. The split was drawn at a June/July boundary, but the AD-HOC token
  carries no month, so both windows match it and there is no tie-break.
  `aeat-registry-authority-flow` relies on the non-overlap window gate to
  guarantee resolution is unique; an overlapping pair means a 2011 M308 filing
  can be computed under either revision's norms.
- `test_every_computed_casilla_is_enrolled_in_a_verification_contract` -- eleven
  computed casillas resolve with no verification contract behind them: M100 2024
  `0611`; M216 `2024-y-siguientes` `07`, `16`, `19`; M309 (all three revisions)
  `decl.cuota-devengada-22` and `decl.resultado-24`; M353 `2021-2025` `03`,
  `05`, `09`.

**Consequential on the Modelo 200 partition (1)**

- `test_the_genuine_cross_year_spans_still_report` reports `('200', '2024')`.

None of these is closable by editing a test. Each needs either an acquisition, an
adjudication against official sources, or authored registry content -- which is
what the open steps in the three predecessor plans already describe.

## Follow-up: the resolution holes were legal-truth defects, not conservatism

Six of the eight residual failures traced to one gate,
`test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today`.
It was authored 2026-08-14 and passed then; the era splits for modelos 194, 270,
308 and 721 landed 2026-08-25/26, so every finding below is an ARRIVAL, not a
regression.

The splits were right in kind: each replaced an over-broad open-ended revision
with evidence-bounded eras. What went wrong is that four were bounded to the
FIRST ejercicio of their orden rather than to the orden's window, converting a
fixed over-claim into a new under-claim. Every orden involved uses one formula --
*"sera aplicable, POR PRIMERA VEZ, a las declaraciones ... correspondientes al
ejercicio YYYY"*. `Por primera vez` OPENS a continuing window at its first
ejercicio; it does not confine the design to it.

### Modelo 194 -- 2020, 2021, 2022 and 2025 were unfilable

The pre-split revision was one open-ended `2019-y-siguientes`; the split bounded
2019, 2023 and 2024 to single ejercicios, so four years resolved to nothing.

`aeat-dr-194-2019` carried an explicit dated refusal -- *"Do NOT successor-bound
this design across the 2020-2022 gap until that is settled"* -- because the
consolidated amendment list could not be reached (the ELI URL 404s) and because
`BOE-A-1999-22309` looked like *"a different orden of the same date"* approving
only modelos 123 and 193. That refusal was correct to make, and is now discharged
on evidence rather than overridden:

- `BOE-A-1999-22309` IS the modelo 194 approving orden. Its title enumerates 123
  and 193 first, but Orden HFP/1284/2023 states verbatim that the modelo 194
  record designs are *"contenidos en el anexo X de la Orden de 18 de noviembre de
  1999"*. The AEAT index's "18 de ENERO" is an index typo.
- BOE's consolidated *Referencias posteriores* for that orden, read 2026-08-30,
  amends anexo X in 2016, 2019, 2023 and 2024 -- and NOWHERE between 2020 and
  2022, and not at all after 2024.

So the 2019 edition governs 2019-2022 and the 2024 edition is open. Corroborated
by AEAT's pages (captured 2026-08-15): only the 2024 design sits on the current
`modelos-100-199` page; 2023 and 2019 are under *ejercicios anteriores*.

The cap also contradicted a sibling. `aeat-dr-188-2023` has the identical
evidence shape -- title "actualizado en 2023", page header "Ejercicio 2023",
EJERCICIO a filer-supplied field at positions 5-8 -- and is correctly left OPEN,
feeding revision `2023-y-siguientes`. A page header naming a year is an edition
label, not a scope, because the year is not baked into the record.

### Modelo 721 -- 2025 was unfilable

Same shape. Its own `orden_aplicabilidad` cites `orden-hac-1504-2024:df-unica`,
which applies the substituted anexo *"por primera vez ... al ejercicio 2024"*,
while the note concluded the revision is *"therefore selected only for 2024 0A"* --
a non-sequitur. BOE's *Referencias posteriores* for `BOE-A-2023-17429` (read
2026-08-30) lists that substitution as the ONLY subsequent amendment, with
nothing in 2025 or 2026.

### Modelo 270 -- 2025 was unfilable, and the stated blocker was not real

The note refused 2025 for want of *"a complete 2025 record-design binary"*. The
amending orden is bundled, and article 3 of Orden HAC/1431/2025 changes only the
LABEL TEXT of four province codes (03 ALICANTE/ALACANT, 12 CASTELLON/CASTELLO,
20 GUIPUZCOA/GIPUZKOA, 48 VIZCAYA/BIZKAIA) inside CODIGO DE PROVINCIA -- and
names that field's positions **118-119 of tipo de registro 2 without altering
them**. The geometry is untouched, so nothing is extrapolated, and this registry
models the field as the two-digit numeric code, never the rotulo. AEAT confirms
it structurally: it reissued a design for modelo 347 under that same orden and
did NOT for modelo 270, whose 2023 design is still the current published one
(captured 2026-08-26). Its df unica reads *"ejercicio 2025 y siguientes"*.

The design source was capped at 2024-12-31 while the revision it grounds now runs
open -- an internal contradiction -- so the source window was opened too. Two
legal-catalogue entries (`orden-hac-1431-2025:art-3`, `:df-unica`) were authored
from the bundled BOE text, every `required_text` phrase verified verbatim.

The revision id had to move to `2023-y-siguientes`: `test_revision_id_window_agreement`
takes no exceptions, and a year-keyed tail on an open window is *"an ungrounded
third statement about applicability"*. That re-keys 60 casilla label/help strings
across four catalogues, done through `dev.locales move-revision` -- the verb built
for exactly this (240 written, 240 released, 0 conflicts, 0 undistributed).

### Modelo 308 -- the one that is NOT a data defect

AEAT itself publishes the split: *"Ejercicios 2009 a 2011-julio"* and *"Ejercicios
2011-julio a 2015"*. The registry models it faithfully, and resolution works when
given a date:

    on=None        -> AmbiguousRevisionSelectionError
    on=2011-03-15  -> 2009-2011-junio
    on=2011-09-15  -> 2011-julio-2015

The limitation is in the RESOLUTION CONTRACT, not the data: the mandated
`(modelo, filing_year, period)` triple carries no date, and modelo 308's only
period token is `AD-HOC`, which has no month -- so the period axis cannot
partition a mid-year boundary the way modelo 303's 2024 split does
(`2024-hasta-08-y-2t` / `2024-desde-09-y-3t`). Only 4 production call sites pass
`on=`, so most resolve to a refusal.

This must NOT be closed by editing data or the gate. Inventing `AD-HOC-H1` tokens
would fabricate period grammar; softening `_period_overlap` would declare clean a
year the app genuinely cannot serve on the mandated triple. It fails CLOSED
(raises, never a wrong number) and is confined to filing year 2011, whose window
closed in 2012. It needs an ADR on whether an AD-HOC work target carries an
operation date.

### Collateral: the sanctioned locale tooling was unreachable

`dev.locales` -- the ONLY sanctioned way to touch the catalogues -- would not
start: `dev/locales/_colanding.py` and two of its test modules still imported from
`cadrumo.application.operator_surface`, whose namespace the inert-namespace
campaign has emptied. Repointed to the canonical defining modules (`contract`,
`models`, `errors`, `help`, `help_models`). The rest of that lane stays red on the
same class of breakage (`operator_surface._contract`, `contribuyente.CCAA`) and
belongs to the campaign that moved them. No locale failure references modelo 270,
and the moved keys resolve in all four catalogues.

### Standing caution on measurement

Full-lane runs are not quotable right now: two parallel runs each lost a worker
mid-flight (~214 and ~670 tests silently not run), and a peer reverted uncommitted
test edits in the shared tree during the session. Sequential runs of the touched
modules are the only sound evidence; on those every changed module passes, and the
only registry failure remaining in that set is the pre-existing modelo 165 / 714
law-coverage gate.

### Generated export-tree enrolment: two owed trees, one wrong-year pairing

Two enrolled rows in `dev/registry/tests/test_generated_export_trees.py` were
red and both looked like stale enrolment. Neither was. Nothing was deleted --
`git status` is clean on both revision directories and both `export/` trees are
absent at HEAD -- and the rows carry the deliberate "enrolled with the layout,
not after it" discipline that the m347 entry above them explains.

`m200-2024` failed with a source-authority refusal rather than an absent tree:
the row paired revision `2024` with `aeat-dr-200-2025`. That source carries
`record_design_epoch = "2025"` and `applies_from = 2025-01-01`, and only
`2025-y-siguientes` declares it among its revision-level `source_refs` -- the
sibling `aeat-dr-200-2024` carries `applies_to = 2024-12-31`. The epoch year is
the ejercicio, not the AEAT publication year, which refutes the tempting reading
that a design published in 2025 under Orden HAC/657/2025 (approving modelo 200
for periodos impositivos of 2024) belongs to the 2024 revision. Three fields
(source_ref, epoch, filing_year) already said 2025 against one saying 2024, so
the revision string was the outlier. Corrected in `266a0cd467`; the anchor
coverage case, previously refused, now passes -- the pairing validates only when
it is right, which is the proof the correction is not cosmetic.

Revision `2024` retains its own reviewed design and a full parsed mapping set
under `dev/registry/mappings/modelo_200/2024/`, and owes an enrolment row once
its tree is rendered. That row is deliberately NOT added yet: enrolling ahead of
a tree is sanctioned, but adding a row whose only effect today is a second
permanent red buys nothing until the render lands.

Both `m200-2025-y-siguientes` and `m390-2022` now fail on the one honest ground
that remains: `render_complete_export_tree` succeeds for each, so the tree is
renderable and simply never published. That was surfacing as a bare
`FileNotFoundError` out of `iterdir`, which reads as a broken row and invites
exactly the wrong repair. The enrolment row is the ONLY staleness detector a
committed tree has, so the assertion now names the tree as owed and says to
publish it through the generator's own publication authority rather than retire
the row.

Unrelated and pre-existing, confirmed in the same run: both m347 rows still fail
at the `filecmp` byte comparison on `0002-record-m347-declarado.toml`, the
`repeat = "binding_rows"` gap the semantic map cannot express. That comparison
also runs BEFORE check mode, so it masks the refusal message the check-mode
guard was given for this case -- the ordering is worth fixing when that gap is
closed.

### The two owed export trees are not "just unpublished" — correcting a claim

An earlier note in this sweep called publishing the two owed trees
(`m200-2025-y-siguientes`, `m390-2022`) unblocked generator work. That was wrong
on two counts, both measured.

**The authored and generated layout shapes are mutually exclusive.** Every
known-good generated tree carries `export/` fragments and an EMPTY
`export_layouts/`: m184 2023-2024 is 6/0, m347 2011-2024 is 5/0, m322 2023 is
7/0. m390 2022 is the inverse -- 0 generated fragments against 14 authored
layouts (23 records, 415 fields), whose fichero layout id is
`modelo-390-2022-fichero-boe`. A generated tree publishes
`generated-modelo-390-2022-fichero`, so publishing would not fill a hole; it
would seat a fifteenth layout claiming the same fichero beside the authored one.
That is duplicate ownership of a filing surface, which the authority is required
to refuse, and it means m390 is an authored-to-generated MIGRATION requiring
adjudication -- not a missing render. The `_SOURCE_DEFECTS` entry for
`aeat-dr-390-2022`, which adjudicates the eleven-character `</T3900700>` constant
against the twelve-byte slot the same cell declares, reads as preparation for
exactly that migration: it exists to make a generated render agree with the
reviewed authored layout.

`m200-2025-y-siguientes` carries neither shape (0/0), so it alone has no
duplicate-ownership conflict.

**There is no publication route into the shipped registry.** The only references
to `publish_validated_generated_export_tree` are its definition in
`_tree_publication.py`, the pipeline re-export, and
`dev/registry/tests/test_generated_tree_publication.py`, which drives it against
temporary fixtures. No CLI verb, script or dev entry point publishes a generated
tree into `src/`. The check module additionally forbids itself a publisher
surface by gate (`test_check_module_has_no_migration_reader_or_publisher_surface`),
so the separation is deliberate -- but the operator-facing half of it was never
built. The enrolment gate's own instruction, "publish it through the generator's
own publication authority", currently names a route that does not exist. That,
rather than an unrendered tree, is why both rows have stayed owed, and it is the
gap to close before either row can go green.

### The dev/registry unit lane, measured module by module

Running the lane as one sequential command does not work in this tree. Two
attempts were invalidated mid-flight by landings, and a third was still buffering
after ninety minutes with nothing readable, because piping a backgrounded run
through `tail` suppresses all interim output. Running the same lane module by
module answered the same question in minutes per chunk, each attributable to a
named commit. The phase asks for sequential runs, which is about worker loss on
this share; it does not ask for one monolithic invocation, and the monolith is
strictly worse here.

All 42 modules covered. Twenty-one tests fail, in three groups, none unexplained.

Four are the generated-export-tree enrolment rows -- both modelo 347 revisions,
modelo 200 2025-y-siguientes and modelo 390 2022. All four are blocked on the
operator-surface decision rather than on effort. The core generator pipeline
behind them is green: check mode, publication, provenance manifest, the semantic
map with its join and validation, source-defect declarations, the variable
envelope and its generation gate, and the record-design intermediate together
give 148 passed with no failures.

Eleven are in the filing export-proof lane and belong to it, not here. They carry
four distinct causes, which is worth stating because sampling one would have
mis-reported all eleven: seven are modelo 200 declaring `calculation` authority
grade against a requested `filing` snapshot -- the same deliberate downgrade that
holds check mode below filing grade for that modelo -- one is a legacy
single-channel proof path that has been disabled in favour of two-channel source
and custody authorities, one is a missing `assess_for` method on that lane's own
authority object, and two are regex assertions downstream of those. That lane
holds uncommitted edits in the same files, which is what mid-refactor looks like.

Six were relocation-stale declarations: a gate names modules by hard-coded path,
a promotion moves them, the declaration expires. That is the gate working. Five
belong to other lanes' sweeps. The sixth was the semantic-map loader's import
pin, in this lane, and it was stale three ways at once -- it pinned package names
rather than the modules that define each symbol, so it asserted the facade shape
the architecture forbids and no longer named the TOML parser's owner; it silently
lacked `is_link_like`; and its facade `__all__` list predated the filing-export
proof work that legitimately grew it from eleven names to twenty.

One further failure was a line ratchet exceeded by exactly one line. The delta was
entirely the import-centralization sweep replacing facade imports with
per-defining-module ones, which is the case that gate's own docstring names as
making a module easier to review rather than harder, so the baseline was raised to
the exact new length and no further.

A caveat that must travel with these numbers: 24 tests were deselected by the
marker expression. This is the unit lane. The workbook parity module drives
LibreOffice and is held out of it, which is precisely why its line ratchet was
placed in the default lane instead.

### Measurements that ran correctly and reported the wrong subject

Every wrong number in this sweep came from an instrument that worked. None came
from a command that failed. They are worth listing together because the failure
is invisible at the call site in each case.

A pipe answers for the last command in it. Reading `exit=$?` after
`git add f.py 2>&1 | head -2` reports `head`, so a command never actually measured
appears to have succeeded. Capture the status of the command itself.

An empty pipe is indistinguishable from a clean result. `git show HEAD:<path>` on
an untracked path emits nothing, and `ast.parse("")` accepts it, so a file that
does not exist at HEAD reports as parsing correctly. Check the byte count before
trusting what came through.

`git diff HEAD -- <path>` cannot see an untracked file. When an index entry has
been removed the file becomes untracked, so diff reports "deleted file mode" while
the content sits on disk. Thirteen registry modules were staged as deleted and
this instrument called all thirteen genuine deletions. The comparison that settles
it is `git show HEAD:<path> | diff - <path>`; identical output proves that
re-adding restores exactly what HEAD holds and can lose nothing.

`git log -1 -- <path>` answers who touched a file last, not who created the thing
in it. A split was attributed to the wrong session on that basis, twice, in both
directions. `git log -S` finds the commit that introduced the content.

A parser reports only its first syntax error. Four broken lines took four rounds
to find one at a time; enumerating every occurrence found them together.

A grep for a number misses its underscore spelling. Searching for `1398` returned
nothing while the file declared `1_398`.

An aggregate invites the feeling of being informed. "595 dirty" was read and moved
past without looking at the letters, and thirteen staged deletions sat inside it
for hours. The same shape produced three different units under one label in a
neighbouring lane. A count without its members is not a measurement.

The pattern behind all of them: the instrument answered a question adjacent to the
one being asked, and looked authoritative doing it. The defence is not more
caution but a second instrument that fails differently — read the members, not the
count; compare content, not status; ask who created, not who touched.

### Phase 0 closed: the registry failure set across both lanes

Both registry lanes are now measured module by module, every failure named, and
every name re-verified at a current HEAD rather than quoted from the run that
found it. The re-verification was not ceremony: of twenty candidates recovered
from one long run, three had already been fixed by landings and one more was an
artifact of my own working directory. Reporting the run's own list would have
handed over four failures that do not exist.

The dev/registry lane, 42 modules, holds three groups. Four are the generated
export-tree enrolment rows, and all four wait on the operator-surface decision
rather than on effort. Eleven belong to the filing export-proof lane and carry
four distinct causes, seven of them one refusal: modelo 200 declaring calculation
authority grade against a requested filing snapshot. The remainder are
relocation-stale declarations, where a gate names modules by hard-coded path and a
promotion moved them; that is the gate working rather than rot. Two failures in
this lane were repaired here -- a loader import pin that was stale three ways at
once, and a line ratchet exceeded by a single import-sweep line.

The registry package lane, 525 modules and 6028 tests, holds sixteen. Two are the
Phase 5 items already named in the brief: bundled record designs registered by no
source, and the filing-capability worklist. One is the modelo 165 layout-authority
coverage gap, which is acquisition-blocked and was measured from the loaded
authority rather than from a test file, which turned out to matter when that file
was split into seven modules mid-measurement. One is the revision-resolution gate
discussed below. The rest span the continuity backlog ratchet, export value
policy, record-design source selection, the disk-cache fingerprint, a ledger
worked example, read-parameter invalidation, two schema validator refusals, and
two design-parser claims.

Two gates disagree about modelo 308's 2011 overlap, and the disagreement is
substantive rather than a defect in either. One adjudicates a year-only refusal as
legitimate when the split is grounded, date-reducible and period-overlapping,
which modelo 308 satisfies, and passes. The other admits no overlap at all,
because a year that resolves to two revisions cannot be calculated at all, and
fails. Both readings are defensible. Implementing the AD-HOC operation-date
decision resolves the overlap and reconciles them, which is a stronger argument
for that record than the one previously made for it.

A caveat travels with all of this. Both lanes exclude tests deselected by the
marker expression, so this is the unit lane; the workbook parity module drives
LibreOffice and sits outside it. And the tree churns hourly -- during this
measurement a module was split into seven, a merge left five files conflicted, and
three failures were fixed underneath the run. The set is accurate as measured and
should be re-measured, not inherited.

### Twelve failures, one missing capability

Counting the symptoms of modelo 200 having no export layout, now that both lanes
are measured, gives a number worth stating plainly: twelve failing tests across
three modules and two lanes trace to it, and none of them is in the lane that owns
the cause.

Two are the generated export-tree enrolment rows for modelo 200 and modelo 390,
which report a tree as owed and cannot be satisfied because no operator route
publishes one.

Seven are in the filing export-proof lane, and all seven carry the same refusal:
modelo 200 declares calculation authority grade, which cannot satisfy a requested
filing snapshot. The revisions state the reason for that grade in their own
comments -- filing refuses until the canonical generator publishes the exact
design for that ejercicio -- so the grade is downstream of the same absence.

Three are in the registry package lane and were only attributable once the
authority was queried directly. The declared-casilla walk admits a revision only
when it carries an export layout, so modelo 200 is enrolled among the modelos it
must reach and is never reached. And two schema validator proofs read
`revision.export_layouts` for modelo 200's 2024 revision to build their negative
case: one asserts exactly one composed envelope-open prefix field and finds none,
the other calls `next()` over the same empty sequence and raises StopIteration.

The second pair is the most instructive. Their docstring states the premise
explicitly -- "the campaign authored Modelo 200's generated export tree, so the
revision declares a layout again" -- and that premise is false: both revisions
carry zero export layouts, confirmed against the loaded authority rather than a
directory listing. These are detector-teeth tests that can no longer construct
their own defect, so they fail for the absence of the fixture rather than for the
defect they guard. A reader seeing "validator rejects ..." in a failure list would
reasonably conclude the validator had stopped rejecting something. It has not.

The practical consequence is that the cost of one undecided capability is being
paid in lanes that cannot fix it, in failures whose names do not mention it.

### A redirect strategy that import centralization defeats

Two tests in the registry package cannot work as written, and the reason is
structural rather than a stale name, so it is worth recording before someone
repairs it the way I first tried to.

`test_read_parameter_authority_invalidation` needs to point the default bundled
registry root at a temporary tree, so that an edit under that root can be observed
reaching the next read. It does that by patching `bundled_path` as an attribute on
the `core.resources` package. Since import centralization, no consumer reads that
attribute: each imports the function from its defining module and holds its own
binding. The patch therefore still succeeds and redirects nothing, the real
bundled registry loads, and the synthetic modelo is simply absent -- the failure
surfaces as `KeyError: '999'`, which names neither the redirect nor the root.

Repointing the patch at the consumer does not rescue it. Patching
`loader_cache.bundled_path`, which is what computes the cached root, still leaves
the run resolving the real tree, because seven modules in that package bind the
symbol independently -- authority, loader_cache, classification_coherence,
external_grounding, formula_runtime_ops, the source-evidence fingerprint, and the
package conftest. Redirecting one is whack-a-mole; redirecting all seven encodes a
list that the next consumer invalidates silently.

That attempted repair was made and backed out rather than left in place. It was
more nearly correct than what it replaced and still did not work, and a plausible
fix carrying a confident comment is worse than an honest failure, because the next
reader inherits the confidence rather than the problem.

The durable point is general. Patching a re-exported name is a technique that
depends on consumers reaching the symbol through a shared surface. An architecture
that requires every consumer to import from the defining module removes that
surface deliberately, and every test that redirects by monkeypatching a package
attribute is silently defeated by it -- silently, because the patch reports
success. Making the root injectable in production is the repair; that is a design
decision for whoever owns the authority, not a test edit.

### The home-office worked example, grounded against the manual

One of the registry package failures looked like a calculation defect and is not.
`test_the_home_office_carve_out_is_not_applied_to_a_local` fails because the
example's own facts produce four aggregation issues, every one reading
`INELIGIBLE_DEDUCTIBILITY` with detail "missing usage ratio" against the category
`suministros_home_office_luz`.

The engine's refusal is correct, and the bundled manual says why. The 2024 renta
manual, discussing an inmueble used partly as vivienda habitual and partly for the
activity, separates the two kinds of cost: charges arising from OWNERSHIP are
deductible in proportion to the part of the dwelling given over to the activity,
while suministros are governed by regla 5.ª of article 30.2 of the IRPF law, which
it states applies "cuando el empresario o profesional ejerza su actividad en su
propia vivienda habitual". The usage ratio is a condition of the home-office
suministros deduction, not an optional refinement, so a home-office suministros row
that carries no ratio is genuinely ineligible and refusing it is the law being
applied rather than a gap.

The test deliberately builds that row. Its aggregation helper defaults to
`SUMINISTROS_LOCAL_AFECTO` -- the local, which is the scenario the module is named
for -- and one assertion re-resolves the same facts under
`SUMINISTROS_HOME_OFFICE_LUZ` to demonstrate that the carve-out does not reach a
local. The home-office variant is therefore fixture, not registry content, and it
is incomplete: it asserts a clean aggregation for a categorisation the law does not
permit without a ratio.

This was left unrepaired deliberately. Completing the fixture means supplying a
usage-ratio figure, and regla 5.ª sets that proportion from the share of the
dwelling actually given over to the activity -- a fact about a taxpayer, which this
example does not state. Inventing a percentage to clear four issues would put a
fabricated tax figure into a worked example whose entire purpose is to be an
independent check on the engine. The finding is that the fixture needs a grounded
ratio, and that the engine and the registry are both behaving correctly.

## Generator finding: one text naturaleza, two vocabularies, one derivation code

`_normalise_field` in the export-tree generator chose between the two text
derivation codes with `"text-a-v1" if type_code == "a" else "text-an-v1"`,
guarded by a seven-member `_TEXT_TYPES` set. AEAT states the same two
naturalezas in two vocabularies: a workbook prints the abbreviation `A`/`An`,
and a PDF design prints the word, which the shipped parser canonicalises to
`Alfabético`/`Alfanumérico`. Accent-folded, `alfabetico` is not `a`, so every
PDF-sourced *alfabético* field fell to the `else` and was recorded as the
ALPHANUMERIC derivation. Nothing refused: the comparison simply evaluated
false.

The signature was visible in the shipped manifests before any code was read.
Across the 27 enrolled trees, joining each `source_ref` to its `corpus_path`
extension:

| source | trees | `text-a-v1` | `text-an-v1` |
| ------ | ----: | ----------: | -----------: |
| `.xlsx` | 14 | 26 | 796 |
| `.xls` | 7 | 11 | 602 |
| `.pdf` | 6 | **0** | 201 |

Every workbook-sourced tree reads the abbreviation and emits both codes. No
PDF-sourced tree emits the alphabetic code even once. Extracting the six
bundled PDFs confirms the designs are not simply free of alphabetic fields --
they carry 24, 24, 13, 31, 29 and 36 `Alfabético` occurrences respectively
(modelos 184 ×2, 185, 296, 347 ×2). A zero against that is a defect, not a
distribution.

The two codes pass identical arguments to `_schema_field` and differ only in
the label, so no emitted byte moves: the damage is confined to provenance
fidelity. That is still a failure of the same kind the export rules name --
a manifest asserting a derivation that was not the applicable one.

### Second defect found in the same set

`blancos` sat in `_TEXT_TYPES` and therefore also landed on `text-an-v1`. A
blank run states no text representation to derive one from. Where the semantic
map declares such a field a FILLER it returns earlier with `filler-v1` and
never reaches the naturaleza read at all; reaching it means the design says
"blanks" while the map says the field carries a value. That is a disagreement
between two authorities, and the honest answer is a refusal naming the field,
not a text derivation invented for it.

### Disposition

`_TEXT_TYPES` is replaced by `_ALPHABETIC_TYPES` and `_ALPHANUMERIC_TYPES`,
split by the naturaleza AEAT names rather than by the vocabulary it names it
in, plus `_BLANK_RUN_TYPES`, which refuses. Both gates were proven by
sabotage: restoring `type_code == "a"` reds exactly the two word-spelling
cases with `assert 'text-an-v1' == 'text-a-v1'` while the abbreviation cases
stay green, and readmitting the blank run reds the refusal with DID NOT RAISE.

### Lesson

A membership set and a derivation keyed off one of its members are two
declarations of the same fact, and the wider set silently absorbs the
mismatch. The tell is a *derived* value whose distribution is degenerate on
one partition of the inputs -- here, a code that never once appears among a
third of the corpus. Reach for that comparison on any generator whose output
is a label rather than a number, because a label carries no arithmetic that
would otherwise fail.

## The blank-run refusal named a live filing-grade defect in modelo 347

The refusal added above fired immediately on real shipped data:

```
official field 'm347-2011.declarado.f027' declares blank-run naturaleza
'Blancos', which states no text representation, but the semantic map does not
declare it a filler
```

Reading the two designs settles it. `aeat-dr-347-2011` states one row for the
whole tail of the declarado record:

```
264 -500 -------- BLANCOS.
```

`aeat-dr-347-2025` is where the field was introduced:

```
264-280 Alfanumérico NIF OPERADOR COMUNITARIO
282     Alfabético   OPERACIÓN CON INVERSIÓN DEL SUJETO PASIVO
```

The 2011 semantic map nevertheless declared, citing `aeat-dr-347-2011` as its
own source:

```toml
export_field_id = "m347-2011.declarado.f027"
kind = "casilla"
casilla_id = "contraparte.nif-operador-comunitario"
```

and the SHIPPED export tree carries it as `offset = 264`, `length = 237`,
`casilla_id = 'contraparte.nif-operador-comunitario'`. 500 − 264 + 1 = 237, so
the extent is exactly the blank run: the region was read correctly and then
bound to a casilla that did not exist in that revision. A 2011-2024 modelo 347
filing carrying a value on `contraparte.nif-operador-comunitario` writes it
left-justified across 237 bytes of space the design mandates be blank. The
field is `required = false`, so the defect is latent rather than universal, but
it is filing-grade, not provenance-grade.

The entry looks copied from the 2025 map without re-reading the 2011 design.
The corrected 2011 declaration is `kind = "filler"` with the casilla binding
removed; the region, legal refs, source ref and anchor are unchanged, because
only the binding was ever wrong.

### What this says about the pre-existing red

Both m347 rows were ALREADY failing check mode before any of this work, both
on `['0002-record-m347-declarado.toml']`, with no diagnosis attached. Baselining
the pre-fix generator against the same two rows confirms it: the drift predates
the change, and the refusal is what finally named its cause. A committed
artifact that a fresh render disagrees with had been read as staleness for as
long as it had been red; it was a data contradiction the whole time.

### Lesson

A generated artifact drifting from its source is reported as "stale", and
staleness is the innocent reading -- it invites republication rather than
diagnosis. Republishing modelo 347 at any point would have overwritten the
evidence and closed the gate green on the WRONG side, keeping the casilla
binding and losing the only signal that anything was wrong. Before republishing
a drifted tree, establish WHICH side is right. The refusal that fires during
the fresh render is the cheapest way to find out.

### Bounding the defect class: how far does the blank-run binding go?

One instance is a bug; the question is whether it is a pattern. The sound test
is EXACT EXTENT: extract every `NNN-NNN ... BLANCOS` row from each PDF design,
then look for a committed `kind = 'casilla'` field whose `[offset, offset+length-1]`
equals one of those ranges exactly. Across all six PDF-sourced designs:

```
aeat-dr-184-2023-2024   (221,487) (230,500)
aeat-dr-184-2025        (230,487) (230,500)
aeat-dr-185-2026        (104,500) (147,500)
aeat-dr-296-2024        (150,499) (190,390) (310,499) (400,487) (430,432)
aeat-dr-347-2011        (77,99) (185,390) (264,500) (334,500) (400,487)
aeat-dr-347-2025        (77,98) (186,390) (306,500) (334,500) (400,487)

exact hits: 1
   m347 2011-2024  m347-declarado  264-500  contraparte.nif-operador-comunitario
```

The single hit is the defect already corrected. The class is bounded at one
instance in the PDF-sourced corpus.

The looser OVERLAP variant of the same test reports 362 rows and is UNSOUND as
run: a record design carries several record types, each with its own position
space starting at 1, and pooling their BLANCOS ranges per modelo compares a
tipo-2 field against a tipo-1 blank run. The 362 is an artifact of that pooling,
not 362 defects, and must not be quoted as a finding. Exact-extent equality is
what makes the test sound without record alignment: a coincidence across two
different record types is vanishingly unlikely, and the generator's own geometry
validation (contiguity plus `declared_total`) already refuses a field straddling
a blank run inside its OWN record.

## Phase 2 measured from the loaded snapshot: both named items are correct absences

`audit_bundled_registry_conformance(validate=True)`, read through the authority
rather than off a directory listing:

```
total rows:                  128
rows NOT registry_validated:   0
rows reporting any gap_tiers: 121
rows reporting required_tier_gaps: 0
```

Every conformance row is `registry_validated`, and no row anywhere reports a
required-tier gap. The two items carried as open resolve as follows.

**modelo 165 revision 2023-2025** does carry `layout_authority` in `gap_tiers`
-- it is the only row in the tree with any gap beyond
`executable_parity_evidence` -- but its `required_tier_gaps` is empty and its
`authority_scope` is `inspection_only`. That is the computation working as
designed: required-tier gaps are projected only for a `filing_eligible` ledger,
so an inspection-only revision keeps the discovery evidence visible in
`gap_tiers` without a non-filing read being promoted to a filing-grade defect.
A layout authority is what FILING needs, and this revision does not claim to
file.

**modelo 714 revision 2025** has `layout_authority` SATISFIED and
`authority_scope = filing`. Its only gap is `executable_parity_evidence`, which
is not a required tier at all.

### The distinction that decides both

`REQUIRED_COVERAGE_TIERS` is `(legal_authority, official_source_guidance,
layout_authority)`, and the module says why the boundary is public: "a gap on
one of these is a failure, while a gap on `executable_parity_evidence` is a
reported absence, and a consumer that cannot tell them apart reports an expected
absence as a defect."

That is precisely the trap here. Reading `gap_tiers` gives 121 of 128 rows
"failing"; reading `required_tier_gaps` gives zero. The registry already
encodes the difference between an absence it expects and one it refuses -- the
reporting error is to collapse them. Read the field the model computes for the
question being asked, not the field whose name is closest to it.

## Provenance: the defect was predicted, deferred, and then half-landed

The naturaleza collapse was not an oversight nobody had seen. The ADR
`2026-08-16-aeat-export-fragment-generator-authority-pdf-source-wire-fact-authority-adr`
names the exact function and the exact cause, and marks it **not landed**:

> The fourth is `_normalise_field` in `_export_tree.py` and is **not landed**. It
> casefolds the AEAT type against `_TEXT_TYPES` and `_NUMERIC_TYPES` -- the
> workbook tokens -- and refuses anything else as an unsupported type, so a
> `Numérico` field never reaches a renderer at all. [...] So the renderer needs
> exactly the two changes eligibility received -- recognise the canonical
> spellings, and route PDF fields to the profile rather than to content
> derivation -- plus the text-type spellings (`Alfanumérico`, `Alfabético`,
> `Blancos`) for the non-numeric anchors. That file is held by an in-flight
> campaign, so it is named here rather than edited.

What happened afterwards is the instructive part. The remedy landed on the
NUMERIC side properly: `_is_numeric_aeat_type` matches both vocabularies, and
its own docstring records the same bug and the same consequence -- "Selecting on
the abbreviations alone made every PDF design's numeric fields ineligible, so no
reviewed rule was ever demanded for them and an empty profile satisfied
exhaustive coverage completely."

On the TEXT side only half the remedy landed. The spellings were added to
`_TEXT_TYPES` -- which is the only reason `alfabetico` was in the set at all --
but the discriminator that reads the set was left as `type_code == "a"`. The
membership widened; the branch that interprets membership did not.

### Lesson

Widening a membership set is not the whole change. Every discriminator that
reads that set is a second, separate declaration of the same vocabulary, and
adding a member silently redistributes inputs across branches that were written
when the set was smaller. The fix on the numeric side was verified by its own
eligibility test; the text side had no equivalent, so nothing failed.

When a deferred remedy is finally applied, re-read the deferral note and check
off each part it named. This one named three: canonical spellings, PDF routing,
and the text-type spellings. Two landed. The third -- the one with no owning
test -- did not, and shipped wrong provenance across six revisions.

`_NUMERIC_TYPES` is removed here as the last remnant of the abbreviation-only
approach: it had no readers left, while its comment still asserted a role
numeric membership no longer takes from it. A dead frozenset named for the
vocabulary is exactly the wrong thing for the next reader to find.

## Closing census: every naturaleza the corpus contains, and where it routes

Parsing all 27 enrolled designs through the shipped
`load_record_design_intermediate` gives the complete input vocabulary --
9 distinct values over ~13,300 field rows:

| naturaleza | rows | routes to |
| --- | ---: | --- |
| `Num`, `N`, `Numérico` | 10,198 | numeric derivation |
| `An`, `Alfanumérico` | 2,799 | `text-an-v1` |
| `A`, `Alfabético` | 191 | `text-a-v1` |
| `No consta` | 95 | reviewed render profile |
| `Blancos` | 28 | refuses unless the map declares a filler |

Every value is handled, and the handling is now correct for each. The census
also dates the defect precisely: **70 of those 191 rows are the `Alfabético`
word spelling**, against 121 carrying the abbreviation `A`. Those 70 were the
rows reaching the alphanumeric derivation.

### Correction: a probe artifact, caught before it was reported

The first run of this census labelled the 95 `No consta` rows
"UNHANDLED -> refused as unsupported". They are nothing of the kind.
`ABSENT_NATURALEZA_TYPE_CODE = "No consta"` is the marker the shipped parser
stamps when AEAT prints the naturaleza cell EMPTY -- deliberately, because "an
inferred `Alfanumerico` would be indistinguishable from one AEAT actually
printed" -- and `_normalise_field` routes exactly those rows to the reviewed
render profile. The probe modelled four branches of a five-branch function and
reported the fifth branch's inputs as unhandled. A probe that reconstructs
production logic evidences only the code its author read.

### Correction: publish mode is exercised; what is missing is an operator surface

An earlier note in this audit recorded that
`publish_validated_generated_export_tree` "has no caller". That was a bad
measurement, not a fact. The grep excluded its own defining module with
`grep -v "_tree_publication.py:"`, and that substring also matches
`test_generated_tree_publication.py:` -- so the exclusion silently removed the
entire publication test file, which calls the authority about ten times across
success, refusal, journal-recovery and rollback paths.

The accurate statement is narrower and still the blocker: publish mode is well
exercised against isolated temporary roots, and has no OPERATOR-facing
invocation that publishes into the bundled registry. So of the three lifecycle
stages, render is exercised, check mode is called for every enrolled tree but
cannot pass for any of them (it demands a filing-complete, operator-reviewed
revision, and none is reviewed yet), and publish has no route an operator can
reach.

**Lesson.** An exclusion pattern is a filename substring, and filenames nest:
`test_generated_tree_publication.py` contains `_tree_publication.py`. Excluding
a module by path fragment can remove its test file, its variants, and anything
whose name embeds it -- and the loss is silent, because a filter that removes
too much looks exactly like a search that found little. Anchor the exclusion
(`^dev/registry/pipeline/_tree_publication.py:`) or exclude by an exact path.

## Phase 1: grounding the AD-HOC adjudication against the bundled orden

The modelo 308 ADR rested on a quotation. Checked against the corpus rather than
recollection: the clause is verbatim in
`corpus/normatives/html/orden-eha-1033-2011.html` under `Disposición final
única. Entrada en vigor`, and the orden is registered at provision granularity
(`orden-eha-1033-2011:disposicion-final-unica`, `:articulo-unico`), so the
citation is a real authority rather than a reference to one.

The stronger evidence is a NEGATIVE. Across the whole 1,971-word orden the word
*ejercicio* occurs **zero** times, while *anexo II* occurs four times and *308*
twelve. The document extracted properly and is unmistakably the right one; it
simply carries no ejercicio-keyed applicability formula anywhere. So the claim
is not merely "this clause states a date rather than an ejercicio" but "the
governing instrument contains no ejercicio at all to key a revision on".

The same orden then supplies affirmative support for the axis the ADR adds: its
refund provision runs the deadline from the operation -- "en el plazo de tres
meses desde que se haya realizado la entrega de bienes que origina el derecho a
la devolución". The law already keys this modelo's obligations to the event
date, so an AD-HOC work target carrying its operation date restates something
the orden relies on rather than inventing an axis.

### Lesson

A positive citation proves a clause exists; it does not prove the alternative
reading is absent. Where a decision turns on which axis the law keys to, the
decisive measurement is the ABSENCE of the rival key across the whole
instrument, and that is only credible with the extraction sanity-checked --
word count, plus a control term you expect to find. Zero occurrences of
*ejercicio* means little on its own; zero *ejercicio* beside twelve *308* and
four *anexo II*, in 1,971 extracted words, means the search worked and the term
is genuinely not there.

## A split that landed one step short took the whole registry lane down

`test_revision_span_matches_published_designs` was split into four
`_revision_span_*_support` modules and deleted. Four consumers still imported
from it. Unlike the earlier sighting of this, the module is now absent at HEAD
as well as on disk with a clean status, so this was not a mid-flight working
tree: a clean copy of main could not collect the registry test lane either.

The severity is out of proportion to the cause, and that is the point worth
recording. Four bad import lines produce four COLLECTION errors, and pytest
interrupts the entire run on a collection error rather than proceeding with
what it could gather. So the lane did not report 6,793 passes and 4 broken
modules -- it reported nothing at all, and had been doing so for as long as the
deletion had been committed. A gate that cannot be collected is
indistinguishable, in a CI summary, from a gate nobody ran.

Every one of the seven imported names resolved to exactly one support module,
so the repair was mechanical rather than a judgement call: 4 errors and 6,793
collected became 0 errors and 6,811 collected.

One surviving reference was prose -- a docstring in
`test_every_bundled_design_is_read_or_reported` naming the deleted module as
"the sibling guard". Repointed at `test_revision_span_boundaries`, which is
where that inventory guard now lives. A dangling name in prose costs nothing at
runtime and everything to the next reader trying to find the guard being
described.

### Lesson

This is the third relocation this session to land with its consumers
unswept, and each time the error names a MISSING MODULE rather than an
unfinished sweep, so the first person to hit it reasonably concludes their own
lane is broken. When a rename or split is the suspected cause, the cheap
discriminator is `git cat-file -e HEAD:<old path>`: present at HEAD and absent
on disk means someone is mid-flight and the sweep is theirs to finish; absent
in both means the breakage has LANDED and repointing is the repair, not an
intrusion.

## An import-integrity scan, and the two breakages collection cannot see

After repairing the span-split consumers, the obvious question was whether any
other relocation had landed unswept. Two static scans over all 6,667 modules
under `src/` and `dev/`, no test run involved.

**Unresolvable modules: 0.** Every first-party `import`/`from ... import`
resolves to a module or package that exists. The span split was the only one.

**Unresolvable NAMES: 2**, and both are the interesting kind, because neither
is visible to a collection sweep -- both imports sit inside a function body, so
they raise only when that one test runs:

- `test_printed_country_name.py` imported `_normalise_printed_country_name`
  from `establishment`. It lives in `country_vocabulary`; `establishment` only
  calls it through that module. Repointed.
- `dev/docs/sequences/tests/test_runner.py` imports
  `probe_subprocess_providers` from `cadrumo.application.provisioning`. That
  symbol is defined nowhere: commit `5d96d24034` (2026-08-07) is titled "delete
  the subprocess provider probe and its doctor branch". The consumer has been
  broken for over three weeks. NOT repaired here -- there is no target to
  repoint to, and deciding what the test should assert once the probe is
  deliberately gone is the deleting lane's call, not a mechanical fix.

### The distinction worth keeping

A module-level bad import kills COLLECTION, and pytest interrupts the whole run,
so it is loud and total. A function-local bad import kills ONE TEST at run time
and reads, in a failure summary, like a product defect rather than an unswept
relocation. The second is strictly harder to attribute and survives far longer
-- three weeks here, against the span split's hours.

### Two scanner traps, both hit and both fixed before reporting

The first pass reported **210** unresolvable modules. All false: for a package
`__init__.py`, the current package is the file's OWN module, not its parent, so
level-1 relative imports were resolved one level too high and every package
initialiser's own submodules read as missing.

The second pass reported **1,639** unresolvable names. Also false: PEP 695
`type X = ...` produces an `ast.TypeAlias` node, which a collector written
around `Assign`/`AnnAssign`/`FunctionDef`/`ClassDef` silently drops -- so every
modern type alias in the tree looked undefined. Handling `TypeAlias` took it to
12, of which 9 were dunder module attributes (`__doc__`, `__path__`) the
scanner does not model.

210, then 1,639, then 2. A scanner's first number is a measurement of the
scanner. Neither figure was reportable, and the tell in both cases was the same:
a defect count far too large to be consistent with a tree whose tests mostly
pass.

## Which narrow vocabularies are dangerous, and which are not

Having found the same defect twice in membership sets, the third one in the
pipeline deserved the same scrutiny -- and it turns out to be correctly built,
for a reason worth stating because it distinguishes the two cases.

`_FILING_INSTRUCTION_ONLY_CONTENTS` is a single-phrase set, `{"no
cumplimentar"}`, matched on an exact stripped casefold. Narrower than the
naturaleza sets ever were, and the narrowness is deliberate: "'no' and
'cumplimentar' both appear inside legitimate descriptions of what a slot
carries, and a loose rule would make real wire facts invisible to review."

The difference that matters is what happens to an unmatched value.

- Naturaleza: an unrecognised text spelling fell to an `else` and was recorded
  as the ALPHANUMERIC derivation. The fall-through was a WRONG ANSWER, silently.
- Filing instruction: an unrecognised variant makes `_states_no_wire_fact`
  false, so the field is read as stating its wire fact, the prose does not
  parse, and the renderer REFUSES. The fall-through is a refusal.

So the question to ask of a narrow vocabulary is not "does it list every
spelling AEAT uses" but "where does an unlisted spelling land". A set whose
miss lands on a refusal can be as narrow as its author can defend, and being
narrow is then a virtue -- it keeps a real value in front of a reviewer. A set
whose miss lands on a branch must be exhaustive, because nothing downstream
will ever question the answer it produced.

That reframes the earlier lesson usefully: widening a set is not the whole
change *when a discriminator reads it*. Where the set only decides
matched-or-refused, widening it is the whole change, and not widening it is
safe.

### Measured: widening that phrase set would have been the defect

Censusing every design field whose content mentions *cumpliment* across all 27
enrolled designs gives 76 distinct contents. Exactly one is the instruction
phrase, on 6 fields:

```
x6   'No cumplimentar'                                    -> matched
```

Every other one is a genuine description of what the slot carries:

```
'Se cumplimentará una de las siguientes claves: "C": ... "T": Transmisión tel…'
'deberá cumplimentarse obligatoriamente uno de los siguientes campos: 121 …'
'Se cumplimenta con el porcentaje de retención aplicado por el obligado a …'
'Se consignarán los días de alta cotizados … cumplimentados a ceros por la izquierda.'
```

So a keyword rule on *cumplimentar* would have swept roughly seventy
value-bearing fields into "the design states no wire fact", which is the precise
harm the author's comment predicted. The prediction was not defensive
hand-waving; it is now measured.

This is the counterexample to the instinct the naturaleza defect encourages.
Having just been burned by a set that was too narrow, the reflex is to widen
every set nearby. Here widening is the defect, and the discriminator is the one
above: a miss lands on a refusal, so narrowness costs a reviewer's attention,
while looseness costs seventy fields their review.

## The HEAD-vs-disk discriminator is DIRECTIONAL, and the deadlock can be mutual

The rule recorded above -- present at HEAD and absent on disk means someone is
mid-flight, absent in both means the breakage has landed -- is sound but
incomplete, and the missing half was found in practice on a facade retirement
running beside this work.

Applied to the FILES a lane is holding, the check says "they are mid-flight,
wait for them". Applied to the MODULES THOSE FILES IMPORT, it can say the same
thing about you. A worked instance, measured module by module:

```
utils                 HEAD=yes  disk=no    <- retiring lane removes it; consumers at HEAD still import it
source_provenance     HEAD=no   disk=yes   <- renaming lane's files import it; it exists only on disk
page_text_extraction  HEAD=yes  disk=yes
extracted_casilla     HEAD=yes  disk=yes
label_regex           HEAD=yes  disk=yes
```

Each lane's commit alone breaks HEAD, in mirror image: one would remove a module
HEAD still imports, the other would import a module HEAD does not have. Reading
only the held files shows one direction and invites an indefinite wait for a
lane that is equally blocked on you.

**The resolution is additive, not a joint commit.** The new module was committed
ALONE, removing nothing, so HEAD resolves for both lanes and either can land
next in any order. The retirement of the displaced module follows afterwards.
The cost is a duplicate definition visible only to a checkout of that single
revision and never to a gate -- which is a real cost under
`no-legacy-compatibility`, and is why the retirement must actually follow rather
than be forgotten.

### Lesson

Run the HEAD-vs-disk check on the module DEPENDENCY EDGES, not on the files. The
file-level answer names who is mid-flight; the edge-level answer tells you
whether the block is one-way or a cycle. And when it is a cycle, look for the
additive move that makes HEAD resolvable for both sides -- coordinating two
lanes into one commit means one absorbs the other's work under its message,
which is the thing to avoid.

A second confirmation from the same exchange: an AST sweep of function bodies
across `src/` and `dev/` came back clean for that retirement -- thirteen
function-local imports touching the relevant package, none reaching the facade.
A clean result from that scan is still worth having, because a green collection
cannot produce it.
