---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-07-17'
body_hash: 'sha256:afb24fb81ed51f19f27be0ca5be938d670c4fa0b51827c5b9fd7b05bfc5619c3'
step_id: S83
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P22.S83

## Outcome

Created `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0003-m130-income-cumulative.toml`:

```
id = "modelo-130-actividad-economica-ingresos-cumulative"
source = "ledger_renta_income_aggregation"
selector = { modelo = "130", target_casilla = "01", fact = "gross_income_sum" }
aggregation = { op = "sum" }
```

Legal refs and source refs follow the established M130 revision pattern. A
`source_citations` block cites `aeat-modelo-130-instructions` with `required_text`
anchoring on `"Ingresos"`. Registry validation passes with no failures.

## Commit

`3fe34b561` — S83+S84: register M130 income binding + wire casilla 01 to ledger aggregation
