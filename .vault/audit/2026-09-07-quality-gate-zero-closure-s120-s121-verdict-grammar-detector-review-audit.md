---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:c06adcd69665e8b64de6eb3ca4b4998e0a4e698c878fe05774d59deb8cedc6d7'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
---
# quality-gate-zero-closure audit: S120 S121 verdict grammar detector review

## Scope

Reviewed W08.P28.S120 and S121 together against the accepted verdict-layer
extension and owning plan. Scope covered `gate_verdict_grammar.py`, its four
non-collected fixtures and eight-test gate, real-tree discovery and anti-vacuity,
mutmut enrollment, and both execution records. Direct probes replayed the exact
historical `_verdict_of` loop and placed an unrelated suffix check in an enrolled
module. No detector, test, fixture, plan, configuration, or execution record was
changed.

The mechanical harness is otherwise sound. Both declared Python roots must each
contain at least 500 modules; the complete real tree is swept; the consumer floor
requires a real enrolled module and specifically `dev/audit/report.py`; weak
literal containment, prefix, suffix, tuple-suffix, and negative-containment
specimens fire; clean and unenrolled specimens stay quiet. The dedicated test is
included in mutmut's selected test set and both source roots are copied. The fresh
isolated mutation result is honestly stated as 117 selected, 111 killed, and six
individually explained inert survivors, without converting it to a score. The
focused suite independently passed all eight tests in 54.51 seconds. No mock,
monkeypatch, suppression, threshold, or exclusion was found.

## Findings

### exact-historical-dynamic-verdict-is-undetected | high | the detector cannot catch the predicate that triggered S119

The repaired `_verdict_of` implementation previously iterated
`for verdict in ("KEPT", "BROKEN")` and tested `text.endswith(verdict)`. That is
the exact suffix predicate S120 exists to make mechanically decidable. The scanner
only calls `_literal_verdicts` on the direct call argument, which accepts string
constants and literal tuple/list/set arguments but not a name bound by a loop or
assignment. An independent source containing `lint-imports`, the declared verdict
tuple, and the historical loop returned no findings.

The advertised positive control does not replay this historical shape. It rewrites
the current parser to `text.endswith("KEPT")`, replacing the dynamic loop variable
with a direct literal that the detector can already see. It therefore proves a
narrower detector than the one authorised and cannot demonstrate that regression
of the repaired consumer bites. Killing all generated behavioral mutants cannot
cover behavior absent from the detector's implementation.

### predicate-receiver-is-not-bound-to-gate-output | high | unrelated string operations in an enrolled module are false positives

Grammar enrollment is module-wide: any executable string containing `lint-imports`
plus any exact verdict literal enrolls every matching predicate in the module. The
scanner performs no data-flow or structural attribution from the predicate receiver
to captured gate output. An independent enrolled specimen whose unrelated
`filename` variable used `filename.endswith("KEPT")` produced a finding. This does
not apply a weak predicate to gate output and is outside the accepted detector
class. Such false positives create pressure for the forbidden exclusions the ADR
explicitly avoids.

## Recommendations

For exact-historical-dynamic-verdict-is-undetected, resolve locally bound verdict
names from literal assignments and bounded iteration, then make the positive
control restore the actual former `_verdict_of` loop rather than a simplified
literal suffix call. Assert both `KEPT` and `BROKEN` findings from that real shape.

For predicate-receiver-is-not-bound-to-gate-output, bind findings to values derived
from the declared producer's captured output or its parsed lines. Add a negative
control for an unrelated receiver in a genuinely enrolled module while retaining
positive direct, normalized, and bounded-loop controls.

After both semantic changes, rerun the complete real-tree gate and the physically
isolated mutation scope. The present mutation disposition remains honest evidence
about current code but cannot close these missing behaviors.

