---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:f0942c75fdd81bcfe2a20e1eacea3bd556398ea4888088f9d0f86b3b8a6866da'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-W02-P05-S51]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-temporal-coverage with a kebab-case feature tag, e.g. #foo-bar.
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

# `registry-temporal-coverage` audit: `Modelo 341 historical layout implementation review`

## Scope

Independent review at live HEAD `f25b8e37664` of the Modelo 341 paths committed
in `cfc47d7194`, limited to the Modelo 341 registry and legal declarations, its
focused tests, and the S51 execution record. The review checked the hash-pinned
AEAT 2005--2015 binary, the 619-position/20-field fixed-width transcription,
the 2016 successor's separate variable-envelope/800-position shape, temporal
selection and refusal boundaries, references, application surfaces, bindings,
and locale resolution. The current whole-tree claimed-year gate was also run
only to distinguish shared-tree failures from this scoped change. The five
focused Modelo 341 tests pass when isolated from the repository-wide fixture;
the ordinary current test runner instead fails during setup on the concurrent
rename of `application.modelo._profile_binding`. With that unrelated fixture
excluded, the whole-tree claimed-year gate reaches registry validation and
fails on unrelated Modelo 200 authority and deadline declarations, before its
assertion body. Neither external result names Modelo 341, and the earlier
Modelo 184 loader failure is not present.

## Findings

### m341-revision-localization | high | Both selected revision eras have no resolvable casilla labels

`src/cadrumo/domain/calculations/registry/modelo_localization.py:74` derives
revision-occurrence keys, but every locale catalogue at
`src/cadrumo/locales/{es,en,ca,hu}/modelo/schema/341.yml:8` still contains only
the retired `2000-y-siguientes` branch. The live 2005--2015 revision declared
at `src/cadrumo/_data/registry/aeat/modelos/341/revisions/2005-2015/revision.toml:1`
therefore has no Spanish value for any of its fifteen derived keys; the same is
true for all twelve 2016-y-siguientes keys. A live read of
`CasillaDefinition.get_label("es")` fails immediately for
`2005-2015/decl.ejercicio` with `MissingTranslationError`, and the direct
catalogue lookup returned `None` for all 27 loaded keys. The registry can load
and the new geometry tests pass without visiting this operator-facing boundary,
so the regression is currently unprotected. The historical application and
export surfaces can consequently resolve a snapshot whose casillas cannot be
presented to an operator.

### m341-selector-validity-axis | medium | The 2005 selector and validity date are contradictory without an adjudicated axis

`src/cadrumo/_data/registry/aeat/modelos/341/revisions/2005-2015/revision.toml:6`
sets `valid_from = 2005-02-01`, while line 8 selects the whole 2005 filing
year. Because `src/cadrumo/domain/calculations/registry/temporal.py:176`
intersects an explicit `on` date with that validity window, the live resolver
selects this revision for `(2005, 1T)` when `on` is omitted but refuses the
same coordinate at `on=2005-01-01`. The new test only samples
`on=2005-04-01` at
`src/cadrumo/domain/calculations/registry/tests/test_modelo_341_historical_design.py:69`,
so it does not prove or explain the disagreement. The governing plan requires
a selector start that disagrees with the declared validity start to surface a
finding, and the research requires an explicit date-axis relationship or
exception reason. The asserted 2005--2015 revision identity therefore has an
unresolved date-window meaning.

## Recommendations

- For `m341-revision-localization`, run the canonical `dev.locales` scaffold,
  then populate the required Spanish values and all locale counterparts for the
  2005--2015 and 2016-y-siguientes occurrence keys. Remove the obsolete
  `2000-y-siguientes` branch in the same M341 correction, and add a focused
  loaded-M341 label-resolution regression covering every casilla in both
  revisions before treating the historical layout as reviewable.

- For `m341-selector-validity-axis`, ground whether `on` is an exercise date,
  a filing-window date, or an effective-publication date for this Modelo 341
  era. Then align the selector/validity declarations or record the sanctioned
  exception with the authoritative date-axis evidence, and add a mutation or
  boundary test for the resulting rule.

