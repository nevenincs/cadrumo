---
tags:
  - '#audit'
  - '#repo-gate-integrity'
date: '2026-08-30'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:fb84d5a8694842bfea5bcbfd9830b90e4bffb497b53fcf4de851a249bbb05b07'
related:
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]'
---
# `repo-gate-integrity` audit: `gates that report clean about the wrong subject`

## Scope and reading rule

This historical audit records cases where a passing check, count, search, test, plan row, or review
was read as evidence about a wider or different subject. The main findings were recorded during the
2026-08-30 campaign; append-only measurements and corrections continue through 2026-09-07. Stable
finding slugs and severities are retained below. “Confirmed” describes the recorded audit finding,
not a claim that every recommended code change landed. Later measurements override earlier claims
only where explicitly identified; retractions and unverified relays remain visible.

A green is evidence only for the property and population actually exercised. Counts require member
comparison; absence requires a search pattern proven against a known instance; remediation
confirmation must independently derive the population. Measurements need their command, environment,
tree state, and time when those affect interpretation.

## Findings

### shared-config-gate-asserts-the-constant-not-its-use | high | the strict-frozen gate proves the canonical config is correct and nothing proves any module uses it

**Evidence and disposition:** The strict/frozen config test checks the canonical constants, not
whether models use them. Census found 302 `ConfigDict` sites (269 production); 62
strict/frozen/forbid production configs omit `validate_default`, with a broader 221-site population
depending on scope. The earlier 103 count mixed tests and production. Keep the canonical test; sweep
local copies, then add a tree-derived usage gate. Key source:
`src/cadrumo/core/tests/test_strict_frozen_config_validates_defaults.py` and local TUI configs.

### narrow-step-fix-lands-on-the-shared-home-only | high | a completed row fixed the canonical config and never swept the local copies its own text names

**Evidence and disposition:** `W05.P23.S307` correctly fixed the canonical strict-frozen config, but
local copies escaped the shared-home change. Local TUI copies were later fixed; a larger census
still identified a wider 221-site population. Keep S307 closed and record any broader sweep
separately; do not treat the canonical row as proof of adoption.

### tests-that-construct-their-own-subject-prove-nothing-about-reachability | high | a closed union advertised three outcomes, production could emit one, and the two dead members had passing tests

**Evidence and disposition:** The refusal union’s three members had 3, 0, and 0 production
constructions; tests manually constructed both unreachable members and passed. Count production
producers, not test-created instances. The zero-producer distinction depends on whether a type is an
input or an output.

### check-construction-sites-has-a-direction-dependency | high | the same zero-construction-site signal is a defect on an output and a missing caller on an input, and the rule as first stated would manufacture false findings

**Evidence and disposition:** A zero-construction signal means different things for an output and an
input. Applying the producer rule blindly manufactured two false edit-contract findings. Derive
reachability from producer/consumer direction and contract obligations, not from a raw construction
count.

### an-enumerated-subject-list-is-a-hardcoded-tally-in-disguise | high | a check that lists its subjects instead of deriving them is correct only about the list, and it looks more careful than the version that works

**Evidence and disposition:** A hand-listed set can go stale just like an exact count while
appearing more deliberate. Derive subjects from the source definition or filesystem/registry
population; compare members, not only cardinality. The later TUI route measurement is a
counterexample, because its set is type-derived.

### remediation-must-precede-the-gate-that-would-catch-it | medium | landing the detector before the sweep reds a hundred sites and the pressure becomes to weaken it

**Evidence and disposition:** A strict-frozen census could initially red 62–221 production sites.
Landing the detector before the sweep creates pressure to weaken it. Complete and measure the
remediation first; land the gate afterward and state that the gate is not the fix.

### selector-narrowing-conceals-red-in-any-form | medium | a marker expression and a keyword expression hide failures identically, and one produced a false green in this audit

**Evidence and disposition:** Marker and keyword selectors can both exclude the test meant to prove
a gate. A campaign-metadata mutation returned three passes because the one relevant test was
omitted. Run the full node id or a verified selector and show the selected node set.

