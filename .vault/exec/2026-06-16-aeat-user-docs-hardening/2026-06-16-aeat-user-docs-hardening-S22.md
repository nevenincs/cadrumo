---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden profile-setup.md

## Scope

- `docs/how-to/profile-setup.md`

## Description

- Verify-close: read `profile-setup.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm finding M2 (profiles addressed by token, not display-name): the page uses `duplicate X Y` making `Y` the address, and no longer documents the divergent `--display-name` then `delete <label>` path.
- Confirm S-PASS (passphrase documented: interactive prompt or `AEAT_SECRET_PASSPHRASE`), S-PREREQ (a "Decide your facts" precondition block plus a quickstart on-ramp), M5/S-LANG (a note that prompts/errors render in Spanish and the quoted blocks are English translations), m3 (`duplicate`/`import` make the new profile active - stated), and m4 (history needs an active bucket - stated) are all resolved.
- Apply one taxpayer-general spot-fix: rename the worked-example heading and body from "freelancer" to "a natural person with an activity" / "an individual", aligning with the aeat-user-docs-hardening taxpayer-general terminology (the page already frames all entity types generally).

## Outcome

- Page verified compliant at HEAD; audit findings M2, S-PASS, S-PREREQ, M5/S-LANG, m3, m4 resolved (2026-06-19 batch). Delta: one spot-fix - "freelancer" -> taxpayer-general phrasing (2 lines).
- Imperative steps, worked example, foral-regime refusal grounded, safety note ("A profile is local ... never submits"), resolving cross-links.

## Notes

- Residual n2 (refusal-localisation inconsistency: `switch` Spanish vs `delete` English on unknown profile) is an APP-side finding, out of documentation-hardening scope. CLI conformance gate green.
