---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace schema-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#schema-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-20'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related: []
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` audit: `m200-m202 pago-fraccionado relation drop`

## Scope

Cross-domain regression review of the modelo-200 (Impuesto sobre
Sociedades) Liquidación formula chain under the active schema-hardening
campaign. Triggered by a red cross-dependency test
(`test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados`)
during the codebase-health campaign's checkpoint sweep. The test
defends the M200 to M202 handoff: modelo 200's cuota del ejercicio a
ingresar must net out the modelo 202 pago-fraccionado instalments
already paid in-year.

## Findings

### Stale-test root cause — resolved diagnosis, MEDIUM

The original failure (`unknown registry input casilla ids: [00592]`)
is a stale test, not a registry defect. Commit `0364f576d`
re-numbered the M200 Liquidación casillas from bare ids to the
segment-qualified scheme: `00592` became `DP200014B:00592` (cuota
líquida) and `00599` became `DP200014B:00599` (cuota del ejercicio a
ingresar/devolver). The cross-dependency test was never updated and
still referenced the bare ids. A test edit modernising the ids to the
segment-qualified scheme is staged in the working tree against
`src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`;
it is correct against committed registry HEAD and is uncommitted
pending the formula adjudication below.

### M202 relation dropped from the `00599` formula — HIGH

Uncommitted working-tree WIP in the M200 records
`formulas.toml` (modelo 200, 2024-y-siguientes revision) rewrites the
`DP200014B:00599` formula. The committed-HEAD form is
`subtract(DP200014B:00592, modelo-200-2024-rel-202-pagos-fraccionados)`
— a direct M200 to M202 cross-modelo relation. The WIP form is a
multi-term `multiply(DP200026:00625 / 100, subtract-chain(DP200014B:00592, 01766, 01784))`
which contains no reference to `modelo-200-2024-rel-202-pagos-fraccionados`.

The modelo-202 relation is the only operand binding the modelo 200
final settlement to the in-year pago-fraccionado instalments. Dropping
it means the computed cuota del ejercicio a ingresar would not net out
instalments already paid — a double-charge against the taxpayer.
Ley 27/2014 art. 41 requires the IS self-assessment to deduct the
pagos fraccionados from the cuota. The WIP `00599` formula, as it
currently stands, would compute an unlawful settlement figure.

## Recommendations

The schema-hardening campaign owner of the M200 `formulas.toml` WIP
must adjudicate, with grounding in the AEAT modelo 200 official form
layout and Ley 27/2014:

1. If the M202 pago-fraccionado relation belongs on `00599`, reinstate
   `modelo-200-2024-rel-202-pagos-fraccionados` as an operand of the
   new multi-term formula. The staged cross-dependency test edit then
   lands green alongside that commit.
2. If the new `00599` term structure relocates the M200 to M202
   linkage to a different casilla, the formula change and the
   cross-dependency test must update together so the handoff stays
   covered by exactly one assertion — the test must not be deleted or
   weakened to a shape that no longer defends the netting.
3. Either way, the M200 to M202 netting must remain enforced by a
   graph-wiring cross-dependency test. Do not close the test as
   tautological or drop it; the relation it defends is a legal
   requirement, not an arbitrary numeric expectation.

Until adjudicated, the staged test id-modernisation must not be
committed in isolation — its `operand_refs` assertion encodes the
M202 relation whose fate this finding decides.