S120 and S121 are not approved. Two high findings remain; no critical finding was
found.
**2026-09-08 historical-loop and receiver-attribution re-review.**
The exact former dynamic loop is now detected: an independent replay of
`for verdict in ("KEPT", "BROKEN"): line.endswith(verdict)` over a value derived
from `subprocess.run(...).stdout` produced both KEPT and BROKEN findings. The
in-memory report regression now restores this historical shape rather than a
literal simplification. A plain unrelated `filename.endswith("KEPT")` is quiet.
These changes close exact-historical-dynamic-verdict-is-undetected and the narrow
unrelated-receiver counterexample behind predicate-receiver-is-not-bound-to-gate-
output.

### provenance-ignores-write-order-and-direct-results | high | overwritten values stay tainted while direct gate-output receivers are missed

`_derived_gate_output_names` computes a scope-wide fixed set of names without
binding a use to its reaching write. Once a name is derived from subprocess output,
a later overwrite cannot remove it. Independent probes showed both
`output = result.stdout; output = "ordinary"; output.endswith("KEPT")` and an
output-derived alias overwritten with `"report-KEPT"` still produce findings.
These are unrelated string predicates at their use sites and reproduce the false-
positive class the remediation was meant to close.

The inverse direct form is also missed:
`subprocess.run(...).stdout.endswith("KEPT")` produced no finding because provenance
is seeded only through an assignment target, not from the receiver expression
itself. The accepted class is a weak predicate applied to gate output, independent
of whether that value was first named. Receiver attribution therefore remains
unsound in both directions.

### current-gate-and-record-evidence-disagree | high | the focused suite is red and both records carry obsolete evidence

Fresh execution of the current files produced one failure and nine passes. The
weak fixture gained an unrelated helper and unbound-verdict controls, shifting its
first in-function finding to line 22, while the expected locator list still requires
line 18. The failure is in the positive-control equality, so the current gate is not
green. S120 and S121 records still describe eight tests; S121 still reports the
superseded 117 selected, 111 killed, six-inert mutation run rather than the stated
279-mutant final mechanism and fifteen inert dispositions. Those records cannot
support the current implementation.

For provenance-ignores-write-order-and-direct-results, model reaching definitions
in source order within each lexical scope, with every write acting as a provenance
update or barrier. Seed provenance directly from a subprocess-result expression as
well as assignments. Add controls for derived-then-overwritten, alias-then-
overwritten, direct result attribute, and imported/qualified subprocess forms.

For current-gate-and-record-evidence-disagree, stabilize the fixture and its exact
locator expectations, rerun the complete focused gate, and rewrite both records to
match the final test count and the exact 279-mutant behavioral/inert disposition.
Do not approve on evidence from the earlier implementation.

S120 and S121 remain unapproved with two high findings. No critical finding was
found.
## 2026-09-08 authoritative exact-revision re-review

Review began against detector SHA-256 `12731DE24206736D5AA141553B6D5870B9F156B480486E121BE0F766D12FC824` and gate SHA-256 `013AB9D547AC04F0F2E7CAC75370EB848618D266DC4188900E4B160D3C4EAD24`. The focused gate completed with 13 passing tests in 81.33 seconds. Ruff and basedpyright both completed cleanly. The gate is marked `unit` and lives under `dev/quality/tests/`; `test-dev-ci` selects that path with a marker expression that includes `unit`, and the per-push workflow invokes `test-dev-ci`. The real-tree sweep covers both declared Python roots, the anti-vacuity control requires a nonempty enrolled population and the actual `dev/audit/report.py` consumer, and the historical positive control is a named non-collected fixture that reproduces the former dynamic verdict loop. No module-sized Python source is embedded in the quality test.

The prior exact-historical-dynamic-verdict-is-undetected finding is closed by the fixture-based loop control. The original narrow unrelated-receiver counterexample is closed, and the covered ordinary assignment, future-write, branch-join, loop, comprehension, direct-result, helper-parameter, and subprocess-alias controls materially improve reaching provenance. The earlier current-gate-and-record-evidence-disagree finding is only partly closed: the focused gate is green, but the execution records still state 12 tests and mutation evidence for an earlier implementation.

During this re-review the live files changed concurrently to detector SHA-256 `15775B6BE57A9AE9597939AA530ECAB535001FB65D852FAEE465A6C2EE3385BF` and gate SHA-256 `26CC368694C14259328AC1434C91678CE7465913769BF2076BCFD97C56EFB4B2`. Consequently the green run proves the requested starting identities, while subsequent counterexample probes and any later mutation run must be bound to their own hashes. This review does not transfer approval across that drift.

