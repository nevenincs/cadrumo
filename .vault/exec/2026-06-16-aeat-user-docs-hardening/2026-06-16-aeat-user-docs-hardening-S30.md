---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:3a84a39c12d87db0c795079f8816af942c35719ef953b9ce1f32b38abde4e74e'
step_id: 'S30'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden setup-llm-classification.md

## Scope

- `docs/how-to/setup-llm-classification.md`

## Description

- Verify-close: read `setup-llm-classification.md` against the hardening standard and its systemic audit patterns (S-PASS, S-PREREQ, S-DRIFT) and confirm resolution at HEAD.
- Confirm S-DRIFT (doc-cites-nonexistent-commands): every command resolves - `aeat app ledger providers`, `aeat config check`, `aeat app ledger classify --llm <provider>`; the supported provider names (`claude`, `antigravity` via Google's `agy` CLI, `codex`) match the live surface, and the retired standalone `gemini` CLI is correctly named as superseded.
- Confirm S-PASS (passphrase prerequisite documented) and S-PREREQ (active profile + at least one unclassified transaction stated before the smoke test).
- Confirm the privacy boundary (never contacts AEAT; provider CLI may send prompt data; treat as taxpayer data) is documented.

## Outcome

- Page verified compliant at HEAD; the systemic S-DRIFT / S-PASS / S-PREREQ patterns are addressed for this page. Delta: none required.

## Notes

- Imperative steps, provider-discovery vs account-login distinction, logged-out refusal relayed verbatim, Spanish-runtime note. CLI conformance gate green.
