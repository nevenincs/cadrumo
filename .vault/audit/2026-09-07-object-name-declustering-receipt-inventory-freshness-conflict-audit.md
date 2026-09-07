---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:64acf152e0209645539dd43d63e6a891703fef1cd2424d0cf3860690177aac52'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
  - "[[2026-09-02-object-name-declustering-adr]]"
  - "[[2026-09-02-object-name-declustering-s23-concurrency-staleness-review-audit]]"
  - "[[2026-09-02-object-name-declustering-s24-scoped-receipt-review-audit]]"
  - "[[2026-09-07-object-name-declustering-receipt-scope-and-teardown-authority-audit]]"
---

# `object-name-declustering` audit: `receipt inventory freshness conflict`

## Scope

Reconciled the accepted ADR, W04.P10 S27-S30, the S23/S24 final-closure audits, the
2026-09-07 receipt-scope audit, `dev/quality/object_name_replay.py`, and the real-Python
post-receipt churn test. Semantic discovery located the S23/S24 audits, the plan, the
accepted ADR, and the replay epicenter; targeted `rg` confirmation pinned the lines below.

## Findings

### receipt-inventory-freshness-conflict | high | Forked fact: literal receipt/current equality conflicts with scoped churn behavior

Classification: **forked fact (judgment)** across the plan, closure audits, current audit
evidence, and live behavior, with an internal plan **contradiction**; this is not status
drift and is not safe to rewrite automatically. The accepted ADR is `accepted`
(`.vault/adr/2026-09-02-object-name-declustering-adr.md:13`) and requires finding identity
to survive unrelated movement while execution refuses concurrent byte changes
(`...-adr.md:22`), with receipt evidence and byte/inventory preconditions kept distinct
(`...-adr.md:54-58`).

Decision inventory: W04.P10.S27 is checked, while S28, S29, and S30 remain open in the plan
(`.vault/plan/2026-09-02-object-name-declustering-plan.md:115-120`). S28 says replay must
compare receipt inventory with a freshly scanned current inventory and the exact manifest
digest without binding current inventory to the authored value (`...-plan.md:118`). Read as
global equality, that requires `receipt.inventory_digest == fresh_current_digest`. S29
requires a real Python declaration to change that digest and a replay case that fails if
that global equality is reintroduced (`...-plan.md:119`). Those requirements cannot both
hold: the S29 case has receipt digest D0 and fresh current digest D1 after unrelated churn.

The S23 and S24 final-closure sections claim the fresh-rescan churn detector is resolved
(`.vault/audit/2026-09-02-object-name-declustering-s23-concurrency-staleness-review-audit.md:119-126`,
`.vault/audit/2026-09-02-object-name-declustering-s24-scoped-receipt-review-audit.md:101-109`),
but the 2026-09-07 receipt-scope audit records repeated freshness refusals and recommends
reopening S23 (`.vault/audit/2026-09-07-object-name-declustering-receipt-scope-and-teardown-authority-audit.md:34-43`,
`:129-134`). That is the same fact forked across lifecycle records.

Live code does not settle the wording: `replay_object_name_component` checks receipt,
manifest, component, and guarded bytes, then calls rehearsal with caller-supplied inventory
(`dev/quality/object_name_replay.py:420-450`); it has no replay-time `scan(...)` or
`receipt.inventory_digest` comparison. Rehearsal compares copied inventory to supplied
current inventory and records the copied digest (`dev/quality/object_name_rehearsal.py:696-701`,
`:794`), while the churn test creates `concurrent_helper.py`, proves the digest changes,
rescans, rebuilds the component, and supplies the fresh values (`dev/quality/tests/test_object_name_replay.py:190-205`).
The test would fail under restored global receipt/current equality, but the implementation
does not itself establish the S28 fresh-current comparison.

No unsafe action was applied. Only this scaffolded audit body was authored; no code, test,
ADR, plan, index, frontmatter, or decision status was changed, and no interpretation was
selected as the governing decision.

## Recommendations

Operator judgment is required before any implementation or status edit: decide whether
S28 means (a) strict receipt/current inventory equality, which would intentionally reject
the S29 unrelated-churn case and therefore require an explicit amendment of the accepted
behavior and its test, or (b) scoped fresh-current validation, in which the receipt retains
rehearsal-time evidence while replay re-scans and revalidates only the selected identity,
graph, and guarded bytes without global equality. Do not choose between these readings in
the curation record.

After that decision, reconcile S28-S30, the S23/S24 final-closure claims, and the
2026-09-07 receipt-scope finding to one authoritative status; then align
`dev/quality/object_name_replay.py` and its real-Python churn test and rerun the focused
quality gates. S30's validity-window measurement remains separately open until its operator
judgment is recorded.
