---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2ea5f83eab97ee1b0cf6216d98a447ad0bfbcac3f9bd90e52063e370365305ad'
step_id: 'S121'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Perform the PRE_RELEASE current-only cutover by proving zero affected nonterminal operations, refusing every superseded journal and lease shape, and deleting the v1 lease reader, acquisition migrator, retired schema dispatchers, fixtures, and migration tests without a compatibility path

## Scope

- `src/cadrumo/application/operations` and `src/cadrumo/adapters/persistence/operations`

## Provenance

- The mixed-source tuple is `f7694d3ae2fb3d43c5b84c813af6daf49e837a25` (pre-mix) -> `7449ce08460b688e7e7147239c02570cbf5428e9` (shared S120/S121 source commit, `feat(operations): tighten lease and journal handling behind projection services`). This S121 follow-on attests and remediates only the current-only persistence surface; no history was rewritten.
- Source digests at the mixed commit: `_lease.py` `9d7932f1695c3fedc2016fdc2171825f66802dfc`, `_journal.py` `d45023b1df340b49466d7380dfdb8a8b182a4a53`, `test_lease.py` `b9105b55ca35536e7569dc956fe711dac18d0ee9`, and `test_journal.py` `4925f4863580f43a09c58859c978352419660801`.
- Final S121 attestation source digests: `_lease.py` `d83c44ddd540c0f14f4a57d972b6758a73095e90`, unchanged `_journal.py` `d45023b1df340b49466d7380dfdb8a8b182a4a53`, `test_lease.py` `a81d6687a97210b9d02ec0b7a9b166e8eb82b968`, and `test_journal.py` `5b69c69882e29e870d4928c42c62f4c83945ab13`.

## Description

- Used Vaultspec RAG repeatedly to locate the canonical lease storage, journal parser, acquisition/inspection paths, and refusal tests; confirmed each finding with an exact repository census.
- Confirmed the PRE_RELEASE delete-and-refuse rule in the governing research and accepted ADRs.
- Deleted `_OperationLeaseRecordV1`, `_legacy_path_for`, `migrate_legacy_before_acquisition`, its acquisition call, and the redundant `_parse_operation_journal_record` wrapper. The remaining persistence authorities hydrate lease schema v2 and journal snapshot schema v6 only.
- Added one narrow refusal guard for a superseded operation-keyed lease path. Under the canonical lease lock, `inspect` and `acquire` compare the retired path with the current scope path and use only `lexists`; they do not open, parse, translate, delete, or rewrite retired bytes. A path collision where `scope_ref == operation_id` is deliberately allowed through the current v2 parser.
- Replaced the synthetic v1-at-current-path fixture with a real historical operation-keyed filename and payload. The witness now requires both `inspect` and `acquire` to raise, preserves the historical bytes, and leaves no v2 successor. The valid current-v2 collision remains usable and byte-stable.
- A read-only workspace census found no affected nonterminal operation invocation or durable operation lease/journal artifact requiring migration; the unrelated terminal profile handover artifact was left untouched.

## Outcome

- `uv run --no-sync ruff check src/cadrumo/adapters/persistence/operations/_lease.py src/cadrumo/adapters/persistence/operations/_journal.py src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py` passed.
- `uv run --no-sync ty check src/cadrumo/adapters/persistence/operations/_lease.py src/cadrumo/adapters/persistence/operations/_journal.py` passed.
- `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/operations/tests/test_lease.py src/cadrumo/adapters/persistence/operations/tests/test_journal.py src/cadrumo/application/operations/tests/test_journal.py` passed: 50 tests.
- Exact scoped searches return no `_OperationLeaseRecordV1`, `_legacy_path_for`, `migrate_legacy_before_acquisition`, `_parse_operation_journal_record`, or compatibility vocabulary in application/persistence operation code; the only expected retired-path symbol is the private refusal helper and its two call sites.
- The aggregate application/persistence operation lane rerun recorded 306 passes and one unrelated persistence-facade export-inventory assertion from concurrent secure-reference work; the assertion concerns additional secure-reference exports and is outside the S121 paths.
- Vaultspec RAG searches returned the canonical lease and journal authorities and their focused tests. The final semantic and exact census proves no duplicate current parser or redeclared retired reader/migrator remains.

## Verification

- The focused current-only matrix, scoped Ruff, and scoped type check above are the post-remediation gates.
- `vault check all --feature tui-architecture` passed after feature-index regeneration and modified-stamp repair.
- The S121 plan row was closed through the Vault CLI, preserving two unknown plan blocks.

## Notes

No durable user data was deleted. The historical witness is test-local and remains byte-for-byte unchanged on refusal. The deleted source surface is recoverable through the mixed source commit and this one follow-on Git commit; this follow-on carries no compatibility path, data rewrite, or history rewrite.
