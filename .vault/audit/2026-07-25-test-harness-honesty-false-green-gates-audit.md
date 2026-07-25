---
tags:
  - '#audit'
  - '#test-harness-honesty'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `test-harness-honesty` audit: `false-green gate audit`

## Scope

A hunt through the test harness for gates that PASS while measuring nothing.
Covered: the ~90 gate modules under `src/cadrumo/tests/`, the scanners and
baselines under `dev/`, the root `conftest.py`, the pytest configuration in
`pyproject.toml`, the `justfile` recipes, and the `dev/ci/` lane definitions.

The audit was driven by a set of false-green shapes each of which has really
shipped in this repository: a marker/selection mismatch that selects nothing and
exits green; a scanner reading the wrong field or key so it reports zero findings
over a real corpus; a gate asserting a total where the property is a
decomposition; a gate written from a docstring rather than from a measurement; a
ratchet whose baseline is looser than actual; and a test whose expected value was
hand-computed from the formula under test.

Method: parallel discovery by subagent, then independent confirmation by the
coordinator against HEAD. Every number below was re-derived by the coordinator
with an explicit interpreter walk rather than a shell one-liner, because an
unescaped dot is a regex wildcard and a misplaced include filter silently widens
a search. Two subagent claims did not survive that confirmation and are recorded
here as corrections, because a misclassification that reaches a remediation queue
costs more than the finding it displaced.

## Findings

### vacuous-xls-extension-gate | critical | A gate's regex cannot match its target, so it has never measured anything

The gate asserting that runtime `.xls` usage routes through the canonical
extension constant compiles its scanner pattern from a raw string carrying a
DOUBLED backslash. The compiled pattern therefore requires a literal backslash
followed by any single character before `xls`, so it can never match a real
Python `".xls"` string literal. The gate has been passing since it was written
while providing zero protection.

Confirmed by direct measurement, not by reading. Loading the compiled pattern and
applying it to a representative source line containing a bare `.xls` literal
returns no match, while the corrected single-backslash pattern matches that line
and correctly declines to match `.xlsx`. Scanning the real production file set the
gate itself selects — 1371 files — the shipped pattern returns 0 hits and the
corrected pattern returns 4.

The failing scenario: an author adds a bare `".xls"` literal anywhere in
production code and the gate stays green, which is not hypothetical, because four
such literals are uncaught right now. They sit in the ledger import CLI's
import-directory extension set, the registry schema-reference allowed-suffix
tuple, and two positions in the registry workbook-parity models. The last of
these is a `Literal` type annotation rather than a runtime value, so it cannot
route through a runtime constant and needs a documented escape rather than a
migration.

Note the count: an earlier pass reported three sites. The measured number is
four, because the workbook-parity module carries two occurrences on separate
lines. The discrepancy is recorded because it is the reason the coordinator
re-derives every subagent number.

### rag-discovery-instrument-answers-while-degraded | high | The mandated discovery instrument returns confident results from a truncated index and does not report itself degraded

The semantic code-search service that project rule makes MANDATORY before any
coding work was, during this audit, serving a code index holding 52 chunks for a
tree of roughly 4546 files, with a rebuild in progress. Its own status payload
reported an empty degraded-reasons list. Four unrelated probes — worker-replacement
detection, worker-count policy, marker-selection hooks, and CLI command-group
registration — each returned ten of ten hits from a single master-key recovery
module. A query about CLI command groups cannot legitimately resolve to a crypto
module.

This is a worse failure than an outage. The governing rule instructs an agent to
REFUSE coding work when the service is down, and a down service triggers that
refusal correctly. A service that ANSWERS from a truncated index never trips the
refusal, so an agent completes its mandated discovery step, concludes that no
canonical owner exists for the concept it is about to implement, and writes a
duplicate authority. That is precisely the outcome the rule exists to prevent,
and it was live for a large concurrent agent fleet, meaning any "semantic search
found nothing" conclusion reached during the window is worthless, including
conclusions recorded in peer reports.

