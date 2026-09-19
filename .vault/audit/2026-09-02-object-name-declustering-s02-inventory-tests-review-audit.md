---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e4511de94dfdf64257a050907ddcf77011f4f22c7e67aa50c96ccf48b1ca7374'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s02 inventory tests review`

## Scope

Reviewed the two `W01.P01.S02` regression tests in
`dev/audit/tests/test_object_names.py` against the accepted inventory contract,
the production serializer in `dev/audit/object_names.py`, and the open medium
finding from the `W01.P01.S01` review. The review covered complete declaration
records, deterministic reruns and input ordering, raw-byte source identity,
inventory-digest sensitivity, line-independent finding identity, line-bearing
site drift, and qualified-site stability. No production or test code was
changed by this review.

The focused suite completed with 24 passing tests. Ruff lint and formatting
checks passed for the production module and focused test module. The new tests
exercise the real `scan` and `to_json` production path with filesystem-backed
fixtures rather than a substitute serializer.

## Findings

### inventory-digest-teeth | medium | Raw-byte digest sensitivity remains unproven

`test_inventory_is_repeatable_and_raw_byte_drift_changes_only_execution_identity`
proves that the affected declaration's `source_hash` changes, but its mutation
prepends two lines. That simultaneously changes serialized declaration lines and
the finding's line-bearing `sites`. Consequently, the asserted
`inventory_digest` change would still occur if the digest projection accidentally
excluded `source_hash`; line and site drift alone make the serialized inventory
different. The test therefore does not bite the production guarantee that a
raw-byte-only edit with unchanged declaration and finding locations invalidates
the inventory digest. Because later manifest and receipt validation relies on
this execution identity, the open `W01.P01.S01` medium is only partially closed.

### declaration-record-shape | low | Complete-record assertion covers identity but not the full schema

`test_inventory_serialises_complete_module_and_symbol_records` proves enrollment
of module, class, enum, synchronous-function, and asynchronous-function records
and checks their locator, path, binding occurrence, and hash. It does not assert
the complete serialized key set or the values of `name`, `kind`, `line`,
`public`, `test`, and `overload`. A regression that drops one of those fields
could therefore retain every current assertion. The test establishes complete
kind enrollment, but not the complete declaration-record serialization claimed
by the step.

## Recommendations

Resolve `inventory-digest-teeth` with a raw-byte mutation after the declaration,
or another byte-only change that preserves every line-bearing declaration and
finding field, then assert that `source_hash` and `inventory_digest` change while
`id`, `sites`, and `qualified_sites` remain equal. This makes removal of the
source hash from the digest projection fail the test.

Resolve `declaration-record-shape` by comparing representative records with
their complete expected dictionaries, or at minimum asserting the exact key set
and values for all serialized declaration fields. Retain the existing
module/class/enum/sync/async enrollment coverage.

## Resolution evidence

The amended drift fixture appends a trailing comment after the declaration. The
source bytes and affected declaration `source_hash` change, while the declaration
line and all finding `sites`, `qualified_sites`, and `id` values remain equal.
The changed `inventory_digest` is therefore attributable to byte identity carried
through the serialized declaration, closing `inventory-digest-teeth`.

The amended record fixture asserts the exact serialized key set and complete
expected values for each module, class, enum, synchronous-function, and
asynchronous-function record. The hash value is separately constrained to the
canonical `sha256:` form, closing `declaration-record-shape`.

Re-review ran the real production-backed focused suite with 24 passing tests.
Ruff lint passed, and Ruff confirmed both reviewed files were already formatted.
No critical, high, medium, or low finding remains open for `W01.P01.S02`; the
original `W01.P01.S01` medium is closed by these amendments.
