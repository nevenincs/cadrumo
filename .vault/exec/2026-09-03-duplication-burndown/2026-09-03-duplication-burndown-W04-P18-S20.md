---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:bed31c82a42e9d42e497a42f9d1bcfe83404dd6b14a1ea09dab34453fb46bd02'
step_id: 'S20'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Adjudicate the 35 identical-expression constant collisions the extended screen surfaces, merging each to a canonical home or recording why an existing decision keeps it local

## Scope

- `dev/quality/constant_value_agreement.py`

## Changes

- `M` `dev/quality/constant_value_agreement.py`
- `M` `src/cadrumo/core/hashing.py`
- `M` `src/cadrumo/application/ledger/id_resolution.py`
- `M` `src/cadrumo/application/user_profile/bundle_export_operation.py`
- `M` `src/cadrumo/adapters/outbound/storage/_integrity.py`
- `M` `src/cadrumo/adapters/persistence/storage/attachment.py`
- `M` `src/cadrumo/domain/attachments/models.py`
- `verify:` `uv run --no-sync python -m dev.quality.constant_value_agreement` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo` -> `fail, peer-owned`

## Notes

The screen reported 35 collisions. Adding one discriminator reduced the real
backlog to 3, and the distinction is the finding: 32 of the 35 build their value
from an imported authority rather than from literals. `SEDE_BASE =
EXTERNAL.aeat.domains.www6` in four sede modules and `BUCKETS_DIRNAME =
storage_location(StorageCategory.BUCKETS).subpath` in two are local bindings of
one canonical value - every copy resolves to whatever the authority says, so
they cannot drift. Only a value retyped from literals is a second source of
truth. Those are now reported as `derived_name_collision` and kept out of the
actionable count.

Of the 3 that remained, 2 were the same value under two names: the lowercase hex
alphabet, declared in five modules as `_HEX_ALPHABET` or `_HEX_DIGITS`, every one
of them used for the same membership test. Merging them onto a published
`core.hashing.HEX_ALPHABET` exposed a sixth declaration under a third name,
`_ASCII_HEX_LOWER`, which no collision kind could ever have caught because only
one module spelled it that way. The tree now carries one declaration and six
importers.

`CSV_EXTENSIONS` is the one collision left and is not merged here: the two sites
are an inbound financial provider and a modelo observation spreadsheet reader,
whose accepted extensions agree today by coincidence rather than by a shared
rule, so consolidating them would invent a coupling the code does not claim.
