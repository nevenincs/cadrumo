---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S31'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S31 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The DONE 7d20b2d984, the docs-claims gate now measures, a positive control asserts every pattern against a must-match and a must-not-match string and a guard requires a new pattern to arrive with its own cases, the retired tap pattern fails 2 of 4 control cases so the control discriminates. GATE, uv run --no-sync pytest dev/docs/tests/test_distribution_claims.py collects 12 and passes and ## Scope

- `dev/docs/tests/test_distribution_claims.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DONE 7d20b2d984, the docs-claims gate now measures, a positive control asserts every pattern against a must-match and a must-not-match string and a guard requires a new pattern to arrive with its own cases, the retired tap pattern fails 2 of 4 control cases so the control discriminates. GATE, uv run --no-sync pytest dev/docs/tests/test_distribution_claims.py collects 12 and passes

## Scope

- `dev/docs/tests/test_distribution_claims.py`

## Description

- Add a positive-control table pinning every claim pattern against strings that must match and strings that must not.
- Add a guard requiring each declared pattern to carry its own control cases, so a new pattern cannot silently escape coverage.
- Add a corpus-not-empty assertion, so the scan cannot pass vacuously over zero files.

## Outcome

The gate now measures. It carried two tests, neither of which passed a string to a pattern, and the corpus scan hit an early return over 59 documents containing zero claims. It was green because it was inert. The suite is now 12 tests, and the retired tap pattern fails 2 of the 4 tap control cases, which is what demonstrates the control discriminates rather than merely passing.

## Notes

My earlier claim to have verified the patterns in both directions was true of a manual evaluation I ran and untrue of the test suite. The manual check was real but it was not a gate, and nothing would have noticed it rotting. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
