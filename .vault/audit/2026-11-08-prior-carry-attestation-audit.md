---
tags:
  - '#audit'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-09'
body_schema: 'body-v2'
body_hash: 'sha256:152782379f6defe17f6a51fdacb38ee7f506fb9df8a57e6327a16eb82a9e0174'
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

## Resolutions

Recorded on `renta/d33-m100-carry` after the coordinator approved the registry declaration on 2026-11-08. Each needs re-review before it is treated as settled.

- attestation-scope: resolved by a registry declaration. `absence_attestation` on the binding names a closed family, validated as a decimal earlier-filing carry. Admission (`src/cadrumo/application/modelo/edit_admission.py`) and the form action (`src/cadrumo/application/modelo/work_form_carry_attestation.py`) read only that declaration, and the action's words are served per family. Pinned by `src/cadrumo/entrypoints/tests/profile_persistence/test_m100_carry_attestation.py` (Modelo 130 and 303 are offered nothing) and `src/cadrumo/domain/calculations/registry/tests/test_binding_absence_attestation.py`, both for every envelope year.
- attested-provenance: resolved. An attested carry's field serves `stated_absent` and its family's origin words (`src/cadrumo/application/modelo/work_form_field_projection.py`, `src/cadrumo/application/modelo/work_form_wording.py`). A typed zero serves neither; the same test file pins this for every Modelo 100 envelope year.
- review-effect-words: resolved. Each staged statement shows its family's served effect words.
- decision-reconciliation: open. The D4 amendment of `2026-08-24-modelo-edit-contract-adr` awaits authorization. `2026-11-08-prior-carry-attestation-adr` now names the registry declaration.

## Re-review 2026-11-08

Independent read-only re-review of `f12fa675a4` and `913990e6ce`: verdict PASS. The attestation-scope, attested-provenance and review-effect-words findings are closed. New findings below, each needing current-code verification.

### locale-key-fanout | medium | A second declared family without words would make the whole work form fail to load

The per-family locale-key maps in `src/cadrumo/application/modelo/work_form_carry_attestation.py` and `src/cadrumo/application/modelo/work_form_wording.py` were unguarded subscripts. Resolved in the follow-up commit: each map is checked at import against every `AbsenceAttestationFamily` member. `src/cadrumo/application/modelo/tests/test_work_form_carry_attestation_words.py` pins authored, distinct words for each family in every output language. The maps stay string-valued dict literals, because the locale key scanner confirms only those.

### attested-resolution-provenance | medium | The statement is visible only on the work form

The ADR's resolution-and-verification bullet says the earlier-filing resolver states an attested carry as attested by the filer. No resolver provenance, source diagnostic or verification finding reads `attested_binding_ids` yet (`src/cadrumo/application/modelo/calculation_bucket_actions.py:666`), so a verification report or calculation projection shows casilla 1380 as `0` either way. Open. Either implement that provenance, or the ADR bullet and the docstring at `src/cadrumo/domain/modelos/calculation_revision_operator_layer.py:21` are narrowed; the choice is the coordinator's.

### carry-row-first-binding | low | The field statement reads only a box's first binding

`src/cadrumo/application/modelo/work_form_field_projection.py:101` reads `row.concrete_bindings[:1]`. Each of the four carries owns its box one to one today, so there is no current effect. Recorded.

### submitted-baseline-scope | low | The registry declaration gates the offer, not a forged submitted surface

`reconfirm_modelo_edit_baseline` does not re-derive the permitted surface, so a fabricated surface entry could attest a non-declared binding. This is the pre-existing trust posture for every intent kind. `SET_OVERRIDE_VALUE` already admits a typed `0` there, so the change adds no financial exposure. Recorded.

### validator-non-decimal-prong | low | The validator's non-decimal branch was untested

Resolved in the follow-up commit: `src/cadrumo/domain/calculations/registry/tests/test_binding_absence_attestation.py` refuses the statement on an earlier-filing read typed as an integer, which validates without it, for every envelope year.

### wire-type-staleness-gate | low | The regenerated window types were not checked by their staleness gate

`node scripts/modelo-fixtures.mjs --check` and the window spec need `node_modules`, which this worktree lacks. Owner DESKTOP. The generated types correspond to the Python models by inspection.
