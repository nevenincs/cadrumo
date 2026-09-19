---
tags:
  - '#audit'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:90925ea38cd5e55faf7cade6ef145cd06e8bdf3adecb723c674da7fc894b8d4a'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-adr]]"
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# `registry-revision-stamp-coverage` audit: `implementation review`

## Scope

Accepted stamp-and-reconfirm coverage decision, carrier inventory, write-side
coordinate propagation, strict persistence admission, shared-gate read paths,
proxy and compatibility deletion, and campaign verification evidence.

## Findings

### implementation-review | critical | persisted-calculation-decision-surfaces-bypassed-reconfirmation

The first formal review found that verification, filing, export, work review,
result summary, and reconciliation loaded a persisted `CalculationRevision`
and then interpreted its values through the current registry without first
re-confirming `registry_snapshot_ref`. The implementation now routes those
boundaries, the shared calculation get/list reads, amendment baselines,
declarations-workspace rows, and M303/M349 sibling reconciliation through the
single calculation-revision wrapper over `revision_carry_outcome`. Divergence
tests cover verify, file, export, work review, result summary, and declarations
projection behavior.

### implementation-review | high | persisted-observation-and-specialized-carrier-gates-were-incomplete

The first formal review found direct observation reads in pulled-filing,
prorrata, prior-payment, and live recapture advisories; Borrador show/list;
the prorrata special-transition writer; and IVA decision persistence bypassing
coordinate re-confirmation. Each now calls its carrier-specific wrapper over
the one shared `revision_carry_outcome` gate. Targeted divergence tests prove
that stale values are refused before projection or persistence.

### implementation-review | high | modelo-303-retained-an-unnormalized-compatibility-shape

The first formal review found an optional generic local-recurrence fallback, a
caller-controlled `normalize_m303_carry` switch, operator-manual M303 writes,
and wording that explicitly retained readable legacy envelopes. The switch and
fallback are deleted. Every supported M303 observation write crosses canonical
disposition-aware normalization, operator-manual M303 writes are refused, and
persisted M303 payload validation rejects a missing disposition or compensation
basis.

### implementation-review | medium | coverage-ratchet-proved-fields-but-not-consumer-gates

The original quality ratchet asserted only that carrier fields were required.
It now also inventories the application read/write boundaries and asserts that
each retains its carrier wrapper around the shared gate. Behavioral divergence
tests cover the operator-facing and advisory paths identified by review.

### implementation-review | medium | second-sweep-found-three-additional-bare-revision-consumers

The post-review catalogue sweep found revision selection, edit execution, and
the M303 annual-summary handoff reading persisted `CalculationRevision` rows
outside the first review's filing surfaces. Selectors and edit execution now use
the calculation-revision adapter over `revision_carry_outcome`; the calculations
resolver calls that same shared gate directly and translates refusal into its
own handoff error. The boundary ratchet names all three, and selector divergence
has a behavioral refusal test.

### implementation-review | medium | stale-fixtures-still-demonstrated-unsupported-m303-shapes

The canonical-only verification run found storage fixtures that still omitted
the official declaration-type header, asserted superseded wallet reason keys,
or used manual M303 persistence to measure a generic overwrite property. The
fixtures now supply canonical filed evidence, assert current typed reasons, and
measure generic overwrite behavior with Modelo 130. A direct validation test
proves an M303 payload without disposition and compensation basis cannot be
deserialized.

### implementation-review | critical | final-review-found-amendment-and-cross-period-gaps

The final independent review found amendment draft construction dropping the
already-resolved registry coordinate and the cross-period filing-revision
blocker interpreting revision state and casilla values before re-confirmation.
Amendment construction now stamps `registry_snapshot.snapshot_ref`; the
cross-period blocker calls `revision_carry_outcome` and returns
`REGISTRY_REVISION_DIVERGENCE` without interpreting the divergent payload.
Behavioral tests cover both the completed amendment flow and early divergence
refusal.

### implementation-review | high | final-review-found-specialized-read-and-admission-gaps

The final independent review found M145 early returns, persisted ModeloDraft
loaders, prior-filing approval fingerprints, and generic calculation-catalogue
admission outside re-confirmation or parent-coordinate validation. M145 now has
one helper over `revision_carry_outcome` used by list, read, transitions, and
existing-create. Review and CLI draft loaders use one application draft adapter;
prior-filing fingerprinting gates every observation; and calculation catalogue
load/save/co-commit admission requires exact equality with the persisted parent
WorkUnit coordinate.

### implementation-review | medium | final-review-expanded-the-boundary-ratchet

The quality ratchet now names amendment construction, cross-period revision
blocking, M145 early-return paths, application draft loaders, prior-filing
fingerprints, and calculation-catalogue parent-coordinate admission. Behavioral
coverage proves cross-period, M145, draft, observation, and repository divergence
refusal. Closure steps were reopened while these findings were resolved.

### implementation-review | medium | final-re-review-found-two-under-declared-m303-fixtures

The bounded re-review confirmed every production critical and high finding was
resolved, then found two carry-test fixtures still declaring official AEAT M303
evidence without the canonical declaration-type and result-disposition surface.
Both fixtures now carry submitted-file declaration headers and compatible
resultado casillas. The exact two-file suite passes all nine tests without any
production fallback or validation relaxation.

### implementation-review | low | final-bounded-review-approved

The final bounded review verified the two corrected M303 fixture surfaces and
returned APPROVED. No critical, high, medium, or unresolved campaign finding
remains.

## Recommendations

Keep the carrier inventory and boundary inventory as paired ratchets: adding a
persisted registry-derived field requires both a canonical coordinate and an
explicit write/read gate entry. Do not restore an M303 normalization flag,
optional recurrence fallback, or deserializable unnormalized payload shape.