### absence-of-old-text-cannot-verify-a-removal | medium | a narrowing note must quote what it dropped, so grepping for the dropped phrase reports unchanged on every correctly-narrowed record

**Evidence and disposition:** A justified narrowing must quote what it excludes, so grepping for the
removed phrase still finds the record. Presence of the old phrase cannot prove no change. Check the
new scope and its rationale directly.

### the-failures-here-are-provenance-not-reasoning | medium | in every case the reasoning on the evidence held, and what failed was knowing what grade of evidence was in hand

**Evidence and disposition:** First-hand reasoning was generally sound; errors came from evidence
grade, scope, timestamp, or tree state being overstated. Distinguish measured facts from
modeled/relayed claims, name originator versus amplifier, and preserve the exact command/environment
and correction.

### relayed-instances-pending-their-own-evidence | low | four further instances reported by other lanes, recorded here unverified

**Disposition:** Five alleged instances were initially relayed without verification; several were
later measured and refuted or narrowed below. They were explicitly not actionable from the relay
alone. Preserve the later per-instance outcomes rather than treating the original relay as a
finding.

### withdrawn-docstring-only-marker-scan | low | reported as an instance of this family and refuted on reading the code

**Disposition:** Withdrawn after reading the production scanner. It scans comments independently and
string literals only within the supplied docstring ranges; the proposed docstring-only blind spot
was false. Do not reopen it without new evidence.

### a-closed-union-can-advertise-outcomes-nothing-emits | high | two of three refusal union members have zero production constructions, and tests constructing them directly made the gap invisible

**Evidence and disposition:** The concrete refusal union had production counts 3/0/0 while tests
manufactured the two absent variants. The union’s advertised outcomes were not all reachable.
Measure production construction sites for every union member and retain the separate
output-versus-input qualification above.

### corrections-and-delivered-work-that-exist-only-in-messages | high | two measurement corrections and most of a lane's delivered work have no durable record, so the session's end erases them

**Evidence and disposition:** S350’s exemption key is `enclosing_symbol` + role + alias + identity,
not a triple that collides on 61 rows; S351’s internal-symbol count is 4, not 6. Both corrections
and lane delivery were absent from durable records. Record corrections and executed work in their
owning audit/plan records, with evidence.

### a-cardinality-match-between-two-different-sets-reads-as-agreement | medium | two parties measured four names each, shared one element, and the matching counts disguised that they were answering different questions

**Evidence and disposition:** Two counts of four shared only one member: `edit_contract.__all__`
versus four named definitions. Both searches were correct but answered different questions. Compare
actual members and defining locations, not matching counts.

### bare-step-numbers-resolve-across-plans | medium | the same Step id exists in three plans, so a naive lookup silently returns a different plan's row

**Evidence and disposition:** S322, S333, S349, S350, S351, and S358 recur in multiple plans.
Unscoped `S322` selected `W05.P83.S322` although the relevant architecture row was `W05.P23.S322`.
Cite plan plus full Step id whenever resolving a row.

### one-sweep-addressed-from-two-plans-double-counts-its-own-remainder | high | two rows in two plans name the same sweep, so each row's figure counts work the other has already done

**Evidence and disposition:** Two plans named the same campaign-id sweep. S322’s completed work
reduced the current remainder from 68 sites/22 modules to 16/9 before S100’s number was read.
Re-measure on the current tree and link shared work rather than summing stale populations.

### a-discrepancy-prompts-the-check-but-is-not-the-check | high | the wrong counts caught today were all caught because they disagreed with an expectation, and a wrong count that agrees with one has no prompt at all

**Evidence and disposition:** Implausible mismatches triggered inspection; matching cardinalities
did not. One search reported four moved types against four expected while sharing one member. Use
independent member-level checks even when totals agree.

### the-supported-terminal-size-set-is-declared-three-times | high | three TUI suites each declare their own minimum/ordinary/wide triple, so no answer exists to which sizes the product supports

**Evidence and disposition:** Three TUI suites independently declare minimum/ordinary/wide sizes,
leaving no canonical answer for supported terminal sizes. Put the supported set in one authority and
have each suite consume it.

### a-style-rule-that-parses-is-not-a-style-rule-that-binds | medium | two TUI stylesheet declarations parsed cleanly, applied nothing, and reported no error

