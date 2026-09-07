---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:37070bb1f15be1eb9beac4c53447355456012f1b761d24fe37bcbc8107f6e67f'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
  - "[[2026-09-02-object-name-declustering-adr]]"
  - "[[2026-09-07-object-name-declustering-receipt-scope-and-teardown-authority-audit]]"
---
# `object-name-declustering` audit: `receipt validity window measurement`

## Scope

Started with Step S30. This audit measures the validity window left by S27-S29 and separates
logical receipt validity from the operational risk of applying through a shared, changing
worktree. Measurements were taken on 2026-09-07 in `Europe/Madrid`; no rehearsal, apply, code,
test, plan, ADR, index, or existing-audit change was performed.

The dirty-worktree measurement used `git status --porcelain=v1` for collapsed status rows,
`git status --porcelain=v1 -uno` for tracked dirty paths, and
`git status --porcelain=v1 -uall` for file-level untracked entries. At 16:58:33 the results
were 445 collapsed rows, 383 tracked dirty paths, and 31,276 file-level entries; 396 of the
tracked-plus-untracked rows were Python paths under `src/` or `dev/` (356 tracked and 40
untracked). A repeat at 17:00:55 returned 453 collapsed rows, 388 tracked paths, 31,285
file-level entries, and 400 Python rows (360 tracked and 40 untracked). The change during this
short interval is itself evidence that the shared worktree is not a stable measurement surface.

The inventory-affecting commit measurement counted one commit when its committed path set
contained at least one `*.py` path below `src/` or `dev/`, using `git log --since=<timestamp>
--pretty=format:<hash-and-timestamp> --date=iso-strict -- src/**/*.py dev/**/*.py`. At 16:58:33
the trailing windows contained 4 commits in 1 hour, 9 in 3 hours, 51 in 6 hours, 134 in
12 hours, and 297 in 24 hours. Those are respectively 4.00, 3.00, 8.50, 11.17, and 12.38
inventory-affecting commits per hour. A rolling-hour scan found a peak of 25 commits per
hour, beginning at approximately 05:48:53. A recheck at 17:01:50 observed 5, 10, 52, 135,
and 299 commits in the same windows; the small movement is consistent with commits landing
while the measurement was running. The rate is therefore reported as an observed range, not
as a fixed repository constant.

Cycle wall-clock evidence is taken from the authoritative receipt-scope and teardown audit,
not extrapolated from a new run. Its green receipt was emitted at 14:25:04, then a freshness
check about 40 seconds later refused the receipt after the inventory digest moved. That audit
records 14 inventory-affecting commits in 90 minutes, 48 commits between one receipt cut and
its apply, an approximately 65-minute rehearse-plus-apply cycle, and one apply that ran for
34 minutes before refusing at verification. It also records 21 refusals across 16 attempts
from 09:26 to 14:25, none attributable to the rename operations. The sampled pilot surface,
`src/cadrumo/application/filing/export_producer.py`, was clean at 17:03:31; its latest two
commits were at 11:57:03 and 11:57:12, so that path had been quiet for about 5 hours and
6 minutes at the measurement.

## Findings

### scoped-validity-window | medium | S27-S29 leave logical validity scoped to selected evidence rather than a global timer

S27 records the current inventory digest scanned from the verified copy while binding authored
intent through the exact manifest digest. S28 re-scans current inventory at replay and checks
fresh selected identity, graph, component, guarded-byte, output, and gate evidence without
requiring the receipt's rehearsal-time global inventory digest to equal the fresh global
inventory. S29 supplies the detector teeth: two real unrelated Python declarations move the
inventory digest after receipt creation, replay is driven with the fresh inventory and
component, the unrelated bytes survive, and a temporary reintroduction of literal
receipt/current equality fails the detector. The surviving logical validity window therefore
has no honest numeric TTL in the available evidence. It remains valid across unrelated
inventory churn and ends when a selected finding, component/graph edge, guarded byte,
target-occupancy condition, manifest/component identity, changed-path contract, regenerated
output, gate result, or other receipt-bound precondition changes. The current pilot path's
5-hour quiet interval is a positive observation, not a guarantee for every component.

### shared-worktree-operational-window | high | The observed cycle cannot be relied on under concurrent shared-worktree development

The historical cycle takes about 65 minutes, while the current/recent Python-path commit rate
is 4-5 commits per trailing hour, 8.5-8.7 per six hours, 11.17-11.25 per twelve hours, and
12.38-12.46 per 24 hours, with a measured peak of 25 per hour. The worktree simultaneously
contains 383-388 tracked dirty paths and 31,276-31,285 file-level status entries, including
396-400 Python rows under the inventory roots. This does not prove that every commit or dirty
path touches the reviewed component, but it does prove that a shared-worktree campaign has a
substantial opportunity for selected-byte, graph, generated-output, transaction-root, or gate
collisions during a 65-minute cycle. The 14-commit/90-minute and 48-commit cut-to-apply
observations in the authoritative refusal corpus corroborate that this is an observed
operational failure mode, not a hypothetical timeout.

The plain operational conclusion is that this campaign requires an exclusive worktree or an
equivalent explicitly quiesced development lane for a reliable rehearse-and-apply completion.
The logical receipt contract no longer requires exclusivity merely because an unrelated Python
declaration changes, but the shared-worktree operational conditions do. A green rehearsal
cannot be treated as permission to start a long apply while peers continue changing the same
worktree.

## Recommendations

Use an exclusive worktree, or record an equivalent quiescence boundary, before beginning any
rehearse-and-apply cycle whose expected wall clock approaches the observed 65 minutes. Re-run
rehearsal immediately before apply and preserve the selected component's bytes, graph surfaces,
generator inputs, transaction-root state, and gate inputs throughout that interval.

Keep the S27-S29 distinction in future validity checks: do not turn the observed commit rate
into a logical global receipt expiry, and do not restore literal receipt/current global
inventory equality without first resolving the S28 interpretation conflict recorded by the
receipt-freshness audit. Treat the current dirty-file and commit-rate numbers as dated
operational evidence, not as a timeless policy threshold.
