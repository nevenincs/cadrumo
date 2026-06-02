---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
step_id: 'S15'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Re-audit M347 singleton marker state

## Scope

- `src/aeat/_data/registry/aeat/modelos/347`

## Description

- Inspect the current shared-worktree state for the governing plan, Modelo 347,
  and semantic-role tests before editing.
- Load Modelo 347 through the production registry loader.
- Count loaded casillas, semantic-role assignments, intentional singleton
  markers, and missing singleton reasons.
- Record the audit result without changing Modelo 347 TOML or unrelated dirty
  semantic-role test files.

## Outcome

- Modelo 347 loaded revision `2008-y-siguientes` with 10 casillas and 10
  semantic-role assignments.
- The only intentional singleton markers are the four quarterly amount roles:
  `contraparte_importe_q1`, `contraparte_importe_q2`,
  `contraparte_importe_q3`, and `contraparte_importe_q4`.
- Every intentional singleton marker has a non-empty reason.
- `P03.S15` is complete as an audit-only step.
- Focused semantic-role tests passed for M347 quarterly singleton markers,
  reviewed singleton warning suppression, and singleton cardinality behavior.

## Notes

- `vaultspec-core vault list ... | Select-Object` still raises a Rich
  broken-pipe `OSError: [Errno 22] Invalid argument` when the downstream pipe
  closes early; this was reported as an observed CLI edge and was not treated as
  registry validation failure.
- `src/aeat/domain/calculations/registry/test_semantic_role.py` is dirty from
  unrelated formatting churn in the shared worktree and was not touched.
- The full committed-corpus singleton warning regression check was attempted and
  failed before assertion because unrelated untracked Modelo 151 directory-mode
  WIP exposes `modelos/151/revisions/2024-y-siguientes` without
  `revision.toml`. This slice did not mutate or clean peer WIP.
