---
tags:
  - '#audit'
  - '#registry-deadline-window-span'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0bd5c39ddc9fe27421e0405573fb44d8b45b0669ea910b1dfefa6a0bed93983d'
related: []
---

# `registry-deadline-window-span` audit: deadline-window span ownership

A registry revision may declare deadline windows only for filing years inside
its own span. Four modelos violated that, and the violations made the entire
registry fail to load, which reddened twelve core tests that never mention
deadlines.

## Fixed: revisions declaring another revision's windows

Modelos 210, 353 and 322 each had a revision carrying byte-identical copies of a
sibling revision's windows. Modelo 210's two revisions (`2025` and
`2026-y-siguientes`) were complete duplicates of one another: all eight window
ids present in both, every body identical.

- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/deadline_windows/0001-deadline-windows.toml` -- carried four `filing_year = 2026` windows
- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2026-y-siguientes/deadline_windows/0001-deadline-windows.toml` -- carried four `filing_year = 2025` windows
- `src/cadrumo/_data/registry/aeat/modelos/353/revisions/2026-y-siguientes/deadline_windows/0001-deadline-windows.toml` -- carried three `filing_year = 2025` windows
- `src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-2022/deadline_windows/0001-deadline-windows.toml` -- carried two `filing_year = 2023` windows

Each out-of-span block was removed, along with its id in the revision's
construct completeness manifest. Registry validation errors fell from 3183 to
2760, and every remaining error belongs to modelo 303 or 184.

Landed as `c5f7ff7f94` and `f6dd525b73`.

## Fixed: an emptied fragment is a hard load failure

Modelo 322's `2008-2022` window fragment held nothing but the two out-of-span
2023 windows, so removing them left a zero-byte TOML file. The loader refuses a
fragment without a `[revisions.<id>]` table, and then refuses a fragment
directory with no TOML in it -- each a `RegistryLoadError` that made the whole
registry unloadable, a strictly worse failure than the duplication being fixed.
The fragment and its directory were removed.

When a span sweep empties a fragment, delete the fragment and its directory in
the same change; do not leave an empty file behind.

## Corrected: modelo 184 -- I deleted the wrong side of the disagreement

`src/cadrumo/_data/registry/aeat/modelos/184/revisions/2015-2024/` declared
`valid_from = 2023-01-01`, `valid_to = 2024-12-31` and
`period_selector = { year_from = 2023, year_to = 2024 }`, while its fragment
carried windows for 2018 through 2022 and its directory was named `2015-2024`.
Five windows therefore failed canonical-owner resolution.

I read the revision file, saw the selector, both validity dates and the source
reference all agreeing on 2023-2024, concluded the windows were unreachable
orphans, and deleted them in `6a69b9715b`. That was wrong. The correct fix was
the selector.

The evidence was in the domain suite, which registry validation was blocking me
from running at the time:

- `test_modelo_184_revision_period_selector_starts_at_2015` asserts
  `revision.valid_from == date(2015, 1, 1)` and
  `revision.period_selector.year_from == 2015`.
- `test_modelo_184_february_deadline_windows_match_hap_2250_2015_art_4` asserts
  the split partitions as `{"2015-2024": 7, "2025-y-siguientes": 2}` -- seven
  windows this revision must own, the five I deleted among them.
- `test_modelo_184_snapshot_builds_for_each_published_filing_year` maps
  ejercicios 2018 through 2024 to `2015-2024` by name.

Orden HAC/1430/2025 partitioned this modelo at ejercicio 2025; it did not move
its start. Reverted and corrected in `9d64e06332`.

**The lesson, and it is the sharper one:** agreement among a revision file's own
fields is not corroboration when a single regression sets all of them. The
selector, both dates and the source ref agreed on 2023-2024 because one bad edit
wrote them together; the directory name and the orphaned windows were the only
surviving witnesses to the truth, and I treated them as the stale side precisely
because they were outnumbered. Corroboration has to come from OUTSIDE the file
-- here, the tests that name the expected span. When the suite that holds that
evidence cannot run, that is a reason to defer the call, not to decide it from
the file alone.

## Open, needs authored windows: modelos 303 and 322 filing-grade gaps

Two revisions claim `filing` authority grade while declaring no deadline windows
of their own. Both were previously masked: each was satisfying the grade with
windows an adjacent revision canonically owns, and removing those duplicates --
in modelo 322 here, in modelo 303 by the separately-briefed deadline-owner fix
`b6312a471c4` -- exposed the real state.

