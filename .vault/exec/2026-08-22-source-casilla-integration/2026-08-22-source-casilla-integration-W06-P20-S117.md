---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:648343ceae6299725fb9f1b1ba3b1be25e9b76f35b482b5478ff798b0942ab4e'
step_id: 'S117'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# prove the final census has no expired deferral, unexplained disappearance, or unsupported connected claim

## Scope

- `dev/source_connectivity/tests/test_campaign_close.py`

## Description

- Compose the canonical live census, discovery, locator, registry-destination, governance, and connected-proof authorities in one campaign-close test.
- Require every discovered capability to have one assignment and every assigned identity to remain discoverable.
- Evaluate expiry against the actual current date so the gate begins refusing when reviewed deferrals lapse.
- Require exact equality between connected census rows and the independently maintained executable-proof fixtures.
- Remove review-rejected fixed-date and exact-count shortcuts before accepting the gate.

## Outcome

The dedicated close test passes on the current tree. It proves that every live capability is assigned exactly once, no assigned capability has disappeared, no census evidence is expired today, and no connected row exists without an independent executable fixture and canonical live proof authority. The current census contains no connected claims, so the registry does not manufacture a source connection.

Independent review initially rejected the fixed 2026-08-25 clock and the hard-coded 478/15 counts. The final implementation uses the canonical current-date boundary and property-based assignment equality. Re-review passed with no critical, high, or medium finding.

The focused campaign-close test passed, the complete source-connectivity suite passed with 64 tests, Ruff passed over the closure and its canonical authorities, and the feature-scoped Vaultspec gate passed after rebuilding the feature index.

## Notes

This step adds a closure gate; it does not promote any candidate, extend any deferral, or assert filing readiness. The dated deferrals currently expire on 2026-12-31, after which this test will deliberately refuse until they are re-adjudicated.

The test and initial tracking scaffolds were captured by concurrent mixed commit `06e55cfadd`. This record preserves that provenance rather than attributing the shared commit solely to S117; the final reviewed tracking corrections are committed separately by exact path.