**Evidence and disposition:** Two stylesheet declarations parsed but applied no layout effect.
Parsing is not a runtime style assertion; verify the resulting widget geometry/painted state.

### the-geometry-harness-has-no-caller-and-the-modelo-screens-have-no-geometry-gate | high | the appearance-defect reader is uncalled, the visual gates cover five screens that exclude the modelo surfaces, and a just-landed layout fix is correct by manual reading only

**Evidence and disposition:** The appearance-defect reader had no caller; existing visual gates
covered five screens and omitted Modelo surfaces. A just-landed Modelo layout fix had only manual
inspection. Wire the harness to callers and gate the actual screens/geometry before claiming
coverage.

### an-interpolated-constant-was-wrong-by-fifteen-columns | high | a two-point interpolation put a layout transition at ~100 columns; measurement puts it at 114, which moves every conclusion drawn from it

**Evidence and disposition:** A two-point interpolation predicted a transition near 100 columns;
direct measurement showed the actual transition at 114/115. Replace interpolation with a complete
width sweep before drawing layout conclusions.

### a-bisection-presumes-one-step-and-silently-reports-the-last | high | the same constant was estimated, then bisected, then swept, and each method found a different truth while looking equally definitive

**Evidence and disposition:** Bisection silently assumed a single transition and disagreed with the
later sweep. Sweep the full domain when multiple layout steps are possible; label earlier estimates
superseded.

### the-nested-scroll-check-cannot-see-a-scrolling-static | medium | both the fix's author and its reviewer credited a CLEAN reading to luck, when the check structurally could not have fired

**Evidence and disposition:** The check could return CLEAN even when a nested static visibly
scrolled; both author and reviewer credited the result to luck. Assert actual scroll ownership and
painted scrollbar state, not a structural proxy that cannot observe the defect.

### a-property-gated-only-where-its-defect-was-found | high | the single-scroll-owner property was tested for one surface of nine, by a test built around the one instance anyone had hit

**Evidence and disposition:** Single-scroll-owner behavior was gated for only one of nine surfaces,
the same surface where the issue was found. Enumerate all nine and test the property across the
population.

### a-fix-introduced-the-defect-its-own-gate-is-named-for | high | bounding a panel created a second visible scrollbar and hid three rows, and both the gate and the reviewer cleared it

**Evidence and disposition:** Bounding a panel added a second visible scrollbar and hid three rows;
both the gate and reviewer passed it. Validate the rendered outcome and review the changed diff, not
just the gate’s named condition.

### a-uniform-error-across-a-varied-population-indicts-the-probe | high | a probe run outside the project environment reported 94 findings that did not exist, and its own uniformity was the only tell

**Evidence and disposition:** A probe outside the project environment reported 94 errors; only two
were real. Uniform failures across varied subjects implicated the probe. Re-run through the project
environment and inspect variance before attributing findings to the tree.

### a-state-produced-by-your-own-instruction-reads-as-someone-elses-failure | high | a row was marked, unmarked on an instruction, then measured and reported as a marking that never happened

**Evidence and disposition:** A row was marked, then unmarked by instruction, then reported as if
the mark had never happened. Attribute measured state to the exact instruction and tree snapshot
that produced it.

### a-clean-bite-proof-is-as-uninformative-as-a-uniform-finding-list | high | three consecutive injections returned CLEAN and none of them proved anything, because out-of-reach and inert produce identical output

**Evidence and disposition:** Three injections returned CLEAN because they were out of reach or
inert. A meaningful bite proof must demonstrate the mutation reached and activated the assertion;
both inaccessible and ineffective mutations otherwise look clean.

### a-closing-condition-stated-as-a-measured-number-goes-stale-when-you-change-the-thing-measured | high | a row's target transition of 94/95 was invalidated by the same campaign's own layout fix, twice, and hitting it would have meant nothing

**Evidence and disposition:** A 94/95-width target was invalidated by the campaign’s own layout fix,
twice. Re-measure after each change and tie closure to the current property, not a stale numeric
target.

### every-scope-count-today-undercounted-and-always-downward | high | four independent scope figures were low, never high, because a search finds the shape it was written for

