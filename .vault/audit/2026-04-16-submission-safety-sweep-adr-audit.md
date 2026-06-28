---
tags:
  - "#audit"
  - "#submission-safety-sweep"
date: 2026-04-16
modified: '2026-04-16'
related:
  - "[[2026-04-16-submission-safety-sweep-adr]]"
  - "[[2026-04-16-submission-safety-sweep-reference]]"
  - "[[2026-04-16-live-write-static-audit]]"
  - "[[2026-04-16-submission-safety-sweep-research]]"
---

# submission-safety-sweep ADR audit

Scope: audit `[[2026-04-16-submission-safety-sweep-adr]]` against issues `#142` through `#146` and charter rules `R2` through `R6`.

Verdict: APPROVED AFTER AMENDMENT.

## Findings

- Initial draft gap: the ADR named an append-only audit log but did not pin the exact file path or payload fields required by `R6`.
- Initial draft gap: the ADR did not explicitly retire the old amendment/complementaria live gate that reused `AEAT_LIVE_TESTS_ENABLED`.
- Initial draft gap: the ADR needed to say clearly that the stubbed CLI live path must fail closed until a real browser/certificate transport exists.

## Resolution

- The ADR now pins the audit log to `.aeat/live-submit-audit.log`.
- The ADR now fixes the required `R6` payload: UTC timestamp, modelo, period, taxpayer NIF, filing checksum, submission URL, AEAT response status, justificante CSV, exact confirmation phrase, env snapshot, PID, and argv.
- The ADR now removes the legacy submission/workflow `override_confirmation` contract and the separate amendment live gate.
- The ADR now records that the current CLI live namespace must fail closed on stubbed transport instead of reporting false live success.

## Approval basis

- Issue `#142`: covered by the distinct `AEAT_LIVE_SUBMIT_ENABLED` gate and pytest refusal.
- Issue `#143`: covered by the private confirmation hook and append-only audit module.
- Issue `#144`: covered by retiring the complementaria-specific live gate and routing amendment live mode through the engine-owned gate.
- Issue `#145`: covered by requiring explicit keyword-only `dry_run=` on submission and workflow APIs.
- Issue `#146`: covered by fail-closed CLI behavior on `_NullSession` wiring.