### reaching-writes-are-not-complete | high | non-Assign writes and destructuring break provenance in both directions

The implementation models only direct-name `Assign` and `AnnAssign` writes. A later named-expression overwrite is therefore invisible: after assigning captured `lint-imports` output to `output`, `(output := "ordinary")` followed by `output.endswith("KEPT")` was still reported. This is a false positive against an ordinary receiver and contradicts the S120 record's statement that every later write acts as a provenance barrier. In the inverse direction, `output, code = subprocess.run([COMMAND]).stdout, 0` followed by `output.endswith("KEPT")` produced no finding, even though the predicate is directly against captured producer output. Reaching-definition closure is not yet established.

### receiver-attribution-still-accepts-discarded-calls | high | a nested producer call taints an unrelated receiver expression

`_is_subprocess_output` walks the entire receiver expression and returns true when any descendant is a matching call. The counterexample `(subprocess.run([COMMAND]), "ordinary")[1].endswith("KEPT")` produced a finding even though the run result is discarded and the receiver is exactly the unrelated literal `"ordinary"`. The earlier predicate-receiver-is-not-bound-to-gate-output finding therefore remains open for composite expressions, despite being closed for the original plain-name specimen. Provenance must follow the value selected by the expression rather than the mere presence of a producer call beneath it.

### producer-invocation-attribution-is-incomplete | high | valid subprocess spellings are outside the detector

A valid `subprocess.run(args=[COMMAND]).stdout.endswith("KEPT")` call produced no finding because only the first positional argument is inspected. A function-local `import subprocess` followed by the same weak predicate also produced no finding because import aliases are collected only from the module body. Both are statically attributable invocations of the declared producer and both apply the prohibited suffix predicate to captured output. The concurrently added composed-command control may close the separate multi-element command case, but it does not close these two counterexamples and was not part of the requested starting identities.

### exact-hash-mutation-and-record-evidence-is-pending | high | S121 cannot be approved from an earlier implementation's run

The S121 record reports 445 selected, 421 killed, and 24 inert survivors while both execution records still describe a 12-test gate. The reviewed gate contains 13 tests, its fixtures include the historical and conditional controls omitted from the record's change list, and an exact-current-hash mutation run was still pending during this review. Under the governing ADR, mutation evidence cannot be inherited across semantic detector or gate changes. S121 remains unapproved until one stable detector/gate identity has a complete bounded run, every survivor is individually disposed, the gate is rerun at those identities, and the records are reconciled to that evidence.

## 2026-09-08 re-review recommendations

Extend the reaching-write model to every supported binding form and barrier, at minimum named expressions and destructuring targets, with paired false-positive and false-negative fixtures. Replace descendant-call membership with value-preserving expression provenance so discarded calls do not taint unrelated values. Attribute `subprocess.run` through its valid `args=` spelling and lexical imports, and add isolated controls for those forms. Then freeze the detector and gate identities, rerun the focused and real-tree gate, run the bounded mutmut scope against exactly those identities, triage every survivor without a score, and update S120/S121 records before requesting another review.

S120 and S121 are not approved. Four high findings remain and no critical finding was found.
## 2026-09-08 repaired-provenance disposition

This re-review inspected detector SHA-256 `6422CA745D0B6CCCC7295BAD4F0FF4A03AEC08355017428A4074D45A60674CAF` and gate SHA-256 `7E5DEBC05439C9554CD50309244A33AB68172163D58541C444C92EEE706CC3FD`. Independent probes confirm that the new named provenance fixture represents the intended repairs rather than merely changing expected output.

The reaching-writes-are-not-complete finding is closed for its demonstrated cases: a named-expression overwrite now removes taint, and tuple destructuring from captured output now supplies provenance. The receiver-attribution-still-accepts-discarded-calls finding is closed: the discarded-run tuple expression is quiet. The valid-spelling portion of producer-invocation-attribution-is-incomplete is closed: both `subprocess.run(args=[COMMAND])` and function-local module/direct imports produce the required findings. These controls remain in a named non-collected fixture rather than embedding a synthetic module in the quality test.

