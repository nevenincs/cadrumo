---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a1c25267957911292fb50e38f39fa7f8c3b6b7c9f65cca5b4131720cc22ddcb1'
step_id: 'S19'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Express Nota 3, the rectificativa case the account-page guard structurally cannot see. CAPABILITY gap in the predicate's inputs, NOT a threshold to widen, and it MUST NOT be fixed by adding dispositions to the account-bearing set because the rule is not about the disposition at all. Nota 3 of the bundled diseno states that a rectificativa whose casilla 111 has content must carry bank data even when the payment form is not devolucion, except where the page-3 domiciliacion-cancellation field is marked. The guard reads only the declaration_type header, so it sees neither casilla 111 nor that marker and cannot express the rule in any form. Threading already established, so this does not need discovery. Both production call sites hold a draft. rendered_casilla_ids and assert_export_mirrors_manifest each take draft, and the renderer builds casilla_values from draft.values two lines above its suppression call. What needs widening is boe_representable_casilla_ids, which takes only layout, headers and schema_provider, plus roughly thirteen test call sites. The inputs MUST reach BOTH sides rather than the renderer alone, because the shared predicate exists so the renderer and the parity assertions cannot disagree about what reaches disk, and fixing one side reintroduces exactly that class of defect. Gate. A rectificativa with casilla 111 populated and the cancellation marker unset carries the account page on a non-devolucion payment form, the same filing with the marker set does not, an ordinary non-rectificativa filing is unchanged, and the renderer and the parity derivation agree on all three

## Scope

- `src/cadrumo/application/filing`
- `src/cadrumo/application/modelo`
- focused filing and modelo export regressions

## Description

- Define the shared DID requirement as the current account-bearing disposition
  or the typed M303 Nota-3 rectificativa condition.
- Thread the draft and prior-domiciliation election through rendering, BOE
  representability, rendered-set, manifest, and record-order parity paths.
- Compose the full refund destination for the additional Nota-3-only C path
  before output or event persistence, while retaining the existing U sign gate.
- Add real public export and dual-layout regressions for KEEP/X, c111 zero,
  distinct refund and charge accounts, and pre-write missing-account refusal.
- Align the neighboring M303 round-trip fixture and rectificativa byte check
  with the resolved registry revision rather than stale 2023 coordinates.

## Outcome

The single predicate now retains the DID page for D/V/X/U independently of
the prior-domiciliation election and additionally retains it for a
rectificativa C with casilla 111 content and KEEP. CANCEL_OR_MODIFY suppresses
only that additional Nota-3 page. The public C path uses RefundAccount, rejects
missing refund data before a temporary file or exported event, and never
substitutes ChargeAccount. S19's independent formal review approved the result
without findings.

## Verification

`uv run --no-sync pytest src/cadrumo/application/filing/tests/test_did_page_bank_account_dispositions.py src/cadrumo/application/filing/tests/test_export_completeness_sets.py src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/application/modelo/tests/test_export_rectificativa.py src/cadrumo/application/modelo/tests/test_export_refund_did.py src/cadrumo/application/modelo/tests/test_export_result_disposition.py src/cadrumo/application/modelo/tests/test_prior_domiciliation_election.py src/cadrumo/application/modelo/tests/test_prior_domiciliation_export_layout.py`

`94 passed in 25.18s`

`uv run --no-sync ruff check src/cadrumo/application/filing/_export.py src/cadrumo/application/filing/_export_parity.py src/cadrumo/application/modelo/_export.py src/cadrumo/application/filing/tests/_export_support.py src/cadrumo/application/filing/tests/test_did_page_bank_account_dispositions.py src/cadrumo/application/filing/tests/test_export_completeness_sets.py src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py src/cadrumo/application/modelo/tests/_export_modelo_303_support.py src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/application/modelo/tests/test_export_rectificativa.py src/cadrumo/application/modelo/tests/test_prior_domiciliation_export_layout.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/filing/_export.py src/cadrumo/application/filing/_export_parity.py src/cadrumo/application/modelo/_export.py`

`0 errors, 0 warnings, 0 notes`

`git diff --check -- <S19 production and focused test paths>`

`clean; Git emitted only a non-failing CRLF-normalization warning for _export_parity.py`

## Notes

The first `vaultspec-core vault add exec` invocation completed its filesystem
write but exceeded the command-response window. A subsequent read confirmed
the canonical S19 record exists; its retry correctly refused to overwrite it.
No source, Git, account, or event data was lost or changed by that incident.