**Evidence and disposition:** Four independent scope counts were low because each search recognized
only its expected shape. Re-derive the population from definitions and inspect the census logic
before publishing totals.

### four-more-frame-readers-are-in-the-state-the-gated-one-was | high | one of five band readers is now gated; the other four are implemented, exported, and driven by nothing but a name-only export assertion

**Evidence and disposition:** One of five frame-band readers was gated; four others were
implemented/exported but had only name-presence assertions. Exercise the four remaining readers’
actual behavior.

### re-run-the-detector-after-the-sweep | high | the control for an undercount is not a better search, because you cannot search for the shape you failed to imagine

**Evidence and disposition:** A better search cannot find a shape the search author did not imagine.
Re-run the property-derived detector over the full tree after remediation, independently of the list
of files just edited.

### a-rationale-that-enumerates-instances-goes-stale-as-the-population-grows | high | a correctly-reasoned exclusion list stayed correct about what it named and silently wrong about what appeared afterwards

**Evidence and disposition:** Exclusion rationale named current instances and silently missed future
ones. Derive exclusions from property/ownership or assert each exclusion still has its stated
reason.

### an-executor-refused-an-instruction-that-violated-a-standing-mandate | high | the lead specified putting a plan Step id in shipped test source, which is the violation another row exists to remove

**Evidence and disposition:** An instruction asked to put a plan Step id into shipped test source,
contrary to the standing mandate. The executor correctly refused. Do not encode transient plan
identifiers in production/test artifacts.

### two-readings-of-one-property-disagreed-and-only-one-was-run | high | a root cause was derived, reported and retracted because membership was tested by two methods that were never compared

**Evidence and disposition:** Two methods disagreed on set membership; a root cause was reported and
then retracted because only one reading had been run. Compare independent definitions/searches
before recording a conclusion.

### a-retraction-is-timestamped-exactly-like-the-claim-it-withdraws | high | a correct root cause was withdrawn as an error because it was re-measured after someone fixed it

**Evidence and disposition:** A correct root cause was withdrawn after a fix, but its timestamp
matched the original claim and obscured that the tree had changed. Timestamp each measurement and
retraction separately against the tree state.

### the-host-load-stamp-invalidates-a-measurement-and-was-printed-in-the-log-being-read | high | a hang was nearly attributed as a real defect three times, and the line refuting each attempt was in the same output

**Evidence and disposition:** Repeated apparent hangs were contradicted by host-load evidence
already in the same output. Preserve load/process stamps and read the full run record before
treating a timing outlier as a defect.

### a-filter-that-cannot-match-produces-a-plausible-number | medium | `grep -h` suppressed the filenames a `/tests/` exclusion needed, turning a 4-site production finding into a 58-site alarm

**Evidence and disposition:** `grep -h` removed filenames needed by a `/tests/` exclusion, turning
four production sites into a 58-site alarm. Keep file identity through filtering and test filters
against a known in-scope and out-of-scope path.

### assigning-a-private-name-a-framework-base-already-uses-hangs-instead-of-erroring | high | one attribute name collided with Textual's own shutdown flag; the symptom was a test hanging forever, with nothing to grep for

**Evidence and disposition:** A private attribute collided with Textual’s shutdown flag and hung a
test indefinitely. Check inherited framework attributes before assigning names; use bounded
child-process tests for hangs.

### ship-the-stricter-assertion-and-let-it-fail | medium | reasoning about a gate's correct scope cost more than running the wrong one, twice in one evening

**Evidence and disposition:** Twice, reasoning about scope replaced the cheap direct run. Run the
stricter assertion to expose its actual subject before weakening or explaining it.

### a-crashed-worker-silently-drops-tests-and-reports-a-clean-total | high | a run of a five-test file reported "1 failed, 2 passed" and nothing anywhere said the other two never executed

**Evidence and disposition:** A five-test file reported one fail/two pass after a worker death, with
two tests absent. Pin `--max-worker-restart=0` for fail-closed evidence and verify collected versus
executed node counts.

### a-remediation-line-that-reproduces-the-failure-it-explains | medium | an honest, correct warning ended with advice that recreated the exact state it was warning about

