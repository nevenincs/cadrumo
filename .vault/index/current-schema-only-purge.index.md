---
generated: true
tags:
  - '#index'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:79b242b2779e55bb7d90feee9c2ccbb7cd6e12110ed55ea546d379a5f83fd638'
related:
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S01]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S02]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S03]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S24]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P03-S04]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P03-S05]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P04-S06]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P04-S07]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S08]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S09]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S10]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S11]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S12]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S13]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S25]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P06-S14]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P06-S15]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P06-S26]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S21]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S22]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S23]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S28]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S29]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S32]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S33]]'
  - '[[2026-08-10-current-schema-only-purge-W03-P07-S35]]'
  - '[[2026-08-10-current-schema-only-purge-adr]]'
  - '[[2026-08-10-current-schema-only-purge-plan]]'
---

# `current-schema-only-purge` feature index

Auto-generated index of all documents tagged with `#current-schema-only-purge`.

## Documents

### adr

- `2026-08-10-current-schema-only-purge-adr` - `current-schema-only-purge` adr: `current-schema-only hydration and persistence` | (**status:** `accepted`)

### exec

- `2026-08-10-current-schema-only-purge-W01-P01-S01` - Require exact schema id and schema version 4 for UserProfileRecord and UserProfileSnapshot
- `2026-08-10-current-schema-only-purge-W01-P01-S02` - Stamp newly created profile records explicitly with the canonical schema version
- `2026-08-10-current-schema-only-purge-W01-P01-S03` - Prove current profile schema hydration and non-current marker refusal
- `2026-08-10-current-schema-only-purge-W01-P01-S24` - Refuse a persisted profile payload that omits schema_version at both read boundaries
- `2026-08-10-current-schema-only-purge-W01-P03-S04` - Define and require the exact current BucketPointer schema marker
- `2026-08-10-current-schema-only-purge-W01-P03-S05` - Prove current BucketPointer round trips and non-current marker refusal
- `2026-08-10-current-schema-only-purge-W01-P04-S06` - Delete mapping-without-invoices coercion from InvoiceCatalogue validation
- `2026-08-10-current-schema-only-purge-W01-P04-S07` - Prove serialized catalogues require the canonical invoices wrapper
- `2026-08-10-current-schema-only-purge-W02-P05-S08` - Require and explicitly write the exact current CipherEnvelope marker
- `2026-08-10-current-schema-only-purge-W02-P05-S09` - Prove CipherEnvelope marker refusal occurs before master-key access
- `2026-08-10-current-schema-only-purge-W02-P05-S10` - Require and preflight the exact current WrappedMasterKey marker before decryption
- `2026-08-10-current-schema-only-purge-W02-P05-S11` - Prove wrapped-master-key marker refusal precedes real unwrap
- `2026-08-10-current-schema-only-purge-W02-P05-S12` - Require explicit current encrypted-bundle envelope payload and KDF markers
- `2026-08-10-current-schema-only-purge-W02-P05-S13` - Prove encrypted-bundle marker refusal and current passphrase round trip
- `2026-08-10-current-schema-only-purge-W02-P05-S25` - Gate the encrypted-bundle kdf_version marker against the current Argon2 version
- `2026-08-10-current-schema-only-purge-W02-P06-S14` - Require and explicitly write the exact current SecretIndex marker
- `2026-08-10-current-schema-only-purge-W02-P06-S15` - Prove missing and non-current secret-index markers refuse real store operations
- `2026-08-10-current-schema-only-purge-W02-P06-S26` - Make the master-key KDF preflight model require a real version
- `2026-08-10-current-schema-only-purge-W03-P07-S21` - Require result_disposition for applicable official Modelo 303 observation payloads
- `2026-08-10-current-schema-only-purge-W03-P07-S22` - Require Modelo 303 result_disposition before any filing persistence write
- `2026-08-10-current-schema-only-purge-W03-P07-S23` - Prove under-declared Modelo 303 observations are refused and current dispositions round trip
- `2026-08-10-current-schema-only-purge-W03-P07-S28` - Establish what the M303 carry normalisation path actually is
- `2026-08-10-current-schema-only-purge-W03-P07-S29` - Stop an unreadable prior observation proving a first IVA period
- `2026-08-10-current-schema-only-purge-W03-P07-S32` - Decide whether the carry gate should admit an operator-manual observation
- `2026-08-10-current-schema-only-purge-W03-P07-S33` - Establish which onboarding paths set the profile activity-start date
- `2026-08-10-current-schema-only-purge-W03-P07-S35` - Select the Modelo 303 recurrence producer before the work, not after it

### plan

- `2026-08-10-current-schema-only-purge-plan` - `current-schema-only-purge` plan
