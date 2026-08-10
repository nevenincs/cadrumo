---
generated: true
tags:
  - '#index'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f2584a94897edee9695c4465fe0ccc6110aff01728ceccca0fe50499ca6e2e30'
related:
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S01]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S02]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P01-S03]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P03-S04]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P03-S05]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P04-S06]]'
  - '[[2026-08-10-current-schema-only-purge-W01-P04-S07]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S08]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S09]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S10]]'
  - '[[2026-08-10-current-schema-only-purge-W02-P05-S11]]'
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
- `2026-08-10-current-schema-only-purge-W01-P03-S04` - Define and require the exact current BucketPointer schema marker
- `2026-08-10-current-schema-only-purge-W01-P03-S05` - Prove current BucketPointer round trips and non-current marker refusal
- `2026-08-10-current-schema-only-purge-W01-P04-S06` - Delete mapping-without-invoices coercion from InvoiceCatalogue validation
- `2026-08-10-current-schema-only-purge-W01-P04-S07` - Prove serialized catalogues require the canonical invoices wrapper
- `2026-08-10-current-schema-only-purge-W02-P05-S08` - Require and explicitly write the exact current CipherEnvelope marker
- `2026-08-10-current-schema-only-purge-W02-P05-S09` - Prove CipherEnvelope marker refusal occurs before master-key access
- `2026-08-10-current-schema-only-purge-W02-P05-S10` - Require and preflight the exact current WrappedMasterKey marker before decryption
- `2026-08-10-current-schema-only-purge-W02-P05-S11` - Prove wrapped-master-key marker refusal precedes real unwrap

### plan

- `2026-08-10-current-schema-only-purge-plan` - `current-schema-only-purge` plan
