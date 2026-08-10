---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:7aecba79519edd1055227cbbc52352ea812e318232535f5562296af853a6b663'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - "[[2026-08-09-m303-carry-reconciliation-prior-domiciliation-s21-reference]]"
---
# `m303-carry-reconciliation` audit: `S21 prior-domiciliation election code review`

## Scope

Reviewed S21's typed prior-domiciliation election, baseline-U resolver and persistence/export provenance against the S21 plan, governing ADR amendment, implementation reference, and the audit template. This review was paused after the first confirmed release-blocking authority finding so it can be remediated and re-reviewed without conflating pre- and post-fix evidence.

Focused remediation re-review conclusion: the preceding HIGH finding is resolved. `resolve_prior_domiciliation_election` now requires exactly one typed submitted-file `declaration_type` fact with value U and a source-header U projection at the same locator before it accepts `CANCEL_OR_MODIFY`. Real encrypted-storage controls cover missing, duplicate, and conflicting headers; non-U values; incorrect provenance; disposition disagreement; and locator disagreement. The focused resolver and M303 carry-ingress modules passed 45 tests.

The remaining full S21 review covered the raw enum boundary, public export, quickfile, file, idempotent file, review-package, and CLI wrappers; the receipt, event, and filing-observation projections; both M303 registry layouts and their source binding; locales; and the S21 tests. It found the event-provenance defect below. No account number was found in the S21 election projection, receipt, event payload, or filing observation.

Focused remediation re-review conclusion: the MEDIUM event-provenance finding is resolved. Both export and filing lifecycle events now retain the semantic baseline U disposition and the submitted-file source-header locator alongside the existing safe baseline identifiers. The real encrypted-storage export-to-file integration test proves the exact coordinates survive both lifecycle events and that neither contains an IBAN. The existing resolver controls remain the mismatch and forged-evidence refusal boundary.

## Findings

### S21 prior-domiciliation election code review | high | Baseline-U authority does not prove the claimed submitted-file header

`resolve_prior_domiciliation_election` accepts a persisted result-disposition projection when its source kind is official, its declared provenance kind is `source_header`, its semantic value is `DOMICILIACION`, and its locator is merely non-empty. `ResultDispositionProjection` likewise constrains the locator only to a non-empty string. Neither model nor resolver proves that the locator identifies the same accepted baseline's submitted-file `declaration_type` header, nor binds the claimed U fact to a submitted-file artifact or authenticated parsed-header record. Consequently a nominal official `source_header` U projection at an unrelated or invented locator unlocks `CANCEL_OR_MODIFY` and can reach marker rendering, receipt, event, and observation persistence without the ADR-required baseline-U header proof. This violates the fail-closed evidence chain stated for S21.

### S21 prior-domiciliation election code review | medium | Lifecycle events drop the submitted-header proof locator

The resolved `PriorDomiciliationElectionProjection` carries the election, baseline filing id, evidence reference, U disposition, and submitted-header locator. The export receipt and filed observation retain that projection, but both `_emit_export_event` and `persist_filed_revision` write only the election plus baseline filing and evidence-reference ids. They omit `baseline_source_header_locator` and the U disposition. A later lifecycle-event audit therefore cannot verify the record-design location of the submitted-file fact that authorized X, despite the ADR and S21 reference requiring safe semantic and baseline join provenance through receipt, event, and observation. The omission is not an IBAN leak and does not bypass the resolver, but it leaves the event ledger incomplete for the legally material proof.

## Recommendations

- Make the persisted disposition evidence attest the submitted-file declaration-type header and its baseline artifact identity, then make the resolver require that attestation before accepting `CANCEL_OR_MODIFY`. Add a real persistence and resolver regression that refuses an official U projection with any unrelated locator and accepts only the authenticated same-baseline header proof.
- Carry the resolved U disposition and submitted-header locator into both the export and filing lifecycle event payloads, with real-event regressions proving the values round trip and that no account material is present.
