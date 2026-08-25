---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e1190ab5551ad2e083b7ec6663158b068192bb1dce68fed5b2c84f5fc2897a52'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `deadline-window-revision-authority` audit: `s46 m210 design axis`

## Scope

Formal bounded review of W02.P05.S46 against the accepted M210 plazo-keying,
registry temporal-coverage, and deadline-window revision-authority decisions. The
review covered only the S46 changes in `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
and `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`.

The review checked source fidelity for the M210 2022 design's devengo scope,
preservation of the four-year refund close, the generalized design-axis classifier,
the M720 legal-effect control, mutation sensitivity, and the absence of a redeclared
selector, resolver, supported-year horizon, or design catalogue. Vaultspec RAG was
used first for semantic overlap discovery, followed by exact-symbol confirmation.

## Findings

No findings.

The bundled AEAT catalogue and manifested artefact title state that
`aeat-dr-210-2022` governs devengos from 1 June 2022 until the 2026 successor.
The added source selector reuses the sole `PeriodSelector` schema and the already
accepted M210 `EVENT-N`/`0A` vocabulary for filing years 2022-2025. It does not widen
the source's physical date bounds, which remain 2022-06-01 through 2025-12-31.

The generalized classifier requires the selector's first claimed year to agree
with the source-bound start year. That classifies the mid-year M210 design on the
devengo/ejercicio axis while leaving `aeat-dr-720` on the presentation/legal-effect
axis because its selector begins at ejercicio 2012 and its source date begins in
2013. The named M210 acceptance and selector-removal mutation tests passed, as did
the existing M720 controls and the non-ejercicio attribution guards.

The M210 2025 refund row remains unchanged at `closes_on = 2030-02-01`, consistent
with the accepted plazo ADR's four-year claim period. The S46 diff introduces no
new deadline date, selector type, filing-window resolver, supported-year constant,
or record-design catalogue.

Current verification produced 17 passes and one expected whole-tree assertion
failure. That assertion reports thirteen pre-existing named design-coverage gaps
and does not report Modelo 210; Ruff passes for the changed test module. This is
consistent with the exec record's earlier 22-pass focused checkpoint. The red
whole-tree inventory remains outside this bounded S46 classifier review and is not
misrepresented as a green repository-wide gate.

## Recommendations

Accept W02.P05.S46. Continue to track the thirteen separately named layout-design
coverage gaps under their owning registry-corpus work; they do not require an S46
workaround or exception.

