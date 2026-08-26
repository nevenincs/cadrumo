---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:500f3a98eff684e6b2817b660d01587d1694871d44ec332a2c000c0821b0d1f3'
step_id: 'S87'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Cut the registry closure CLI over from the disabled single-channel proof port to the canonical two-channel assessment, preserving typed per-channel refusals and public receipt secrecy, and prove an eligible two-receipt assessment can satisfy the filing-export limb without a second writer or payload digest projection

## Scope

- `src/cadrumo/application/registry/`
- `src/cadrumo/application/filing/`
- `dev/registry/conformance/`
- `dev/registry/`
- `src/cadrumo/application/registry/tests/`
- `dev/registry/conformance/tests/`

## Description

- Replace the closure composer's disabled single-channel lookup with the strict two-channel assessment port at the law-selected revision and layout coordinate.
- Retain conformance and secure-replay refusals as distinct typed public closure data.
- Project public conformance and secure-replay receipt identity while excluding taxpayer values, emitted payloads, and payload digests.
- Wire the live closure command to canonical two-channel conformance with an explicit unavailable secure-replay authority.
- Add synthetic strict-model bridge coverage and live-versus-offline command assertions without claiming taxpayer acceptance.

## Outcome

The filing-export limb now satisfies only from matching conformance and secure-replay receipts produced through the canonical `export_draft` writer. Missing replay remains an explicit `secure_replay:authority_unavailable` refusal, and offline evaluation remains a distinct no-authority refusal. The legacy `proof_for` protocol is no longer exported or consumed by registry closure.

## Notes

Exact-path Ruff, whitespace, import, and collection checks passed. Nine isolated strict closure-model tests passed. Formal review found no high or critical issue; its one medium facade-export finding was removed before closure. The combined focused registry and command run reached seven passes, then the shared bundled-authority fixture failed before the remaining S87 assertions because concurrent uncommitted Modelo 200 work currently violates registry projection, source, applicability, and deadline invariants. S87 did not alter or stage that tree. The focused suite must be rerun after its owner restores a valid bundled registry.
