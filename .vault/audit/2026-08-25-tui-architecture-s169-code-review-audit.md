---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a281578cf4e01233433b552ce4a5a64e0c0feb1b1921c3ae908f1e4f243a95a8'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-25-tui-architecture-s169-plan-review-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S169]]"
---

# `tui-architecture` audit: `S169 code review`

## Scope

Independent implementation review of `W03.P20.S169` against the accepted TUI
architecture ADR, the amended plan row, the plan-only architecture review, and
the S169 execution record. The committed review state is
`cfa4a7de414fa8edee9052f70a8d6f8fb20fdff0`; the S169 surface is unchanged from
`cf87cd7fb21bc3e3232357dc7dd34e0b5800c95a`, with provenance frozen through
`796a29fafa1297f88e3e2a65a0490c97bc451902`,
`41e98433f73ef5cfb82c9e94e000fc638bd6a57d`,
`49577a525c1d0ff443ab9d4c692b24e27d7936d0`, and
`f3d439a8bfde16029b9ece651d687268a49d9853`.

The review read the defining modules and focused tests, ran semantic discovery
over code and decisions, and ran an exact committed-HEAD AST/source census for
definitions, imports, aliases, bridges, decoders, and retired paths. The dirty
live tree carries unrelated concurrent public-module relocations, including
temporarily deleted private error modules and untracked public replacements;
those changes are outside the frozen evidence and are not attributed to S169.

## Findings

### one-select-proof | medium | The four new query-count tests count repository calls, not SQL SELECT statements

`src/cadrumo/adapters/persistence/profile/tests/test_secure_model_document.py:58`,
`src/cadrumo/adapters/persistence/profile/tests/test_secure_model_document.py:100`,
`src/cadrumo/domain/modelos/tests/test_secure_storage_roundtrip.py:141`, and
`src/cadrumo/domain/modelos/tests/test_secure_storage_roundtrip.py:180` replace
`SecureObjectRepository.load` with a `pytest.MonkeyPatch` wrapper and assert that
the wrapper was called once. That proves one public repository invocation, but
not the plan's exact one-`SELECT` contract: a future implementation could issue
two SQL queries inside one `load` call and every test would remain green. The
same construction conflicts with the repository quality rule forbidding mocks,
fakes, and monkeypatches in real-behaviour gates. The payload/revision
interleaving assertions are useful and do demonstrate that the kernel consumes
one returned `SecureObjectRecord`; the defect is the narrower claim that these
tests prove the number of database reads.

No critical or high implementation defect was found. Both singleton kernels
make `load` project `load_revisioned`; each present path decodes `record.payload`
and returns `record.revision_id` from the same single repository result, while
each absent path returns its declared empty document and the absent-revision
sentinel. The WorkUnit adapter delegates decoding to the enveloped kernel and
retains one classification/version translation boundary whose structured
context is preserved.

The committed-HEAD AST census found exactly one
`WorkUnitCatalogueRepositoryProtocol` definition, in
`src/cadrumo/domain/modelos/work_unit_repository.py:16`; exactly twenty
application import sites, all direct from that defining module; and zero wrong
imports or symbol aliases. The old definition and package re-export are absent.
The retired application replay-guard module is absent, package initializers do
not bridge the adapter-owned replacement, and production consumers name
`src/cadrumo/adapters/persistence/profile/recipient_replay_guard.py` directly.
The WorkUnit hand decoder and secondary raw reader are absent. Existing real
encrypted-SQL roundtrip, ciphertext-at-rest, corruption refusal, concurrent CAS,
and revision-lineage coverage remains meaningful on the governed storage path.

## Recommendations

Replace the four repository-method wrappers with real SQLAlchemy engine
statement instrumentation, following the existing
`before_cursor_execute`/`event.remove` pattern in
`src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_object_write_batching.py`.
Assert exactly one secure-object `SELECT` for both present and absent reads in
both wire shapes, retain the interleaving payload/revision cohesion assertion,
and do not use a mock, fake, stub, or monkeypatch. Re-run the two focused test
modules, the import-hygiene gate, and scoped Ruff from a clean committed state.

## Disposition

**REVISION REQUIRED.** The production cutover satisfies the reviewed ownership,
atomic-read, direct-import, CAS, lineage, and encryption contracts, but S169 may
not receive a PASS while the medium one-`SELECT` verification gap remains.

