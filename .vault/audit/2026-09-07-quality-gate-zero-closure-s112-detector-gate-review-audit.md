---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9a4aefc0d205ed33d901b40b8957cc10156016ad5fe40273145d939ee9937821'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# `quality-gate-zero-closure` audit: `S112 detector gate implementation review`

## Scope

Reviewed `W08.P24.S112` against the accepted blind-green decision, the binding
commit-time adjudication, the owning plan, and the S109-S112 execution records.
The reviewed implementation surface was limited to the tautological-assertion,
subsuming-disjunction, and self-echoing-token gates, their production scanners,
their non-collected fixtures, and the shared mutmut configuration. No production,
test, plan, or execution-record file was changed by this review.

The three focused gate modules passed together: 54 tests in 66.48 seconds. The
review also drove two legitimate counterexamples through the production scanners;
both were reported, establishing the two precision findings below. The current
S112 record contains no mutmut invocation or survivor dispositions. Separate fresh
evidence kills subsuming mutant
`x_scan_paths_for_subsuming_disjunctions__mutmut_7`, but that single outcome does
not establish a bounded run and individual disposition for every detector named by
S112.

## Findings

### subsumption-effectful-haystack | high | textual equality is mistaken for one evaluated haystack

`scan_subsuming_disjunctions` uses `ast.unparse` text as haystack identity and
accepts every expression shape. It therefore reports
`assert "a" in next(stream) or "ba" in next(stream)` even though the two calls can
return different values and the broad operand does not subsume the specific one.
The gate's negative controls cover different names but not repeated effectful
expressions. This exceeds the detector's closed semantic claim and creates a future
false-positive pressure that cannot be resolved with an exemption under the
accepted decision.

### self-echo-result-is-unbound | high | invocation tokens are joined to unrelated assertions in the same function

`scan_self_echoing_tokens` collects every supported invocation token in a function
and then joins that set to every membership disjunction in the function. It does
not bind the invocation's assigned result to the assertion haystack or respect
which invocation produced that result. A function invoking `first` into
`first.output`, then invoking `show` into another result, is reported when it later
asserts `"show" in first.output`. The supplied token cannot have been echoed by the
asserted result in that specimen. The positive controls prove token matching, but
the negative controls do not prove the causal relation S111 and S112 claim.

### per-detector-mutation-proof-missing | high | S112's mutation completion claim is not evidenced

The governing decision requires a bounded mutation run for each detector after
its implementation, gate, or shared mutation configuration changes, followed by
individual disposition of every non-killed mutant. The S112 execution record lists
pytest, Ruff, type checking, and lock verification only. Earlier tautology
measurement recorded surviving behaviour-changing mutants, no self-echoing-token
run is recorded, and the fresh subsumption evidence establishes only that one
specific filesystem-decoding mutant is killed. These facts do not prove that each
of the three detector gates can fail across its bounded mutant set. S112 therefore
cannot be approved or closed on the current evidence.

## Recommendations

For `subsumption-effectful-haystack`, constrain accepted haystacks to an
explicitly side-effect-free AST shape whose repeated evaluation preserves the
subsumption argument, and add the repeated-call specimen as a negative control.
Do not add an exclusion or declaration.

For `self-echo-result-is-unbound`, trace each supported invocation's assigned
result to the asserted output expression and join only that invocation's literal
arguments. Add a two-invocation specimen proving that a token supplied to one
result cannot condemn an assertion over another.

For `per-detector-mutation-proof-missing`, after the two precision repairs and
their gate controls land, run mutmut separately for each S112 detector from a
fresh reproducible POSIX/WSL snapshot using the recorded bounded invocation.
Record every terminal outcome, triage every survivor individually as behavioural
or semantically inert, and add the exact invocations and dispositions to S112's
execution evidence. A mutation score or one representative killed mutant is not
a substitute.

**2026-09-07 re-review status ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ã‚ `subsumption-effectful-haystack`.** The new
stable-reference predicate and `effectful_repeated_haystack` negative control
correctly reject repeated calls, so the original demonstrated `next(stream)`
counterexample is resolved. The finding remains open at high severity because the
predicate classifies arbitrary attribute chains as stable even though Python
attribute access can invoke a descriptor. The production scanner reports
`assert "a" in source.value or "ba" in source.value`; a property may return a
different value on each access, so the operands still need not share one evaluated
haystack. Close this by either restricting the accepted reference shape to names,
or by grounding any accepted attribute form in a property-free binding the scanner
can actually prove, with a descriptor-backed negative control.

