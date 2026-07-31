---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:200b39cd96f92c0af4d64122d888ba362b5e21b4963c9c273ec4205a11d55a42'
step_id: 'S07'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden classify-with-llm.md

## Scope

- `docs/how-to/classify-with-llm.md`

## Description

- Verify-close: read `classify-with-llm.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding m19 (documented LLM preview fields not surfaced): the page documents the text preview fields (classification, category, confidence, reason) AND the machine-readable record - provider, `provenance` (`llm:<provider>`), `persisted` (`false` in preview) - via the global `aeat --format json` flag placed before the subcommand.
- Confirm finding m18 (`--nif` silently ignored) is not applicable to this page: it addresses the transaction by the positional id and never documents `--nif`; the real identity flag is `--tax-id` (re-diagnosed as an app-side no-code-change concern).
- Confirm the single-transaction limit, the `--saturate` tax-field flow, the passphrase prereq, and the never-contact-AEAT boundary are documented.

## Outcome

- Page verified compliant at HEAD; finding m19 resolved via the documented global-JSON provenance/persisted fields. Delta: none required.

## Notes

- Residual m18 is APP-side (no-profile generic "No such option" does not suggest `--tax-id`) - a CLI-global concern, out of documentation scope. CLI conformance gate green.
