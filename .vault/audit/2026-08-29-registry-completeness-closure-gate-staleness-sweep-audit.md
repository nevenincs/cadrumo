---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-29'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:fd09067af59038323cdad6d1d2a833cb9483aafecbd9e039fc9972d62133d8f6'
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