**2026-09-07 re-review status ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ã‚ `self-echo-result-is-unbound`.** The result-name
join and `unrelated_invocation_result` negative control correctly prevent a token
from one assigned result condemning another result. The finding remains open at
high severity because the index ignores intervening non-supported assignments.
The production scanner reports a self echo when `result` is assigned from
`invoke_cached_cli(["show"])`, then overwritten by `unrelated_call()`, and only
then asserted through `result.output`. The supported invocation did not produce the
asserted value. The binding must account for every intervening write to the name,
and the gate needs this overwritten-result negative control; more generally, the
accepted control-flow shape must be one whose reaching definition is provable.

**2026-09-07 scope-aware re-review - `self-echo-result-is-unbound`.** The
same-scope traversal closes the nested-function counterexample, traversal-position
ordering closes the same-line ambiguity, and ordinary, annotated, augmented, and
named-expression writes now act as barriers. The new unbound and
continue-after-rejected-operand controls also show that one unsupported membership
cannot terminate the remaining disjunction sweep. Those repairs pass their 21-test
focused gate with Ruff lint, formatting, and `ty` green.

The high finding nevertheless remains open because the accepted shape is still
wider than the causal claim. `_result_name` accepts every direct attribute rather
than a declared captured-output attribute, so an assertion over `result.metadata`
is reported as an output echo. The write index also misses other same-scope name
bindings: tuple-unpack assignment and a `for` target can replace `result` after the
supported invocation, yet both specimens are still reported against the obsolete
invocation binding. Restrict the haystack attribute to the detector's declared
captured-text surface and make every intervening binding of the result name a
barrier, including destructuring and statement target bindings, with one control
for each supported boundary. No new critical finding was found.

**2026-09-07 re-review status ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ã‚ tautology mutation controls and test doubles.**
The added mapping-truthiness case, exact diagnostic controls, UTF-8 filesystem
adapter control, source attribution assertion, and skip-notice newline assertion
exercise the behaviour categories previously exposed by the tautology mutation
triage. The three S112 gate modules contain no `monkeypatch`, `unittest.mock`,
patching API, or mock-object use. The focused run passed all 60 tests in 67.88
seconds; Ruff lint and `ty` passed. These controls introduce no remaining high or
critical review finding, subject to the still-open per-detector mutation evidence
finding above.

**2026-09-07 re-review status ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ã‚ focused formatting.** `ruff format --check`
reports that `self_echoing_tokens.py`, `subsuming_disjunctions.py`, and
`test_tautological_assertion_gate.py` would be reformatted. This is a low-severity
mechanical closure defect; format those files and repeat the focused check without
changing detector semantics.

**2026-09-07 final focused re-review - `subsumption-effectful-haystack`.** The
stable-reference predicate now accepts only `ast.Name`; both repeated calls and
attribute access are explicit negative controls, and a rejected candidate is also
shown not to terminate the later sweep. Direct probes return no finding for either
counterexample. The detector now stays inside the same-evaluated-name claim, so
this high finding is closed.

**2026-09-07 final focused re-review - `self-echo-result-is-unbound`.** Recording
unsupported ordinary assignments as barriers closes the previously demonstrated
cross-result and intervening-`Assign` counterexamples. The finding remains open at
high severity because the recursive function walk crosses lexical scopes and the
write index recognises only `ast.Assign`. A supported invocation assigned inside a
nested helper is joined to an assertion over the outer function's unrelated local
of the same name. An intervening annotated assignment likewise does not become a
barrier. Both specimens produce `SelfEchoingToken` findings in the current scanner.
Keep each scan within one lexical function body without descending into nested
function or class scopes, and treat every supported name-binding form as either a
proven invocation binding or a barrier; add both specimens as negative controls.

**2026-09-07 final focused re-review - formatting and focused verification.** The
focused suite now passes all 63 tests in 59.97 seconds. Ruff lint, Ruff formatting,
and `ty` all pass over the five reviewed implementation and gate files. The prior
low formatting defect is closed. No new high or critical issue was found in the
subsumption or tautology controls, and the mock/monkeypatch prohibition remains
satisfied. The independent `per-detector-mutation-proof-missing` high finding
remains open until its recorded evidence requirement is met.

**2026-09-07 final binding-boundary resolution - `self-echo-result-is-unbound`.**
The detector now accepts only a direct `.output` reference and indexes all binding
events needed by its same-scope claim: direct and destructuring assignments,
annotated, augmented, and named-expression writes, synchronous and asynchronous
loop and context-manager targets, exception names, definitions, and imports.
Comprehensions and nested definitions are correctly kept outside the enclosing
lexical traversal. The metadata, tuple-unpack, loop-target, nested-scope, and
annotated-overwrite counterexamples all return no finding, while the positive and
continue-after-rejected-operand controls still fire. This closes the remaining
precision high finding.

The focused gate passed 25 tests in 14.61 seconds on the final reviewed snapshot;
Ruff lint, Ruff formatting, and `ty` passed, and no mock or monkeypatch use was
found. No high or critical issue remains in the two precision repairs. The separate
`per-detector-mutation-proof-missing` high finding remains open until its recorded
mutation evidence and survivor dispositions exist.