```
modelo 303 revision 2023 claims 'filing' authority grade while ['deadline_windows']
remain blocked pending evidence.
modelo 322 revision 2008-2022 claims 'filing' authority grade while
['deadline_windows'] remain blocked pending evidence.
```

Each governs a real filing year and needs its windows authored:

- **modelo 303 revision `2023`** -- `valid_from 2023-01-01`, `valid_to
  2023-12-31`; zero windows authored.
- **modelo 322 revision `2008-2022`** -- the directory name is again misleading:
  the revision declares `valid_from 2022-01-01`, `valid_to 2022-12-31` and
  `period_selector = { years = [2022], periods = ["01" .. "12"] }`, so it governs
  2022 alone and needs twelve monthly windows.

"Declare the family not applicable" is not available to either: both are
self-assessment modelos with real statutory filing deadlines for the years they
govern, so a not-applicable declaration would be false. The remaining honest
options are authoring the windows against AEAT sources, or downgrading the
authority grade. Authoring requires `legal_refs` and `source_refs` grounded in
official sources, which is why this is recorded rather than guessed.

These two errors are the whole remaining registry-validation surface -- the
count fell from 3183 to 2 -- and they gate the entire tree above core, because
registry validation raises during collection.

## The regression is systematic: sweep every revision id against its span

Modelo 184 was not a one-off. A sweep of every revision whose directory id
encodes a start year found seven disagreements between the id and the
revision's own `valid_from` / `period_selector.year_from`. Two more were the
same defect and are corrected in `34285f97b8`:

  308  `2009-y-siguientes`  valid_from 2019-01-01, year_from 2019  -> 2009
  309  `2004-y-siguientes`  valid_from 2023-01-01, year_from 2023  -> 2004

Both are pinned by tests asserting the earlier start, which is the outside
corroboration the 184 mistake taught me to require. Every one of these
revisions carries `reviewed_at = 2026-08-19` and
`reviewed_by = agent-prepared-pending-operator`, so one sweep appears to have
narrowed several spans at once.

Four disagreements are deliberately NOT touched, because an id is a label and
the selector is the authority -- only evidence outside the file settles which
is wrong:

- **modelo 322 `2008-2022`** -- its own test asserts `valid_from == date(2022,
  1, 1)`, the current value, so the directory name is merely a stale label and
  the 2022 windows authored here are correct.
- **modelos 151, 185 and 720** -- no test asserts a span either way. Recorded
  for an owner rather than guessed at.

## Domain layer remainder, owned elsewhere

With the registry validating, the domain layer measures 83 failures, and every
cluster traced back to another team's in-flight work rather than to a defect
this campaign can close:

- **~51, modelo 200** -- the revision was split, reverted 31 hours later, and
  span-split progress folded in three hours ago; tests request `filing` grade
  while the revision currently declares `calculation`.
- **~14, revision-scoped source windows** -- modelos 193 and 353 cite
  `aeat-calendario-contribuyente-2025/2026` sources whose `applies_from` falls
  after the revision's `valid_to`. Both citations were added within the last
  three hours. Worth noting for whoever owns it: a revision for ejercicio 2024
  is FILED in 2025, so citing the 2025 calendar may well be correct and the
  validator's devengo-span assumption the thing to revisit.
- **~3, modelo 210 quarters** -- the quarterly `1T..4T` windows were replaced
  wholesale with annual `0A` tipo-specific windows by the plazo-authority work;
  the quarterly tests are stale against that new model.

## A measurement note: the tree churns faster than a layer runs

The domain layer takes roughly 22 minutes and peers committed six times during
one run, so a whole-layer failure list is not evidence on its own. Two things
were needed: a runner that records HEAD plus a refreshed tracked-tree hash
before and after and refuses to report a number when they differ, and a
two-pass protocol where the long run only NOMINATES candidates and a short
second pass over just those modules confirms them. Reproduction across two runs
at different HEADs is stronger evidence than tree-stability at either one.

## Application layer: a real cluster fixed, the rest peer-owned

`application/aggregation` measures 24 failures, down from 39. Fifteen shared one
cause worth naming, because it is a test-authoring trap rather than a defect in
what the tests cover.

