---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:f723543dbd3193cca8952dfebe621708b5688bc6a6bb6ce9c874be1376c4db50'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]"
---
# `quality-gate-zero-closure` audit: `Blind-green implementation review`

## Scope

Reviewed the live changes for `W08.P27.S104` and `W08.P23.S108` against the
blind-green decision, its measurement record, the owning implementation plan,
the canonical absence-assertion audit, and the 2026-09-07 amendment to the
earlier decision. The review was limited to the S104 manifest and lockfile
change, the S108 scanner and two historical-record corrections, the two
quality-gate plan checkboxes, and their execution records. Concurrent changes
in every other path were excluded.

Focused verification completed during this review: `uv lock --check`, Ruff on
`dev/quality/tautological_assertion_scan.py`, the 31-test tautology gate, and a
targeted diff check all passed. The pinned mutmut 3.7.0 runner was also read to
verify how `source_paths`, test selection, and the generated `mutants/` tree
interact. Two findings remain below; no additional findings were found in the
reviewed S108 record or in the lockfile contents.

## Findings

### mutmut-selection-cannot-collect-gate | high | the recorded mutation invocation does not copy its selected gate into the mutant tree

`pyproject.toml` limits mutation generation to
`dev/quality/tautological_assertion_scan.py` and selects
`dev/tests/test_tautological_assertion_gate.py`. In mutmut 3.7.0, the runner
copies the configured source paths into `mutants/`, then runs pytest from that
directory. Its default `also_copy` set includes `tests/` and `test/`, but not
`dev/tests/`; this repository has no `also_copy` entry for that path. Therefore
the exact invocation recorded by S104 cannot collect the selected gate from a
fresh run unless an operator manually seeds an undeclared copy. A manually
prepared measurement scratch would not prove the checked-in invocation is
reproducible. This blocks the prerequisite's reproducible mutation evidence
and must be resolved before the measurement or detector bite claims can rely on
this configuration.

### boundary-wording-overstates-corpus-join | low | the corrected scanner prose presents source-corpus absence as runtime non-emission

The S108 scanner docstring lists “absence literals that are never emitted” as a
statically decidable class. The governing measurement describes the available
probe more narrowly: it joins an asserted literal against the source corpus
and locale catalogues, and explicitly records that helper-composed or otherwise
runtime-generated output can evade that corpus. The correction successfully
removes the refuted family-wide claim, but this wording can still cause a
future detector to claim proof of runtime non-emission when it has only proved
absence from the searched corpus. This is a precision risk, not a failure of
the three-location correction itself.

## Recommendations

For `mutmut-selection-cannot-collect-gate`, declare the test-tree copy needed
by the exact invocation (or move the selected gate to a path deliberately
copied by the runner), then rerun from a fresh POSIX/WSL environment and retain
the collection and mutation evidence. Future detector gates under
`dev/quality/tests/` need the same explicit copy treatment when they are added
to a mutmut selection.

For `boundary-wording-overstates-corpus-join`, qualify the scanner prose as a
source-corpus/catalogue join and preserve the explicit limitation that it is a
diagnostic floor rather than proof that no runtime path can emit the literal.

**2026-09-07 disposition.** The configuration now declares `dev/tests` in
`also_copy`; mutmut 3.7.0 resolves that copy together with the single scanner
source and selected gate. The high finding remains open until a fresh POSIX run
proves collection and mutation from the generated tree. The scanner wording
now names the declared source/catalogue corpus and its runtime-composition
limit; Ruff and the 31 focused gate tests pass, closing the low finding.

**2026-09-07 re-review status — `mutmut-selection-cannot-collect-gate`.** The
current live configuration is `also_copy = ["src/cadrumo", "dev"]`, which
supersedes the narrower `dev/tests` entry described in the prior disposition.
Mutmut 3.7.0 appends these configured directories to its copy set and runs
pytest from `mutants/`; copying the whole `dev` tree places the selected gate
under `mutants/dev/tests/`, while copying `src/cadrumo` supplies the package
tree for imports. The runner generates mutations for the configured scanner
source after those copies, so the source mutation remains the tested file.
Static inspection therefore confirms the selected test path is collectable in
the generated tree. A fresh POSIX mutation run remains S105 evidence and is
not claimed by this review.

