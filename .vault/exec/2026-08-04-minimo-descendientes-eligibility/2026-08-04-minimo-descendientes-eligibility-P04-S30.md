---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:24d7f5ad7e884b7cf1aebda32b4c8a98b845722ca4fda9267facb7b152a8ce18'
step_id: 'S30'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Re-scope every operator-facing description of the declared-months fact

## Scope

- `src/cadrumo/locales/`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`
- `src/cadrumo/application/wizard/`

## Description

- State both Art. 81.1 limbs in the wizard prompt, the wizard help and the calculate-flag help, across all four catalogues.
- Add a structural guard asserting each locale names the entry-date route, by keyword marker rather than by rendered sentence.

## Outcome

The date-scoped adopción window is now reachable through the documented surface. Before this, every description scoped the question to a child under three, so an operator answering as asked entered zero for a five-year-old adoptee and received nothing — an under-grant of up to 1.200 euros per child, reachable only by an operator willing to contradict the prompt.

Code and all four catalogues landed in one commit, which was the explicit instruction after a sibling Step had shipped its two halves through different landing paths.

## Notes

The prose first landed ASCII-stripped in Spanish, Catalan and Hungarian, because it was typed through a shell heredoc that mangles non-ASCII. That is not cosmetic in a Spanish filing product: the text read "menor de 3 anos", which is not "años" but a different and crude word. Corrected in a follow-up by passing values to the locales CLI as argv elements from a UTF-8 source file, never through a heredoc. Scope of the correction was three keys per locale, not one — the first sweep fixed a single key and read clean because the probe searched only the string it had already fixed.

The guard shipped with a defect of its own: its Hungarian marker was the ASCII "belep", chosen against the stripped prose, so it silently PINNED the degradation and correcting the language failed the test. Accenting the marker was therefore part of the fix rather than an adjustment to it. This is the third acceptance criterion in this Phase that certified the defect it guarded.

Neither locale gate catches accent-stripping. Parity checks that every key exists in every catalogue; the translation-honesty ratchet checks that a value is not byte-identical to English. An accent-stripped Spanish sentence satisfies both. The gap is recorded rather than closed, because inventing a gate under time pressure is how the pinned marker happened in the first place.

One remaining ASCII "anos" in the Spanish catalogue at a Modelo schema label is NOT from this work; a content search attributes it to the localization migration checkpoint, so it is left for that campaign rather than edited across a live cutover.
