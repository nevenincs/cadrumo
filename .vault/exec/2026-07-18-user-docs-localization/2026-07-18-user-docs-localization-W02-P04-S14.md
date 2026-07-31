---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:91f35c13f4bbfea5415ccfa5a48a1c47b7eaf374c176acb981c1f82d25c8bec5'
step_id: 'S14'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

# Translate the explanation and reference section catalogues to Catalan

## Scope

- `docs/locales/ca`

## Description

- Translate the explanation and reference section catalogues to Catalan (7 pages each section).

## Outcome

The `docs/locales/ca/LC_MESSAGES/explanation/**` and `.../reference/**` catalogues are fully translated. Delivered across commits tagged `W02.P04.S14` (9eaacfb018, 1ab50bb725, 67863b4a1c). Rolled into the ca language reaching 2994/2994 entries, zero untranslated, zero fuzzy at HEAD.

## Notes

The ca reference/review-calculation-values catalogue carried a pre-existing non-breaking-space drift on one maritime-exemption msgid, surfaced and reconciled (fuzzy cleared, translation correct) in the W03 pass (commit 167961772c); ca stayed 100% complete. Vault-only closure.