### producer-callable-identity-ignores-reaching-writes | high | shadowed and future imports are falsely attributed to subprocess

Import collection is scope-wide and its aliases are treated as timeless names rather than reaching definitions. After `import subprocess`, assigning `subprocess = fake` and calling `subprocess.run([COMMAND])` still produced a finding. The direct form behaves the same way after `from subprocess import run; run = fake`. A call through `local_process` before a later `import subprocess as local_process` was also retroactively attributed. These receivers are not proven calls to the declared producer. This is the same origin-attribution requirement as the narrowed producer-invocation-attribution-is-incomplete finding: recognizing local imports is necessary, but recognition without source-order barriers introduces false positives. Model import bindings and subsequent writes at the call site, with controls for module alias shadowing, direct alias shadowing, and future local imports.

### current-conditional-control-is-red | high | the repaired gate's expected findings lag its fixture

The focused invocation completed with one failure and 14 passes. `gate_verdict_conditional_edges.py.fixture` now contains a same-branch assignment and predicate at line 92. The detector correctly reports that fifth `endswith("KEPT")` finding because both the write and use occur on the same conditional path, while the test still expects only the four findings at lines 27, 54, 68, and 76. The claimed 15-test green state is not the live state at the reviewed hashes. Reconcile the positive-control expectation and rerun the complete focused gate without weakening the detector.

The exact-hash-mutation-and-record-evidence-is-pending finding remains open. No mutation evidence tied to the reviewed detector/gate pair was available, and the execution records still cannot substitute an earlier implementation's result.

S120 and S121 remain unapproved. Three high findings remain: producer-callable reaching identity, the red current gate, and missing exact-hash mutation/record closure. No critical finding was found.
## 2026-09-08 import-identity third disposition

This review began at detector SHA-256 `A05D3D3617ACF6AB13DF54E86715FFC098E1C15E1ADDBD86AD86C80FCFFE3161` and gate SHA-256 `25972AB18919C3820ADC9FA033AC5C70B83A470458B849A2B3DE6328ACC71B1B`. The focused gate passed 16 tests in 46.96 seconds at that pair. Independent controls found module-alias, direct-alias, parameter, assignment, named-expression, future-import, class-definition, loop-target, and comprehension-target shadows quiet; ordinary module/direct producer calls still yielded the expected findings. The conditional fixture yielded all currently declared same-path findings. Ruff, ty, and basedpyright were clean.

The implementation then drifted during review, first to detector/gate `8D33E6B79849C698E3E3E72542024D89A46ADAA75F6D557E89032DF8B510BBB9` / `6EDCCED415AD12EED029C7DF1A01587D8DB85E119A9544D14220ECCF01F861BA`, and then to detector `4CEFFC7D728746D7618B21C9D62B3D7EA78262299D2FAAB866F4BCFE4CA8644B` with the same gate hash. Evidence is not transferred across those identities.

The prior producer-callable-identity-ignores-reaching-writes finding is closed for assignments, named expressions, parameters, future imports, class definitions, and loop/comprehension targets. A residual definition form remains.

### function-definition-shadow-is-still-attributed | high | a local function named subprocess does not block the imported module

With a module-level `import subprocess`, a function that first declares local `def subprocess(): pass` and then evaluates `subprocess.run([COMMAND]).stdout.endswith("KEPT")` still produced a finding at the latest observed detector identity. Python resolves that name to the local function, not the imported subprocess module, so this is a false producer attribution. The advertised definition barrier handles a class definition but not a function definition. Add direct and asynchronous function-definition shadow controls and make both bindings block imported module/direct aliases at the use site.

### live-gate-drifted-red-again | high | the current fixture and expected provenance list disagree

A fresh focused run against the later live files completed with one failure and 15 passes. The provenance fixture now produces one additional `endswith("KEPT")` item before the expected `startswith("BROKEN")`, while its exact expected list was not updated. As in the prior red-gate finding, a green run at an earlier hash cannot certify the changed gate surface. Stabilize the fixture and expected semantics, then rerun at unchanged hashes.

