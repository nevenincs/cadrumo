---
tags:
  - '#audit'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:6397911ec68f6b8b7cc73cb92c74606f531b25238eaf46622555d2a83c691e3b'
related: []
---

# `data-output-standardization` audit: `financial catalogue dir liveness`

## Scope

Per-dir live-vs-vestigial write-status verification of the `var/financial/*`
catalogue directories and the two registry store directories declared by the
integration-fields settings mixin, at HEAD of `chore/eliminate-shims`, to
decide which fields Step S02 derives from the state root and which it deletes
as consumer-less. Method: grep every production (non-test) consumer of each
settings field, then read the persistence path and the tests that pin whether
each on-disk directory is still written. This gates S02 deletions per the
no-dormant-source discipline; the ADR (ruling R1) mandates the verification
before migration.

## Findings

### financial-txs-dir | live | Master-key file-envelope store, keep and derive.

`cadrumo_financial_txs_dir` is read by `default_rotation_plan` in
`_rotation.py`, which registers it as a `*.envelope.json` file-consumer with
HKDF context `cadrumo.domain.transactions.catalogue.v1`. The rotation
docstring states these are master-key-encrypted file envelopes (distinct from
the SQL secure-object store, which the same docstring explicitly excludes).
The field is a live consumer; keep it and derive its default from the state
root in S02.

### invoices-dir | live | Master-key file-envelope store, keep and derive.

`cadrumo_invoices_dir` is registered in `default_rotation_plan` with HKDF
context `cadrumo.domain.invoices.catalogue.v1`. Same disposition as the
transactions catalogue: live file-envelope consumer, keep and derive.

### attachments-dir | live | Manifest envelopes plus blob roots, keep and derive.

`cadrumo_attachments_dir` is read twice in production: `default_rotation_plan`
registers `<dir>/manifests` (HKDF context `aeat.domain.attachments.manifest.v1`)
and `default_blob_store_roots` registers the dir as a blob-store root. Live
consumer; keep and derive. The `aeat.`-prefixed HKDF context is an encryption
AAD binding, not a settings name, and is out of scope for the location/naming
rulings.

### usage-ratios-path | live | Single-file envelope, keep and derive.

`cadrumo_usage_ratios_path` is registered in `default_rotation_plan` as a
single-file envelope (HKDF context `cadrumo.domain.usage_ratios.profile.v1`,
target filename `usage-ratios.json`). Live consumer; keep and derive. This is
the one `_path` (file) field among the financial set; its derivation targets
the file path, not a directory.

### registry-parity-store-dir | live | CLI default for parity artifacts, keep and derive.

`cadrumo_registry_parity_store_dir` is read by the registry CLI in
`entrypoints/cli/registry.py` as the default archive location for registry
parity-tape artifacts when the operator omits an explicit path. Live consumer;
keep and derive.

### registry-disk-cache-dir | live | Loader cache redirect, keep (relocated by W01.P02).

`cadrumo_registry_disk_cache_dir` defaults to `None` (falling back to the OS
temp dir today) and is redirected by test isolation to keep xdist workers off a
shared pickle. It is a live cache-location control consumed by the registry
loader. It is not a `var/financial` catalogue and is not deleted; its
production default relocation to the cache root is W01.P02 scope, not S02.

### purchase-invoice-evidence-dir | vestigial | No production consumer, delete in S02.

`cadrumo_purchase_invoice_evidence_dir` has zero production consumers: the only
references are its field definition, the `_normalize_repo_relative_paths`
validator tuple, `env/.env.example`, and `docs/reference/environment-overrides.md`.
Purchase-invoice evidence now persists in the encrypted `SecureObjectRepository`
under namespace `cadrumo.application.ledger.purchase_invoice_evidence`; the
secure-storage test asserts the plaintext `<dir>/<bucket>.jsonl` file is never
written. The field is dead vocabulary. Delete it in S02 and sweep the validator
tuple, the dotenv example, the env-overrides doc, and the two test references
(`test_evidence_storage_errors.py` asserts the plaintext file's absence;
`_evidence_test_support` isolates the field).

### ledgers-dir | vestigial | No production consumer, delete in S02.

`cadrumo_ledgers_dir` has zero production consumers: the only references are its
field definition, the `_normalize_repo_relative_paths` validator tuple,
`env/.env.example`, `docs/reference/environment-overrides.md`, and two tests.
Inventory and amortization ledgers now persist as secure objects under the
profile inventory-ledger namespace; the inventory secure-storage test asserts
the plaintext `<dir>/inventory/<bucket>.json` file is never written, and
`test_inventory_verbs.py` only overrides the field for isolation. The field is
dead vocabulary. Delete it in S02 and sweep the validator tuple, the dotenv
example, the env-overrides doc, and the two test references.

## Recommendations

- S02 derives from the state root and keeps: `cadrumo_financial_txs_dir`,
  `cadrumo_invoices_dir`, `cadrumo_attachments_dir`, `cadrumo_usage_ratios_path`,
  `cadrumo_registry_parity_store_dir`, and `cadrumo_registry_disk_cache_dir`
  (the last relocated to the cache root only in W01.P02).
- S02 deletes `cadrumo_purchase_invoice_evidence_dir` and `cadrumo_ledgers_dir`
  as consumer-less, sweeping every reference: the field definitions in
  `_config_integration_fields.py`, the `_normalize_repo_relative_paths`
  validator tuple in `config.py`, the two `env/.env.example` lines, the two
  `docs/reference/environment-overrides.md` rows, and the test references that
  read or override the deleted fields.
- Residual lifecycle question (out of S02 scope, for W02): confirm whether the
  four live financial file-envelope catalogues still accumulate on-disk
  envelopes in production, or whether the rotation plan now visits directories
  that are empty in the common secure-object-only flow. This is a lifecycle /
  dead-mechanism question, not a settings-field-deletion question, and does not
  change the S02 keep decision (the fields are consumed by live production code
  regardless).
