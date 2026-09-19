---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a68e6d2825d24b3da1f0bcb58e77975a96e232d5db87f06cfca034975d25b164'
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
- Remove the evidence-reader boundary's remaining `MissingOptionalExtraError` and provider-exception prose bridges at both text and vision call sites.

## Outcome

- Reader availability and operation failure retain their distinct typed outcomes.
- Batch and vision contracts derive reviewed condition identities from the canonical provisioning enum.
- Exact runtime lookup resolves the operation-failure leaf to a native value in Catalan, English, Spanish, and Hungarian.
- Filer postcode setup failure reaches the shared CLI projection as `ledger.filer.postcode_valid`, evidence `filer_postcode_present=false`, no action, and `operator_decision`.
- Missing optional reader dependencies now preserve the canonical optional-extra registry identity as `extra`, `import_name`, and `importable=false`; provider failures preserve availability and error-type facts.
- Text and vision evidence-reader refusals carry no exception string, install command, or independently authored English recovery message.
- The exact ledger scan reports zero remaining `PurchaseInvoiceEvidenceInputError` stringification bridges and no `MissingOptionalExtraError` recovery-prose bridge.
- The focused reader suite passes 30 tests; Ruff, basedpyright, and the broader S38 evidence checks pass.
- S38 remains open for independent re-review.

## Notes

- The removed string was not presentation-only: it discarded the terminal verdict and moved potentially sensitive malformed profile data into ordinary review-notice context.
- The reader boundary now reports facts only. Any future recovery action must be linked by the canonical action catalogue, not reconstructed from `MissingOptionalExtraError.install_hint` or exception text.
- Other ledger `str(exc)` sites are row-level validation diagnostics and not optional-reader/precondition-envelope conversions; they remain separate campaign candidates rather than being silently broadened into S38.
- The read-only historical rehoming join remains red for the S38 target `PurchaseInvoiceEvidenceInputError` plus four unrelated Modelo error fingerprints and `LedgerStorageError`. No rehoming ledger write was made.
- The full locale audit and scaffold checks remain red on unrelated catalogue debt, with zero findings for `ledger.evidence.reader.operation_failed`.
- S90 and S94 were not edited.

## Coordinated canonical rehoming reconciliation

A fresh read-only derivation established three identical stability boundaries separated by at least sixty seconds. Immediately before mutation, the canonical guard revalidated the ledger, plan, all-source, rendered postimage, structural-delta, and locator-delta hashes byte-for-byte. OWNER_ZERO was zero and every one of the twenty-four structural additions had exactly one open owner. The delta contained thirty-five removals, no historical-row, disposition, or current-identity changes, and 144 locator-only refreshes recorded as incidental metadata.

Exactly one S50 canonical-tool write produced the proven postimage. The resulting ledger SHA-256 is `bc6ddc3b5edddd852a155e48ca58ec6e3aa188f716cecef8615b9bef20de2aec`. Direct validation returned `E_REHOMING_VALIDATED:238`; the single immediate no-write replay returned `E_REHOMING_MIGRATION_CHECKED:238`. No second locator chase or write was performed. The complete canonical rehoming lane passed 74 tests.

This owner Step remains open for independent review and ledger reconciliation.
