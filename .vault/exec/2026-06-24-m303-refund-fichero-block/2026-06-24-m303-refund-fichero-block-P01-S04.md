---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S04'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-refund-fichero-block with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-06-24-m303-refund-fichero-block-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the secure-storage roundtrip and anti-tautology proof for the new financial refund-account fields and ## Scope

- `src/aeat/domain/user_profile/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the secure-storage roundtrip and anti-tautology proof for the new financial refund-account fields

## Scope

- `src/aeat/domain/user_profile/tests`

## Description

- Add the secure-storage roundtrip test for the refund-account financial fields: build a profile carrying the IBAN, SWIFT-BIC, and the full foreign-bank block at non-default values, push it through the real encrypted SQL boundary, reload, and assert strict equality plus per-field value equality.
- Populate the foreign-bank block with a genuinely non-default fixture (US bank, CHASUS33XXX SWIFT-BIC, full address) so a save-drops-field regression cannot hide behind a default.
- Add the anti-tautology proof: surgically corrupt the persisted IBAN fact inside the on-disk JSON envelope, reload through the real decrypt/parse pipeline, and assert strict inequality against the in-memory original.

## Outcome

- `src/aeat/application/user_profile/tests/test_refund_account_persistence_roundtrip.py` exercises the real `EphemeralMasterKeyProvider` / SQLite encrypted boundary, asserts `loaded == original`, and asserts each refund-account fact value survives the cycle.
- The anti-tautology test corrupts exactly one persisted IBAN fact and asserts the reload surfaces the corruption as strict inequality, so a broken boundary reds the gate.
- The test also carries the IBAN validator acceptance/rejection cases. The full file passes at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the test satisfies the roundtrip-discipline mandate (real adapters, strict pydantic equality, non-default fixture, anti-tautology proof).