The exact-hash-mutation-and-record-evidence-is-pending finding remains open. No complete mutation result tied to a stable final detector/gate pair was available.

S120 and S121 remain unapproved. Three high findings remain: local function-definition producer shadowing, the red live gate after drift, and missing exact-hash mutation/record closure. No critical finding was found.
## 2026-09-08 stable semantic approval disposition

This fourth re-review is authoritative for detector SHA-256 `A76C8BEBDC161807BC32229490D25D800DCB98C3B5FEDA88BC10BB57BB24C5DB` and gate SHA-256 `FC96F3451C04876E0504AED722FA4E09FA53845D288BEC87EC294F3891D7FAFF`. Both identities remained unchanged through the independent probes and complete verification.

The function-definition-shadow-is-still-attributed finding is closed. Nested synchronous function, asynchronous function, and class definitions now block imported subprocess module/direct identities in their enclosing scope. Assignment, named-expression, parameter, loop target, comprehension target, and future local-import barriers remain quiet. Independent ordinary controls through `subprocess.run(args=[COMMAND])` and directly imported `run([COMMAND])` still produce the expected `endswith("KEPT")` and `startswith("BROKEN")` findings, so the barriers do not achieve silence by disabling producer attribution.

The live-gate-drifted-red-again finding is closed. The current conditional fixture produces its six declared same-path findings at lines 27, 54, 68, 76, 91, and 96, and the complete focused gate passed all 16 tests in 46.94 seconds. Ruff, ty, and basedpyright were independently clean. The named fixtures continue to carry the historical positive control, provenance counterexamples, and import-binding controls outside collected test code; the real-tree sweep, non-collapsing consumer floor, and per-push marker/path selection remain intact.

All semantic findings recorded by this audit are closed for the stable identities above. S120 is approved on detector semantics and gate design. S121 is not yet approved because exact-hash-mutation-and-record-evidence-is-pending remains open: the governing decision requires a bounded mutation run against this exact stable detector/gate pair, individual disposition of every survivor, a green post-run gate at the same identities, and execution records reconciled to the final 16-test and mutation evidence. No other high or critical finding remains.
## 2026-09-08 mutation-control semantic re-review

This review is authoritative for detector SHA-256 `3F567EA4740B7D648F3FD0931B0048BF9FACE275BBEECA568EC6CD5553A37031` and gate SHA-256 `9DD2A8FB5E2A14FF8C6CF173F43BD29D707B6FD9F4E9D583634B62713271A192`. The identities remained stable through the review. The focused gate passed all 17 tests in 79.27 seconds; Ruff lint, Ruff formatting, ty, and basedpyright were clean.

All earlier source-order, reaching-write, receiver-selection, helper propagation, import-origin, shadowing, and historical-loop findings remain closed. Independent probes confirmed that shadowed producer aliases remain quiet, the historical stdout-plus-stderr capture still fires, and both positional and keyword producer invocations retain attribution. The new named fixture is preferable to embedding a synthetic module in test logic, and most of its cases express observable source semantics: bounded loop values, selected tuple elements, all-path conditional provenance, reaching verdict writes, comprehension bindings, branch joins, terminating exception paths, and alias collisions.

### nonempty-binop-controls-encode-overbroad-taint | high | mutation teeth require findings where the producer grammar cannot determine the predicate

The `left-binop` control requires `(subprocess.run(...).stdout + "ordinary").endswith("KEPT")` to be a finding. That predicate is necessarily false because the receiver ends in `"ordinary"`, regardless of whether import-linter emits a bare verdict or a verdict with parenthetical context. The symmetric prefix counterexample `("ordinary" + subprocess.run(...).stdout).startswith("KEPT")` is likewise necessarily false, yet the detector reports it. These are not blind-green weak readings of a gate-output token; the nonempty literal has replaced the relevant boundary grammar. Requiring them appears designed to distinguish the implementation's `left provenance or right provenance` branch from an `and` mutant rather than to protect the accepted behavior.

