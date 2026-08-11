---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ed7c3fe53de1614e3f9d140ac3bc2abf985985468a991598eaab8c108a8cbf9d'
step_id: 'S38'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Consume the S33 typed reader-availability facts at _batch_ingest.py and _llm_classification.py within the exclusive ledger area, retain no MissingOptionalExtraError prose or compatibility bridge, and preserve only explicit typed reader-availability verdicts

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_filer_precondition_projection.py`
- `src/cadrumo/locales`

## Description

- Preserve the exact S33 reader-unavailability verdict when an on-host reader call fails and its confirmation probe is unavailable.
- Keep an operation failure whose confirmation probe is available distinct from a reader-unavailability precondition.
- Replace the remaining test-authored provisioning condition identifiers with `ProvisioningPreconditionCondition` values.
- Author the `ledger.evidence.reader.operation_failed` presentation leaf in every supported locale through the canonical locale-maintenance command.
- Remove the filer-establishment `str(refusal)` conversion that flattened `PurchaseInvoiceEvidenceInputError` into review-item prose.
- Propagate the original filer postcode refusal so its exception identity, failed condition, evidence facts, null action, and closed outcome reach the shared CLI boundary unchanged.
- Scan the ledger application scope for equivalent typed `PurchaseInvoiceEvidenceInputError` stringification bridges.

## Outcome

- Reader availability and operation failure retain their distinct typed outcomes.
- Batch and vision contracts derive reviewed condition identities from the canonical provisioning enum.
- Exact runtime lookup resolves the operation-failure leaf to a native value in Catalan, English, Spanish, and Hungarian.
- Filer postcode setup failure reaches the shared CLI projection as `ledger.filer.postcode_valid`, evidence `filer_postcode_present=false`, no action, and `operator_decision`.
- The exact ledger scan reports zero remaining `PurchaseInvoiceEvidenceInputError` stringification bridges.
- Nineteen filer-establishment tests, three real confirm-path tests, and one CLI projection test pass; Ruff check and format, basedpyright, and diff whitespace validation pass.
- S38 remains open for independent re-review.

## Notes

- The removed string was not presentation-only: it discarded the terminal verdict and moved potentially sensitive malformed profile data into ordinary review-notice context.
- The read-only historical rehoming join remains red for the S38 target `PurchaseInvoiceEvidenceInputError` plus four unrelated Modelo error fingerprints. No rehoming ledger write was made.
- The full locale audit and scaffold checks remain red on unrelated catalogue debt, with zero findings for `ledger.evidence.reader.operation_failed`.
- S90 and S94 were not edited.
