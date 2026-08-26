---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:4c2779579544ba5c1a298c3e8d4eef130f3f19470abb3f80409d9a51bdbb627f'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
---

# `tui-architecture` audit: `S24 aggregate deadline and cancellation safety review`

## Scope

Independent formal review of exactly `W02.P05.S24` against the live open plan
row, decisions D3 and D5 of the accepted TUI architecture ADR, the linked
research, the S24 execution record, the current diff from `HEAD`, and the whole
changed production and test surface in `cadrumo.application.operations`. The
review covered aggregate execution deadlines, distinct durable cancellation
request and acknowledgement, irreversible-section behavior, cleanup-deadline
escalation, terminal gating, restart and persisted-schema implications, and the
declared S24 scope boundary.

The semantic RAG service was offline and the user explicitly waived RAG for
this review. Grounding therefore used the named canonical documents plus direct
source, diff, constructor, persistence, and test inspection. Extensive unrelated
shared-worktree changes were excluded from the review and validation boundary.

## Findings

### false-timeout-terminal | high | TIMED_OUT can become durable while executor work is still running

`OperationSupervisor.settle` applies executor-completion gating only when the
receipt condition is `CANCELLED`. A `TIMED_OUT` receipt takes the unrestricted
path even though D5 explicitly forbids `TIMED_OUT` while a non-cooperative task
may still run. A real encrypted-operand, filesystem-journal, and owner-lease
probe started the concrete waiting executor, called `settle` with `TIMED_OUT`
before releasing it, and observed `terminal/timed_out` durably while the start
task remained incomplete. After release, `start` returned its stale `RUNNING`
context snapshot while `inspect` remained `TERMINAL`. Cleanup had no registered
resource to block this path. S24 therefore permits contradictory authoritative
observations and a false terminal claim; the later exhaustive S95 proof cannot
defer the missing production guard.

### same-version-safety-defaults | high | New deadline and cancellation facts silently widen persisted schema v2

`OperationPersistedSnapshot` adds four nullable, defaulted safety fields while
retaining `schema_version: Literal[2]`. Direct validation of a serialized v2
snapshot with all four fields absent succeeds and supplies `None` for each. The
operation journal is classified `DURABLE`, and the active pre-release
compatibility rule requires a persisted shape change to advance the current
version and strictly refuse the old shape rather than loosen the read model.
The same-version widening also makes a pre-S24 running v2 record
indistinguishable from a current deadline-absent record, so restart observation
cannot prove whether missing execution, cleanup, request, and acknowledgement
facts are legitimate policy or missing safety state. S24 must establish a
strict current v3 shape and refuse pre-current operation-journal snapshots now;
the repository's `PRE_RELEASE` regime does not authorize a v2-to-v3 upgrader or
fabricated old-version fixture.

The remaining reviewed behavior is sound within its boundary: aggregate expiry
durably requests cancellation; request and acknowledgement occupy separate
revisions; requests remain recordable inside nested irreversible sections while
acknowledgement is refused until exit; cleanup-deadline expiry escalates to
`SETTLING` without fabricating a terminal state; and `CANCELLED` requires a
durable acknowledgement, completed local executor task, and completed owned
cleanup. Restart conservatively lacks local executor-completion proof, so a
post-crash cancellation cannot falsely settle `CANCELLED` through that path.

Focused validation passed 16 executor-and-journal unit tests and 25 real
supervisor integration tests. Scoped Ruff check and format check passed;
BasedPyright reported zero errors, warnings, or notes; and scoped diff hygiene
passed. `vaultspec-core vault check all` exited zero with 1,322 shared-corpus
warnings. The audit's annotations, modified stamp, links, placeholders, and
structure are clean; the S24 execution record retains one unrelated markdown
hygiene warning and was not edited under this review's ownership boundary.

## Recommendations

1. Gate `TIMED_OUT` settlement on authoritative proof that executor work and
   owned cleanup have ended, and reject any terminal receipt that would race an
   active local executor into a contradictory durable terminal snapshot.
   Preserve conservative `SETTLING` behavior when that proof is unavailable.
2. Bump `OperationPersistedSnapshot` to strict schema v3 and make the production
   journal reader refuse v1 and v2 records under the current `PRE_RELEASE`
   compatibility regime. Add real-boundary tests proving missing v3 safety
   fields and pre-current versions are refused, while fully populated v3 facts
   survive strict persistence round trips.
3. Re-run the 16 focused unit tests, 25 supervisor integration tests, scoped
   Ruff check and format check, BasedPyright, and VaultSpec validation after
   remediation. Current pre-remediation validation is green but does not cover
   either reproduced safety failure.

## Final re-review

PASS. Both original HIGH findings are resolved, and the final review found no
remaining correctness, authority, safety, restart, compatibility, scope, or
test-quality findings.

`false-timeout-terminal` is resolved. Every stop-like terminal condition now
requires completed local executor work whenever this supervisor tracks the
task. A real encrypted-operand, filesystem-journal, and owner-lease test proves
that `TIMED_OUT` is refused while the executor remains live, preserves the
durable `RUNNING` snapshot and lease, and succeeds only after executor
completion. The re-review additionally found and reproduced the same unsafe
shape for `INTERRUPTED`; the final guard now refuses `INTERRUPTED` when a known
local task is live while retaining the absent-task exception required by fresh
owner-loss reconciliation. The new byte-preserving refusal test and the
existing fresh-supervisor recovery test prove both sides of that authority
boundary.

`same-version-safety-defaults` is resolved. `OperationPersistedSnapshot` now
uses `Literal[3]`, and all four nullable deadline and cancellation facts are
required-present fields. Production creation and every direct adapter fixture
supply them explicitly. The filesystem reader parses only the current strict
record: the v1-to-v2 rewrite and its JSON/cast support are deleted, and targeted
search found no alternative operation-journal upgrader or compatibility read
path. Model tests refuse raw v1, raw v2, and each missing v3 safety field. The
real filesystem test refuses v1 and v2 bytes without rewriting them, while the
current v3 round trips exercise the adapter boundary.

Final independent validation passed 16 executor-and-journal unit tests and 32
integration tests across the supervisor and the journal, lease, and persistence
adapter collateral. Ruff check passed, all 11 reviewed files were already
formatted, BasedPyright reported zero errors, warnings, or notes, and scoped
diff hygiene passed. The final disposition is PASS; the plan row remains open
for its authorized executor.
