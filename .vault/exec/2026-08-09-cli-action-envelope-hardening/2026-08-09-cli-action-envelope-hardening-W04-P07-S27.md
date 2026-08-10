---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e18521cbc9d97c5ada24fddc465966503f9b1b5caa94f4f4cfe1a17f2a57240d'
step_id: 'S27'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
## Description

S27 remains open while its review boundary is resolved. The record captures only public-production installed-console journeys for the canonical Modelo precondition action chain. It does not close the plan Step, create a final audit, or claim an unreproducible state as an end-to-end journey.

## Outcome

### Public-production journey matrix

| Journey | Public setup and received action | Schema-derived dispatch and retry | Result |
| --- | --- | --- | --- |
| Verify after no calculation | Natural profile; M111 2026 2T work with a real retenciÃ³n observation; `modelo.work.verify` refuses with `operator.modelo.work.calculate`. | The action's live input schema produced the installed-console argv; calculate then retry verify. | Verification persisted; selector passed serial `-n 0` in 61.45 s. |
| File after no calculation, then unverified calculation | Same real M111 work; file first returns calculate, then returns `operator.modelo.work.verify` after calculate. | Live schemas dispatched calculate then verify; file retried. The unverified refusal DTO was observed in en, es, ca, and hu before verify. | Filing persisted; selector passed serial `-n 0` in 99.26 s. |
| Required bindings are decision support | Legal profile; M202 2026 1P calculate refuses with `operator.modelo.bindings.list`. | The received discovery action ran through its live schema; retry deliberately remained refused because the operator still had not supplied required facts. | State stayed unchanged and the same action recurred; selector passed serial `-n 0` in 57.85 s. |
| Discarded work is terminal | A real M111 work unit was discarded through the installed console. | Calculate, verify, and file were each retried in en, es, ca, and hu. | Every refusal carried action null and terminal no-recovery outcome; state was unchanged across the 24 console invocations; selector passed serial `-n 0` in 170.73 s. |
| `operator.registry.verify` | **Non-executable through public production setup.** Public work lifecycle operations reject unregistered modelo, revision, and period coordinates before persistence. | No action was dispatched and no retry is claimed. The former private-repository seed that manufactured persisted M999 state was removed. | Existing producer and schema coverage remains in `src/cadrumo/application/modelo/tests/test_actions.py`, `src/cadrumo/application/modelo/tests/test_verification_preconditions.py`, `src/cadrumo/application/modelo/tests/test_s24_precondition_campaign.py`, and `src/cadrumo/entrypoints/cli/tests/test_modelo_verification_report_view.py`. |

The registry row is conditionally deferred, not silently omitted: it remains structural-only unless a future public, product-valid setup capability can represent an unavailable registry state. No test-only public seed, adapter export, or private persistence path will be added. If no such production capability is introduced, that row remains permanently non-executable by design.

### Canonical-source and drift evidence

- Semantic code search used `canonical locale-neutral action envelope schema-derived recovery chains precondition refusal only:prod exclude:tests`; it returned the locale-neutral Modelo precondition owner and the shared resolved-action renderer. The paired Vault query, `canonical action envelopes CLI preconditions recovery localisation architecture decision status:accepted`, returned the accepted CLI action-envelope ADR, campaign plan, reference, and prior audits.
- Fixed-point exact scans found one production declaration of `operator.modelo.work.verify` in `src/cadrumo/application/operator_actions/_catalogue.py`; the Modelo precondition profile references that action rather than redeclaring it.
- The unverified-file failure factory is defined once in `src/cadrumo/application/modelo/_preconditions.py` and has exactly two production consumers: `src/cadrumo/application/modelo/_filing_actions.py` and `src/cadrumo/application/modelo/_work_addressing.py`.
- The post-review test imports only public facades for state inspection. There are no private precondition imports, private persistence repository imports, adapter-engine-module imports, or synthetic action/failure construction in `src/cadrumo/entrypoints/cli/tests/test_modelo_action_recovery.py`.

## Notes

Scoped post-review checks passed: Ruff, Ruff format, and basedpyright reported no errors or warnings; `git diff --check` passed. Collection found exactly the four real integration journeys. Each was rerun individually through the installed `aeat.exe` console with `-n 0 -m integration`.

The plan remains open at `W04.P07.S27`; this is evidence for continued review, not Step completion. No final audit was created.
