---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S15'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
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
     The Write comparison tests covering JSON match and mismatch diagnostics, text match, exit-code failure, and @expect pass and fail and ## Scope

- `dev/docs/sequences/tests/test_compare.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Write comparison tests covering JSON match and mismatch diagnostics, text match, exit-code failure, and @expect pass and fail

## Scope

- `dev/docs/sequences/tests/test_compare.py`

## Description

- Produce every golden under test from a REAL sandboxed CLI execution (`config profile list` sequences, JSON and text variants) projected through the real store — no hand-shaped fixtures.
- Prove the clean path end to end: golden written from run A, a fresh sandboxed run B compares with zero problems through the full `check_transcript` tier, covering masking and text normalisation across two real runs.
- Prove the store roundtrip with strict model equality, the canonical review-diffable file form, the missing-golden refusal naming the refresh invocation, and the strict-schema refusal of a hand-edited golden carrying a smuggled mask-extension key.
- Red every divergence class by mutating the committed artifact: envelope status drift (named frame and differing path), a deleted envelope field (the anti-tautology proof), exit-code drift, frame-count drift, capture-value drift, and text drift (unified diff with the exact removed line).
- Cover `@expect` pass, semantic failure quoting the live value, and missing-path diagnostics against the live run, plus a signature gate pinning that no comparison function accepts a mask or fields parameter.

## Outcome

17 real-behaviour tests green (68 across the whole engine suite), each mismatch reported with the page, sequence id, frame index, argv, and the refresh remedy. The deleted-field mutation proves a corrupted stored payload cannot pass, so the suite's clean passes are non-tautological.

## Notes

Strict python-mode validation refuses JSON-document lists for tuple fields, so golden mutation in tests re-validates through JSON mode exactly as the store's reader does.
