---
tags:
  - '#exec'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S03'
related:
  - "[[2026-07-01-determinism-replay-residual-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace determinism-replay-residual with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-01-determinism-replay-residual-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Confirm whether the two ambiguous directory scans feed ordered output and ## Scope

- `wrap the output-feeding scans in sorted() at the boundary and leave the membership/aggregation scans alone.`
- `src/aeat/application/user_profile/_profile_repository.py`
- `src/aeat/entrypoints/cli/_ledger_import_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm whether the two ambiguous directory scans feed ordered output

## Scope

- `wrap the output-feeding scans in sorted() at the boundary and leave the membership/aggregation scans alone.`
- `src/aeat/application/user_profile/_profile_repository.py`
- `src/aeat/entrypoints/cli/_ledger_import_cli.py`

## Description

- Verified the two ADR-named ambiguous directory scans against the sort-at-output-boundary rule.
- `entrypoints/cli/_ledger_import_cli.py` `_resolve_import_paths`: the directory scan that determines the order statement files are imported (and thus created-row order) is ALREADY `sorted(...)` at the boundary — confirmed compliant, no change.
- `application/user_profile/_profile_repository.py` `ProfileRepository.list`: its `iterdir()` scan feeds two consumers — the operator-facing profile listing, whose order is sorted by its consumer `list_profiles` (sorts by `profile_id`, gated by `test_list_profiles_returns_sorted_listings`), and an order-independent uniqueness guard. Neither reaches an unsorted output listing, so per Decision 3 ("leave the confirmed membership/aggregation uses alone") the scan is intentionally NOT sorted — over-sorting it would be the misleading noise the ADR rejects.
- Added `entrypoints/cli/tests/test_import_directory_ordering.py`: pins the import-scan sort invariant (a directory of files created in non-sorted order resolves to sorted order; a non-importable extension is excluded; a single-file path passes through) so a future edit cannot silently regress it to raw OS scan order.

## Outcome

- No production code change was required: both output-feeding sites are already handled (import scan inline-sorted; profile listing sorted by its consumer). The previously-ungated import-scan sort is now gated (2 tests pass); ruff clean.
- The sort-at-output-boundary discipline is an ADR codification CANDIDATE only — not promoted to a project rule this cycle, per the codify discipline (never codify on first encounter; promote after it holds through a cycle).

## Notes

- This is a legitimate verify-then-no-change outcome the ADR Decision 3 explicitly anticipated; the deliverable is the verification conclusion plus the new regression gate for the one previously-ungated site.
