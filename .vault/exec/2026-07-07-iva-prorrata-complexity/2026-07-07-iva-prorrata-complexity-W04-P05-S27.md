---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S27'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-prorrata-complexity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S27 and 2026-07-07-iva-prorrata-complexity-plan placeholders are machine-filled by
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
     The Add an is_interrupted=True entry to the encrypted-SQL prorrata register roundtrip fixture so the interrupted marker crosses the encrypted boundary under test and ## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add an is_interrupted=True entry to the encrypted-SQL prorrata register roundtrip fixture so the interrupted marker crosses the encrypted boundary under test

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add an `interrupted=True` (art. 105.Cinco sin-operaciones) entry to the encrypted-SQL prorrata register roundtrip fixture `_populated_register`, and assert after the encrypted save/load that the interrupted marker survives and the inactive year carries no provisional/definitive percentage.

## Outcome

The interrupted-ejercicio marker now crosses the encrypted secure-object boundary under test (previously covered only at the domain-JSON level), per aeat-roundtrip-discipline. The roundtrip suite is 4 passed under `-n0`, including the corrupt-payload and missing-field anti-tautology proofs which continue to exercise the first entry unaffected by the appended interrupted row.

## Notes

- The interrupted entry uses `regime = NINGUNA` (the inactive-year convention used by the domain-level interrupted tests); the register-model validator enforces that an interrupted entry carries no percentage/volume/provenance, so the fixture entry is a pure marker.
