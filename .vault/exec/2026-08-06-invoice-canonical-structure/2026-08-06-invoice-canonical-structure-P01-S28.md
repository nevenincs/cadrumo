---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:8a460f076ca781356f409ef2d48eaf968a01a6390fb9b342290fa4afddcbde56'
step_id: 'S28'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Produce the three-lane capability inventory covering income, business operations and purchase evidence, listing for BOTH stores every field, validator, CLI verb, downstream binding and persistence or custody behaviour, each with its named canonical replacement and the test that proves it, and scoping the field comparison to a per-axis diff of DEFAULTS AND NULLABILITY rather than field presence, because an axis that routes a filing can be permissive on the canonical side and strict on the slim side, which converts a loud failure into a quiet wrong answer and is invisible to a field-list inventory, treating any entry with no named replacement as a blocker on the fold rather than a waiver

## Scope

- `src/cadrumo/application/ledger/_business_operation_invoice.py`

## Description

- Assembled the three-lane inventory from the measurements taken across this phase rather than from a fresh sweep, since each row's proof already exists as an executed gate.
- Scoped the field comparison to defaults and nullability per axis, as this Step was rescoped to require, rather than to field presence.
- Confirmed the two outstanding gaps still hold at `HEAD` before concluding.
- Exercised this Step's standing authority to rule on whether the fold is ready.

## Outcome

**Ruling: the fold is NOT ready. Two rows have no passing proof, and both are conservation gaps rather than polish.** This Step carries standing authority to reach that conclusion, and the plan's whole-plan gate makes it binding: no `P03` Step opens until every row across all three lanes has a named replacement and a passing proof.

### Lane 1 - business operations (M347, M349)

| Capability | Canonical replacement | Proof |
|---|---|---|
| Party tax id, country, date, base, invoice total, clave, legal name | Same seven facts on the canonical projection | `S01`, fact-level, both modelos |
| EU party identity for a counterparty holding a domestic NIF and an EU VAT ID | Structural: a non-domestic country forces the tax id to BE that country's NIF-IVA | `S01` + `S02` refusal proof |
| Country derived from an EU VAT-ID prefix | Operator states it; the canonical entry verbs now require it | `S36` refusal + positive control |
| Bucket attribution | Unattributed records declare; only a populated mismatch excludes | `S35` + cross-bucket control |
| Direction axis on the shared observation | Required, no default | `S09` |
| Per-party rollup, declaration floor | Unchanged - the resolver is shared | existing M347 coverage |

### Lane 2 - income (renta sales evidence)

| Capability | Canonical replacement | Proof |
|---|---|---|
| Decomposition into typed components | Canonical-only contract, unchanged by the fold | existing decomposition coverage |
| Grounded IVA treatment | Canonical records carry an IVA category; ex-slim ones cannot | **`S33`, NOT YET RUN** |

### Lane 3 - purchase evidence

| Capability | Canonical replacement | Proof |
|---|---|---|
| Evidence bytes, attachment custody | Untouched by the fold - a separate store | existing custody coverage |
| Confirm-boundary override set | Widened | **`S26`, NOT YET RUN** |
| Profile export/import carry | Namespace already registered with structured custody | **`S29` strengthens a weak proof, NOT YET RUN** |

### Cross-lane

| Capability | Canonical replacement | Proof |
|---|---|---|
| Record lifecycle timestamps | Carried, optional, outside identity | `S10` roundtrip + anti-tautology |
| Unrepresentable record shapes | Refuse loudly per class | `S08`, seven classes |
| **Bucket lifecycle events (six types) and the operator's event ids** | **NONE** | **`S37` - no canonical emitter exists** |
| **Invoice class, series, rectifies-number, recargo on the writer** | **NONE** | **`S30` - confirmed absent at `HEAD`** |

### The two blocking rows

**`S37` - no canonical lifecycle events.** The slim services emit six dedicated event types on create, update and remove and return their ids in the operator's mutation result. The canonical write paths emit nothing. Repointing the bare verbs would drop the invoice audit trail and the event-ids field in one change, and deleting the slim store would orphan six enum members. This row has no replacement at all, which is the definition of a blocker under this plan's law.

**`S30` - the writer cannot reach what the aggregate already models.** Re-confirmed absent at `HEAD`: no invoice-class, series, rectifies-number or recargo parameter exists on the canonical construction path, so every canonically-written invoice is an ordinary invoice with no series and no recargo **by construction**, and a rectificativa is unrepresentable. Folding the operator surface onto an aggregate that cannot express a rectificativa is a capability loss on its face.

### What this ruling does not say

It does not say the fold is wrong or that the campaign should stop. Seven rows are proven and the two most feared axes — declarable coverage and EU party identity — came back **conserved**, one of them structurally. The ruling is narrow: two named rows, each with a named Step, and `P03` opens when they close.

## Verification

This Step is closed by a complete artefact rather than by a green assertion, so its evidence is the proof column above. Each cited Step's own record carries its quoted runner output.

The two blocking rows were re-confirmed at `HEAD` rather than carried forward from an earlier reading:

    rg -n "invoice_class|series|recargo_amount|rectifies_invoice_number" application/invoices/_creation.py
    (no matches - S30 gap holds)

    rg -n "BucketEventType|append_event|record_event|bucket_event" application/invoices/{_creation,_lifecycle,_linking,_bulk_import}.py
    (no matches - S37 gap holds)

A row whose proof column names a Step that has not run is marked as such rather than counted. Counting an unrun proof is how a conservation gate certifies a loss.

## Notes

**The rescope to defaults and nullability earned its place.** Three rows in this inventory are invisible to a field-presence comparison, because both stores carry the field and the incompatibility lives in the cross-field rule or the default that only one side has: the bucket attribution filter, the counterparty country default, and the tax-id/country coupling. A field-list inventory would have reported parity on all three and cleared the fold.

**Two rows came back as capability GAINS, which the inventory records rather than glossing.** The canonical model refuses shapes the slim model accepts — an internally inconsistent tax-id/country pairing, non-reconciling totals — and represents one the slim model cannot, the factura simplificada. A conservation inventory that only looks for losses would have missed that the fold also narrows a too-permissive input contract, which is part of why it is worth doing.

**Lane 2 and lane 3 rows are marked unrun rather than assumed.** Their Steps exist and are scheduled; nothing here claims they will fail. But an inventory whose purpose is to gate a deletion cannot count a proof that has not executed, and the plan says so explicitly.