**Evidence and disposition:** Correct warning text ended with advice that recreated the state being
prevented. Execute remediation instructions in a disposable example and verify both the bad and safe
direction.

### a-probe-that-perturbs-its-subject-produces-state-evidence-that-outranks-the-truth | high | three instrumentation attempts each changed the behaviour under test, and one of them silently disabled the very send it was measuring

**Evidence and disposition:** Three instrumentation attempts changed behavior; one silently disabled
the send being measured. Validate probes against an independent observation and ensure
instrumentation does not mutate its subject.

### a-gate-that-imports-the-tree-it-guards-cannot-run-when-that-tree-is-broken | high | the parse gate reused the project's canonical scanner and was therefore unimportable in exactly the state it exists to detect

**Evidence and disposition:** The parse gate imported the project scanner it was meant to guard, so
it could not run in the broken-import state. Keep critical syntax/import gates independent of the
tree under test.

### a-settle-condition-is-the-wrong-gate-on-recording-durable-work | high | a rule written to answer "has this producer stopped" was applied to block a record whose truth did not depend on any producer

**Evidence and disposition:** A condition for “producer stopped” blocked recording work whose truth
did not depend on that producer. Gate durable evidence on its own truth and dependencies, not
unrelated session settlement.

### the-corrections-ran-both-ways-and-each-direction-caught-a-different-class | high | the executor caught what the delegating view had compressed away; the lead caught what the local view could not see was miscounted

**Evidence and disposition:** Executor review caught information compressed from a delegating
summary; lead review found a local count error. Preserve two-way review: implementation evidence
flows upward, while independent scope/authority checks flow back down.

### the-timeout-everyone-attributed-to-the-share-was-an-uncached-full-tree-parse | high | four observations were read as I/O stalls; the cause was a gate re-parsing 6396 files three times and walking every tree per symbol

**Evidence and disposition:** Four observations blamed I/O; the gate parsed 6,396 files three times
and walked trees per symbol. Profile and inspect repeated work before attributing delay to a network
share; cache/reuse one scan where semantics allow.

### a-gate-pinning-a-consumer-tally-reddened-on-correct-work | high | a check named for "exactly seven direct consumers" failed because legitimate work removed one, and updating seven to six would have re-armed it

**Evidence and disposition:** An “exactly seven consumers” assertion failed when legitimate work
removed one; changing seven to six would re-arm a brittle tally. Assert required relationships and
discovered members, not a frozen consumer count.

### the-session-held-the-refutation-of-its-own-claim-and-did-not-join-it | high | three times, the measurement disproving a live conclusion had already been taken, by the same agents, in the same session

**Evidence and disposition:** Three times, the same session had already measured evidence that
disproved its current conclusion. Join contradictory measurements before reporting; do not let a
narrative outrun its own output.

### every-file-parses-and-every-import-resolves-are-different-properties | medium | a gate written after a broken sweep covers only the breakage class that produced it, and its name invites the wider inference

**Evidence and disposition:** A syntax gate written after a broken sweep covered only syntax, while
its name invited import-resolution confidence. Separate parse and import-resolution claims and label
each gate narrowly.

### the-wrong-inference-was-free-and-the-right-answer-cost-one-command | high | in every case the correct check was cheap and got skipped, because the reasoning already felt complete

**Evidence and disposition:** Cheap direct commands would have settled multiple claims but were
skipped after reasoning felt complete. Run the decisive command before publishing an inference.

### a-truncating-write-on-a-flaky-mount-is-a-data-loss-risk-with-a-two-line-fix | medium | an edit to a shared plan file failed with OSError, and the same call could have emptied it

**Evidence and disposition:** An edit failed with `OSError` on a shared mount after truncation could
already have destroyed the file. Use atomic replacement or a write path that preserves the old file
on failure.

### a-ranking-query-cannot-answer-an-absence-question | high | an enumeration piped through `head` was read as complete, and absence-from-the-visible-portion was asserted as absence

**Evidence and disposition:** An enumeration piped through `head` was treated as a complete
population, and unseen rows as absent. Use an untruncated query for absence; display limits are not
evidence of completeness.

