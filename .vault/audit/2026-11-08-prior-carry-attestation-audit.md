---
tags:
  - '#audit'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:f93aa40d964ba770cc97d9f842ed4f8802eadf6641fd69dc3eb7f8c88fb36bb4'
related:
  - "[[2026-11-08-prior-carry-attestation-plan]]"
---

# `prior-carry-attestation` audit: `prior-carry attestation plan close review`

## Scope

Plan-close review of `2026-11-08-prior-carry-attestation-plan` Steps S01 to S05, commits `a80f488943` to `c73a6702bd` on `renta/d33-m100-carry`, against `2026-11-08-prior-carry-attestation-adr`. Independent read-only reviewer; verdict FAIL. Findings below are as reported; each needs current-code verification before it is treated as settled.

## Findings

### attestation-scope | critical | The statement is admitted and served on every modelo's earlier-filing decimal bindings with Modelo 100 art. 50.3 words

`src/cadrumo/application/modelo/edit_admission.py:237` admits `ATTEST_NO_AMOUNT` on any writable decimal `previous_filing` binding, and `src/cadrumo/application/modelo/work_form_carry_attestation.py:36` offers it for each such binding holding no value, with no carry-family scoping, while the served words cite Ley 35/2006 art. 50.3. Measured: a Modelo 130 2026 1T form serves it for `irpf.previous_year_economic_activity_net_income`, `modelo-130-pagos-fraccionados-anteriores` and `modelo-130-resultados-negativos-anteriores`; applying it moves casilla 13 from unresolved to 100.00, asserting a prior-year net income of zero and granting the RD 439/2007 art. 110.3.c minoración. A Modelo 303 form serves it for `modelo-303-compensacion-pendiente-anteriores`. Reopens S01 and S03.

### attested-provenance | high | The statement is invisible on every read surface

Only the edit executor and the replay chain read `attested_binding_ids`; the served form for an attested Modelo 100 and for the same carries typed as zero differ only in the revision id, so no field origin, note or verification finding shows the statement. The resolution-and-verification bullet of the ADR is unimplemented and S02 closed on tests alone. Reopens S02 and S03.

### decision-reconciliation | medium | `2026-08-24-modelo-edit-contract-adr` still enumerates two binding intent kinds

The attestation ADR amends its D4, but that record still names only `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE`. The amendment is to be presented for authorization and applied.

### window-carry-selection | medium | The window narrowed the served statement to the carries it had placed

`native/desktop/frontend/src/components/modelo/form/session.ts` computed the stated condition over placed fields only, hiding the offer while a served carry stayed open. Fixed in `f55e0c3b01`: the offer stands until every served binding is staged as stated.

### staged-statement-rebase | low | A staged statement survived a rebase that resolved the carry

Fixed in `f55e0c3b01`: a restage drops the statement once the carry's box reads as imported.

### contract-docstring | low | The binding intent docstring named only one value-free kind

Fixed in `f55e0c3b01` at `src/cadrumo/application/modelo/edit_models.py:790`.

### review-effect-words | low | Each staged statement showed the whole statement paragraph as its review effect

`native/desktop/frontend/src/components/modelo/dialogs/ReviewDialog.tsx:54` renders the full served statement once per staged carry. Open; to be served as a short per-edit effect phrase with the family words.

## Recommendations

- attestation-scope: the carry family that may take the statement, and the words it serves, are to be declared in the registry on the binding rather than inferred from source kind or listed in Python. This needs coordinator approval as a registry data change; a follow-on amendment to `2026-11-08-prior-carry-attestation-adr` names the declaration.
- attested-provenance: surface the statement on the carry's form field with served words, keyed to the same family declaration, and re-pin it in the S02 test.
- decision-reconciliation: present the D4 amendment of `2026-08-24-modelo-edit-contract-adr` naming the third intent kind and its admission condition.
