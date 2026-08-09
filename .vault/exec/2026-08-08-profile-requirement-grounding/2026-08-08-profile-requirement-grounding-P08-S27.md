---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0266729b7f197bcf1766f189aa210c4f6a615c848039a0d763e686ece9fc7d94'
step_id: 'S27'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Reconcile the three CLI surfaces that still read the separate ProfileKey-derived profile_health.missing_required mechanism and emit raw dotted paths (config profile status, wizard status, overview diagnostics): either wire them through the same enriched ProfilePreflightRequirement path this campaign built, or record a grounded reason each must stay on the separate mechanism

## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_rendering.py`
- `src/cadrumo/application/wizard/_status.py`
- `src/cadrumo/application/diagnostics.py`

## Description

- Traced all three surfaces to their shared source: `application/workflow/_profile_health.py:assess_active_profile_health` (consumed by `config profile status` via `_status_rendering.py` and by `diagnostics.py`) and `application/wizard/_status.py`'s own direct call both compute `validate_profile_values(values)` - the `PROFILE_KEYS`-driven validator, not `ProfileValidationService`/schema-driven, and not `ProfilePreflightService`.
- Confirmed via P08.S24's measured inventory why this is not a narrow rendering fix: `PROFILE_KEYS` declares 1 required field (`identity.tax_id`); the schema declares 15. Swapping any of these three surfaces onto the schema-driven `missing_required_field_paths`/`build_profile_preflight_requirement` path this campaign built would not just relabel the same verdict with better metadata - it would flip the READINESS VERDICT ITSELF for every real profile that satisfies `PROFILE_KEYS`' single required field but not all 15 schema-required fields (which, per S24, includes ordinary profiles missing e.g. `activities.description` or `iva.regime`, both schema-required but wizard-optional).
- Confirmed the wizard's own completion concept is deliberately narrower than the schema's, not merely under-flagged: `wizard/_status.py`'s `profile_ready = identity_ready and enrolment_ready` is the wizard flow's own "have you answered what I asked" gate, and S24 found 12 schema-required fields (`attribution_entity_socios.*`, `attribution_received.*`, `usage_ratios.*`) that the wizard flow never asks about at all - there is no wizard question whose completion could ever satisfy them. A profile that has genuinely finished the wizard cannot, by construction, also satisfy the schema's stricter required set for those twelve fields.
- Confirmed the governing ADR already scoped this reconciliation OUT of this plan before P08 existed: the plan's own Description states "Reconciling the separate ProfileKey and _DEADLINE_RELEVANT_FIELDS mechanisms against this canonical schema is explicitly out of scope for this plan and is deferred to a follow-up." P08's broader mandate re-opened INVESTIGATING it (done, above), but a unilateral behaviour-flipping swap across three operator-facing surfaces, based on an audit finding rather than a deliberate product decision with its own review, would contradict that standing deferral rather than fulfil it.

## Outcome

**Recorded, not actioned**, per this Step's own second sanctioned disposition. No code changed. The concrete blast radius (1 vs 15 required fields; a wizard-completion concept that is structurally narrower than schema-completeness by design, not merely stale) is now measured and on record for whoever makes the reconciliation decision, rather than left as an unquantified "drift" claim.

## Verification

No test-affecting change. The investigation itself is the deliverable; every claim above is traced to a specific file:line read against the current tree (`_profile_health.py:279-281`, `wizard/_status.py:86-97`, `diagnostics.py:400-426`) rather than inferred.

## Notes

This Step's disposition mirrors P08.S26's deferred categories (the ProfileKey requirement-flag disagreements, the wizard-invisible required fields) for the same underlying reason: this campaign's mandate is to MEASURE and EXPOSE drift, not to unilaterally resolve every drift finding by flipping user-visible behaviour without a dedicated decision. A reconciliation that silently changed what "profile ready" means for potentially many real operators, shipped inside a campaign whose own governing ADR explicitly deferred exactly this reconciliation, would be a worse outcome than leaving it honestly recorded and open.
