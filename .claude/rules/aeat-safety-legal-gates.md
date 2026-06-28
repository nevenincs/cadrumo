---
name: aeat-safety-legal-gates
trigger: always_on
---

# AEAT safety and legal gates

Never perform live AEAT submission. Build, validate, verify, export, and require human filing outside the app. Treat live-write paths as prohibited unless a future accepted ADR explicitly replaces this rule.

Guard every external AEAT write surface behind explicit live-test controls. Use `AEAT_LIVE_TESTS_ENABLED` for live-test opt-in. Keep dry-run behavior as the default.

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources, or live oracle replay. Do not invent legal behavior. Do not treat user preference as authority for regulated calculations.

Reject tests or code paths that can file, mutate, notify, or submit remotely without an explicit safety gate and auditable provenance.
