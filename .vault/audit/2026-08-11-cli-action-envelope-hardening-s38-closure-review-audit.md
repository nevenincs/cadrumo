---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0614ace0f9cea2bdb09b61c9b498246aa7b61acc99cfbad77327b3198f217c9a'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S38 independent closure review`

## Scope

Independent closure review of S38 after remediation of its prior condition-redeclaration and unregistered-operation-key findings. The review covered the complete ledger application surface for `MissingOptionalExtraError`, `PurchaseInvoiceEvidenceInputError` stringification bridges, reader facts, terminal verdict propagation, locale ownership, and the shared CLI projection.

## Findings

### s38-target-contract | low | The current reader and filer paths preserve typed facts without a presentation bridge

The current `src/cadrumo/application/ledger` scan found no `str()` conversion of a caught `PurchaseInvoiceEvidenceInputError`. The text and vision reader paths retain registry `extra`, `import_name`, and `importable` facts for a missing extra, retain only availability and exception-kind facts after a successful probe, and emit explicit no-recovery verdicts. The filer postcode refusal reaches the shared CLI projection intact, so malformed profile content is not moved into ordinary diagnostic context. The canonical provisioning condition enum and all four locale leaves are exercised by the focused lane.

### s38-rehoming-prerequisite | high | The current S38 fingerprint set is not yet reconciled in the canonical rehoming ledger

The fresh direct rehoming validation refused `PurchaseInvoiceEvidenceInputError` with `E_REHOMING_FINGERPRINT_MULTISET`. The same run reported four Modelo error families and `LedgerStorageError` outside S38. This is a structural ownership prerequisite, not evidence of a reader-contract regression, but it prevents S38 closure.

### s38-exec-hygiene | low | The current S38 execution record has one markdown blank-run warning

The full Vault check reported one extra blank line in the S38 execution record. The repository also has historical shared Vault warnings outside this review surface.

## Recommendations

Keep S38 open. The S50 rehoming owner should reconcile the exact current S38 fingerprint multiset without claiming the unrelated Modelo or ledger-storage rows, then rerun the direct rehoming validation. The S38 execution-record owner should repair the markdown warning through the Vault CLI. Re-run this independent review after both closure prerequisites pass.
