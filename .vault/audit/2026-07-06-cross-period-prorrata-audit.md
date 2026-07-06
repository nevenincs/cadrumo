---
tags:
  - '#audit'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
  - "[[2026-07-06-cross-period-prorrata-W02-P03-S10]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
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

# `cross-period-prorrata` audit: `S10-S18 seed/override review`

## Scope

Reviewed the `W02.P03.S10` through `W02.P04.S18` seed/override implementation and vault
closure artifacts: the carried-prior-definitive seed helper, the evaluation
surface for blocking/advisory findings, source-observation identity recording on
the carried entry, the committed real-observation seed tests, the legacy
field-absent observation compatibility needed to exercise the missing-stamp
advisory, the AEAT-authorised and inicio-de-actividades override recording
services, the application in-force lookup that delegates to the single domain
precedence ladder, the prior-observation cross-check findings, and the committed
override/cross-check tests. The review also checked the
S10/S11/S12/S13/S14/S15/S16/S17/S18 exec records, the plan checkbox mutations
performed by the vault CLI, and the rebuilt feature index. The review checked
intent alignment with the accepted prorrata ADR, the period-revision carry rule,
the existing anti-tautology null-refusal proof, and the plan boundary that leaves
in-year apportionment to the next wave.

## Findings

No open findings.

## Recommendations

- Continue with `W03.P05.S19` for provisional apportionment in the shared aggregation path.
- Do not treat this narrow seed review as the campaign close honesty audit.

## S19 Review

Reviewed the `W03.P05.S19` implementation in the shared IVA ledger aggregation
path. The diff adds an internal `IvaLedgerProrrataApportionment` carrier, loads
the whole-entity active general register entry for the filing year, resolves the
already-declared domain precedence ladder, and applies the resulting percentage
only after `ledger_iva_aggregation` selector resolution. The binding-value
postprocess derives its target set from revision casillas whose section includes
`deducible` and whose binding selector fact is `iva_amount_sum`, so base bindings
and devengado reverse-charge bindings stay unapportioned while deducible reverse
charge and soportado/import cuota bindings are reduced. No new binding source
kind, resolver convention, validator convention, or registry selector shape was
introduced.

Findings: no open S19 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched aggregation files,
and the local IVA aggregation subset that does not load the full registry passed.
The broader registry-backed IVA tests currently fail before reaching this code on
unrelated Modelo 714 registry validation diagnostics.
