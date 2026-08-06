---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:0f9a85a6e7e7a40ae262869f6ab36aadb0d484b151635eced452ab734b60b905'
step_id: 'S41'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Let the invoice record its fecha de operacion, so the art. 75 devengo date has an authoritative source instead of the issue-date proxy

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Add an `InvoiceOperationDateRole` enum (`OPERATION_PERFORMED`, `ADVANCE_PAYMENT_RECEIVED`) to `_enums.py`.
- Add `operation_date: date | None` and `operation_date_role: InvoiceOperationDateRole | None` to `Invoice`, as ONE field pair rather than two date fields, matching art. 6.1.i treating both clauses as one datum.
- Add a model validator refusing a date recorded without its role, and a role recorded without its date.
- Normalise `operation_date` (ISO-8601 coercion) and `operation_date_role` (enum coercion) at the same `mode="before"` boundary the other typed fields use.

## Outcome

Landed as commit `1751ce04cf` (combined with P06.S42-S45; see Notes).

An invoice can now state the fecha de operación distinct from the issue date, naming which of art. 6.1.i's two clauses (operation performed vs. advance payment received) the date answers. An invoice with no such fact keeps `operation_date` and `operation_date_role` both `None`, unchanged from before this Step.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_invoice_operation_date.py -n 0 -q --no-header
5 passed in 2.47s
```

```
uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/aggregation src/cadrumo/application/invoices src/cadrumo/application/ledger src/cadrumo/entrypoints/cli src/cadrumo/domain/iva src/cadrumo/domain/transactions -n auto -q --no-header
2743 passed in 64.42s
```

Mutation-proof: removing the all-or-nothing pairing check (`if (self.operation_date is None) != (self.operation_date_role is None): raise ...`) reddens exactly `test_a_date_without_a_role_is_refused` and `test_a_role_without_a_date_is_refused` (2 failed, 3 passed), nothing else. `_models.py` restored byte-exact afterwards, verified by SHA-256 match against the pre-mutation copy.

## Notes

**Landed together with P06.S42-S45.** All five Steps touch the same `Invoice` model's identity/validator block in an interleaved way and were executed as one continuous pass per the dispatching brief's explicit instruction to do them "sequentially in one pass, not in parallel." Splitting the single edit session into five separate commits after the fact would have meant reconstructing five artificial file states via hunk surgery with no corresponding real intermediate state; one commit covering all five Steps is the honest representation of how the work was actually done. Each Step's own guard is independently mutation-proven (see Verification) so completion is not resting on the shared commit alone.

**Two downstream ripples absorbed, outside the named Scope.** Making `Invoice.counterparty_tax_id` optional (P06.S44) would have crashed two existing consumers that assumed it was always a `str`: `application/invoices/_source_resolver.py`'s M347/M349 projection (now skips an untagged invoice instead of raising) and the CLI catalogue-invoice payload (`entrypoints/cli/_ledger_catalogue_invoice_payloads.py`, widened to `str | None`). Both are one-line-scale, behaviour-preserving fixes for a regression this Step's own change would otherwise have introduced; left unfixed they are `no-in-scope-regression` violations, not separate work.

**Incidental fix: `recargo_amount` was missing from the strict-mode JSON coercion loop.** Extending that loop for `suplido_amount` (P06.S42) surfaced that `recargo_amount` (landed in a prior Step) was never added to it, so a persisted invoice carrying a recargo would fail to reload from JSON (`Invoice.model_config` is `strict=True`, which rejects a JSON-decoded string for a `Decimal` field unless pre-coerced). Fixed in the same edit; proven by extending `test_secure_storage_roundtrip.py`'s populated fixture to carry a non-zero `recargo_amount` and `suplido_amount` through a real encrypted-storage roundtrip.

**A peer commit swept and then partially reverted one of this Step's cluster's changes.** `application/aggregation/_invoice_retencion.py`'s `MISSING_COUNTERPARTY_TAX_ID` guard (added for the S44 ripple above) was picked up by a concurrent peer commit (`9869cb3e19`) that used `git commit --only` against a path that read from the working tree rather than a precise index, sweeping this session's then-uncommitted retención guard in as a byproduct; a peer follow-up commit (`fbc6f759ff`) then removed this session's `_invoice_devengo` import from `application/aggregation/__init__.py` because the peer saw a "dangling import to an uncommitted module" (the module was still untracked in the shared working tree at that moment) and explained the fix in its own commit message, leaving `_invoice_devengo.py` and its test untouched for this session to land properly. Re-applied the import and `__all__` entry before committing here; no functional content was lost, and the retención guard is verified present at HEAD.
