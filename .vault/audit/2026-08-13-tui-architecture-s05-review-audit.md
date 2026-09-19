---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:be250fb086dbb6439b0fc0bd45a940bf0f731e5696a6fec3569c74d4b5276e54'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `W01.P01.S05 independent review`

## Scope

Independent review of `W01.P01.S05`: the accepted TUI census contract, the real-tree manifest test, and its focused execution evidence. The review checked oracle independence, exact declaration and reverse-edge coverage, line identity, fail-closed behavior, and test-policy compliance.

## Findings

### shared-discovery-oracle | high | The proof repeats the generator's blind spots

The test derives modules, exports, imports, and qualified references with the same private helpers used by `generate_tui_migration_manifest`, including `_legacy_tui_modules`, `_legacy_export_origins`, `walk_module_imports`, and `_qualified_tui_references`. It also repeats the generator's line-wide reference suppression: if any legacy import occurs on a line, every qualified string reference reported on that line is discarded. A new qualified reference placed on the same physical line as a legacy import is therefore absent from both sides and leaves the accepted digest unchanged. Likewise, both paths inherit `_legacy_tui_modules` scanning only immediate `*.py` children. The comparison independently assembles sets, but it is not an independent source oracle and cannot prove the discovery helpers' completeness or fail closed on these new identities.

### duplicate-row-collapse | medium | Set comparisons and the digest do not prove one row per edge

All four discovered and manifested collections are converted to sets, and `_tui_migration_identity_sha256` also hashes a set of row facts. If the generator emits an identical module, export, import, or reference row twice, both the equality test and accepted digest still pass. This contradicts the test's `exactly one manifest row` contract and the Step outcome that the manifest invents no rows.

## Recommendations

- Add mutation-sensitive real-tree proofs for a nested legacy module and a qualified reference sharing a line with a legacy import, using a canonical source-discovery surface that does not inherit the manifest assembler's filtering decisions.
- Compare multiplicities or assert row-key uniqueness before set equality, and ensure the accepted digest refuses duplicate rows rather than normalizing them away.

The focused evidence reports two passing real-tree tests in 138.66 seconds and a clean Ruff check, with no mocks, fakes, patches, skips, xfails, or copied identity allowlist. Those gates exercise only the shared-oracle and set-normalized forms above, so they do not close either finding.

## Remediation re-review disposition

### shared-discovery-oracle | closed | Each reviewed discovery escape now has an independent mutation proof

The scanner now recursively discovers production modules below the legacy root, retains qualified-reference occurrences even when an import shares their physical line, and the acceptance test no longer imports the scanner's module, export, import, or reference discovery helpers. Focused synthetic-package tests directly prove the same-line reference and nested-module refusal forms. The real-tree module/export comparison uses independent filesystem and AST collection with occurrence counters.

### duplicate-row-collapse | closed | Row multiplicity now participates in comparison and digest identity

The production digest hashes the sorted row sequence rather than a set, and the acceptance proof compares declaration multiplicities with `Counter`. A planted duplicate semantic import changes the accepted digest and is refused.

### post-pin-verification | medium | The final accepted digest has not been exercised by pytest

The focused run honestly produced six expected stale-pin failures and six passes, revealing observed digest `2f77b05c5397ad31006a5d95d7f3f0a37fa416c0e856530fa96b63ccc9e747be`. That value was then mechanically updated in the production and scanner-test pins, but pytest was not rerun. Ruff proves syntax and lint only; it cannot establish that all twelve focused tests now pass with the final accepted state. One post-pin rerun of the exact focused pytest command is required before PASS. No critical or high findings remain.

## Final closure disposition

### post-pin-verification | closed | The uncontaminated accepted census passes the exact focused gate

Fixture source strings now interpolate `LEGACY_TUI_PACKAGE` rather than embedding discoverable legacy identities in the acceptance test's own AST. The resulting live census is restored to exactly 515 rows, decomposed as 16 modules, 129 exports, 351 imports, and 19 qualified references; the S05 test contributes zero consumer rows. Production and scanner-test pins agree on digest `4eda54f61f2d91912366af74bc8684732afce84ed2fb4e45c11c19ff28ee549f`.

The nested-module refusal, same-line import-plus-reference occurrence, and duplicate-row digest mutation proofs remain present. The final exact focused pytest command records 12 passed in 237.69 seconds, and the focused Ruff command passed. No critical, high, or medium findings remain.
