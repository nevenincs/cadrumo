# AEAT safety and legal gates

**Never perform live AEAT submission.** Build, validate, verify, export, and
require human filing outside the app. Live-write paths are prohibited unless a
future accepted ADR explicitly replaces this rule.

Guard every external AEAT write surface behind explicit live-test controls. Use
`CADRUMO_LIVE_TESTS_ENABLED` for live-test opt-in, and keep dry-run behavior as
the default.

Any read-only AEAT probe is pinned to the consulta view and **fails closed** on a
filing-tool or procedure-launcher landing.

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources,
or live oracle replay. Do not invent legal behavior, and do not treat user
preference as authority for regulated calculations.

Reject tests or code paths that can file, mutate, notify, or submit remotely
without an explicit safety gate and auditable provenance.

Companion: `sensitive-financial-data-secure-storage-only`.