**2026-09-07 re-review status — `boundary-wording-overstates-corpus-join`.**
The current scanner wording still names a declared source/catalogue corpus and
immediately limits corpus absence to a diagnostic floor rather than proof
against runtime composition. No wording regression is present; this finding
remains closed.

**2026-09-07 follow-up — `mutmut-selection-cannot-collect-gate`.** Static
re-review confirms that `also_copy = ["dev/tests"]` is now present in
`pyproject.toml`. Mutmut 3.7.0 appends that configured directory to its
default copy set; its generated tree therefore contains
`mutants/dev/tests/test_tautological_assertion_gate.py` alongside the selected
`mutants/dev/quality/tautological_assertion_scan.py`, and its pytest runner
executes from that tree. The original collectability defect is resolved. A
fresh POSIX mutation run remains S105 evidence and is deliberately not claimed
by this static re-review.

**2026-09-07 follow-up — `boundary-wording-overstates-corpus-join`.** The
current scanner wording now says “absence literals with no producer in a
declared source/catalogue corpus” and immediately states that corpus absence
is only a diagnostic floor, not proof against runtime composition. This
matches the measured probe boundary; the low finding is closed.

**2026-09-07 correction to the preceding high-finding follow-up.** That
follow-up captured an earlier live snapshot using `also_copy = ["dev/tests"]`.
The current authoritative configuration is the broader
`also_copy = ["src/cadrumo", "dev"]` recorded in the re-review status above;
the static collectability conclusion is unchanged, and the fresh POSIX run
remains owned by S105.

**2026-09-07 execution closure — `mutmut-selection-cannot-collect-gate`.** A
fresh WSL run at detached revision
`6166c37a38fd40af64af58286f6dc7922266d4c2`, using both copied scan roots,
collected the gate and completed 77 terminal mutant outcomes in 61.19 seconds
with no error-class result. The checked-in invocation is therefore proven
executable from the generated tree, closing the high finding.

## Full-campaign review in progress

Review of the expanded implementation found and closed three semantic defects
before mutation evidence was accepted. First, the durable boundary correction
still called corpus-only never-emitted literals decidable in the historical
audit and said four additional classes in the closed interface plan. The
scanner, audit correction, and closed-plan correction now agree on three
additional decidable classes and preserve corpus-only producer absence as
undecidable.

Second, `locale_bound_assertions.py` attached pin state too broadly. A pinned
call elsewhere in a helper, a pinned assignment after the assertion, and an
environment-returning helper used as though it returned output could each hide
an unpinned assertion. Pin propagation is now line-sensitive, follows returned
output, and distinguishes environment mappings from captured output. Named
non-collected fixtures exercise each counterexample; the locale gate passes 19
tests and the two real-tree locale-axis cases pass independently.

Third, the repaired report consumer still implemented its stated final-word
grammar with dynamic suffix containment. That accepted `NOTKEPT` as `KEPT`.
`report.py` now parses the final whitespace-delimited token before optional
parenthetical context. Direct controls accept the four valid bare/context
forms and reject suffix lookalikes; the verdict gate passes six tests.

The source specimens for the locale, taxonomy, verdict, subsumption, and
self-echo detectors live outside their test logic in non-collected fixture
files. Atomic expression strings remain appropriate parser inputs in the
pre-existing tautology gate. The six detector/gate pairs pass Ruff, formatting,
and type checking, and all six execute together under the per-push marker (`94
passed`). The taxonomy conformance gate independently passes its undeclared-site
and stale-declaration controls; the superseded off-lane gate and shrink-only
pending list are removed.

This review is not yet approval. Per-detector mutation runs and individual
survivor dispositions remain required. Mutation results from a snapshot older
than the locale helper-kind correction cannot close that detector.

### Verdict mutation closure and execution-integrity follow-up

