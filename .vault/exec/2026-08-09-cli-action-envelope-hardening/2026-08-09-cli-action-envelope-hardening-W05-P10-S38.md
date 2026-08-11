---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7c2d3f2ec8932ac3d1d246c46ed41c35b452253adf1a05b9ad159bc262a40790'
step_id: 'S38'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Consume the S33 typed reader-availability facts at _batch_ingest.py and _llm_classification.py within the exclusive ledger area, retain no MissingOptionalExtraError prose or compatibility bridge, and preserve only explicit typed reader-availability verdicts

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/locales`

## Description

- Replace batch inference-pause reason, detail, remediation, and cause copies with S33 facts and a mandatory precondition verdict.
- Preserve the exact S33 reader-unavailability verdict when an on-host reader call fails and its confirmation probe is unavailable.
- Keep an operation failure whose confirmation probe is available distinct from a reader-unavailability precondition.
- Correct the classifier contract to name `PurchaseInvoiceEvidenceInputError` and its exact provisioning verdict without transport or localized wording.
- Replace the remaining test-authored runtime-reachability and headroom condition identifiers with `ProvisioningPreconditionCondition` values.
- Author the `ledger.evidence.reader.operation_failed` presentation leaf in every supported locale through the canonical locale-maintenance command.

## Outcome

- The application producer preserves the exact provisioning verdict through `PurchaseInvoiceEvidenceInputError` when reader availability is not satisfied.
- A reader call that fails after the confirmation probe reports availability remains `LLMClassifierError`, so no false precondition is invented.
- The batch and vision contracts now derive all three reviewed condition identities from the canonical provisioning enum.
- Exact runtime lookup resolves the operation-failure leaf to a native nonempty value in Catalan, English, Spanish, and Hungarian with no placeholders.
- Two focused real batch tests and one focused real vision test pass; Ruff check and format, basedpyright, and diff whitespace validation pass.
- S38 remains open for independent re-review.

## Notes

- The full locale audit and scaffold checks remain red on unrelated catalogue debt, with zero findings for `ledger.evidence.reader.operation_failed`.
- S90 owns CLI propagation of the typed `PurchaseInvoiceEvidenceInputError` handoff.
- S94 owns the LLM-layer consumer proof and was not edited during this remediation.
- No `MissingOptionalExtraError` prose, compatibility field, duplicate exception identity, raw condition-id assertion, runtime fallback, or locale-specific action wording was introduced.