Each file built a fixture-backed `TransactionCatalogueRepository` and injected
it, but left the SIBLING repositories unset. Production then resolved those from
the real bucket storage runtime -- `import_ledger_transactions` reaching for a
`BucketEventHistoryRepository`, `_load_income_invoices` for an
`InvoiceCatalogueRepository` -- which is not ready in a unit-lane test. Every one
of those tests failed on `errors.storage.runtime.not_ready` before reaching a
single assertion, so the coverage they appear to give was not being exercised at
all. Injecting one repository is not enough: a partially-injected call still
reaches the runtime through whichever seam was left defaulted. Fixed in
`65bafa2f04` against the pattern `test_m210_irnr_income_ledger` already used.

The remaining failures are other teams' in-flight work:

- **modelo 151** was split into `2015-2022` plus `2025-y-siguientes`, and three
  application tests still name `2015-y-siguientes`, the pre-split revision. Note
  that `2025-y-siguientes` declares `valid_from = 2023-01-01`, so it is a third
  id-versus-span disagreement -- but the contiguous 2015-2022 span beside it
  suggests the SPAN is right and the NAME is wrong here, the opposite of 184.
  Left for whoever owns the split.
- **modelo 200 and modelo 036** grade refusals, and **modelo 390** revision
  selection for 2026, reach into the application layer from the registry work
  already recorded above.

## Every layer above core is gated on one shared artefact

Measuring upward stopped being possible, and the reason is structural rather
than a backlog of defects.

The application layer measured 715 failures across a 28-minute run. That number
is not evidence: 15 commits landed while it ran, and roughly 410 of the failures
were registry-sourced. Checking the registry directly afterwards showed it
failing validation on modelo 390 semantic-role constraints, and `git status`
showed those exact 390 casilla fragments DIRTY -- a peer mid-edit, uncommitted,
with 75 files dirty overall.

The harness lane fails the same way: its full-corpus collectability harness
cannot collect `test_clasificacion_casillas_oficiales.py` while the registry is
invalid. So core is the only layer that can be measured independently. Domain,
application, adapters, entrypoints and harness all load the registry during
collection, which means:

**A single invalid registry turns every layer above core red at once, and the
registry is invalid whenever any of several teams is mid-edit.**

That is why layer numbers above core have oscillated between "green" and
"hundreds of failures" within the same hour without any code changing. It is not
flakiness in the tests and not phantom failures in the peers' sense -- the
registry genuinely is invalid at those moments, and genuinely valid at others.

What would make upward measurement possible, in rough order of cost:

- Measure against a fixed commit in a separate git worktree, so peer edits to
  the shared working tree cannot reach the run at all. This is the only option
  that removes the problem rather than working around it.
- Treat registry validity as a precondition gate: assert it immediately before
  and after a layer run, and discard the run when either check fails, the same
  way the tree-fingerprint check discards a run whose HEAD moved.

Until one of those exists, an "all-green" claim for any layer above core is a
statement about one lucky minute, not about the tree.

## The committed tree is red; the green reading lives in one working tree

Measuring from an isolated `git worktree` at a frozen commit settled a question
the shared tree could not answer, and the answer was not the expected one.

Running the registry-validity check two ways at the same moment:

- main's WORKING TREE: passes.
- commit `cf04b1f274`, checked out in a separate worktree: FAILS, on modelo 390
  semantic-role constraint incompatibility across the 2022, 2023, 2024 and 2025
  casillas against the 2021 canonical.

The difference is three uncommitted paths in main: a modified 2021 casilla
fragment, a modified `2022/revision.toml`, and an UNTRACKED
`2022/casilla_continuidad_evolutions/` directory. The repair exists only as
work-in-progress in one working tree. The committed state of this repository
does not load a valid registry.

That matters beyond this session: a fresh clone, a CI run, or any worktree
created from HEAD gets the red registry. The green readings that made this
campaign look nearly finished were reading one person's uncommitted work.

I had this backwards twice before getting it right. First I inferred from
`git status` that dirty files CAUSED the breakage; then, when main passed, I
corrected that to "the repair is committed". Both were wrong, and only running
the same check against a frozen checkout distinguished them. A working tree
cannot testify about what is committed.

## Layer measurements from the isolated worktree

Taken at the frozen red-registry commit, so the registry-caused share is
separated rather than mixed in:

| layer | failures | registry-caused | genuine |
|---|---|---|---|
| core (main worktree) | 0 of 2233 | -- | 0 |
| adapters | 346 | 333 | 13 |
| entrypoints | 31 | few | ~20 |