The verdict detector's first valid current-source run selected 117 mutants,
killed 110, and left seven survivors. Six were semantically inert: four altered
only `SyntaxError` filename metadata and two substituted the equivalent `UTF-8`
codec alias. The seventh removed explicit UTF-8 decoding from the separate
consumer-enumeration adapter. A direct mutation-visible codec contract was
added at that boundary, and a focused mutmut recheck killed it. The resulting
terminal set is 111 killed and six individually disposed inert survivors. The
full pass took 153.40 seconds and the focused current-test recheck 31.72 seconds;
no aggregate mutation metric was calculated.

Two attempted verdict runs are deliberately excluded from evidence. In the
first, a still-running copy operation overwrote the narrowed scratch
configuration and mutmut named the older detector modules rather than the
verdict detector. In the second, Windows launcher quoting applied `cd` in a
child shell but ran mutmut in the repository root. That attempt produced no
terminal result; its process and exact `mutants/`, `focused.log`, and
`focused.seconds` artifacts were removed. The accepted recheck used a physical
script under WSL `/tmp`, named exactly the intended mutant, left no repository
scratch, and updated that mutant to killed.

The initial subsumption worker report also claimed a clean suppression scan
while the live test still carried `# noqa: S603`. Review caught and removed the
directive. A process-pool replacement was then rejected because the spawned
child imported the original module outside mutmut's mutation boundary. The
current direct filesystem-adapter seam observes normalized UTF-8 decoding and
path attribution in the mutated process itself. Current mutation proof for that
replacement remains pending and is not claimed here.

The completed P28 surfaces pass together: the verdict grammar gate, deferred
edge two-drift declaration, and public cache-identity manager test report 27
passing tests in 170.42 seconds. P28 is technically verified but remains open
in plan order until the earlier detector phases close.

### Locale mutation closure

The current locale detector and test hashes match the final external snapshot.
The gate passes 50 tests and mutmut selected 454 mutants in 562.323 seconds,
killing 428. All 48 initially actionable survivors were killed by named,
non-collected fixture controls covering declaration preambles, explicit UTF-8
decoding, multipart flag prefixes, malformed and direct argv calls, keyword
ordering, environment-map data flow, fixed-point helper propagation,
line-sensitive state, output-name detection, and continued assertion traversal.
The 26 remaining survivors were individually reviewed as semantic equivalents:
falsey-default substitutions, fixed-point flags whose writes are unchanged,
parallel AST dict sequences under alternate `zip(strict=...)` flags, impossible
`JoinedStr` fallbacks, non-absence labels filtered identically, codec aliases,
and parser-filename-only diagnostics. No aggregate mutation metric was used.

The two-locale control remains bound to the detector's real-tree hit set. Its
recorded pre-repair run failed in both parameterized directions; the current
Spanish and English axis is part of the 50-test passing gate. P25's missing
phase summary was scaffolded through `vaultspec-core` and now records that
evidence without claiming the four behavioral nodes that stopped before their
edited assertions.

### Taxonomy mechanism and aggregate-lane closure

The taxonomy detector's current bounded run selected 410 mutants, killed 404, and left six individually reviewed inert survivors. They are confined to an inflated-but-equivalent nested-function span, an impossible equal-span nested-function case, an equivalent strict-subset predicate over the current taxonomy context, inclusive declaration-span bounds, and two parser-filename-only changes. All initially behavior-changing survivors were killed. The current gate passes its exact undeclared-site and stale-declaration controls together with the real-tree conformance sweep (`3 passed`). The superseded off-lane gate and its shrink-only pending list are absent.

The final all-class lane proof uses the existing `test-dev-ci` marker expression and names all six gate files explicitly. It collected 193 tests and passed all 193 in 184.59 seconds. SHA-256 values for all twelve detector/gate modules were captured before and after the run and remained identical, so concurrent worktree edits did not invalidate the result. `just --dry-run test-dev-ci` includes `dev/quality/tests` under that marker, and the per-push workflow invokes `just test-dev-ci`; no workflow or recipe change is part of this campaign.

