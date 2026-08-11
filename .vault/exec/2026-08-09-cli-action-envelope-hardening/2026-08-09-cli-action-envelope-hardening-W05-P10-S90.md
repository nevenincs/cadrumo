---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7e64bfa303a5905695dc832f81a07591b6d5f1d4ae712b2e765c7541f4002731'
step_id: 'S90'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate ledger CLI action producers and co-located renderers without independently authored command prose, including direct typed-error consumer migration so canonical refusals reach the shared envelope intact.

## Scope

- Declared ledger CLI surface in `src/cadrumo/entrypoints/cli/_ledger*.py`.
- Co-located ledger CLI behavior, action-conformance, locale, and census evidence.
- `src/cadrumo/locales/{ca,en,es,hu}.yml` through the canonical locale authority.

## Description

- Remove CLI catches that flatten registered typed failures into `BadParameter` plus locally authored recovery commands.
- Remove or neutralize raw command/action prose in ledger help, refusal, notice, and operator-facing function help surfaces when no canonical catalogue action exists.
- Preserve `source_command` values solely as audit provenance, not operator guidance.
- Remove proven-orphan locale leaves and keep all surviving user-facing projections translation-complete.

## Outcome

`OutboundStorageError`, `CounterpartyEstablishmentConflictError`, `PurchaseInvoiceEvidenceInputError`, and `LLMClassifierError` now reach the shared typed boundary on their owned paths. No replacement action was invented where the canonical catalogue has no attach, withdraw, confirm, or manual-classification action identity.

The fixed-point sweep removed or neutralized direct action prose from link, doclink, counterparty confirmation, evidence extraction, pull-folder, rich-invoice link descriptions, split-child guidance, and LLM-rejection notices. Locale-authority mutations removed the orphaned `cli.ledger.classify.llm_failed`, `cli.ledger.doclink.refused`, and `cli.ledger.counterparty.errors.confirmation_conflict` leaves across ca/en/es/hu and reconciled the surviving link, pull-folder, and LLM notice leaves in all four locales.

Ruff, formatting, compileall, and diff checks pass. Real console checks for localized `ledger link --help` and `ledger pull-folder --help` pass and show no discarded command hint. S90 remains open for independent re-review.

## Notes

- The focused integration lane produced three passes; five failures and eleven setup errors are external to this delta: the shared profile helper lacks a newly required tax-residence flag and the local Ollama provider is unavailable.
- Focused census and recovery-rehoming lanes exceeded their execution windows and remain unverified. The census authority accepts an immutable Git revision, so the uncommitted working-tree delta cannot be reconciled honestly before coordinated ledger authorization.
- BasedPyright remains externally red on pre-existing CLI private-usage and unknown-type diagnostics; no diagnostic points to a changed line.
- The locale audit no longer reports an S90 orphan but remains externally red on unrelated missing schema/profile leaves.
- No compatibility bridge, manual disposition mutation, Git operation, or plan closure was added.
