---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` audit: `M347 singleton marker audit`

## Scope

Re-audited Modelo 347 after shared-worktree changes to confirm the semantic-role
singleton markers are still intentional, reasoned, and loaded by the real registry
path. The audit scope was the directory-mode registry at
`src/aeat/_data/registry/aeat/modelos/347` and the governing plan step `P03.S15`.

## Findings

- **Pass:** Modelo 347 remains directory-mode with one loaded revision,
  `2008-y-siguientes`, and 10 loaded casillas.
- **Pass:** All 10 casillas carry semantic roles after loader validation.
- **Pass:** The four quarterly amount roles are the only intentional singleton
  markers: `contraparte_importe_q1`, `contraparte_importe_q2`,
  `contraparte_importe_q3`, and `contraparte_importe_q4`.
- **Pass:** Each intentional singleton marker carries a non-empty
  `semantic_role_cardinality_reason`; the real loader reported reason lengths
  of 205, 206, 205, and 205 characters respectively.
- **Pass:** No Modelo 347 TOML mutation is required for this step.
- **Blocked broader corpus check:** The full committed-corpus singleton warning
  regression test is currently blocked by unrelated shared-worktree Modelo 151
  directory-mode WIP: `modelos/151/revisions/2024-y-siguientes` exists without
  `revision.toml`.

## Recommendations

Close `P03.S15` as an audit-only slice. Continue the semantic-role edge pass with
`P03.S16`, which targets Modelo 349 `base_intracomunitaria` coverage, and leave
the unrelated dirty `test_semantic_role.py` formatting churn untouched until the
signed-cuota slice owns that file. Treat the Modelo 151 loader failure as a
separate shared-worktree blocker unless the owner lands or removes that WIP.

## Codification candidates

None. The audit confirmed the current registry state rather than discovering a
new cross-session rule.
