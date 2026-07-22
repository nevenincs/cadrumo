---
tags:
  - '#audit'
  - '#duplication-evidence-repair'
date: '2026-07-22'
modified: '2026-07-22'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
  - "[[2026-07-17-duplication-evidence-repair-adr]]"
  - "[[2026-07-17-cli-authority-verb-conformance-audit]]"
---

# `duplication-evidence-repair` audit: `Close honesty review`

## Scope

Fresh-context honesty review of the duplication evidence repair plan, which reported seven of seven steps complete with no close audit. The campaign close honesty review discipline requires this gate before structural completeness may be declared; it never ran, so the plan was declared complete without it. This record is that gate.

The reviewer adopted an inherited-campaign persona and treated every plan claim as untrusted until re-verified against the tree at review time. The duplication runner was executed live and both test suites were run in full rather than read. The review was read-only; no file was modified.

Commands run and their real output: the duplication and dev-audit-report suites returned twenty-two passed in one hundred ninety-nine seconds; the runner itself reported fourteen clones at zero point zero nine percent duplicated lines; a plan status run reported seven of seven steps complete with all seven unlinked.

## Findings

### core-defect-closed | low | The false-green defect is structurally unreachable and its proofs are genuine

The campaign's central stake holds and could not be broken. The observed-zero constructor in `dev/audit/duplication.py` raises when no files were analysed, so the green state cannot be built without proof of inspection. The parser refuses green when either the clone-count line or the summary table is absent. Missing scanner, timeout, operating-system error, and non-zero exit each route to an unavailable outcome carrying a diagnostic reason, and `dev/audit/report.py` maps unavailable to amber with an explicit statement that the absence of evidence is not a clean-tree signal. Green is granted on observed-zero alone. No code path leads from an unavailable scan to green.

The proofs are non-tautological, which matters more than the code. The test module pins the byte-exact real scanner output captured under the original defect and asserts it classifies as unavailable. Failure conditions are forced rather than faked: a genuine non-zero exit is obtained by launching a real process that rejects its arguments, a real millisecond timeout is applied to a real subprocess, and the green assertion is earned from a real scan over a genuinely clone-free subtree. A files-analysed lower bound prevents a partial scan passing as a full one. No assertion is anchored to a value the code under test computed.

### single-scanner-owner-python | low | One owner for the scanner invocation across the Python tree

The health report no longer builds a scanner command; its only remaining subprocess call belongs to the unrelated layering dimension, and it delegates the whole measurement to the runner. The build recipe invokes the runner module directly with no shell pipeline. A guard test walks the development tree and asserts the set of modules constructing a scanner command is exactly the runner.

### disposition-record-internally-inconsistent | high | The disposition record contradicts its own arithmetic

The dispositions file declares sixty-five observed groups. It contains sixty-six group blocks and sixty-six classification lines, and its own summary section sums to sixty-six. The closing commit recorded both figures side by side as a passing gate without reconciling them. Either a sixty-sixth group was recorded that the scan did not observe, or the declared count is wrong.

### disposition-record-has-no-gate | high | The plan's own verification criterion is unverifiable by construction

The plan asserts that every observed clone group carries an explicit recorded disposition. No test, gate, or consumer reads the dispositions file anywhere in the tree; the only other mentions are the plan step itself and one prose reference in an unrelated execution record. The claim cannot be checked and can rot silently. Every other step in this plan landed a real gate, which makes this step the outlier rather than the pattern.

### disposition-record-already-stale | high | The recorded counts no longer reconcile with the live runner

The runner now reports fourteen clone groups at zero point zero nine percent against the record's sixty-five groups at zero point four one percent from five days earlier. Cross-checking every file in the fourteen current groups against the record's location entries shows all sixteen distinct files still present, so file-level coverage happens to hold and the drop is consistent with genuine consolidation landing in peer campaigns rather than a measurement regression. The location spans and the declared counts are nonetheless stale, and with no freshness gate nothing will detect further drift. A point-in-time snapshot is presented as a standing disposition.

### zero-exec-records | high | Seven checked steps carry no execution records and no close audit answered for them

The execution record folder for this feature does not exist and all seven steps report unlinked. The plan closure discipline permits exactly two states: an execution record, or a close audit explicitly recording why a step is a deferred carry-forward. Neither existed at the time the plan was declared complete. The originating rescope record covers the first six steps by naming their landing commit, which is a defensible substitute, but it does not cover the seventh, which it explicitly left unchecked.

### adr-blocker-removed-then-abandoned | high | The stated blocker to execution records was cleared and nobody returned

The seventh step's commit states its reason for producing no execution record: the execution scaffolding requires a decision record under this feature tag and none existed. That decision record was subsequently authored six commits later and is accepted. Its problem statement declares its entire purpose to be supplying exactly that grounding so the plan can close honestly under the closure discipline. The obstacle was deliberately removed and the records it was authored to unblock were never scaffolded for any of the seven steps. The fix landed; the follow-through did not.

### second-scanner-spec-in-build-recipe | medium | The single-owner gate does not scan the build recipe, which carries a second pinned scanner version

The environment-check recipe runs a scanner version probe carrying a second hardcoded version literal that can drift from the runner's pinned specification. A version probe cannot itself produce a false green, so the exposure is narrow. The guard test globs only Python files under the development tree, so a reintroduced scanner in the build recipe, a shell script, the source tree, or the packaging tree would pass silently. The gate proves less than its docstring claims.

### step-scope-names-the-wrong-module | low | The sixth step cites a module that does not hold its proofs

The step scopes itself to the dev-audit-report test module, which carries the end-to-end dimension test but not the false-green proof suite. The unavailable, non-zero, timeout, unparseable, bad-path, missing-scanner, and single-owner proofs all live in the runner's own test module, which the step never names. The work is done and exceeds the step's text; only the scope citation misleads an auditor reading the plan alone.

### plan-frontmatter-omits-own-adr | low | The plan does not relate to its own grounding decision record

The plan lists five related documents, none of which is the decision record authored specifically to ground it. The decision record links to the plan, so the graph edge exists in one direction only.

### no-vague-steps | low | No step hides behind a declarative verb

All seven step actions are imperative and name an artefact. None defers a decision without a gate. The seventh step's action text is concrete; its weakness is the missing gate on the artefact it produced, not vague wording.

## Recommendations

Reconcile the dispositions file against a fresh runner execution, correcting the declared group count, duplicated percentage, and files-analysed figures, and either removing the sixty-sixth block or explaining it. The summary section must equal the block count.

Land the gate the seventh step never received: a test that runs the scan and asserts every observed group's file set is covered by a recorded location entry converts an unverifiable prose claim into the same class of proof the other six steps each earned. Keep it coverage-based and advisory-tolerant rather than count-based, because the governing decision record keeps the clone count advisory.

Widen the single-owner guard beyond Python files under the development tree to the whole tracked tree including the build recipe and shell scripts, exempting the runner and the version probe by explicit name; alternatively have the probe read the runner's pinned specification so the version literal exists once.

Scaffold the seven execution records now that the decision-record blocker is gone, or amend this audit into the sanctioned close-audit answer for them. The former is preferable, since the decision record was authored specifically to enable it.

Add the grounding decision record to the plan's related field, and correct the sixth step's scope to name the module that actually holds its proofs.

The plan should not stand at seven of seven complete until the dispositions reconciliation, the coverage gate, and the execution-record disposition are addressed.
