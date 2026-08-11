---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:cc89254701de31112bca74be20b9c898a11f4609885ecbc8b3eebc1fce84cad3'
step_id: 'S51'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-export-fragment-generator-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S51 and 2026-08-10-aeat-export-fragment-generator-authority-plan placeholders are machine-filled by
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
     The Enforce M303 export applicability before rendering: optional canonical values may emit blank only when law/profile says not applicable, while exonerado, prorrata, differentiated-sector, simplified-regime, amendment, payment, and account populations with missing required authority refuse the whole export. Prove unsupported fields cannot be reclassified as filler, header defaults, or legacy lookups and ## Scope

- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Enforce M303 export applicability before rendering: optional canonical values may emit blank only when law/profile says not applicable, while exonerado, prorrata, differentiated-sector, simplified-regime, amendment, payment, and account populations with missing required authority refuse the whole export. Prove unsupported fields cannot be reclassified as filler, header defaults, or legacy lookups

## Scope

- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add one immutable explicit applicability envelope for the S47 through S50 M303 units.
- Validate annual-summary, prorrata, differentiated-sector, simplified-row, and producer authority before layout or target creation.
- Remove superseded optional per-unit export parameters and delegate canonical validators and projectors.
- Carry the typed envelope through Modelo export orchestration and real CLI callers without synthesis.
- Refuse missing, ambiguous, unsupported, defaulted, or payload-on-nonapplicable units with no artifact.

## Outcome

M303 export now requires one explicit typed whole-unit applicability decision. Complete units pass the pre-layout boundary for all five epochs and reach the intentionally withdrawn-layout refusal without an artifact. Missing applicable facts, absent envelopes, invalid producers, and non-M303 envelope misuse refuse earlier. Explicit non-applicability is the only blank authority.

Application and Modelo lanes passed, including 12 Modelo tests and a real CLI integration test. Ruff and targeted Basedpyright passed. Independent review passed with zero findings.

## Notes

Initial review found that the lower filing gate was not propagated through production Modelo orchestration. The typed envelope was threaded through command, temporary-write, filing, CLI export, review-package, and quickfile paths, then re-reviewed successfully. M303 layouts remain withdrawn for S19 and S20.
