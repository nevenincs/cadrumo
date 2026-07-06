---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S09'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The add the anti-tautology corrupt-payload proof: mutate the on-disk register to delete a field, reload, assert ValidationError or strict inequality surfaces and ## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the anti-tautology corrupt-payload proof: mutate the on-disk register to delete a field, reload, assert ValidationError or strict inequality surfaces

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add two anti-tautology proofs to the roundtrip suite that reach into the encrypted `SecureObjectRow`, decrypt with the payload AAD, mutate the on-disk document, re-encrypt, and reload.
- Corrupt probe: rewrite the first entry's `provisional_percentage` and assert the strict-equality witness surfaces the drift (`reloaded != original`, value now the corrupted one).
- Absent-field probe: delete the required `regime` field and assert the load path raises `pydantic.ValidationError` naming `regime`, never a silent re-default.

## Outcome

Both probes bite: the corruption is caught by strict inequality and the deleted required field raises at load. If either passed silently, the register persistence boundary would be tautological.

## Notes

The absent-field probe deletes `regime` (a required, non-defaultable field) rather than an optional field, so the drop genuinely raises; an optional field would silently re-default and not prove the boundary.
