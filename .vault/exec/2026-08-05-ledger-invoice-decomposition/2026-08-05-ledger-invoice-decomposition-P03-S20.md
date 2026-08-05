---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3053092515439d2e9160b828f3438fefe0845345306cd94acb96e3b8291af2c3'
step_id: 'S20'
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
     The S20 and 2026-08-05-ledger-invoice-decomposition-plan placeholders are machine-filled by
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
     The Route received-invoice retencion into the existing per-perceptor store behind retenciones_aggregation, never a second parallel retencion path and ## Scope

- `src/cadrumo/application/aggregation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route received-invoice retencion into the existing per-perceptor store behind retenciones_aggregation, never a second parallel retencion path

## Scope

- `src/cadrumo/application/aggregation`

## Description

- Add `src/cadrumo/application/aggregation/_invoice_retencion.py` projecting a received invoice's declared retencion into the existing `RetencionObservation` type.
- Stamp the observation `payable_invoice`, already a canonical retenciones source kind, so the store needed no widening.
- Take the retencion scheme as a required declared argument rather than inferring it.
- Exclude and surface four cases instead of dropping them: an issued invoice, no declared retencion, a non-resident supplier, and an unresolved conversion.
- Return both outcome classes together from `route_invoice_retenciones` so a caller cannot persist what routed without holding what did not.
- Promote the six symbols into the package `__all__` in the same commit as the module.
- Add thirteen behavioural cases in `src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py`.

## Outcome

Landed as commit `3cb0d3c13c` (5 files, +544, 0 deletions).

Raw counts, serial runs (`-n 0`): `test_invoice_retencion_routing.py` 13 passed; the two new suites together 25 passed; `application/aggregation/tests` 563 passed with 7 deselected. Tree-wide collection clean at 20008 of 23888.

No second retencion path was created, which is the whole point of the step. The projection emits the same observation type the operator-declared path emits, and `test_routed_observations_aggregate_through_the_existing_modelo_111_path` drives the projected observations through the existing `aggregate_retenciones_111` to prove no new aggregator stands between the projection and the committed Modelo 111 rollups.

MEASURED before building: the per-perceptor store had exactly one producer, the operator through the `--retencion-observation` option on the aggregate CLI. No invoice or ledger projection into it existed, so this is new capacity rather than a duplicate.

## Notes

The retencion scheme is the reason this step could not be finished as a fully automatic pipeline, and the limit is legal rather than technical. Which clave a payment falls under, whether trabajo, actividades economicas, actividades profesionales or premios, is a fact about the perceptor's activity and not a property of the invoice. A received invoice from a professional distinguishes actividades profesionales from actividades economicas only through the supplier's IAE seccion, which no invoice field records, and the closed IRPF-category enum that would carry it is deferred to its own decision by the governing ADR's own operator questions. The scheme is therefore a required parameter. Inferring it would file a figure under a clave the taxpayer never asserted, the same class of fabrication the inversion prohibition forbids.

The non-resident-supplier exclusion is a judgement the operator may want to revisit. The retenedor obligation on payments to non-residents runs through the IRNR surface rather than the IRPF per-perceptor family this store feeds, so routing such an invoice into Modelo 111 would file it under a modelo that does not govern it. Exclusion is the conservative direction because it surfaces the invoice rather than mis-filing it, but the ADR expressly leaves the foreign-counterparty retencion expectation open pending LIRPF art. 99 and RIRPF art. 76 reaching the bundled corpus, so this is a defensible default rather than a settled ruling.

The peer's in-flight `IvaRetencionRole` enum in `src/cadrumo/domain/iva/_components.py` declares the same credit-versus-liability distinction this module routes on, from the per-category side. This module derives the role from the invoice kind directly, which is invariant across categories and stated in the ADR, so the two are not competing declarations of one fact. Once that work lands, a follow-up should confirm they agree rather than drift.
