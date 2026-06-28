---
tags:
  - '#adr'
  - '#live-submit-permanently-forbidden'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-live-submit-permanently-forbidden-research]]'
  - '[[2026-04-27-security-storage-audit-audit]]'
  - '[[2026-04-18-live-submit-cli-excision-adr]]'
  - '[[2026-04-18-auth-provider-abstraction-adr]]'
  - '[[2026-04-25-workflow-live-flag-excision-adr]]'
---

# `live-submit-permanently-forbidden` adr: `live AEAT submission is permanently forbidden` | (**status:** `accepted`)

## Problem Statement

Older project surfaces still described live AEAT submission as a future or
hidden capability even though the user mandate is stronger: the product must
never submit to AEAT on Kent's behalf. The repository therefore needed a
single policy ADR that supersedes the older "four-factor gate" and
"reintroduce in 1.0.0" framing.

## Considerations

- Issue `#116` remains the controlling safety charter.
- Issue `#197` remains the controlling product charter: `produce -> verify ->
  export`.
- The 2026-04-27 security audit shows that keeping live-submit execution
  reachable would compound already-serious storage and trace-retention risks.
- The repository still needs dry-run, preflight, export, verification, and
  read-path authentication.
- Historical ADRs from 2026-04-18 and 2026-04-25 remain important lineage, but
  they no longer describe the accepted end state.

## Constraints

- No live AEAT sandbox exists; every successful write is legally binding.
- The implementation must preserve existing dry-run and export behavior.
- The implementation must remove product-facing live-submit env vars and CLI
  surfaces without weakening live-read support.
- The branch must leave a durable regression test that catches future
  reintroduction attempts.

## Implementation

- `SubmissionEngine` is now dry-run-only. `dry_run=False` raises
  `LiveSubmitForbiddenError` immediately.
- The historical live-transport constructor keyword is no longer part of the
  supported constructor contract. Legacy callers that still pass it receive
  `LiveSubmitForbiddenError`.
- `AeatAccessGate.require_live_write()` is reduced to a permanent-deny shim.
- `Modelo130Submitter.submit()` now refuses immediately instead of executing any
  browser write action.
- `AEAT_LIVE_SUBMIT_ENABLED` and `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN` are removed
  from `Settings` and `env/.env.example`.
- CLI and workflow docstrings are rewritten to state present-tense permanent
  prohibition.
- `ROADMAP.md` and `docs/coverage/kent-capabilities.md` are rewritten so live
  submit is no longer framed as a 1.0.0 capability.
- A dedicated regression module asserts the permanent prohibition through
  constructor refusal, engine source introspection, gate refusal, settings
  introspection, and CLI command absence.
- The missing mandate source file is created under `.vaultspec/rules/rules/`
  and provider copies are regenerated.

## Rationale

- Permanent prohibition matches the user's repeated product directive, whereas
  the older gate architecture preserved an unwanted future product direction.
- Removing executable write paths is safer than keeping dormant write code
  behind increasingly complex gates.
- A single canonical refusal error is easier to reason about than the older
  chain of env-gate, pytest-gate, confirmation, transport, and rejection
  variants.
- Preserving live-read gating while permanently forbidding live writes keeps the
  repository aligned with real Kent needs: inspect, verify, export, and upload
  manually.
- Historical ADRs remain useful lineage, but they must be explicitly marked as
  superseded where they imply reintroduction.

## Consequences

- Live AEAT submission is permanently out of scope for the product.
- Kent-facing docs now describe only `produce -> verify -> export` plus manual
  portal upload.
- The old four-factor live-submit gate becomes historical context only.
- The security-audit findings about uncontrolled live-submit storage are
  mitigated by removing every reachable write path.
- Auth-provider work remains valid for read-only AEAT operations such as sede
  navigation, notifications, and past-filing import; it is not a stepping stone
  toward future live submission.

### Security-audit findings consumed by this ADR

- Uncontrolled `.aeat/live-submit-audit.log` persistence is addressed by making
  the log unreachable from product execution.
- `AEAT_LIVE_SUBMIT_ENABLED` documentation drift is addressed by removing the
  variable from configuration and env docs.
- Broader sensitive trace/session persistence risk is reduced by eliminating the
  executable live-submit branch that could have generated real write artifacts.
