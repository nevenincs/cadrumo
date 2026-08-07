---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ff3d2a0e12ab26ed20c4e22b7672e9293ee5b5951ff98b323a9ec6a95554154c'
step_id: 'S16'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Remove every locale leaf orphaned by the deletion through the locales CLI so all four catalogues stay in parity, then run the locale and apidocs drift gates

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Remove every locale leaf orphaned by the collapse through the locales CLI, across all four catalogues.
- Add the one key the campaign introduced but never registered, with a real translation in each language.
- Correct the operator-facing link strings that described the retired two-store behaviour.
- Run the locale parity, inter-locale and apidocs drift gates.

## Outcome

All four catalogues carry an identical key set. The orphans removed were the six help and refusal strings the deleted slim verbs owned, the four importing-error keys from a module retired earlier in the campaign, and the two sub-noun keys.

The catalogues also gained the empty-patch refusal key, which the update service referenced but no catalogue carried -- the parity gate was reporting it as a missing codebase key.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_parity.py src/cadrumo/tests/test_locale_translation_honesty.py -m "unit or integration"
    40 passed

    uv run --no-sync python -m dev.docs.apidocs scaffold --check
    Stub tree is conformant. No drift detected.

## Notes

Locale writes on this volume were unreliable. Several remove calls reported success while the leaf survived in one catalogue -- the drive's concurrent-I/O failure, which surfaces as a silent write drop rather than an error. Every removal was verified by re-reading all four catalogues and diffing their key sets, and three stragglers were caught and re-removed that way. A removal loop trusted on its exit status alone would have left the catalogues out of parity.

Two strings needed correcting, not just de-orphaning. The link refusal and the invoice-id help both told the operator that ids minted by `invoice add` cannot be linked, and pointed at the retired sub-noun instead. That was true while two stores existed and false the moment they collapsed: an operator following the message would have hunted for a verb that no longer exists, to solve a problem that no longer occurs.
