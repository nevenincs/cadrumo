---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e2528e63cdb9187a6d4cc0fa2a36a8aa7e27f2883f9412e3fef4a1e2d822a309'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
## Scope

Independent close-out review of `W04.P07.S27`, "Prove calculate verify and file negative-recovery-retry journeys", under the accepted `cli-action-envelope-hardening` architecture. The review covers the current installed-console evidence, locale-neutral response structure, public-facade test boundary, canonical action/failure ownership, and the honest disposition of `operator.registry.verify`.

## Findings

### PASS â€” four stable public-production installed-console journeys

| Journey | Observed canonical action or outcome | Stable serial result |
| --- | --- | --- |
| Verify after no calculation | `operator.modelo.work.calculate`, then schema-derived calculate and retry verify | PASS, `-n 0 -m integration`, 61.45 s; verification persisted. |
| File after no calculation and then unverified calculation | Calculate followed by `operator.modelo.work.verify`; file retry after both actions | PASS, 99.26 s; filing persisted. The unverified refusal structure was equal in en, es, ca, and hu apart from rendered message. |
| M202 required bindings | `operator.modelo.bindings.list`; discovery action succeeds but retry remains honestly refused with state unchanged | PASS, 57.85 s. |
| Discarded work terminal matrix | Action null and terminal no-recovery outcome for calculate, verify, and file in en, es, ca, and hu | PASS, 170.73 s across 24 installed-console invocations; retries preserve both terminal response and state. |

Collection found exactly these four real integration journeys in `src/cadrumo/entrypoints/cli/tests/test_modelo_action_recovery.py`.

### PASS â€” public-facade and canonical ownership boundary

The review removed the synthetic registry-unavailable test setup. It had imported private precondition code and direct persistence repositories to manufacture an unregistered M999 work/revision. The current journey test observes persisted state through public `application.modelo.get_work_unit` and imports SQL engine disposal only through the public storage-SQL facade. It contains no private precondition import, repository import, engine-module import, or constructed action/failure.

Fixed-point checks found one production declaration of `operator.modelo.work.verify` in `src/cadrumo/application/operator_actions/_catalogue.py`; Modelo profiles reference it. The shared unverified-file failure factory is defined once in `src/cadrumo/application/modelo/_preconditions.py` and has two production consumers only: `_filing_actions.py` and `_work_addressing.py`. No redeclared S27 action or failure capability was found.

Semantic code search for `canonical locale-neutral action envelope schema-derived recovery chains precondition refusal only:prod exclude:tests` located the Modelo precondition authority and common action renderer. The paired Vault search for `canonical action envelopes CLI preconditions recovery localisation architecture decision status:accepted` located the accepted ADR, plan, reference, and prior campaign audits.

Scoped Ruff, format, basedpyright, and `git diff --check` checks passed. The four selectors each passed after the public-facade remediation on the same stable tree.

### PASS with carried structural-only disposition â€” `operator.registry.verify`

`operator.registry.verify` is non-executable through public production setup. Public work lifecycle operations correctly reject unregistered modelo, revision, or period coordinates before persistence. The removed private-repository seed was therefore not valid journey evidence; no real registry recovery journey is claimed.

Existing producer/action-schema coverage remains in `src/cadrumo/application/modelo/tests/test_actions.py`, `src/cadrumo/application/modelo/tests/test_verification_preconditions.py`, `src/cadrumo/application/modelo/tests/test_s24_precondition_campaign.py`, and `src/cadrumo/entrypoints/cli/tests/test_modelo_verification_report_view.py`.

## Recommendations

Close S27: its required public-production negative-recovery-retry proof is now complete and independently reviewed PASS.

Carry the `operator.registry.verify` classification to W06 runtime-matrix closure as `non-executable through public production setup`, with its lifecycle-rejection invariant and cited structural producer/schema coverage. It remains structural-only unless a future public, product-valid setup capability can represent unavailable registry state. Do not add a test-only public seed, adapter export, or private persistence route. If such a capability is never introduced, preserve the row as permanently non-executable by design.
