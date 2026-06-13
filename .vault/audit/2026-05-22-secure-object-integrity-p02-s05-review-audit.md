---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-22-secure-object-integrity-P02-S05]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `secure-object-integrity` P02.S05 Code Review

P02S05-001 | HIGH | Guard misses known default repository wrapper paths
The guard only considers test files whose source contains the literal string `SecureObjectRepository` and then only records direct zero-argument `SecureObjectRepository()` AST calls. That misses the known contamination class described in the drift research: tests that open `EphemeralMasterKeyProvider` and instantiate domain or adapter repositories whose constructors default internally to `SecureObjectRepository()`. Examples include `InvoiceCatalogueRepository`, `TransactionCatalogueRepository`, and `FiledDeclaracionObservationStore`. If `AEAT_DATABASE_URL` isolation regressed in those tests, the current guard would skip or miss them because the test source does not need to name `SecureObjectRepository`, even though writes still route through the process-default SQL repository.

Resolution: addressed before S05 closure. The guard now detects actual constructor calls for direct `SecureObjectRepository()` and known default SQL-backed wrapper constructors, including transaction, invoice, filing, workflow, profile, calculation, live snapshot, attachment, model catalogue repositories, and filed-declaration observation store aliases. Existing discovered file-level violations are explicitly inventoried as pending P02.S06 work; new unclassified files fail the guard. The filed-declaration alias pass surfaced two additional pending files, which were added to the P02.S06 inventory.

P02S05-002 | HIGH | Raw whole-file isolation exemption can be bypassed by comments or unrelated helpers
`_declares_temp_database_isolation()` returns true when the raw file text contains both `AEAT_DATABASE_URL` and `dispose_engine`, and the main test then suppresses every default repository call in that file. This does not prove that the environment variable is set to a temporary database, that cached engines are disposed before and after the relevant operation, or that the default repository call is inside the isolated scope. Comments, docstrings, or one unrelated fixture can therefore exempt an unisolated `EphemeralMasterKeyProvider` plus default repository use elsewhere in the same module.

Resolution: addressed before S05 closure. The guard now requires an actual autouse pytest fixture that sets `AEAT_DATABASE_URL` to a temp SQLite URL and calls `dispose_engine()` around a yielding fixture. Raw comments and unrelated text no longer exempt a file.

P02S05-003 | MEDIUM | Ephemeral-key detection can false-positive from comments
The initial file filter checks for `EphemeralMasterKeyProvider` with a raw substring search rather than AST usage. A test module that has a legitimate default `SecureObjectRepository()` call but only mentions `EphemeralMasterKeyProvider` in a comment or docstring would be treated as risky and fail unless it declares database isolation. The constructor-call side avoids comments by using AST, but the ephemeral-key side does not.

Resolution: addressed before S05 closure. The guard now detects actual `EphemeralMasterKeyProvider(...)` calls via AST instead of raw substring search.

## Gates Observed

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed 1 test after remediation.

## Policy Notes

No new no-fakes/no-stubs/no-mocks/no-monkeypatch/skip/xfail violation was found in `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`. The test is static and imports from the codebase under review, but the findings above mean it is too weak to enforce the intended P02 hygiene contract.

## Re-review After Remediation

P02S05-001-R1 | HIGH | Wrapper coverage is improved but still misses a known risky store
Status: partially resolved. The remediation removes the direct `SecureObjectRepository` substring gate and adds a broad inventory of default SQL-backed wrapper constructors. However, the inventory still omits `FiledDeclaracionObservationStore`, one of the original drift-research contamination examples. That store constructs a default `SecureObjectRepository()` internally, and a synthetic AST check with `EphemeralMasterKeyProvider()` plus `FiledDeclaracionObservationStore(...)` produced no risky constructor calls. P02.S05 should keep this finding open until the known store is classified by the guard or otherwise covered by an equivalent static rule.

P02S05-002-R1 | HIGH | Raw whole-file isolation exemption no longer closes on comments alone
Status: resolved for the reviewed failure mode. The guard now inspects AST for an autouse pytest fixture that sets a temp SQLite `AEAT_DATABASE_URL` and disposes the engine around a yielding fixture. A comment-only `AEAT_DATABASE_URL` / `dispose_engine` sample no longer satisfies isolation. Follow-up for P02.S06: drain the explicit `_PENDING_P02_S06_FILES` inventory and keep pending-file exemptions scoped to files, not as permanent policy.

P02S05-003-R1 | MEDIUM | Ephemeral-key detection no longer false-positives from comments
Status: resolved. The guard now detects actual `EphemeralMasterKeyProvider(...)` calls via AST. A sample module that only mentions `EphemeralMasterKeyProvider` in a comment is not treated as an ephemeral-key test.

## Re-review Gates Observed

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed 1 test.

## Final Re-review After Filed-declaration Store Coverage

P02S05-001-R2 | HIGH | Known wrapper coverage now includes filed-declaration stores
Status: resolved for P02.S05. The constructor inventory now includes both `FiledDeclaracionObservationStore` and `FiledDeclarationObservationStore`. A targeted AST probe confirmed that `EphemeralMasterKeyProvider()` combined with either filed-declaration store spelling is now reported as a risky default SQL-backed constructor call. The two existing files surfaced by that coverage, `src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py` and `src/aeat/entrypoints/cli/test_registry_cli.py`, are explicitly listed in `_PENDING_P02_S06_FILES`, so the guard still fails for new unclassified files while preserving the existing backlog for P02.S06.

Follow-up remains P02.S06: drain `_PENDING_P02_S06_FILES` by adding real temp database isolation or explicit repository injection to each inventoried file. No additional P02.S05 findings remain open after this final re-review.

## Final Re-review Gates Observed

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed.
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` passed 1 test.
