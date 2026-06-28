---
tags:
  - '#audit'
  - '#iva-live-reconciliation'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-wallet-live-history-code-review-audit]]'
  - '[[2026-05-19-live-iva-compensation-wallet-code-review-audit]]'
---

# `iva-live-reconciliation` Code Review

Status: REVISION PARTIALLY REMEDIATED; RESIDUAL REGISTRY/PROFILE VALIDATION ITEMS REMAIN QUEUED.

IVA-LIVE-001 | HIGH | Persisted blocked wallet decisions are not enforced by the normal Modelo 303 calculation path

`src/aeat/application/modelo/_actions.py:_apply_iva_compensation_decision_binding` returns immediately when `decision is None` at `src/aeat/application/modelo/_actions.py:933`, and `src/aeat/entrypoints/cli/_modelo.py:1259` calls `calculate_modelo_revision` without loading or passing the `IvaWalletDecisionRepository` decision persisted by the live wallet pull. The integration tests prove blocking only when a test manually supplies `iva_compensation_decision`, but the operator CLI can still calculate Modelo 303 with manual/local binding values and bypass a previously persisted `blocked=True` AEAT-wallet/local-recurrence divergence.

IVA-LIVE-002 | HIGH | Local recurrence failures are silently downgraded to wallet-only reconciliation

`src/aeat/application/calculations/_binding_prefill.py:162` catches every `Exception` from previous-filing binding resolution and returns an empty report at `src/aeat/application/calculations/_binding_prefill.py:174`. `src/aeat/application/calculations/_iva_wallet_reconciliation.py:130` then treats the missing binding as `local_recurrence_amount=None`, allowing `reconcile_iva_compensation_wallet` to select a fresh wallet as non-blocking `wallet_only` at `src/aeat/application/calculations/_iva_wallet_reconciliation.py:287`. A malformed filed observation, repository corruption, or registry selector drift can therefore erase the local cross-check instead of blocking review.

IVA-LIVE-003 | HIGH | Modelo 303 submitted-file fallback is not safely grounded or context-bound

`src/aeat/adapters/outbound/aeat/sede/_declarations.py:1261` bypasses registry export parsing for Modelo 303 when the snapshot has no export layout, then `_observed_modelo_303_casillas_from_submitted_file` decodes with replacement, finds the first `<T30303000>` tag, and reads hard-coded offsets for casillas `87`, `69`, and `71` at `src/aeat/adapters/outbound/aeat/sede/_declarations.py:1289`. That fallback never calls `_verify_submitted_file_context`, so it does not validate Modelo/year/period against the declaration row. The test at `src/aeat/adapters/outbound/aeat/sede/test_declarations.py:123` is synthetic and mirrors the same offsets in `_modelo_303_page_03_payload` at `src/aeat/adapters/outbound/aeat/sede/test_declarations.py:172`, so it does not ground the positions against a real AEAT submitted-file fixture or record-design parser.

IVA-LIVE-004 | HIGH | Lazy registry authority validation can hide cross-registry drift on calculation paths

`src/aeat/domain/calculations/registry/_authority.py:81` validates only the requested modelo before building a snapshot. That flows through `RegistryValidator.validate_modelo` at `src/aeat/domain/calculations/registry/_validate.py:244`, whose `_validate_modelo` path does not run relation closure, previous-filing binding closure, selector-shape, semantic-role consistency, or cross-revision drift checks; those are only in `validate_registry` at `src/aeat/domain/calculations/registry/_validate.py:298`. The live and calculation paths using `resources().modelos.authority.snapshot` can therefore run with a locally valid Modelo 303 while dangerous registry-wide drift remains invisible unless a separate full registry verification command was run.

IVA-LIVE-005 | MEDIUM | Wallet parser treats an unrecognized authenticated page as a valid zero-balance wallet

`src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py:117` scans for a table whose text contains broad header tokens. If none is found, `rows` remains empty, `total_pending` becomes `0`, and `parse_iva_compensation_wallet_html` returns an `IvaCompensationWalletObservation` at `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py:132`. A login interstitial, authorization error page, or AEAT DOM change can be persisted as a valid zero wallet and then become a non-blocking wallet-only decision when no local recurrence exists.

IVA-LIVE-006 | MEDIUM | CLI root/live activation accepts an active-profile token without validating the profile bucket

`src/aeat/entrypoints/cli/__init__.py:_activate_active_bucket_session` only checks that `resolve_active_bucket_id()` returns a string before installing the master-key provider at `src/aeat/entrypoints/cli/__init__.py:164`. `resolve_active_bucket_id` returns the environment override or pointer value without checking `read_profile_bucket` or the profile lifecycle record at `src/aeat/application/workflow/_models.py:189`, while `Settings._resolve_database_url_for_active_profile` creates a per-bucket database URL directly from that string at `src/aeat/core/config.py:875`. Live wallet and filed-history commands can therefore run under a stale or nonexistent active profile name instead of failing before auth/session acquisition and persistence.

Remediation log:

IVA-LIVE-001 | FIXED | Persisted blocked wallet decisions are replayed by calculation

`calculate_modelo_revision` now loads a persisted Modelo 303 IVA wallet decision for the work unit bucket's `identity.tax_id` when the caller did not pass one explicitly. A blocked decision is therefore enforced by the backend calculation path, including the normal CLI path. Covered by `test_persisted_blocked_wallet_decision_is_replayed_by_modelo_303_calculation`.

IVA-LIVE-002 | FIXED | Local recurrence resolver failures now remain hard failures

`resolve_bindings_from_local_store` no longer catches every previous-filing resolution exception and returns an empty binding report. A malformed or incomplete prior Modelo 303 observation now raises instead of downgrading reconciliation to wallet-only. Covered by `test_binding_prefill_refuses_incomplete_prior_filing_observation`.

IVA-LIVE-003 | PARTIAL FIX | Modelo 303 submitted-file fallback validates page-03 record shape

The fallback now requires a complete official page-03 fixed-width record and validates the `</T30303000>` footer before reading casillas `87`, `69`, and `71`. This does not yet replace the synthetic parser fixture with a sanitized live submitted-file fixture; that grounding task remains queued.

IVA-LIVE-005 | FIXED | Unrecognized wallet pages are rejected

`parse_iva_compensation_wallet_html` now raises when the captured page does not contain a recognizable IVA compensation wallet table. Empty recognized wallet tables still produce a valid zero-balance observation. Covered by `test_parse_iva_compensation_wallet_html_refuses_unrecognized_page`.

Residual queue:

IVA-LIVE-004 remains open for a separate registry-validation design decision: live IVA should not be blocked by unrelated Modelo 100/123 registry drift, but selected-model snapshots need an explicit dependency-closure validation mode rather than silently relying on full-registry CI.

IVA-LIVE-006 remains open for profile lifecycle repair: CLI live activation should distinguish an active bucket pointer from a valid profile record without regressing live auth flows for already-provisioned buckets.