A second-order observation: over the audit the code job identifier changed while
chunk counts climbed from 52 to 791, indicating the file watcher re-triggered the
rebuild as peers committed. Under a fleet committing every few minutes the code
index may not converge at all, so the degraded window is not self-limiting.

The service was deliberately NOT restarted, because a restart discards in-progress
index work and induces the perpetual-rebuild state this finding describes.

The failing scenario: an agent follows the mandate, gets a confident empty or
irrelevant result for a concept that does in fact have a canonical owner, and
ships a parallel implementation of it. The remediation is not a code change in
this repository; it is a degraded-state signal on the service so a truncated index
either refuses to answer or marks its answers untrustworthy, which is the same
positive-control principle this audit applies to every other gate.

### packaging-preflight-recipe-runs-a-partial-lane | medium | A release-gate recipe silently drops a third of its own tests and exits green

The packaging preflight recipe invokes pytest against the packaging test
directory with no marker override, so it inherits the project default marker
expression from the pytest configuration. That directory is mixed-marker.

Confirmed by collection: 224 of 330 tests are selected and 106 are deselected,
and the run exits zero. Among the silently dropped modules are those named for
the packaging smoke workflow, the Scoop workflow, the Homebrew workflow, and
Docker smoke selection — that is, tests named for exactly the workflows the
recipe gates. The recipe is a declared dependency of both the Linux and Docker
packaging smoke targets.

This is the partial-run variant of the marker-mismatch shape, and it is the
dangerous variant: a fully deselected run exits with the no-tests-collected
status, which a strict caller notices, whereas a partially deselected run exits
zero with a green summary. A yellow banner does name the deselected count, but
nothing escalates it.

Mitigating context, which is why this is medium rather than high: the continuous
integration static lane runs the same directories under a broader marker
expression, so the dropped integration contracts do execute somewhere. The defect
is a misleading local gate, not a hole in continuous integration. The recipe
comment describes itself as lightweight, so unit-only selection may be the
intent; if so the intent should be stated explicitly, because the recipe's name
and its position as a smoke-target dependency both suggest otherwise to a reader.

### stale-size-budget-pins-permit-silent-regrowth | medium | Module size ceilings documented as having no headroom now sit far above actual

The codebase size-budget gate carries per-module and per-callable line-limit
overrides, many documented in comments as pinned at exactly the present size with
no headroom. Peers have since split or shrunk those modules without lowering the
pins, so the ceilings now sit well above actual and the documented no-headroom
claim is false.

Aggregate positive slack across the module overrides is 8901 lines. The
coordinator independently confirmed the three worst production offenders: the
overview calendar module is pinned at 1667 against an actual 947, giving 720 lines
of invisible regrowth; the registry applicability module is pinned at 2156 against
1606, giving 550; the modelo verification-actions module is pinned at 1750 against
1379, giving 371. Callable pins show the same drift, the widest being a modelo
projection function pinned at 290 against an actual 146.

The gate is NOT vacuous — it still catches growth past the pin — so this is a
weakened ratchet rather than a dead one. The failing scenario: the calendar module
regrows by 700 lines, which is the kind of accretion the budget exists to force a
conversation about, and the gate stays green while its own comment claims the
module has no room to grow.

### held-serial-escalation-is-inert-by-design | low | An unwired mechanism was misreported as dead code; recording the distinction so it is not "fixed"

An earlier pass reported the controller-side held-serial refusal helpers as dead
code, on the evidence that a whole-tree symbol search finds them only in their own
defining module and that no conftest registers the hooks that would call them.
The evidence is accurate. The CONCLUSION is wrong.

Those helpers were landed deliberately inert earlier the same day, in a commit
whose message states that nothing outside the module references them, that
behaviour is unchanged until a conftest registers the hooks, and why landing the
unwired half is preferable to holding it in a working tree. The absent references
are the documented design, not rot.