Review also removed a forbidden subprocess suppression from the locale gate and replaced the raw process call with pytest's `pytester` subprocess facility. Module-sized Python specimens, including the runtime class-method locator case, now live in named non-collected fixture files rather than embedded test strings. The six detector/gate pairs pass Ruff lint, Ruff formatting, and `ty`, and a campaign-wide search finds no suppression, skip, xfail, baseline, or allowlist mechanism.

The S115 record now separates its seven-plus-one pre-repair detector demonstration, runtime-axis mechanism, and S116 repair ownership. A fresh current affected-node run produced 12 passes and the same four failures already recorded by S116; each failure occurs before the assertion changed by this campaign, so none is represented as a behavioral pass. The final current-byte locale mutation rerun remains pending; full-campaign approval remains withheld until it completes and its survivors are individually disposed.
## 2026-09-08 five-condition completion audit pending verdict mutation

This review derives completion from mechanisms, not from an exhausted finding population. It inspected the accepted blind-green decision, its measurement research, the owning plan, the canonical absence-assertion audit, the 2026-09-07 amendment, current implementation and gate files, and execution records. The current plan status is 21 of 22 Steps; only W08.P28.S121 remains open.

### End condition 1: mutation instrument, measured cost, and cadence

Satisfied. `pyproject.toml` pins `mutmut==3.7.0`, `uv.lock` resolves exactly 3.7.0, mutation generation is bounded to one named detector module, and `also_copy = ["src/cadrumo", "dev"]` supplies the generated tree without broadening mutation generation. The initial reproducible WSL measurement selected 77 mutants in 61.19 seconds, killed 70, and left seven survivors; the measurement audit individually classified six as behavioral findings and one as the inert case-equivalent codec spelling. After controls were added, the current tautology disposition is 77 selected, 76 killed, and one inert survivor. The accepted ADR and S107 declare a manual, external-`/tmp`, one-detector-at-a-time, change-triggered, verify-only cadence from measured costs. No mutation score is reported or used, no repository `mutants/` tree exists, and no mutmut hook, workflow lane, or `justfile` wrapper is installed.

### End condition 2: refuted boundary corrected in all three durable locations

Satisfied. The scanner docstring names tautology, subsumption, self echo, and locale binding as class-specific decidable cases while retaining corpus-only producer absence and semantic relevance as undecidable. The historical wrong-subject audit retains its original finding and appends the same correction with a related link to the accepted decision. The interface plan retains the closed historical S106 row and carries the matching correction in its Description with the accepted decision in `related`. None of the three locations still presents corpus absence as runtime non-emission.

### End condition 3: detector mechanisms and per-push reach

Satisfied for five mutation-proven detectors and semantically satisfied but mutation-incomplete for the verdict detector. Tautology, subsuming disjunction, self echo, locale-bound absence, taxonomy conformance, and verdict grammar each have a detector under `dev/quality/` and a paired `unit` gate under `dev/quality/tests/`. Their gates sweep the real tree, carry representative positive controls in atomic parser inputs or named non-collected fixtures, and refuse a collapsed corpus through per-root or real-consumer anti-vacuity controls. The existing `test-dev-ci` recipe includes `dev/quality/tests` under `unit or (integration and not serial)`, and the per-push workflow invokes that recipe.

The current marker expression independently collected all 227 tests in 3.73 seconds. The six gates then passed all 227 tests in 217.31 seconds. All twelve detector/gate SHA-256 identities matched the values captured before that aggregate run, including verdict detector/gate `A76C8BE...24C5DB` / `FC96F345...D7FAFF`. Existing exact detector mutation dispositions are: tautology 77 selected, 76 killed, one inert; subsumption 75 selected, 69 killed, six inert; self echo 143 selected, 139 killed, four inert; locale 475 selected, 452 killed, 23 inert; taxonomy 472 selected, 462 killed, ten inert. Each record states that all behavioral survivors were killed and individually explains the remaining equivalents without a score. The verdict detector's semantic review is clean and its focused gate passes 16 tests, but no mutation result yet exists for the current exact identities.

### End condition 4: both locales over the detector hit set