### a-remediations-confirmation-can-be-scoped-to-the-list-it-just-fixed | high | a sweeper fixes a hand-listed set, re-runs a scan scoped to that same list, and reads the green as covering the population

**Evidence and disposition:** A sweeper fixed hand-listed sites and re-ran the detector only on
those sites; CLEAN proved only the edit list. Derive the confirmation population anew from the
property so it can find an unfixed site outside the list.

### the-tautology-scan-is-the-only-mechanisable-member-of-this-family | medium | one shape here is decidable by a linter and the rest structurally are not, which is worth stating so the gate is not over-read

**Evidence and disposition:** The original claim that only tautology scans are mechanically
decidable was corrected on 2026-09-07: subsuming disjunctions, self-echoing invocation tokens, and
locale-bound absence assertions are also statically decidable. Corpus-only never-emitted literals
and genuinely semantic irrelevance remain undecidable. See the quality-gate zero-closure audit/ADR;
a zero result alone does not prove a scan has teeth.

## Dated amendments and final dispositions

### 2026-08-31: allowlists, plans, executors, and workspace evidence

- Gate allowlist census covered 608 entries across 3,730 modules: zero stale exclusions. The 176
  stale-looking inventory entries were live campaign work, not defects. Moving-target diagnosis was
  confirmed across three casualties; do not classify a changed tree from an old allowlist snapshot.

- The interface-plan governance records were one incomplete dependency chain, not eight
  independent rows. `W05.P23.S71` named test paths that did not exist; resolve each link before
  writing or checking dependent records.

- Seven Modelo executors declared eleven phase codes and
  initially emitted none; effect reporting was also false. Remediation is per executor. Later
  measurement confirmed all seven conform after their own fixes. Preserve that later result as
  superseding the initial state.

- A taxpayer-readiness fixture appeared in 105 files, but was a
  shared core with scenario-specific tails, not 19 interchangeable copies. An initial suggestion to
  consolidate a 15-path literal was corrected: use `complete_profile_facts(schema,
  facts=scenario_tail)` so the schema remains the authority; a shared literal would still be a
  second authority.

- The M130 casilla-name map appears in 34 modules. A safe canonical private
  shape already exists; moving a test consumer across the boundary requires a ruling, not hardcoding
  a public copy.

- `ModeloExportCommand` raised `NameError` because its runtime dependency was
  imported under `TYPE_CHECKING`; the import was moved to runtime and a guard-only-name gate added.

- A report of two torn relocations was retracted after the tree-wide codemod was inspected. The
  subsequent inert namespace break was real and measured on the settled tree.

### 2026-08-31: `modelo.work.file` and conformance

The initial blocker was profile completeness, not a layering defect: fixture taxpayer `X1234567L`
did not match profile `12345678Z`; correcting identity enabled verification. The standalone case
measured 88.52 seconds and was not a performance defect. M100 declares 2,103 casillas but the
scenario writes four, so the declaration count does not explain cost. The domain path succeeds; the
platform wrapper still raised an opaque `RuntimeError` after reporting `effect=UPDATED`, and its
cause remained unresolved. A timeout stack was not accepted as a profile. Separately, a workflow
gate calling `asyncio.run` failed for async callers; the gate must await within its caller’s loop.

All seven Modelo executors ultimately conformed, with the last requiring a taxpayer fixture rather
than a code change. Readiness was measured in 51 distinct shapes. S353’s population moved 25→21;
three fields were proven scenario-specific, not fill-in work. Complexity entries first described as
stale suppressions were corrected: keys were misnamed, not hiding regressions. Branch-classification
duplication received four distinct dispositions and its gate is green. A filesystem census cannot
adjudicate an untracked file against Git; a future file was recorded separately.

### 2026-08-31: sweep corrections and boundary decisions

- Absolute-only import census was incomplete: `src/cadrumo` contained 35,735 relative edges and
  17,269 absolute ones. Resolving relative import levels changed “four dead namespaces” to zero; an
  actual relative consumer of `_parsers.extract_pages_text` had been deleted and package import
  broke. Resolve relative edges and prove deletions by importing the affected package.

