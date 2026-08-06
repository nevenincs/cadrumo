---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:9579be06a82d2f6c9190a3bce4799aa9538c00fe7d98d91e8279d52420a1181e'
step_id: 'S06'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden classify-with-llm-evidence.md

## Scope

- `docs/how-to/classify-with-llm-evidence.md`

## Description

- Verify-close: read `classify-with-llm-evidence.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M20 (cloud-evidence consent gate does not fire on a no-evidence transaction): the page now states the precondition explicitly - the consent gate fires only when real text-layer evidence is attached, and a no-evidence transaction sends nothing extra (only the transaction row, exactly as plain LLM classify).
- Confirm the security posture is documented accurately: on-host default (no acknowledgement), gestor-mode bar, per-run non-sticky `--evidence-acknowledged`, invoice bytes in encrypted storage decrypted in-memory only (never temp file/log/cache), and `qwen2.5vl:3b` as the default local vision model.

## Outcome

- Page verified compliant at HEAD; finding M20 resolved (2026-06-19 documentation batch; a test confirms no evidence leaks the cloud boundary without the ack). Delta: none required.

## Notes

- The `qwen2.5vl:7b` mention is a correct optional upgrade over the `3b` default (not the S-DRIFT default-model error, which was in workstation-setup). CLI conformance gate green.
