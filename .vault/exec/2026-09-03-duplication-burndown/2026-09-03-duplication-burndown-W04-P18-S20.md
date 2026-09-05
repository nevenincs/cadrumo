---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:a56706d828b34b6193d34eb57b9fcc256472074072c0e47fd2badc82ea91563f'
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

## Continuation

The discriminator this Step introduced was wrong on its first form and was
replaced. It used an allowlist of known constructors, which misclassified
`TypeAdapter(tuple[int | float, ...])` as safe - and the Step's own earlier test
failed on exactly that case. The rule is now simply whether the expression
contains any literal: names and attributes alone read a value that lives
elsewhere, while a string, a number, `True` or a bare `...` means the value was
written down at that site. The honest effect was to RAISE the actionable count
from 3 to 5, because two findings had been wrongly marked safe. A maintained
allowlist would have kept hiding them.

Three further merges followed. `LEGAL_REFS_ADAPTER` and `SOURCE_REFS_ADAPTER`
now live in `domain/calculations/registry/ids.py` beside the types they
validate, so a change to `LegalRefId` cannot leave a copy validating the old
shape. And four aggregation ledgers each declared
`_IssueDetail = Annotated[str, ElidedProse(512)]` while two of their siblings
already imported the canonical `core.prose_elision.IssueDetail`; the four now
read it too. The canonical carries the reasoning for the 512 bound - refusing a
longer sentence would drop the explanation for a ledger exclusion, a silent
under-declaration dressed as a validation error - and none of the four copies
carried that.

Two collisions remain and neither is merged, for stated reasons rather than
fatigue. `CSV_EXTENSIONS` is coincidental agreement between an inbound provider
and a spreadsheet reader. `_AT` is a devtools fixture timestamp inside the
deferred `entrypoints.tui` prefix. Two same-shaped aliases were also
deliberately left alone: `_IssueMessage` and `_GroundingDetail` carry the same
`ElidedProse(512)` constraint but name different concepts, and merging on shape
would have made the names lie.

## Stem restatements adjudicated

The thirteen `stem_restatement` rows were read individually, and most are NOT
defects. Value plus a shared name stem still pairs constants that were chosen
independently:

* `KEY_SIZE` is AES-256's key length; `_RECOVERY_KEY_SIZE` sits beside
  `_MNEMONIC_WORD_COUNT = 24` and is mnemonic entropy, 24 words being 256 bits.
  Both are 32 for unrelated reasons, and merging them would couple the recovery
  format to the cipher.
* `_HASH_CHUNK_SIZE` buffers a local file into `hashlib`; `_CHUNK_SIZE` in the
  manuals fetcher buffers an HTTP response. Both are the conventional 64 KiB,
  independently chosen.

That is the kind's honest limitation: it reports a candidate, and a
conventional value under a related name is its false-positive shape.

One row is a real defect and is fixed here. `application/auth/sessions.py`
declared `_PROFILE_TAX_ID_PATH = "identity.tax_id"` and then used the raw
literal three more times IN THE SAME FILE, so the constant carried none of the
weight it was written for. The three uses now route through it.

The wider fact is larger than this Step and is left for an owner. The path
string `"identity.tax_id"` appears as a bare literal across 23 production
modules and 261 test modules with no canonical declaration anywhere: the user
profile has no fact-path vocabulary, so a rename of that path would drift
silently across the tree. Naming that vocabulary is a design decision about
where profile fact paths live, not a consolidation this campaign can make on
its own authority.
