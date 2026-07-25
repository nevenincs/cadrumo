---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S02'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Carry honest sensitivity copy on the cleartext transport arm so an operator choosing it is told what leaves encrypted storage, since the cleartext arm is the one selection that removes the confidentiality guarantee

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`

## Description

- Give both transport choices a `description` copy slot, not a bare label, so the SELECT states the consequence of each arm at the point of choice.
- Name the cleartext arm for what it is rather than by its flag: the label marks it local and subject-access only, and the description states the file is unencrypted JSON carrying sensitive financial data that must never be emailed, synced, or transferred.
- Mark the encrypted arm as the recommended default and describe it as AEAD passphrase encryption safe for transfer between machines, so the contrast is explicit rather than implied.
- Hold the prose in the four shipped locale catalogues behind `LOCALE_KEY` references, since the definitions carry references only and the copy assembler resolves them loudly at render.

## Outcome

Landed in commit `c4545973f9`. This pass verified the step rather than re-authoring the copy.

The cleartext description resolves to prose naming the exact exposure — unencrypted JSON containing sensitive financial data, local or subject-access handling only, never email, sync, or transfer — rather than generic wording, satisfying the requirement that the operator be told what leaves encrypted storage. The five transport keys carry a real translation in each of the four catalogues; `uv run --no-sync pytest src/cadrumo/tests/test_parity.py` passes, so no catalogue is missing a key, and none of these keys appears in the translation-honesty ratchet's untranslated set.

Render is proven rather than assumed: the line-mode and full-screen frontend drives resolve every one of these references through the production copy assembler, so a missing or misspelled key fails the render rather than degrading silently.

## Notes

Copy assertions are deliberately structural — the tests pin key resolution and choice identity, never the localized prose itself, since asserting generated prose (or pulling the expected string from the code under test) would be tautological.
