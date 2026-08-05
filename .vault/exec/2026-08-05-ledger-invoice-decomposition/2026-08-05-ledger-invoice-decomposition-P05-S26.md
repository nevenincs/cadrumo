---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:03d0d6f830eaf30ade17844175e6b75d0acde7711cfa727761ea73410c5db312'
step_id: 'S26'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-invoice-decomposition with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Name the dropped retencion credit in the ungrounded advisory, not only the income mis-measurement, since the lost credit is the larger half of the harm and ## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Name the dropped retencion credit in the ungrounded advisory, not only the income mis-measurement, since the lost credit is the larger half of the harm

## Scope

- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Extend `_ungrounded_income_diagnostics` to name the dropped retención credit alongside the income mis-measurement, reusing the already-threaded row count and summed cash rather than deriving a second figure.
- Ground the added clause on the observed fact that every row this screen catches has grounding `CASH_FALLBACK`, and the withheld-amount inference refuses to run without the same missing `taxable_base`, so the ISSUED-side retención credit (RIRPF art. 110.3.a) is silently zero on the same rows.
- Shorten `_ungrounded_income_consequence`'s three branch strings to buy character headroom for the new clause, and measure the worst-case realised message against the diagnostic's own 512-character cap before landing, since the builder was already flagged as sharing a tight budget.
- Leave severity, the notice channel, the model's existing eliding validator, and truncation semantics untouched.

## Outcome

Landed the retención-credit clause in the same diagnostic the income mis-measurement clause already builds, so a single advisory now names both halves of the harm. Measured the realised message length across all three consequence branches at representative row counts and totals; worst case leaves over 150 characters of headroom under the 512 cap for the transaction-id sample, comfortably clear of the truncation floor.

Confirmed the role distinction before writing the text: every row this screen catches is the taxpayer's own issued-invoice income with no declared `taxable_base`, so the dropped credit is the ISSUED-side retención credit that already rides the renta income ledger (M130/M100 retenciones casilla), never the per-perceptor retenedor-liability store a received invoice routes into. The added clause and its docstring state this distinction explicitly; the code touches only `_modelo_bindings.py` and reads no per-perceptor store.

Test evidence: `test_renta_income_actividad_contract.py`, `test_cross_domain_invoice_scenario.py`, `test_advisory_message_constructibility.py`, `test_diagnostic_message_bound.py` -- 40 passed. Full `application/aggregation` suite -- 607 passed (2 serial-marked benchmark tests held, unrelated).

## Notes

The sibling Step P05.S22 was found already landed by a peer at HEAD before this Step began (binding-level reconciliation in `test_cross_domain_invoice_scenario.py`); no edit was made there and no exec record was authored for it under this Step.

The advisory message is not routed through the locale catalogue today -- it is a raw literal built in `_modelo_bindings.py`, matching every other message this same function already builds. No new locale keys were introduced; nothing here touches `src/cadrumo/locales/*.yml`.