**96 per cent of the adapter layer's redness was one registry defect.** The same
almost certainly applies to the application layer's 715 and much of domain's 83.
Layer counts above core measure shared-artefact validity far more than they
measure the layer, which is why fixing registry validation (3183 -> 0 earlier in
this campaign) moved more tests than any test-level work.

The adapters' 13 genuine failures: a TUI width limit on
`_recovery_words_screen.py`; two `en-copy`/`es-copy` locale assertions in
`test_flow_tui_app`; a custody test not raising `ProfileCustodyPasswordError`;
two `MovementRecord` validation errors in `test_inventory_concurrent_write`; a
source-mesh revision roundtrip; `test_package_module_allowlist` flagging
`test_auth_preconditions.py` and siblings (new peer files); the operations
facade export ordering; and `AuthDiagnosticDetail.operator_report_command`.

## Open: a submitted-file fixture disagrees with the fixed-width codec

Seven `TestSubmittedFileObservation` tests fail with:

```
signed export field 'modelo-130-casilla-03' must use ASCII space or N as its
sign marker
```

`src/cadrumo/tests/fixtures/aeat-sede/submitted-files/modelo-130-2026-1T-redacted.txt`
holds unbroken digit runs where the layout expects a sign position. The
fixture is six weeks old and unchanged; the codec rule arrived two weeks ago
with `6875cfeb625 feat(export): centralize fixed-width codec`. So one of the two
is wrong and the newer one is the codec.

Three things need an owner, and none should be guessed:

1. **Is modelo 130 casilla 03 signed in the official design?** It carries the
   rendimiento neto, which can be negative, so a sign position is plausible --
   but plausible is not grounding, and inventing a fixed-width layout fact is
   exactly what `aeat-calculation-grounding` forbids.
