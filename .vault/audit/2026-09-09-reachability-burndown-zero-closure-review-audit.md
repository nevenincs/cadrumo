---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1bb7eac367c05a262918f713280d785b397767d7824e16b6aefa4e333b59f195'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace reachability-burndown with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `reachability-burndown` audit: `exact zero closure review`

## Scope

Reviewed the live reachability-burndown worktree against its accepted decision,
implementation plan, exact-confidence audit, zero-target quality gates, and focused
detector-teeth tests. The review covered deletion overreach, import and ownership
boundaries, compatibility surfaces, duplicate authorities, exact finding projection,
and the ability of each closure gate to detect a planted defect.

## Findings

### unconsumed-export-teeth | high | The clean export signal is not backed by a passing planted-defect control

`dev/quality/unconsumed_export_coverage.py:66` chooses repository-relative identity
whenever the supplied tree happens to live below the repository, while
`dev/quality/tests/test_unconsumed_export_coverage.py:24` constructs the expected
identity relative to the supplied package root. In the repository-configured pytest
scratch tree those identities differ, so the positive detector-teeth case at line 28
returns no finding for a declared unused export. The focused suite exits 1 with one
failure and eight passes. Consequently the live `unconsumed-export coverage: no
findings` result is not sufficient closure evidence: the gate's positive control is
red at the exact point where it must prove that zero is meaningful.

Validation: `uv run --no-sync pytest -q
dev/quality/tests/test_unreachable_module_coverage.py
dev/quality/tests/test_unused_symbol_coverage.py
dev/quality/tests/test_unconsumed_export_coverage.py` exits 1 at
`test_an_exact_unused_export_without_a_production_importer_is_reported`.

### exact-confidence-exit | high | An all-zero exact audit still exits nonzero

`dev/audit/unreachable_code.py:1767` preserves the unfiltered result's `FINDINGS`
outcome after removing every row outside the requested confidence tier. The CLI at
line 1921 then returns the findings status solely from that stale outcome, although its
line 1896 contract says it exits on findings and the rendered JSON contains no modules,
symbols, tests, or exact finding identifiers. The current tree therefore prints an
all-zero exact headline while the process exits 1. This is not residual exact debt; it
is lower-confidence debt leaking through the projection's status. It makes the exact
audit unusable as an unambiguous automation contract and conflicts with the plan's
requirement that audit and zero-target gates agree from one stable revision.

Validation: `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact
--json` reports 2046 of 2046 shipped modules reachable, empty `exact_finding_ids`,
empty `modules`, `symbols`, and `tests`, but exits 1.

### detector-typecheck | high | The reviewed detector surface fails strict type checking

The focused strict checker reports ten errors. Nine are in
`dev/audit/unreachable_code.py`, including deprecated `ast.Index` use at line 943 and
unknown container or AST value types at lines 969-972 and 1295-1301. One is the
partially unknown `consumed` set inferred at
`dev/quality/unconsumed_export_coverage.py:90`. Shipping the closure with these errors
would violate the repository's strict type-quality gate even though Ruff accepts the
same files.

Validation: `uv run --no-sync basedpyright dev/audit/unreachable_code.py
dev/quality/unconsumed_export_coverage.py dev/quality/unused_symbol_coverage.py
dev/quality/unreachable_module_coverage.py` exits 1 with ten errors. `uv run --no-sync
ruff check` over the same detector files and representative changed test-support files
exits 0.

No critical findings were identified. No medium or low findings were identified in
the reviewed closure contract. The three live zero-target commands for unreachable
modules, exact unused symbols plus orphaned tests, and unconsumed exports each exit 0,
but the findings above prevent treating those headlines as final closure.

### closure-rereview | low | All three high findings are resolved in the live tree

Re-review of the current tree confirmed that every previously recorded blocker is
closed. The focused unreachable-module, unused-symbol, and unconsumed-export
detector-teeth suite passes all nine tests, including the planted unused-export
positive control. The filtered exact audit now returns a `CLEAN` outcome and exits 0,
with 2046 of 2046 shipped modules reachable and empty exact finding, module, symbol,
and orphan-test populations. Targeted strict checking of the four detector modules
reports zero errors, warnings, or notes.

The live zero-target gates independently exit 0 and report no unreachable modules, no
exact unused symbols or orphaned tests, and no unconsumed exports. Whole-tree Ruff,
whole-tree Ruff formatting, and the import-architecture gate also exit 0. A concurrent
first attempt at the unused-symbol gate encountered a Windows thread-start failure;
the required sequential rerun completed normally at exact zero and exit 0, so the
transient process-resource failure is not product or detector evidence.

Validation: `uv run --no-sync pytest -q
dev/quality/tests/test_unreachable_module_coverage.py
dev/quality/tests/test_unused_symbol_coverage.py
dev/quality/tests/test_unconsumed_export_coverage.py` exits 0 with nine passes;
`uv run --no-sync python -m dev.audit.unreachable_code --confidence exact --json`,
`uv run --no-sync python -m dev.quality.unreachable_module_coverage`, `uv run
--no-sync python -m dev.quality.unused_symbol_coverage`, and `uv run --no-sync python
-m dev.quality.unconsumed_export_coverage` each exit 0; `uv run --no-sync basedpyright
dev/audit/unreachable_code.py dev/quality/unconsumed_export_coverage.py
dev/quality/unused_symbol_coverage.py dev/quality/unreachable_module_coverage.py`
reports zero diagnostics; and the repository commands behind `check-style`,
`check-format`, and `check-imports` each exit 0.

## Recommendations

Make export finding identities relative to the scan root under both production and
isolated detector-teeth execution, then rerun the focused three-file suite and the live
export gate. Recompute the filtered audit outcome from the filtered populations so an
empty exact projection is clean while a non-empty exact projection still fails. Resolve
all strict checker diagnostics without suppressions, aliases, shims, or widened
exclusions. Rerun the exact audit, all three zero-target gates, their detector-teeth
suite, Ruff, and the repository's owning strict type gate before declaring closure.

These recommendations have been satisfied in the re-reviewed tree. No follow-up
implementation recommendation remains from this audit.