Satisfied. The locale gate derives the runtime nodes from the detector's own real-tree hit set and runs each under both `CADRUMO_OUTPUT_LANGUAGE=es` and `CADRUMO_OUTPUT_LANGUAGE=en`, explicitly clearing the repository default marker expression. The S115 record preserves the required failing-before evidence: the complete pre-repair four-catalogue sweep failed in both parameterized directions, with Spanish exposing seven English-only sites and English exposing one Spanish-only site. Its isolated runtime fixture separately passes under Spanish and fails under English, and no defect was planted in the shipped tree. The current detector/gate mutation disposition is tied to exact hashes and leaves no behavioral survivor.

### End condition 5: taxonomy accessor or checked site declaration

Satisfied. The real-tree conformance gate accepts a taxonomy-related absence assertion only when it reaches the canonical accessor or when its token is named by `PINNED_TAXONOMY_LITERALS` and the adjacent rationale names the containing function and token. Isolated controls fail both drift directions as `undeclared-site` and `stale-declaration`, and further controls reject unrelated same-named accessors and undocumented declarations. The former off-lane `src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py` is absent. Searches of `src` and `dev` find neither `PENDING_UNDECLARED` nor the rejected `PINNED_TAXONOMY_ABSENCE_SITES`; the only live sanctioned declaration symbol is `PINNED_TAXONOMY_LITERALS`. The exact taxonomy mutation run and individual inert dispositions are recorded.

### verdict-exact-mutation-proof-pending | high | the sixth detector has not yet been killed at its current identities

The campaign cannot satisfy end condition 3 or close S121 until a bounded mutation run targets verdict detector `A76C8BE...24C5DB` with gate `FC96F345...D7FAFF`, every survivor is individually disposed, and a post-run focused gate remains green at those same hashes. The earlier 117/111/6 and 445/421/24 records describe superseded implementations and are not transferable evidence.

### execution-records-lag-current-mechanisms | high | aggregate and verdict records state obsolete counts and hashes

This non-mutation finding must also be closed before final approval. S113 records 223 collected/passing tests and verdict hashes `82EF4114...17354` / `050303CD...FEC2F`, whereas the current independently verified lane has 227 tests and verdict hashes `A76C8BE...24C5DB` / `FC96F345...D7FAFF`. S120 still calls the verdict gate a 12-test suite and P28's summary still records eight verdict tests and 27 combined tests; the current focused and P28 evidence is 16 and 35 respectively. S121 likewise lists a superseded fixture set and mutation result. Reconcile S113, S120, S121, and the P28 summary to the final stable run rather than leaving contradictory receipts beside the completed plan.

No additional semantic, locale, taxonomy, forbidden-mechanism, removal, or per-push-selection finding remains. Full-campaign approval is withheld for the two high evidence-integrity findings above; no critical finding was found.

## 2026-09-08 S112 subsumption exact mutation disposition

### s112-subsumption-mutation-proof | low | exact detector and gate evidence closes the mechanism

The current S112 subsumption detector and gate match SHA-256 `5D74756B3E02C282C0E4E71787F0834202B3E120BE418B7D386194718FB605E8` and `CA675F02EA16B9A9917BFD3FD3A79536102EEF179C77E008C15510CC90A11B31`. Independent verification passed all 14 focused tests in 7.09 seconds, with Ruff lint, Ruff formatting, and `ty` clean. The bounded mutmut 3.7.0 receipt at those exact identities and configuration snapshot `EECF07EF6C2F204655E89AB0329C6363BCCD5E1B0F73090CBF0D26E7A6317ECF` selected 75 mutants, killed 69, and left six individually reviewed inert survivors in 212.92 seconds; all other terminal categories were zero. The survivors are confined to an equivalent UTF-8 codec alias, two falsey/default forms of `ast.dump(include_attributes=False)`, selection of a structurally equal second stable haystack, and two parser-filename-only changes. The earlier behavior-changing `path=None` and ambient-decoding mutations are killed. No mutation score is calculated or used.

