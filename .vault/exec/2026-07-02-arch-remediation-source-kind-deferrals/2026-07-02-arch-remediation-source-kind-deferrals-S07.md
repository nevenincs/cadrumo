---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9edc6e4722134f6cbf15eb3a84364a58e62ff9f8fcc1c926f28e099c592d5a8b'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Migrate the refund_operation deferral to a structured annotation citing this deferrals ADR with no promotion date and the M360 next-hardening-campaign review trigger

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Migrate the `refund_operation` (M360) deferral to a structured target citing the deferrals ADR, M360 next-hardening review trigger.
- Also governed the `donativo_donor` (M182) kind, which landed in the deferred set after the plan was authored, under the same informativa pattern (deferrals ADR, M182 review trigger) so the S08 gate holds for all seven current members.

## Outcome

M360 refund is governed; the post-plan M182 donativo kind is governed too — the deferral set is now complete under the annotation contract.

## Notes

The plan predated the M182 donativo source kind; annotating it here is the self-auditing intent (a deferred kind without owner+trigger would fail S08).
