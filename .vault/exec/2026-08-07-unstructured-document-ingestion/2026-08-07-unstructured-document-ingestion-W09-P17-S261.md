---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:4d3589e6097ac5252710f0c692b4a971bed6e8da76cd3919b5dde4405ee759aa'
step_id: 'S261'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Rule the two empty-container surfaces, and open what the ruling creates

## Scope

- `src/cadrumo/application/modelo`

## Description

- Refuse to answer the row as one question. It asks for a single ruling over two surfaces, and the two do not share an answer, which is why it had sat unresolved.
- Name the discriminator that separates a silent zero from capacity built ahead of a producer: is the empty container CONSUMED by a live path that produces a declarable number.
- Measure each surface against it, from the consumer side rather than from the symbol.
- Rule each, then open the implementing rows in the SAME action, because a ruling on code is not self-executing.

## Outcome

**Modelo 131 agrario — a real gap wrapped around a correct rule.** Nothing in production writes the activity type. Zero writes outside tests, no CLI, no importer, no adapter, while the renta income ledger reads it on the live path and a registry binding folds the result into a casilla. So an agrarian filer's volumen resolves to zero and nothing tells them.

The exclusion itself is right, and the binding's own comment reasons it out: a row with no declared activity must not enter, because silence cannot mean agrarian and admitting it would route a NON-agrarian filer's income into an agrarian casilla. That is the over-declaration error, and the author chose the fail-safe direction deliberately. So this is not a wrong rule. It is a correct rule with no channel for the operator to satisfy its antecedent.

**The obvious remedy was wrong, and I recommended it before measuring.** Building an operator capture surface against the transaction field would mint the producer for a shape the accepted design REJECTS: the activity type is a fact recorded per activity slot, so it belongs on a per-activity profile row with the transaction carrying a reference. What shipped is the value on the row, knowingly, as an interim, because no profile row exists and waiting would have blocked the aggregation behind unbuilt infrastructure — and a shipped gate stands as a tripwire for the moment a second home appears. Building the capture now would have made that dated hazard land sooner and with more data behind it.

So the ruling splits: advisory NOW, capture DEFERRED with a named release condition.

**Modelo 720 — the row's premise is false, and so was my first reading of it.** The redeclaration advisory is NOT dormant. It is wired to the live verify path through the application-layer gate, carries an end-to-end test, and guards a real silent-omission case: an already-declared foreign-asset bloque whose valuation grows past the re-declaration delta and is then omitted cannot be noticed by any formula, total or export gate, because the omitted row simply is not there.

I first reported it as exported-with-no-caller. That was wrong, and wrong the same way twice more today: I searched for the calculations-layer symbol, found no hits outside tests, and concluded absence — without following the wrapper one layer out to the gate that calls it and the verify path that calls the gate. A symbol sweep answers who NAMES an identifier, never whether a capability is REACHED.

**What is excluded.** This record rules; it implements nothing. The advisory, the deferred capture and the surviving M720 data question are opened as their own rows in the same action, so the debt this ruling creates has an owner and a row rather than living in prose. The M720 question that survives is narrower than the row asked: not whether the advisory is wired, but whether its input collection is ever non-empty on a real verify run — and that must be measured on a live path, since reading imports is what produced the wrong answer the first time.

## Verification

Measured at HEAD, from the consumer side:

    tipo_actividad read on the live path   application/aggregation/_renta_income_ledger.py:658
    folded into a casilla                  registry modelos/131/revisions/2026/bindings/0002-m131-volumen-agrario.toml
    written in production                  nowhere; matches only under tests/
    accepted design and its tripwire       src/cadrumo/tests/test_tipo_actividad_single_home.py

    M720 advisory gate                     application/modelo/_m720_redeclaration_gate.py
    called by the live verify path         application/modelo/_verification_actions.py
    end-to-end coverage                    application/modelo/tests/test_modelo_720_redeclaration_e2e.py

No gate run requested: this row rules and changes no code.

## Notes

Three inference errors in one session, all the same move, and this row carries two of them. The repeating shape is worth more than the ruling: grep a symbol, find no hits outside tests, conclude the capability is absent. Zero callers of a symbol is evidence about the symbol.

The ruling was reached by asking the discriminator question of each surface separately rather than looking for one answer that covered both. The row could not be closed for as long as it was read as one question, and that is what kept it open.
