---
tags:
  - '#audit'
  - '#registry-deadline-window-span'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2495d0eaeef813609ef78e7c6f5e1c97539172c9a96d4035f657fff1288f68e6'
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

## Durable lesson

A revision's span lives in three places that can disagree: the directory name,
the `period_selector`, and the prose. The `period_selector` is the one the
loader honours; the directory name is decoration and misled this investigation
until the selector was read. Check the selector, never the directory name, when
deciding which years a revision owns.
