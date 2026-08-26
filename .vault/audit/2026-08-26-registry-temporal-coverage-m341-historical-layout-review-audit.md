---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e3dda51fefb1e6e98cbb0a8a2b674d8f3301de3f47db181741d515d291dbfdd4'
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

Independent review of the Modelo 341 paths committed in `cfc47d7194` as they
stand at the live review HEAD, limited to the Modelo 341 registry and legal declarations, its
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

## Remediation evidence (2026-08-26)

Both findings are remediated in the bounded M341 correction. The canonical
`dev.locales move-revision` migration copied the retired
`2000-y-siguientes` occurrence subtree into `2005-2015` and
`2016-y-siguientes`, distributed only casillas each destination actually
declares, and released the retired subtree. `dev.locales scaffold` then added
the three historical-only wire occurrences, and `dev.locales set` supplied
real Spanish, English, Catalan, and Hungarian labels. The focused regression
loads both live revisions and resolves every casilla label in every shipped
locale; it also pins the three historical Spanish wire labels so a null,
stale-revision key, or semantic relabel fails. The registry-aware revision
parity suite passes, and `dev.locales scaffold --check` reports all four
catalogues clean.

The date-axis finding is resolved by preserving, documenting, and testing the
existing generic boundary rather than flattening it. The accepted
period-revision resolver ADR defines `filing_year` plus `period` as the natural
coordinate and `on` as an optional reference date intersected with
`valid_from`. BOE-A-2004-17306's final provision makes telematic presentation
available only from the first presentation period beginning after 1 February
2005. Accordingly, the revision keeps the 2005 ejercicio selector and the
independent `valid_from = 2005-02-01` as-of boundary: an explicit 31 January
request refuses, while 1 February admits the same `2005/1T` coordinate. The
focused test now proves both sides.

Verification evidence: the seven focused M341 tests pass with pytest's
repository confcut, Ruff passes the M341 test module, the direct M341
`RegistryValidator.validate_modelo` gate passes, the revision-locale parity
suite passes, and locale scaffold check reports `ca`, `en`, `es`, and `hu`
clean. The whole shipped-schema runtime localization test remains blocked by
14,028 unrelated null translations introduced by the concurrent Modelo 200
partition; its first failure is `modelo 200 / 2025-y-siguientes`, not Modelo
341. S51 remains open for the other modelos in its row.

## Remediation verification (2026-08-26, current HEAD)

`m341-revision-localization` is closed. The generated locale migration carries
only `2005-2015` and `2016-y-siguientes` beneath Modelo 341 in each of
`src/cadrumo/locales/{ca,en,es,hu}/modelo/schema/341.yml`; an exact search
finds no `2000-y-siguientes` residue. The focused test at
`src/cadrumo/domain/calculations/registry/tests/test_modelo_341_historical_design.py:96`
is non-tautological: it verifies the exact live casilla sets, invokes the
production resolver for every shipped locale, and pins the three
historical-only Spanish wire labels. An independent direct load resolved all
108 `(revision, casilla, locale)` combinations. The seven-test focused module
passes with the registry confcut and Ruff reports no finding.

`m341-selector-validity-axis` remains a medium finding. The new comment and
boundary test describe `2005-02-01` as the date at which Modelo 341 becomes
selectable, but the cited BOE final provision says presentation may occur from
the first presentation period that begins after that date. Its Modelo 341
deadline provision places the first-quarter presentation in the first twenty
days of April. Consequently,
`src/cadrumo/_data/registry/aeat/modelos/341/revisions/2005-2015/revision.toml:7`
does not ground selection at `2005-02-01`, and the new positive assertion at
`src/cadrumo/domain/calculations/registry/tests/test_modelo_341_historical_design.py:92`
only proves the registry's own declaration. Establish the actual `on` axis
from the authoritative date, revise the boundary or source declaration to
match it, and make the mutation test prove that source-derived boundary.

Verdict: PASS with one residual MEDIUM; no critical or high finding remains.

## Final date-axis remediation (2026-08-26)

The residual medium is fixed forward without changing the 2005 ejercicio or
the historical layout's authority window. The exact BOE-A-2004-17306 final
provision does not make 1 February itself a Modelo 341 presentation date: it
permits presentation from the first presentation period beginning after that
threshold. The existing generic quarterly deadline model, grounded in Modelo
341's plazo provision, opens the first-quarter presentation window on 1 April
and closes it after the first twenty natural days. The historical revision's
independent as-of axis therefore now begins on `2005-04-01`.

The focused boundary regression proves both adjacent civil dates through the
canonical selector: `2005/1T` with `on=2005-03-31` refuses and the same natural
coordinate with `on=2005-04-01` selects `2005-2015`. This removes the
self-grounded February admission while preserving the source-backed exercise
and byte-layout scope. S51 remains open for the other modelos in its row.