Mutation controls must not expand detector semantics merely to kill a generated mutant. Replace the nonempty compositions with value-preserving forms such as `output + ""` and `"" + output`, which still prove one-sided expression propagation without changing the predicate's grammar. If the `or`-to-`and` mutant becomes observationally indistinguishable after controls are restricted to supported, value-preserving behavior, dispose it as semantically inert with that reason instead of preserving a false-positive contract.

The exact-hash-mutation-and-record-evidence-is-pending finding remains open. The A76-era run selected 994 mutants, killed 838, and left 156 survivors over a superseded detector/gate pair; its survivors are not fully triaged and none of that evidence transfers to the current identities.

S120 and S121 are not approved at the current pair. Two high findings remain: the overbroad nonempty-composition mutation control and missing exact-current-hash mutation/record closure. No critical finding was found.
## 2026-09-08 value-preserving composition disposition

The nonempty-binop-controls-encode-overbroad-taint finding is closed. The `left-binop` and `right-binop` controls now concatenate only the empty string: `run.stdout + ""` and `"" + run.stdout`. Both expressions preserve the producer output value and grammar exactly while independently requiring provenance from either binary operand. They therefore distinguish the one-sided provenance mutation through accepted detector behavior rather than by teaching the gate to report a predicate whose result was fixed by an unrelated literal. The focused mutation-control test passed at unchanged detector/gate hashes `3F567EA...A37031` / `9DD2A8FB...71A192`.

No semantic high or critical finding remains for this pair. S120 is approved on semantics and gate design. S121 remains unapproved only for exact-hash-mutation-and-record-evidence-is-pending: a complete bounded mutation run and individual survivor disposition must target the current detector, gate, and corrected fixture bytes before the record can close.
## 2026-09-08 simplified-fixture semantic disposition

This review is authoritative for detector SHA-256 `3F567EA4740B7D648F3FD0931B0048BF9FACE275BBEECA568EC6CD5553A37031`, gate SHA-256 `FC96F3451C04876E0504AED722FA4E09FA53845D288BEC87EC294F3891D7FAFF`, and the declared 16-fixture aggregate `831C28DF49A03BCC825CFD46EBF8C6212BE4C23F6FC2F838C30C17734AC050A7`. The former omnibus `gate_verdict_mutation_controls` fixture and its test are absent. The complete focused gate passed all 16 tests in 47.55 seconds at the current detector semantics; the gate hash changed only through the removal/formatting of the omnibus test.

The remaining named source fixtures are behavior-level AST specimens. They mention no private detector helper, mutant identifier, survivor number, or implementation branch. Each fixture has one public semantic subject: declared weak predicate shapes, the historical report loop, clean and unenrolled modules, output overwrites and future writes, foreign versus real subprocess origins, direct and keyword invocations, command reaching values, selected tuple values, destructuring and named-expression barriers, import shadowing, helper propagation, source order and cycles, or conditional reachability. Their gates assert public findings or silence, including path, predicate, verdict, and selected source location where attribution is contractual. The deliberately non-executable future/unbound branches are valid parser specimens for a static detector and are paired with real-tree execution evidence rather than presented as runtime programs.

Semantic coverage remains complete for the accepted class. The historical positive control reproduces the former dynamic `KEPT`/`BROKEN` loop against captured `lint-imports` output. Ordinary direct and helper-derived output positives still fire; unrelated, overwritten, shadowed, future, cyclic, and unenrolled cases remain quiet. The consumer floor requires the actual `dev/audit/report.py` enrollment and the final test sweeps both declared repository roots. Removing the omnibus fixture therefore removes mutation-directed duplication without removing the positive control, negative precision controls, anti-vacuity floor, or real-tree sweep.

No semantic, fixture-design, high, or critical finding remains for this exact snapshot. S120 is approved on detector semantics and test design. S121 remains unapproved only until a bounded mutation run targets this detector, gate, and exact fixture aggregate, every survivor is individually disposed, and records are reconciled. The A76-era 994-selected, 838-killed, 156-survivor run is historical: it exercised different fixture bytes, its survivors are untriaged, and it cannot close the current Step.

