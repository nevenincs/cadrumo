---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:04e54342fb161686b2b34b808c2fc0c04d823242ecb8e03d3b11c4fdde5a3a20'
step_id: 'S03'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Inventory every production slim-store consumer and record the named canonical replacement for each in the execution record, refusing to proceed to P03 while any consumer has no replacement

## Scope

- `src/cadrumo/application/ledger/_business_operation_invoice.py`

## Description

- Swept every production (non-test) consumer of the slim store by symbol at `HEAD`, covering the model, the repository, both services, the direction enum and the storage namespace.
- Ran a second sweep over NON-Python production files, because a symbol sweep scoped to `.py` misses the data and catalogue consumers.
- Classified each consumer as a code consumer or a prose-only consumer, since the two need different sweeps and only one of them fails a build.
- Checked canonical error-code parity explicitly, as a registered error class with no canonical counterpart would be a consumer with no replacement and would block the fold.

## Outcome

**Thirteen production Python consumers, four locale catalogues and one generated report. Every one has a named canonical replacement, so no consumer blocks the fold.** The Step is closed by the completeness of this list, not by the absence of a gap.

**Code consumers, the store itself and its facade**

- `application/ledger/_business_operation_invoice.py` — the model, both services, the repository and the direction enum. Replacement: the canonical aggregate in `domain/invoices` with the services in `application/invoices`. Deleted by `S14`.
- `application/ledger/__init__.py` — facade re-exports of all of the above. Replacement: the exports are removed with the store, no bridge left behind.

**Code consumers, the calculation path**

- `application/invoices/_source_resolver.py` — the two-store union, the slim loader and the slim observation adapter. Replacement: the canonical loader alone, proven by `S01` to carry every declarable fact. Removed by `S13`.
- `application/invoices/__init__.py` — imports the slim symbols the resolver unions. Replacement: same as above.

**Code consumers, the operator surface**

- `entrypoints/cli/_ledger_business_invoice_cli.py` — the five bare verbs. Replacement: the same verbs repointed at the canonical aggregate by `S11`, keeping the operator noun and the kind flag.
- `entrypoints/cli/_ledger_business_payloads.py` — the slim CLI payload schemas. Replacement: the canonical payload schemas. Deleted by `S15`.

**Code consumers, persistence and custody**

- `adapters/persistence/storage/_namespace_registry.py` — the slim namespace definition and its enrolment. Replacement: the canonical invoice-catalogue namespace, which already exists and already carries structured custody.
- `adapters/persistence/storage/__init__.py` — the namespace re-export.
- `application/user_profile/_custody_carry.py` — registers a bound resolver against the slim namespace string. Replacement: the canonical namespace resolver, which is already registered.

**Code consumer, the error registry**

- `core/errors/registry/_domain_part1.py` — two registered error codes, for malformed input and for a missing record. Replacement exists and is already registered on the canonical side: the canonical validation error and the canonical not-found error each carry their own code. Checked explicitly rather than assumed, because an unreplaced registered error would have been a genuine blocker.

**Prose-only consumers — the class a symbol sweep passes over**

- `application/invoices/_creation.py`, `entrypoints/cli/_ledger_payloads.py` and `entrypoints/cli/_ledger_catalogue_invoice_payloads.py` name the slim model in docstrings only, with no import and no call. They break no build when the class is deleted, so a deletion Step that greps for callers will leave all three referring to a class that no longer exists.

**Catalogue and generated consumers**

- The four locale catalogues carry the slim verbs' help and error leaves. Replacement: removal through the locales CLI so all four stay in parity, which `S16` owns.
- The terminology evaluation coverage report names the concept and is generated, so it regenerates rather than needing an edit.

## Verification

    rg -n "BusinessOperationInvoice|PayableInvoiceService|CollectibleInvoiceService|LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE|business_operation_invoice" --glob "src/cadrumo/**/*.py" --glob "!**/tests/**" -l
    13 files

    rg -n "business_operation_invoice|BUSINESS_OPERATION_INVOICE" --glob "src/cadrumo/**/*" --glob "!**/tests/**" --glob "!**/*.py" -l
    5 files (4 locale catalogues, 1 generated coverage report)

Error-code parity was confirmed against the registry rather than inferred from the class names:

    rg -n "domain\.invoices\." src/cadrumo/core/errors/registry/*.py
    7 registered canonical invoice error codes, including InvoiceNotFoundError and InvoiceValidationError

The inventory is a measurement and lands no code, so there is no test run to quote. Its claims are falsifiable by re-running the two sweeps above.

## Notes

**The Step's predicted RED did not occur and the reason is recorded rather than smoothed over.** The criterion expected the inventory to name at least one production consumer with no canonical replacement. Every consumer has one. The Step's own closing condition is a complete list rather than a clean assertion, so it closes on completeness, but the prediction was wrong and that is stated here rather than left implied by a tick.

**Two ordering hazards this inventory surfaced that the deletion Steps must carry.**

The custody-carry registration and the namespace definition sit in different packages and must land in ONE commit. Removing the namespace while the custody resolver still registers against its string leaves profile export or import resolving a namespace that no longer exists, and a profile carry is the one operation where that failure costs a taxpayer their data rather than a test run.

The three prose-only consumers are invisible to a caller sweep. They are recorded here by name so the deletion Steps sweep documentation as well as imports.

**Scope boundary against the capability inventory.** This Step inventories CONSUMERS and finds all replaceable. It is not a finding that the fold is safe: the structural properties with no direct canonical counterpart are capabilities rather than consumers, and belong to the capability inventory and the lane-partition decision. The clearest instance is the slim store's per-bucket-and-source-kind document partition, which the canonical single-document-per-profile store does not reproduce.
