---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:4acf81c8c5fd3929218a32324373f10ec1ed80b1840a275a888b44b340c31001'
step_id: 'S21'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the focused Modelo 369 verification suite after widening the invoice boundary

## Scope

- `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`

## Description

- Confirm verification and OSS/IOSS resolver boundaries consume `InvoiceCatalogueRepositoryProtocol`.
- Inspect the distinct ambient-versus-injected store path through public calculate and legacy verification.
- Run `uv run --no-sync pytest -vv -n 0 src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py` serially.

## Outcome

All five collected nodes passed in 58.64 seconds:

- `test_m369_oss_resolver_folds_real_candidates_at_mesh_boundary`
- `test_m369_live_path_folds_oss_invoices_not_no_live_source_advisory`
- `test_m369_unresolved_oss_source_refuses_verification_and_export`
- `test_m369_recalculate_existing_unrouted_draft_refuses_verification_and_export`
- `test_m369_zero_valued_oss_invoice_remains_verifiable`

The distinct-store node uses a separate injected SQL engine for the invoice catalogue, confirms the same-bucket ambient invoice repository is absent before and after execution, passes the injected Protocol implementation into both public calculate and legacy verify, and proves calculation provenance plus successful legacy verification come from that injected source. The remaining nodes prove real candidate folding, unresolved and legacy-unrouted refusal, recalculation behavior, and valid zero-valued OSS invoice handling through the widened boundary.

## Notes

No source or test file was changed. No incidents or skipped verification.