## 2026-09-08 simplified-detector semantic review

The reviewed snapshot matches detector SHA-256 `D28C129D65837DE9865A9663B89C8E8433F7C59C65E1856DCD3FE2DFA5AC770A` and gate SHA-256 `D2BFA082481F6EE88210AF93026CFF56C57376BFBFB2CB764B071F0678F8F46B`. The gate uses nine named behavior fixtures with aggregate SHA-256 `99C264ABDBDA16B95FBC724CEE38F97D593584ACED86AE9A36DEA344A4344658`; the removed omnibus mutation-control fixture and seven implementation-edge fixtures remain absent. The focused gate passed all eight tests in 43.90 seconds. Ruff lint, Ruff formatting, and `ty` passed over the detector and gate. The historical report positive control, direct subprocess forms, simple output assignment, enclosing output/verdict loops, real-tree sweep, consumer anti-vacuity, and UTF-8 path attribution are present and green.

### declared-producer-rebinding | high | non-subprocess bindings are still attributed to the declared producer

The simplification does not preserve the producer side of S120's required AST-to-declared-output-grammar join. `_name_is_shadowed` recognizes only ordinary direct assignment and ordinary parameters. A module-level `import subprocess` followed in the consuming function by a loop target named `subprocess`, tuple destructuring into `subprocess`, or a nested definition named `subprocess` is still reported when a direct `subprocess.run` output receives an `endswith` verdict predicate. Independent probes produced one `endswith` finding for each specimen, even though the invoked object is the intervening local binding and is not the declared subprocess producer. These are direct-output predicates within the detector's advertised closed shape; resolving whether the syntactic callee is actually the declared producer is not optional general data-flow analysis. The existing foreign-import control does not exercise local rebinding.

Record every same-scope binding that can replace an imported module or direct function alias before the call, or contract the implementation to an import/call form whose identity it can prove. Add named negative controls for representative non-assignment bindings before approving mutation work. The nested conditional output-assignment probe was not treated as a finding because it falls outside the explicitly advertised simple preceding assignment shape. Mutation rerun is not yet probative: semantic approval is withheld until `declared-producer-rebinding` is closed at a new exact detector/gate identity. No critical finding was found.

## 2026-09-08 producer-rebinding repair re-review

The reviewed repair matches detector SHA-256 `1CEFF3CF364BACC4AF6382683E9B06B10A5A42B06D841AFD9B54F9DBCB490081`, gate SHA-256 `E41D2216647F63BD26D62E6017636D9AB3DEB5BEAFE06F4B98BF42E80BDA2CB7`, and ten-fixture aggregate SHA-256 `6E8DB60E6A5E68647DAFA8646196CCB6DF2FEB9FDC9C4866AF6B08D16D57ACEF`. Independent probes confirm that loop-target, tuple-destructuring, and nested-definition rebinding no longer produce findings, while the ordinary direct subprocess positive still produces the expected `KEPT` suffix finding. The focused gate passed all eight tests in 41.79 seconds; Ruff lint, Ruff formatting, `ty`, and BasedPyright passed.

### declared-producer-rebinding | high | partially repaired but additional same-scope bindings remain misattributed

The prior finding remains open. The new binding-event logic covers only ordinary positional and keyword-only parameters, assignment, annotated assignment, loop targets, and definitions. A variadic parameter named `subprocess` and a `with` optional-vars target named `subprocess` both replace the imported producer, yet independent direct-output probes still report an `endswith('KEPT')` finding. A direct call before a later ordinary assignment to `subprocess` is also reported even though Python makes that name local for the entire function and the imported module cannot be the invoked binding. These are not broader output data-flow shapes: each predicate is applied directly to the apparent call output, and each counterexample tests the required identity join for the declared producer.

Complete the function-scope binding model for variadic parameters, context-manager targets, and function-wide local declarations, then add behavior-named negative controls. Other binding forms with the same lexical effect should be handled by the same rule rather than enumerated only after mutation exposes them. Mutation rerun is not approved at this identity. No critical finding was found.
