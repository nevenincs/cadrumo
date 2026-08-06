---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:b66e2d00c8f76963e80d42baa6b9550cb1067a6ad9536db5c4b9ee0839ccd401'
step_id: 'S24'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden quickstart.md

## Scope

- `docs/how-to/quickstart.md`

## Description

- Verify-close: read `quickstart.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M3 (linear path breaks for a real first-timer): the page now follows one working from-nothing chain - profile (with name/surnames/activity-start-date) -> `ledger add` GROSS amounts + expense category -> classify -> work create -> calculate with first-period prior bindings `=0` -> verify granted -> export `.boe` -> `overview agenda --allow-incomplete`.
- Confirm finding M4 (no sample CSV / column format): the page shows the concrete semicolon-delimited CSV with comma decimals and the sign-carries-direction convention.
- Confirm S-ORDER (top-to-bottom runnable), S-PASS (passphrase section), and S-LANG (Spanish-runtime note) are addressed.

## Outcome

- Page verified compliant at HEAD; findings M3, M4, S-ORDER, S-PASS, S-LANG resolved (2026-06-19 documentation batch; goal-acceptance persona confirmed a 946-byte `.boe` from the page alone). Delta: none required.

## Notes

- Residual m1 (`ledger import <missing-file>` traceback) and n1 (`ledger add` absent from curated top-level help) are APP-side findings, m1 already fixed per the audit. CLI conformance gate green.
