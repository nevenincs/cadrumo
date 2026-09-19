---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:dc498bde355cb98b0b33b695190bbc6b0832b43ae254c3b9401286d5d77d5eef'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# `m303-carry-reconciliation` audit: `M303 carry reconciliation S08 code review`

## Scope

Final re-review (2026-08-09): APPROVED. The replay discriminator now requires both a local/filed-history selected authority and an observation-envelope recurrence source of the corresponding allowed kind. The encrypted-store normal-resolution regression proves that an explicit taxpayer override with an envelope-like evidence locator remains the persisted decision, while the four stale/conflicting local-envelope replay paths still fail closed.

## Findings

### persisted-zero-replay | high | A cached local-recurrence zero bypasses later envelope refusal

`resolve_iva_compensation_decision_for_calculation` replays an existing persisted wallet decision, but `_refresh_local_iva_compensation_decision_if_evidence_changed` refreshes only `first_period_zero` and `missing` decisions. A validated refund envelope produces the non-blocking `local_recurrence_zero` decision, so a later revision-stamp mismatch or replacement with a legacy/conflicting envelope is not re-read before the decision is accepted for calculation. That makes an envelope which now fails the carry boundary continue to establish casilla 110 through the persisted decision. The direct lazy-reader controls cover the initial invalid-envelope read but not this persisted-decision replay.

### locator-prefix-overmatches-override | medium | A taxpayer override can be mistaken for an observation-envelope recurrence

`_decision_uses_observation_envelope_recurrence` tests only whether any authority `source_locator` begins with `observation-envelope:`. `IvaCompensationOverride.evidence_locator` accepts any non-empty string and becomes the `taxpayer_override` authority source locator, so an override using that prefix is refreshed through the envelope-only lazy path and may be overwritten with a missing decision. The test proves the intended local-envelope cases, but does not prove that a prefixed override remains settled.

## Recommendations

- For `persisted-zero-replay`, revalidate or refresh every decision whose authority includes local envelope recurrence before calculation replay, and add an end-to-end regression that persists a valid refund zero, makes its envelope stale or conflicting, and proves the next calculation blocks.
- For `locator-prefix-overmatches-override`, require the local recurrence authority kind as well as the canonical locator prefix, and add a replay regression for a `taxpayer_override` whose evidence locator happens to start with that prefix.