This is recorded as a finding because the misclassification is the actionable
part. An auditor who reaches "five symbols, one file, no callers" and stops has
produced a remediation ticket to delete or wire a mechanism whose author
deliberately staged it, and in a shared worktree that ticket can be actioned by
someone who never reads the commit message. The discriminator is cheap: before
calling a symbol dead, read the commit that introduced it. The genuine open
question here is not whether the helpers are dead but whether to wire them, which
is a live decision with a real cost — wiring changes what every run reports — and
therefore belongs to an owner rather than to a cleanup sweep.

### harness-surface-judged-sound | low | The majority of the audited gate surface carries genuine positive controls

Recorded so the covered surface is distinguishable from the unexamined one. The
zero-tolerance detectors for mocks, monkeypatching, skip and xfail markers, and
tautological assertions all carry parametrized positive and negative controls plus
a discovery guard asserting the walk actually found modules. The enrollment and
rationale inventories share a real recursive-glob substrate whose emptiness would
fail loudly in a separate membership gate that asserts concrete known paths. The
import-hygiene gate uses set equality rather than a bare count ceiling, so a
count ceiling cannot mask an unnamed new violation. The ledger corpus fidelity
gate asserts a minimum built-row count of 500 and validates every row through the
real model, so it is not the open-the-files-and-extract-nothing shape. The
deselection-banner and acceptance-wall gates are proven by real pytest
subprocesses, and the acceptance-wall gate carries a genuine anti-tautology proof
that mutates a real assertion and asserts the subprocess fails. The duplication
audit reporter was previously hardened against exactly the false-green this audit
hunts and now asserts a positive duplication state as its control.

An honest negative result also belongs here: an exhaustive sweep of documented run
commands — gate docstrings, justfile recipes, continuous-integration lanes, and
rule prose — found NO documented command that collects zero tests and exits green.
Every documented invocation either carries an explicit marker expression or
targets modules whose markers match the default. The partial-run recipe above is
the only real selection defect found. That negative is only meaningful because
each command's collected count was measured rather than inferred.

## Recommendations

Fix the vacuous extension gate as ONE change that corrects the regex and disposes
of all four uncaught sites together. The regex correction must not land alone: on
its own it turns the gate red for the whole fleet, which is why this audit
reports it rather than fixing it. Add a positive-control assertion that the
pattern matches a representative literal, so the regex cannot silently rot again.
This is the general remedy for the shape — a scanner should assert it can see a
token it is known to contain, alongside the negative result it reports.

Raise the degraded-index problem with the search service rather than in this
repository. The needed behaviour is that a truncated or mid-rebuild index either
declines to answer or marks its results untrustworthy, so the existing refusal
rule can fire. Until then, treat semantic code-search results as unusable while
chunk counts are far below the tree size, and pair every sweep with an exhaustive
targeted search. Any conclusion of the form "semantic search found no existing
owner" recorded during the degraded window should be re-derived before it is
relied on.

Decide the packaging preflight recipe's intent and make it explicit. Either widen
its marker expression to match the lane that continuous integration runs, or state
in the recipe that it is unit-only by design and name the target that runs the
integration contracts. The current state, where the name and dependency position
imply full coverage while the invocation delivers two thirds of it, is the part
worth removing.

Re-baseline the size-budget pins to measured actuals, and prefer a generated
baseline over hand-maintained comments, since the comments are what went stale
rather than the mechanism.

Treat the wiring of the inert held-serial refusal, and of the worker-replacement
detector this audit landed, as a single owner decision rather than two cleanup
tasks. Both mechanisms are complete, tested, and referenced by nothing; both
change what a run REPORTS when wired, so both must land when a coordinator can
absorb the resulting signal rather than during a period when a large fleet has
in-flight suites. Wiring the detector additionally requires deciding where the
observed worker identifiers come from, which is a hook-registration question this
audit deliberately left open.
