---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:87731911281c58d8cd5a9cfc19ed59ce835d3ca159f2b63739dd8ffe694c2b27'
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
## Coordinated rehoming reconciliation

After three identical read-only boundaries separated by at least sixty seconds, the canonical S50 migration wrote one 238-row postimage. The isolated target delta was exactly eight removals, four additions, and thirty-eight preserved target identities. The additions were exactly three `PurchaseInvoiceEvidenceInputError` fingerprints owned by S38 and one `LLMContentionError` fingerprint owned by S94; thirty-one separately recorded locator-only refreshes were incidental metadata.

The resulting ledger SHA-256 is `9de39139862dd9c4a057c981a3f9d47de401f37675616ed1745d3f254b0ce1e5`. Direct validation passed with `E_REHOMING_VALIDATED:238`, and all four target error families matched the live fingerprint multisets and declared owners exactly. The immediate no-write byte replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT` after concurrent source movement; no second locator chase or write was performed. The complete 74-test lane finished with 71 passes and three externally concurrent failures: new Modelo error-family multiset drift in two tests and a source parse failure in `_action_resolution.py` in the owner-scope test.

This step remains open for independent review.
## Frozen Notice residual remediation

Fresh semantic discovery confirmed that neither the split-recommendation predicate nor the empty LLM-diagnostics predicate has a genuine action identity in the canonical operator-action catalogue. Both are observations, not executable recoveries: the split decision requires operator review, while absent metrics provide no safe transaction or classification inputs.

The two live Notice paths now render only their canonical localized fact keys, with no English default fallback, continuation sentence, synthetic `actionability` context, guessed action, or raw command. Their text mirrors the same Notice message rather than translating a second independently authored copy. The ca/en/es/hu catalogue values were narrowed through the locale authority to the same neutral facts.

Focused real JSON/Notice tests pass (2 passed), including explicit `action is None` and empty neutral context. Ruff and formatting pass. Exact residual search finds neither retired default continuation nor retired actionability identity. The immutable-HEAD census remains globally open on pre-existing campaign clusters and cannot observe this uncommitted delta. Locale audit remains externally red on unrelated schema/profile gaps and concurrent IVA-wallet leaves.

S90 remains open for independent review.
