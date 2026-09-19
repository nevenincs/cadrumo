---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:76a48da93736a0a643144f10648164d3f0568ff7e2079f72366289c891fcdf64'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-27-secure-storage-performance-hardening-closure-honesty-review-audit]]"
---

# `secure-storage-performance-hardening` audit: eight-axis structural sweep

Scoped to the surface this campaign touched -- the CLI command graph, the
profile-summary boundary, and the package roots on their resolution paths.
Each axis states what was checked and how, so a reader can tell a real sweep
from an assertion.

## Axis 1 - calculation-engine grounding

Not applicable. The campaign changed import timing and one projection; it
altered no formula, binding, casilla or legal reference. Confirmed by diff:
no file under `_data/registry/` or `domain/calculations/registry/` carries a
semantic change from this campaign.

## Axis 2 - persistence-boundary identity

**One finding, actioned.** Sweeping for consumers of the profile projection
found `entrypoints/tui/devtools/surfaces.py` calling
`CommittedProfileRepository().load()` to obtain a LABEL, inside a context that
already holds an unlocked session -- a per-profile custody lock, password
material, transaction journal and label-head verification, for a string. Same
defect the sandbox notice carried. Fixed to read the summary projection.

Remaining users of the authenticated aggregate are `user_profile/lifecycle.py`
(which legitimately needs it) and the aggregate's own tests.

## Axis 3 - cross-domain handoffs

The listing path crosses entrypoint -> application -> adapter once, through the
custody PORT, and the port translates persistence failures at the boundary
rather than leaking adapter error types upward. That translation was proven by
a health-report assertion that previously pinned the leaked adapter type.

## Axis 4 - export/import fidelity

Not applicable. No export or import format changed.

## Axis 5 - workflow and CLI surface

**Three findings, all actioned.** `app ledger ratios set`, `app ledger evidence
batch` and `app modelo reconcile import` could not be CONSTRUCTED -- each
raised `ValueError: wrong parameter order` and was unreachable through the real
CLI. Fixed structurally at the runtime so no spec declaration can produce an
illegal signature, and verified by rendering help for all three through the
`aeat` executable.

## Axis 6 - selector/binding drift

No binding selectors changed. The `BindingId` alias is implicated only by
placement -- it lives in `registry.ids` and pulls the registry package into
every consumer of `domain.calculations` value objects -- and that is carried
as the S40 residue.

## Axis 7 - semantic functionality-cluster overlap

**One finding, actioned.** `profile_bucket_scan` was a SECOND definition of
"which profiles exist": the same UUID-and-label projection, computed through
the authenticated aggregate. Two definitions of one fact that could disagree.
Consolidated onto `summary_inventory`, with a refusing variant
(`require_summaries`) for callers that cannot render an explanation.

Verified after: `ProfileSummary` and `ProfileSummaryInventory` have exactly one
definition each; `ProfileSummaryOutcome` one, in `core`.

## Axis 8 - runtime import-graph coupling

The executed graph was measured directly rather than inferred, in fresh
processes across all 365 nodes.

- `config/profile/list` resolves loading **zero** capability families.
- **351 of 365** nodes resolve loading zero families; 14 are enumerated with
  causes and stale-entry cases.
- The static half (`.importlinter`) had been aborting before evaluating ANY
  contract; restored, and now reports 4 kept / 6 broken over 5481 files.

The six broken contracts -- llm-to-persistence, four TUI contracts, and the
layered architecture contract -- are pre-existing and owned by other campaigns.
They were invisible while the suite aborted.

## Disposition

Five findings across the eight axes. All five are actioned in code:
three unreachable commands, one duplicate projection, one aggregate-for-a-label
site. Nothing is deferred without a named owner or a stale-detecting gate.