2. **Is this fixture real or synthetic?** It is named `-redacted`, implying a
   sanitised AEAT artefact, but its content reads synthetic: `CONTEXT TEST`,
   `ANA`, NIF `I12345678Z`. That distinction decides the fix -- a real artefact
   means the codec must accept what AEAT actually emits (external-world
   variability is explicitly not this project's legacy), while a synthetic one
   means the fixture encodes the field wrongly and should be regenerated from
   the layout.
3. **It carries no provenance sidecar.** `aeat-quality-gates` requires every
   fixture to declare `real_corpus` or `synthetic_generated`, cross-checked
   against physical evidence. This one declares nothing, which is why question 2
   cannot be answered from the tree. The sibling
   `modelo-100-2024-0A-carry-agreement-synthetic.json` shows the shape.

The provenance gap is the root problem: had the fixture declared what it is, the
codec change would have been checked against a known artefact class instead of
turning seven tests red with an unanswerable question.

## Full-tree measurement and the remaining clusters

Measured at frozen commit `e493848e93`, the first commit in this campaign whose
COMMITTED registry validates:

| layer | failed | passed | pass rate |
|---|---|---|---|
| core | 0 | 2233 | 100.0% |
| domain | 97 | 8728 | 98.9% |
| application | 514 | 8604 | 94.4% |
| adapters | 34 | 4261 | 99.2% |
| entrypoints | 15 | 1382 | 98.9% |
| **total** | **660** | **25208** | **97.4%** |

### Closed since that measurement

- **Ledger evidence, 82 -> 41.** Fourteen modules seeded no profile, so every
  confirm and draft test refused on the missing fiscal-address postcode -- the
  fact that separates peninsula from Canarias and Ceuta y Melilla, never read
  off an invoice -- before reaching any assertion. Seeding moved into
  `_evidence_test_support` as an autouse fixture each module binds.
- **`test_invoice_link_event`, 3 -> 0.** All three asserted the bucket event log
  was entirely empty, but the profile capsule has emitted its own
  `PROFILE_BUCKET_CREATED` event for eleven days. They now assert the delta.

### Open, with diagnosis

- **~119, modelo 200 and 036 authority grade.** `modelo 200 revision
  2024-y-siguientes declares 'calculation' authority grade, which cannot satisfy
  the requested 'filing' snapshot authority`. Whole modules ride on this --
  `test_export_implicit_decimal_slots` is 13 failures of nothing else. Same
  class as the 117/126/128/136 attestations already briefed out; needs an
  attestation decision, not a code change.
- **~41, confirmation blockers.** The confirmation gate began requiring blocker
  resolutions eleven days ago (`252e29f6f95`) and these tests supply none. The
  postcode refusal was masking this. Each needs the right resolution
  constructed against the blockers its fixture invoice actually raises.
- **~16, rectificativa aggregate context.** `CalculationRevision` refuses a
  rectificativa built without a context-bound
  `CalculationRevisionAggregateContext`. The canonical pattern is in
  `test_m303_rectificativa_motive_lifecycle`: build the context from work units,
  filing records, justificantes and registry snapshots, then
  `model_validate(..., context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY:
  context})`. Nine of these sit in `test_prior_domiciliation_election`.

  **This is not a mechanical fixture edit, and should not be attempted as one.**
  For an M303 rectificativa `validate_calculation_revision_aggregate` also calls
  `_require_m303_filing_evidence(revision)`, so the REVISION must itself carry
  M303 filing evidence whose coordinate resolves a record design, whose design
  authority the snapshot must attest, and whose motive and target receipt must
  both exist -- the receipt carrying a presentation_id and matching the
  taxpayer and filing coordinate. `test_prior_domiciliation_election` builds its
  revisions with `filing_instance_evidence=None`, so satisfying the validator
  means reconstructing that whole evidence chain inside a module whose subject is
  direct-debit election refusals. Whoever owns the M303 rectificativa evidence
  chain should decide whether these tests need real rectificativa revisions at
  all, or whether their subject is reachable without one. Guessing a fixture
  here risks encoding a defect as the contract.
- **~5, source provenance id.** Fixtures use a placeholder
  `calculation_revision_id` of sixty-four `a` characters that no longer matches
  the content-addressed derivation.
- **7, the m130 submitted-file fixture** recorded above, blocked on provenance.

### The pattern worth carrying forward

Roughly 120 of the failures closed in this campaign were tests that never
reached an assertion -- missing fixture facts, absolute assertions invalidated
by a new lifecycle event, partially-injected repositories escaping to a real
runtime. A test failing in setup is worse than one failing an assertion: its
name still promises coverage, and the suite still counts it, but it has not
exercised the behaviour it is named for since the day it broke. Several had been
in that state for eleven days or more.

## Measured: what the modelo 200 filing-grade attestation would buy

The largest open cluster was recorded above as "an attestation decision, not a
code change". That is still true, but the decision can be made with numbers
rather than in the dark. Measured in the throwaway measurement worktree, never
in the shared tree, by raising `authority_grade` on modelo 200 revision
`2024-y-siguientes` from `calculation` to `filing` and then restoring it:

| state | filing + modelo packages |
|---|---|
| `authority_grade = "calculation"` (committed today) | 280 failed, 2086 passed |
| `authority_grade = "filing"` | **230 failed, 2136 passed** |

**Registry validation passes at filing grade.** Every enrolled family is already
present in that revision -- applicability, bindings, casillas, completeness
manifest, constructs, deadline windows, export, formulas, parameters,
projection endpoints, relations, verification expectations and predicates -- so
the filing rung's assertion that every family resolves is already satisfied by
the data. Unlike modelo 322, where the equivalent refusal exposed a genuine
absence of deadline windows, there is no data gap here to close first.

So the attestation is a stamp, not a work item.

**Corrected, and the correction is large.** The 50 figure counted only the
filing and modelo packages. The domain layer refuses the same way at
`_snapshot.py:386`, and 50 of its 84 failures are modelo 200 modules. Measured
the same way -- raise the grade, run the layer, restore:

| layer | at `calculation` | at `filing` |
|---|---|---|
| domain | 84 failed, 8757 passed | **33 failed, 8809 passed** |
| filing + modelo | 280 failed, 2086 passed | **230 failed, 2136 passed** |

That is **roughly 101 tests from one stamp**, about a sixth of every failure
left in the tree, and whole modules are nothing but this refusal --
`test_export_implicit_decimal_slots` is 13, `test_modelo_200_tipo_gravamen_dispatch`
is 20.

What it is NOT is a stamp anyone should apply casually. The revision carries
`review_status = "agent_reviewed"` and
`reviewed_by = "agent-prepared-pending-operator"`, and the filing rung is the
one that asserts this revision is fit to compute a real taxpayer's filing.
`aeat-calculation-grounding` is explicit that an agent must not stamp a
filing-grade claim under the operator's name. That is why this is recorded with
its measurement rather than applied: the operator now knows the cost is zero
data work and the benefit is 50 tests, and the judgement of whether modelo 200's
2024 content is genuinely filing-grade remains theirs.

The same question applies to modelo 036 revision `2025-02-03-y-siguientes`,
which refuses the same way at `applicability` grade (34 failures).

## Re-measured at `1a82cab2fd`: 660 -> 604

The same five-layer sweep, same method, same isolated worktree, at a later
commit whose registry validates:

| layer | was | now | delta |
|---|---|---|---|
| core | 0 | 1 | +1 |
| domain | 97 | 84 | -13 |
| application | 514 | 462 | -52 |
| adapters | 34 | 36 | +2 |
| entrypoints | 15 | 21 | +6 |
| **total** | **660** | **604** | **-56** |

Pass rate 97.45% -> 97.67%.

### A frozen baseline goes stale, and that is a second failure mode

Before re-measuring I was about to work the twenty `modelo 390: no revision for
year=2026` failures. They no longer exist: peers landed modelo 390 and 369
deadline work after the baseline was taken, and `test_agenda` passes. An hour
would have gone into a cluster the tree had already fixed.

The isolated worktree solved CONTAMINATION -- a run whose tree moves underneath
it. It does not solve STALENESS -- a frozen baseline aging out as real fixes
land elsewhere. Both need the same discipline: re-measure immediately before
acting on a cluster, not only before reporting one.

### Core regressed from green, and it is not the layer's own doing

`test_production_exception_classes_do_not_introduce_unregistered_builtin_roots`
now fails on two classes added by the operations work:

- `application.operations._observation._DefinitionContractMismatchError(RuntimeError)`
  is caught by name inside its own module at `_observation.py:120`, so it is a
  pure internal control-flow signal and the sanctioned fix is a
  `__bare_base_rationale__` declaration.
- `application.operations._journal.OperationObservationCursorAheadError(ValueError)`
  is raised in the persistence adapter and nothing catches it, so it escapes to
  its callers. The gate's other sanctioned route -- derive from `CadrumoError`
  so the class binds to the error registry -- is the fitting one, and it needs a
  registered error code.

Which code, and whether that error is meant to reach an operator at all, are
decisions inside the operations feature, which has been landing in stages
throughout this campaign. Left for its owner with both routes named. Note that
fixing only the first leaves the gate red, so this is one item, not two.

## My span corrections collide with a second gate, and I have to say so

`test_every_claimed_filing_year_is_covered_by_its_declared_layout_design`
fails listing fourteen modelos whose revisions claim ejercicios their own
declared layout design does not cover. Three of them -- 184, 308 and 309 -- are
revisions whose spans I corrected in this campaign.

The corrections were right by the evidence available: modelo 184 has a test
literally named `test_modelo_184_revision_period_selector_starts_at_2015`
asserting `valid_from == date(2015, 1, 1)` and `year_from == 2015`, plus a
partition assertion requiring that revision to own seven windows; 308 and 309
carry equivalent tests naming 2009 and 2004. Restoring those starts is what
those gates demand.

But widening the claimed span widens what the layout design must cover, and the
designs do not. So:

- **Gate A** (`test_modelo_184_revision_period_selector_starts_at_2015`) reds if
  the selector starts late.
- **Gate B** (`test_every_claimed_filing_year_is_covered_by_its_declared_layout_design`)
  reds if the selector starts early and the design does not reach back.

`aeat-quality-gates` names this exactly: "if fix A reds gate B and fix B reds
gate A, neither is right and a third shape is needed", and warns against
resolving it by hiding the construct from one gate's matcher. The third shape
here is the layout designs covering the years their revisions claim -- registry
data work needing AEAT grounding for each modelo's design span, not a selector
tweak in either direction.

Two things keep this honest rather than convenient:

1. **The gate was already red for eleven other modelos** -- 126, 128, 165, 180,
   181, 200, 210, 270, 341, 353, 576 -- so my three did not break a green gate;
   they joined a standing failure whose root cause they share.
2. **Reverting my corrections would not fix it.** It would trade fourteen
   entries for eleven while re-breaking three explicit start-year tests and
   restoring the orphaned-window state that made modelo 184 unresolvable for
   ejercicios 2018 through 2022 in the first place.

Recorded rather than silently left: anyone reading the span fixes should know
they surface a design-coverage gap rather than close one, and that the gap is
the pre-existing condition of this registry.

## Diagnosed: the CLI runtime tests fail on a global-graph coupling

`test_command_runtime` fails three cases with an opaque envelope --
`cli.runtime.unexpected_absent`, exit code 6, "Interno. El comando fallo por un
error interno inesperado". The envelope redacts the cause by design, so the
message names nothing actionable.

Traced by invoking the same synthetic app outside pytest and reading the
exception the envelope swallows:

```
_profile_authentication_gate.py:167, in preflight_parsed_leaf
    node = next(node for node in COMMAND_GRAPH.nodes() if node.spec.key == spec.key)
StopIteration
```

`build_command_app(graph)` compiles an app from ANY spec graph -- that is what
the runtime is for, and what these tests exercise with a two-node synthetic
graph. But the auth preflight resolves the invoked spec against the GLOBAL
production `COMMAND_GRAPH`, so a spec that is not in the shipped surface raises
a bare `StopIteration` that reaches the boundary as an unclassified internal
error. Landed `903dd90992`, two days ago.

The fix is a design choice inside that feature, and both obvious options are
wrong in a way worth stating:

- Giving `next(...)` a `None` default and falling back to a default posture
  would let a spec absent from the production graph run with whatever posture
  the default carries. The posture governs PROFILE AUTHENTICATION, so a
  permissive default fails open on an authentication gate.
- Refusing when the spec is absent fails closed correctly, but still leaves
  these tests red, because their specs are legitimately absent from the shipped
  graph.

The shape that resolves both is for the preflight to consult the graph the app
was built from rather than a module-global, which is a change to how the gate
receives its graph. Left to the owner of the command-runtime work with the
cause named, since the diagnosis -- not the patch -- was the hard part.

## Partially diagnosed: the TUI locale tests

`test_rebuild_for_locale_reassembles_copy_under_the_new_language` fails on its
FIRST assertion: inside `output_language_scope("en")` the rendered page prompt
is `es-copy`, not `en-copy`. It fails in isolation, so it is not pollution from
a sibling test.

What is established:

- The scope itself is sound. Driving it standalone -- enter
  `output_language_scope("en")` plus `locales_root_scope(root)`, then call
  `output_language()` and `tr("flows.test.copy")` -- returns `en` and
  `en-copy`. The seam works.
- `resolve_copy` calls `tr()` directly for a `LOCALE_KEY` ref with no caching,
  so the flow copy path adds nothing between the scope and the lookup.
- The locales-root override DOES reach the running app: the rendered text is
  `es-copy`, a string that exists only in the test's fixture root, so the app is
  reading the fixture catalogues and picking the wrong language within them.

So the divergence appears once the copy is resolved inside the running Textual
app rather than on the calling thread, while the same call resolves correctly
outside it. `activate_output_language` writes `os.environ` and resets the
process-wide Settings cache, which should cross threads; identifying what the
app resolves differently needs instrumentation inside the app's own render
path, which is where this stops.

Recorded rather than guessed at. Note the shape for whoever continues: the
useful next probe is asserting `output_language()` from inside the running app
rather than from the test body, which distinguishes "the app sees a different
language" from "the app resolved its copy earlier than the assertion assumes".

## The 2026 filing year is admitted but modelo 390 cannot serve it

Twenty application failures resolve to one refusal:

```
modelo 390: no revision for year=2026 period='0A'
```

`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml` declares
`years = [2022, 2023, 2024, 2025, 2026]`. Modelo 390 authors one revision per
year and its latest is `2025`, so a 2026 filing coordinate resolves to nothing.
Its siblings do not have this shape: modelos 303, 322 and 353 all carry
`2026-y-siguientes`, and modelo 130 carries an open-ended `2019-y-siguientes`,
so only 390's per-year authoring makes the admitted year unreachable.

This is not a defect anyone introduced. The catalogue's own comment states the
policy: "A year is admitted here only after the coverage audit enumerates its
unresolved modelo/period prerequisites; the audit remains advisory until the
separately authorised enforcement flip." Modelo 390's missing 2026 revision is
one of those enumerated-but-unresolved prerequisites, and these twenty failures
are that advisory state made visible in the suite.

Closing it means authoring a modelo 390 revision for ejercicio 2026, which
needs the AEAT orden that governs it. That orden is ordinarily published late
in the year for a return filed the following January, so it may not exist yet --
which is precisely why the prerequisite is deferred rather than outstanding.

Recorded so these twenty stop being re-diagnosed: they are neither ordinary
repair nor a regression, and they will not close until either the 2026 orden is
published and its revision authored, or 2026 is withdrawn from the admitted
years.

I also want to correct an earlier claim in this campaign: I reported this
cluster as "already fixed by peers" on the strength of `test_agenda` passing.
That was one test, not the cluster. The twenty are still red.

## Open, needs a period-taxonomy ruling: modelo 036 censal observations

`test_modelo_036_censal_continuity` fails with:

```
1 validation error for RegistryModeloObservation
period: invalid period code 'alta'
```

Both sides of this are correctly grounded, which is what makes it a decision
rather than a bug:

- **The registry is right.** Modelo 036's revision declares
  `period_selector = { year_from = 2025, periods = ["alta", "modificacion",
  "baja"] }`, and its own note explains the modelo is addressed by censal
  events "rather than calendar periods", anchored to RD 1065/2007 and Orden
  EHA/1274/2007. Core supports this: `core/_period.py` defines
  `RegistryPeriodCode`, whose accepted set includes the administrative censo
  tokens, and `test_period.py` carries a `modelo-036-censo-events` case.
- **The model is also right, by its own contract.**
  `RegistryModeloObservation.period` is annotated `FilingPeriodCode`, which
  `core/_period.py` documents as deliberately narrower: "the administrative
  censo tokens and the symbolic EVENT-N selector are refused", for "a period a
  taxpayer files in rather than a registry coordinate".

So a modelo 036 observation cannot currently be persisted, because its period
IS an administrative token and the observation field refuses exactly those.

The ruling needed is which side an observation's `period` belongs to. Widening
it to `RegistryPeriodCode` admits administrative tokens into observations, and
`Period.contains()` cannot compute a date span for `alta` -- so anything that
period-filters observations would need to handle a coordinate with no span.
Narrowing the registry instead would contradict RD 1065/2007. Neither is a
patch, and `aeat-registry-authority-flow` reserves the period grammar as one
authority with no parallel boundaries or aliases, so this is not a call to make
inside a test fixture.

## The modelo 200 "attestation" was mostly a caller over-demanding a rung

This campaign spent hours treating modelo 200's `calculation` authority grade as
a missing operator attestation worth roughly a hundred tests. That framing was
wrong, and the correction generalises.

`ValidatedRegistryAuthority.snapshot` documents `grade` as "the rung of
authority the CALLER needs", defaulting to the strictest. The calculate path
passed nothing, so it silently demanded FILING from every modelo it touched.
Modelo 200's revision declares `calculation` -- the rung defined as "can
additionally compute the modelo's amounts" -- so a Sociedades filer could not
CALCULATE: work done entirely in memory, producing no fichero, refused for
authority it never needed.

Fixed by threading an optional rung through
`resolve_registry_snapshot_for_work_unit` (defaulting to FILING, so its
ten-plus other callers are byte-identical) and passing CALCULATION from the two
calculate-path sites. Measured in an isolated worktree at one commit, with and
without the diff: **190 failed -> 172, eighteen newly passing, none newly
failing.**

This is the third instance of one shape, and the shape is worth naming: **ask
what the caller needs before concluding the registry is under-declared.**

- modelo 036 is censal, filed on AEAT's sede, produces no fichero here.
- modelo 721 is informative, declares `calculation_class = "informative"` and
  ships no export or formulas family.
- modelo 200 IS a filing modelo, but the CALCULATE path is not a filing
  operation.

In all three the registry was right and the caller over-demanded.

### What the remaining modelo 200 clusters actually are

Not attestation either. Requesting the calculation rung in
`test_export_implicit_decimal_slots` moves it from 13 failures to 12, proving a
calculation-rung snapshot does carry the export family. The twelve that remain
fail on assertions of the form `modelo-200-page-001b-casilla-00041 is no
longer...`: the tests pin export field ids the registry no longer declares,
which is drift against the modelo 200 export-layout sweep
(`registry(modelo-200, modelo-714)`). That belongs to whoever owns that sweep,
and no attestation closes it.

## Durable lesson

A revision's span lives in three places that can disagree: the directory name,
the `period_selector`, and the prose. The `period_selector` is the one the
loader honours; the directory name is decoration and misled this investigation
until the selector was read. Check the selector, never the directory name, when
deciding which years a revision owns.
