---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1c70072389c1947ac7858b5a585c6c8aefe182495af2298b673b18462822e5de'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P01.S01 legacy TUI migration manifest review`

## Scope

Independent review of `W01.P01.S01` against the accepted TUI architecture decision, its research census, the live legacy TUI tree, the current `dev/quality/import_hygiene_scan.py` and `dev/tests/test_import_hygiene_scan.py` diffs, the empty S01 execution record, and current-tree validation evidence.

## Findings

### aggregate-count-proof | medium | The tests do not prove an exact identity census

`dev/tests/test_import_hygiene_scan.py:43` hard-codes the current module count while lines 44-46 accept only aggregate lower bounds, contrary to the quality rule that gates properties rather than exact counts. Those assertions can stay green when one required consumer disappears and an unrelated row replaces it; the two spot identities at lines 49-63 do not prove the full facade export set, every production and test consumer, every development surface, or each row's exact owner and replacement.

### unverified-gates | medium | Focused validation produced no passing evidence and the execution record is empty

The focused `dev/tests/test_import_hygiene_scan.py` plus Ruff command exceeded 124 seconds without a result, so neither gate is evidenced green. The scaffolded `W01.P01.S01` execution record contains no Description, Outcome, Notes, command output, or commit reference. Current `git diff --check` is clean for the reviewed files, but that is not substitute evidence for AST behavior or the exact CLI JSON route.

### silent-consumer-parse-loss | high | Consumer parse failures silently remove rows from the supposedly exact manifest

`dev/quality/import_hygiene_scan.py:343-354` converts a missing, malformed, or undecodable consumer into an empty import list, and lines 1519-1522 independently suppress the same parse failures for qualified references. A consumer file that cannot be parsed therefore contributes no import or reference rows and does not fail the manifest, whereas legacy-module parse failures correctly raise at lines 1335-1338. This violates exactness and fail-closed census semantics.

### identity-policy-fallback | high | New symbols and consumers enter the manifest without an accepted identity disposition

`dev/quality/import_hygiene_scan.py:1372-1374` falls back from an unlisted symbol to its source module's broad disposition, and lines 1485-1542 automatically enroll every newly discovered consumer. Consequently a new export or import from any already-known legacy module, or a new consumer of an existing identity, joins the manifest without a reviewed exact `(module, symbol, consumer class)` policy row. The only refusal test at `dev/tests/test_import_hygiene_scan.py:76-90` plants a new module, so it cannot catch either fail-open path. This contradicts the accepted decision that the generated migration manifest is keyed by exact module, imported symbol, and consumer class and admits no new identity.

## Recommendations

- Replace aggregate thresholds with an independently derived, bidirectional identity join that proves every discovered declaration, export, import, and qualified reference has exactly one expected disposition and every expected identity still exists.
- Make every scanned Python read or parse failure a `TuiMigrationManifestError` carrying the repository-relative locator; prove the gate bites with real temporary files and no patches or test doubles.
- Require explicit accepted policy at the identity granularity authorized by D12, including consumer class where the decision requires it; add refusal cases for a new symbol in an existing module and a new consumer of an existing symbol.
- Re-run the focused pytest file, Ruff on the two reviewed files, the live CLI JSON emission route, and the applicable VaultSpec check; record exact commands and results in the S01 execution record before closure.

## Re-review disposition

### silent-consumer-parse-loss | closed | Consumer parse failures now refuse the manifest

`_parse_tui_manifest_consumer` now raises `TuiMigrationManifestError` for read, syntax, or decoding failures before either import or qualified-reference discovery, and `test_tui_migration_manifest_refuses_an_unreadable_consumer` exercises the refusal with a real malformed temporary Python file.

### identity-policy-fallback | closed | The accepted semantic identity digest rejects new symbols and consumers

The scanner now checks the complete discovered semantic identity set against `_ACCEPTED_TUI_MIGRATION_IDENTITY_SHA256`, and `test_tui_migration_manifest_refuses_a_new_symbol_or_consumer_identity` proves both a new export in an accepted module and a new consumer of an accepted symbol are rejected. The module-level disposition fallback no longer permits either change to enter the accepted manifest silently.

### aggregate-count-proof | open-medium | The exactness digest omits disposition and deletion-proof fields

The aggregate thresholds were removed, closing their direct substitution weakness, but `_tui_migration_identity_sha256` hashes only kind, legacy module, symbol, consumer, and consumer kind. Changes to `owner_lane`, `replacement`, or deletion proof can therefore leave the digest green, while the live test checks only that those values are non-empty plus two spot mappings. The original requirement to prove each row's exact owner and replacement remains incomplete.

### unverified-gates | open-medium | The execution record is populated but current focused gates remain unconfirmed

The S01 execution record now contains implementation detail and reports focused Ruff and three new tests passing, so the empty-record portion is closed. The bounded current re-review command covering the four relevant regression tests plus Ruff did not complete on the shared drive before review termination and produced no result; the record also does not preserve exact command lines. Current passing evidence for the remediated surface therefore remains incomplete.

## Final re-review disposition

### aggregate-count-proof | closed | Full semantic identity and disposition rows are digest-bound

`_tui_migration_identity_sha256` now binds kind, legacy module, symbol, consumer, consumer class, owner lane, replacement, deletion proof, and state while excluding only volatile line locators. `test_tui_migration_manifest_refuses_disposition_drift` independently mutates owner lane, replacement, and deletion proof and proves each change is refused. The accepted live digest therefore covers the full stable row contract rather than an aggregate count or partial identity.

### unverified-gates | closed | Exact bounded commands and completed results are recorded

The S01 execution record now preserves the exact focused commands and outcomes: Ruff formatting completed, Ruff checks passed, Ruff format checking passed, and `uv run --no-sync pytest -q dev/tests/test_import_hygiene_scan.py -k "tui_migration_manifest"` completed with eight passing tests in 281.40 seconds. The previously empty and non-specific evidence gap is closed.

No critical, high, or medium findings remain from this review.