The live whole `pyproject.toml` hash has since advanced to `F58C68B2DCDD35A83509DB62EE0233A042D0541F1CBC4267311C4F04C9BBAD23`, while its mutation block continues to select this detector, this gate, and both real-tree roots. The receipt remains bound to its named configuration snapshot and exact detector/gate bytes; it is not relabeled as a run over the later whole TOML. This closes the S112 subsumption component of end condition 3. It does not close or weaken the separately recorded current-verdict mutation-proof and execution-record reconciliation findings, so full-campaign approval remains withheld on those existing items only.

### 2026-09-08 S112 evidence-identity correction

The preceding S112 identity qualification is superseded. SHA-256 `EECF07EF6C2F204655E89AB0329C6363BCCD5E1B0F73090CBF0D26E7A6317ECF` identifies `dev/quality/tests/fixtures/subsuming_disjunction_cases.toml`, not `pyproject.toml`. The supplied and current `pyproject.toml` SHA-256 is `F58C68B2DCDD35A83509DB62EE0233A042D0541F1CBC4267311C4F04C9BBAD23`; no S112 mutation-configuration drift occurred. The detector, gate, fixture, and configuration evidence is exact, and the S112 closure remains approved without that qualification. The campaign's separately recorded outstanding findings are unaffected.

## 2026-09-08 simplified verdict-detector semantic disposition

The simplified verdict snapshot was reviewed at detector SHA-256 `D28C129D65837DE9865A9663B89C8E8433F7C59C65E1856DCD3FE2DFA5AC770A`, gate SHA-256 `D2BFA082481F6EE88210AF93026CFF56C57376BFBFB2CB764B071F0678F8F46B`, and nine-fixture aggregate SHA-256 `99C264ABDBDA16B95FBC724CEE38F97D593584ACED86AE9A36DEA344A4344658`. The focused gate passed eight tests in 43.90 seconds and Ruff lint, Ruff formatting, and `ty` passed. Its historical positive, real-tree sweep, anti-vacuity, and direct/simple/loop output specimens remain behavior-level controls rather than an omnibus mutation fixture.

### verdict-declared-producer-rebinding | high | simplified producer attribution admits false positives

End condition 3 is not semantically satisfied at this snapshot. With a module-level subprocess import, an intervening same-function loop target, tuple-destructuring target, or nested definition named `subprocess` replaces the imported binding, yet a following direct `subprocess.run` output predicate is attributed to import-linter. Independent probes report the weak `KEPT` suffix predicate in all three cases. The ADR and S120 require the predicate to be joined to the declared producer grammar; these calls are not to that producer, even though their surface is deliberately inside the closed direct-output shape. The existing foreign-module control does not cover local binding replacement.

Semantic approval and the mutation rerun are withheld until producer identity is proven across same-scope bindings or the advertised import/call boundary is explicitly narrowed to a form the detector can prove, with named negative controls. No additional high or critical finding was established; conditional assignments nested under control flow were treated as outside the declared simple-preceding-assignment boundary. Existing campaign evidence and record-reconciliation findings remain in force.

## 2026-09-08 verdict producer-rebinding repair disposition

At detector `1CEFF3CF364BACC4AF6382683E9B06B10A5A42B06D841AFD9B54F9DBCB490081` and gate `E41D2216647F63BD26D62E6017636D9AB3DEB5BEAFE06F4B98BF42E80BDA2CB7`, the original loop-target, tuple-destructuring, and nested-definition counterexamples are closed and the ordinary direct producer positive remains live. The focused gate passed eight tests in 41.79 seconds, and Ruff lint, Ruff formatting, `ty`, and BasedPyright passed.

### verdict-declared-producer-rebinding | high | semantic approval remains withheld

The producer-identity repair is incomplete. Direct-output probes are still reported after `subprocess` is rebound by a variadic parameter or a context-manager target. A call before a later assignment is also attributed to the module import even though Python treats `subprocess` as a function-local name throughout that scope. All three cases are within the detector's advertised direct-output shape and violate S120's join to the declared producer grammar. End condition 3 therefore remains semantically open at this identity. Add general lexical binding controls and named negative specimens before running mutation; the mutation rerun is not approved. No critical finding was found.