- The alleged
  hardcoded TUI route set was refuted: `declared_destination_ids()` derives from
  `ModeloWorkspaceDestinationIdV1`; `_require_total_destination_table` checks missing and extra IDs
  and duplicate destinations. No remediation.

- Workspace scanner’s three stated exclusions were
  valid, but `workspace.py` itself was a stale exclusion. That entry was removed; surviving
  exclusions now assert their reason still exists. This remediation landed and both directions were
  exercised.

- The earlier 19-copy readiness finding and its proposed shared literal were superseded
  by the `complete_profile_facts` correction above.

- `W07.P17.S361`’s specific
  `BucketEventHistoryRepositoryProtocol` import no longer existed at HEAD, but HEAD collection was
  not run; the evidence weakens the named cause, not proof of collection.

- Work-target revision
  comparison was duplicated between `work_addressing.py` and `workspace.py`. It was consolidated as
  `diverging_work_target_revision_axes`; the authority raises and Workspace records the same axis
  result. Focused verification: 82 passed, including whitespace normalization, per-axis divergence,
  absent axes, and law-selected revisions. The computed Workspace disposition still has no
  production reader; consolidation did not resolve reachability.

- `facts` named three shapes across
  Workspace refusal, edit refusal, and work-review blocker. Rename edit message arguments and track
  the required evidence reference in both refusal contracts; do not delete a required
  zero-population field.

- C3 editor work was initially marked blocked because intent/submission
  models appeared private. A correction found public `edit_contract.py` already existed and
  publishes four symbols; the unresolved boundary decision concerns the withheld intent/submission
  family, not absence of a public contract. The operator later ruled for a narrow application-owned
  `edit_session.py` facade; S72–S79 closed through that facade. Do not preserve the broader
  72-symbol relocation proposal as current fact.

- Two absence claims were corrected after searches
  used patterns that could not match real registration/consumer forms. A non-empty grep has
  evidence; an empty grep does not. Validate patterns against a known instance or enumerate by
  construction.

- Workspace baseline equality is meaningful for deterministic content coordinates;
  edit baseline equality is not, because it includes issued/expiry timestamps and an admission id.
  An editor used the wrong equality and permanently signaled stale state; it was corrected to
  `reconfirm_modelo_edit_baseline`. Document each comparison contract.

- Three boundary questions
  remain one ruling: private authority for edit submission, the operator-actions catalogue, and the
  revision-safe casilla resolver used by 34 test modules. The edit case now has the narrow facade
  precedent; test consumers and action surfaces still need an explicit ruling. Keep literals local
  and do not bypass the package boundary to green a gate.

- Conformance sequencing: `file` and
  `amend` depend on the revision-safe casilla boundary ruling; `export` likely has a
  verification/completeness dependency but that inference was not measured. `modelo.edit.apply` is
  the best independent next case: resolve dynamically from the admitted surface, use
  `ModeloEditApplySubmissionV1.from_submission`, preload catalogue objects, and hold the tree stable
  across admission and guarded submission.

## Recommendations retained

1. For strict-frozen adoption, record canonical and local populations separately; sweep by file,
  keep genuine deviations with inline reasons, then land a population-derived gate. Leave
  `W05.P23.S307` closed.

2. For every green gate, state its actual subject, selector, environment,
  and property. A clean result cannot establish scope that the detector never observes.

3. For
  import/de-export work, resolve relative imports, preserve filenames through filters, check
  plausible totals, and import the affected package after a removal.

4. For test evidence, compare
  collected and executed nodes; disable silent xdist worker restart; prove mutation reachability and
  activation.

5. For layouts, sweep the full terminal-width range, check all surfaces and actual
  painted output, and remeasure after every layout change.

6. For plan/registry work, use full
  plan-qualified Step ids, durable records for corrections, current-tree populations, and
  member-level comparisons.

7. For Modelo boundaries, use public defining modules or a narrow
  application-owned facade; record unresolved authority decisions instead of crossing private
  boundaries.

8. For current status, keep the `modelo.work.file` wrapper RuntimeError unresolved,
  preserve the async-caller fix requirement, and distinguish historical evidence from present
  certification.


