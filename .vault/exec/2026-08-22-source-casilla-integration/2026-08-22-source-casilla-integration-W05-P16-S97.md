---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b5528303d3ca8957b33d0966c2741cd4dfd11f28ded9c107d6a62819e10fb9d1'
step_id: 'S97'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S97 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The retain the M360 refund-operation ingress-blocked census disposition and permit reopening only after one secure owner retains the full official request/document carrier with durable identity and fingerprint and S98 proves encrypted persistence/replay diagnostics/review and supported repeated-record export and ## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`
- `dev/source_connectivity/tests/test_m360_deferral.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# retain the M360 refund-operation ingress-blocked census disposition and permit reopening only after one secure owner retains the full official request/document carrier with durable identity and fingerprint and S98 proves encrypted persistence/replay diagnostics/review and supported repeated-record export

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`
- `dev/source_connectivity/tests/test_m360_deferral.py`

## Description

- Amend S97 through the plan CLI from impossible resolver enrollment to the evidence-backed bounded deferral.
- Retain the canonical M360 census row as `ingress_blocked` with an explicit owner, expiry, and owned follow-up.
- State the exact reopening predicate: complete official carrier, immutable durable identity and fingerprint, secure owner, and S98 proof.
- Bind the predicate and absence of resolver, connected proof, and repeated-record lifecycle with the focused census test.

## Outcome

Modelo 360 remains explicitly deferred. No resolver or M360 calculation semantics were introduced. Reopening is possible only after every evidence-backed carrier and proof condition is met.

## Notes

- The first predicate exceeded the census model's 500-character limit; it was shortened without dropping a required official axis.
- Focused pytest passed: `dev/source_connectivity/tests/test_m360_deferral.py` (3 passed). Focused Ruff passed.
- The feature-scoped vault check reported no errors; its remaining warnings are pre-existing feature reference/template hygiene.
- Formal self-review audit was intentionally excluded by the authorized S97 scope.

