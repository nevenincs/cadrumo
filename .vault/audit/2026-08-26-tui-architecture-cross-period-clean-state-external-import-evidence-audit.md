---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:8a9fae7bb37cea882d71cc2b407d17932a9f6720f0f13f63d561b3e13758f890'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `cross period clean state suite red from the external import evidence refusal`

## Scope

Attribution pass over a red test slice, run to establish whether today's
campaign landings regressed anything. Sequential (`-n 0`), because the parallel
run died with six `node down` workers on this worktree's backing share and that
signal is not diagnostic. Read-only; no production code changed.

Measured: `src/cadrumo/domain/portals` plus `src/cadrumo/application/calculations`,
33 failed, 765 passed, 4 errors, 21m10s.

## Findings

### The failures are not this campaign's, and not uncommitted peer state

None of the failing test files carry working-tree modifications. The failures
concentrate in `test_cross_period_clean_state.py`,
`test_cross_period_clean_state_provenance.py` and
`test_cross_period_external_evidence.py`.

One failure traced to its raise site:
`src/cadrumo/application/modelo/external_import_actions.py:486` raising
`ExternalModeloImportError` with
`application.modelo.errors.external_import_m303_filing_evidence_required`.

That refusal was introduced by commit `5662e92b44` (2026-08-26), which promoted
the external import actions module alongside the modelo 184 era-revision rework.
The raising module itself is committed and clean in the working tree, so this is
a committed change from another campaign's work landed today, not in-flight
state that will resolve itself when a peer commits.

### The refusal is plausibly correct, which is why this must not be "fixed" quickly

Requiring filing evidence before an external modelo import is the shape
`no-silent-under-declaration` asks for, not a defect on its face. The likely
correct remediation is that the cross-period fixtures must now supply the
evidence the refusal demands.

The dangerous remediation is the fast one: relaxing or bypassing the refusal to
turn 33 tests green. That would weaken a filing-evidence gate to satisfy
fixtures, which is the inverse of the rule the refusal appears to serve. Whoever
owns `5662e92b44` should adjudicate whether the fixtures or the refusal are
wrong; this pass deliberately does not rule on it.

### Two runs were wasted before this measurement, for avoidable reasons

Recorded because the causes are already written down as rules and were still
tripped. The first run piped pytest through `tail` before the log write, so
truncation happened upstream of the file and the FAILED summary was lost, and
its reported exit status was the pipeline's last command rather than pytest's.
The second was captured correctly but under-budgeted and was killed at 82% by
its own timeout, again before any summary existed. Both cost a full cycle.

## Recommendations

- Route this to the owner of `5662e92b44` rather than to whoever next sees the
  red slice; the fixture-versus-refusal judgement belongs with that change.
- Do not relax the evidence refusal to restore green without that adjudication.
- Re-measure sequentially. A parallel run on this share reports `node down`
  worker deaths that are indistinguishable from real failures at a glance.
- Treat this slice as red for attribution purposes until it is resolved: it
  cannot currently confirm or deny a regression from any other campaign.
