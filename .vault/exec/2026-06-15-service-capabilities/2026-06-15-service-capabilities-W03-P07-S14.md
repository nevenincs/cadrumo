---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S14'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Write the onboarding how-to doc covering bootstrap, capabilities, and the doctor

## Scope

- `docs/how-to`

## Description

- Author `docs/how-to/onboarding.md`: a clean-machine guide covering `just bootstrap` (install), `just doctor` / `aeat config check` (readiness), `just provision` + `ollama serve`/`ollama pull` + provider-CLI (fill gaps), and `aeat config profile capabilities show/set` (opt in/out of cloud upload — off by default, gestor-barred — on-host vision, and Google export).
- Register the page as the first "How do I start this?" card and the first hidden toctree entry in `docs/how-to/index.md`.
- Verify every documented command against the live CLI and justfile before authoring; cross-links target existing how-to pages.

## Outcome

A newcomer now has a single front-door guide from empty checkout to a working, capability-configured tool. Documented-command conformance (48 tests) passes; the imperative-step, simple-terminology style follows the user-docs-hardening rule. Committed as `6bf45d03e`.

## Notes

The full nitpicky Sphinx build (`-n -W`) is the slow gate; it runs in the S15 verification pass rather than per-doc. Links and toctree wiring were verified by inspection (all targets exist).