**2026-09-07 final S112 mutation re-review - `per-detector-mutation-proof-missing`.**
A fresh isolated mutmut run bounded to `self_echoing_tokens` selected 143 of the
configured 295 mutants. It terminated with 139 killed and four surviving outcomes.
Each survivor was reviewed individually rather than converted into a score:

- `x__echoed_token__mutmut_11` changes `continue` to `break` after tokens are
  sorted by descending length. Once the first token shorter than four characters
  is reached, every remaining token is also shorter, so neither form can produce
  a candidate.
- `x_scan_self_echoing_tokens__mutmut_36` changes
  `assignment_position < position` to `assignment_position <= position`. One AST
  traversal node cannot simultaneously be the indexed assignment and the later
  assertion, so equality cannot alter the selected reaching binding.
- `x_scan_self_echoing_tokens__mutmut_5` and
  `x_scan_self_echoing_tokens__mutmut_6` remove or change the filename passed to
  `ast.parse`. They affect only `SyntaxError` attribution outside the detector's
  verdict over parseable modules.

All eight previously surviving behaviour-changing mutants are killed by real
syntax controls, including starred destructuring, context-manager and exception
targets, and dotted and aliased imports. Together with the already reviewed
tautology and subsumption mutation evidence, this closes
`per-detector-mutation-proof-missing`: every non-killed outcome is individually
disposed as equivalent or metadata-only, and no mutation score is used as a pass
condition.

The final current-tree verification passed 79 focused tests in 52.57 seconds.
Ruff lint passed, Ruff confirmed all six reviewed files are formatted, `ty`
passed, and the three gate modules contain no mock or monkeypatch use. The
positive controls, per-root anti-vacuity floors, real-tree sweeps, precision
repairs, and bounded mutation evidence now satisfy S112. All three high findings
in this audit are closed; no high or critical finding remains.

## 2026-09-08 exact S112 subsumption mutation closure

### subsumption-current-mutation-proof | low | closed with individually disposed survivors

The reviewed detector and gate match SHA-256 `5D74756B3E02C282C0E4E71787F0834202B3E120BE418B7D386194718FB605E8` and `CA675F02EA16B9A9917BFD3FD3A79536102EEF179C77E008C15510CC90A11B31`. An independent current-tree run passed all 14 gate tests in 7.09 seconds; Ruff lint, Ruff formatting, and `ty` also passed over the pair. This independently confirms the positive strict-substring verdict, stable-reference precision controls, real-tree sweep, anti-vacuity floors, direct UTF-8 filesystem adapter, and path and line attribution at the reviewed identities.

The accepted bounded mutmut 3.7.0 run used the exact detector and gate identities above and configuration snapshot SHA-256 `EECF07EF6C2F204655E89AB0329C6363BCCD5E1B0F73090CBF0D26E7A6317ECF`. It selected 75 mutants, killed 69, and terminated with six survivors in 212.92 seconds, with zero error, suspicious, timeout, no-test, skipped, or typecheck outcomes. Each survivor is semantically inert: `UTF-8` is the same registered codec as `utf-8`; passing `None` for `ast.dump(include_attributes=...)` is falsey and has the same result as `False`; omitting that argument uses the same `False` default; choosing the second structurally equal haystack produces the same stable-name subject; and the two `ast.parse` filename changes affect only syntax-error metadata outside this detector's parseable-source verdict. The formerly actionable `path=None` and ambient-default-decoding mutants are killed by the current filesystem boundary control. No aggregate mutation score is used.

The live whole `pyproject.toml` subsequently advanced to SHA-256 `F58C68B2DCDD35A83509DB62EE0233A042D0541F1CBC4267311C4F04C9BBAD23`. Its current `[tool.mutmut]` block still names `dev/quality/subsuming_disjunctions.py`, copies both real scan roots, and selects `dev/quality/tests/test_subsuming_disjunctions.py`; therefore this is recorded as post-run whole-file identity drift, not as a transfer of the run to a different detector or gate. S112's subsumption mutation requirement is closed at the exact source and gate identities. No high or critical S112 finding remains.

### 2026-09-08 evidence-identity correction

The preceding identity qualification is superseded. SHA-256 `EECF07EF6C2F204655E89AB0329C6363BCCD5E1B0F73090CBF0D26E7A6317ECF` identifies the named behavior fixture `dev/quality/tests/fixtures/subsuming_disjunction_cases.toml`, not `pyproject.toml`. The supplied and current `pyproject.toml` SHA-256 is `F58C68B2DCDD35A83509DB62EE0233A042D0541F1CBC4267311C4F04C9BBAD23`; there was no mutation-configuration drift in this S112 receipt. The exact detector, gate, fixture, and configuration identities therefore agree, and the S112 closure disposition remains unchanged.
