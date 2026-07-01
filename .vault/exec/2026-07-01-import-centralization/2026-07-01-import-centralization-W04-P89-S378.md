---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S378'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S378 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Add a ratcheting production-Family-1 baseline JSON that fails the gate when the current cross-package private-import count exceeds the committed baseline, and shrink the baseline in the same commit as any fix that reduces the count and ## Scope

- `dev/import_hygiene_scan.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a ratcheting production-Family-1 baseline JSON that fails the gate when the current cross-package private-import count exceeds the committed baseline, and shrink the baseline in the same commit as any fix that reduces the count

## Scope

- `dev/import_hygiene_scan.py`

## Description

Precondition correctness fix ahead of this Step's ratcheting-baseline work, not
the baseline itself.

- Found `discover_facades()` matched only the plain `__all__ = [...]` form
  (`ast.Assign`) and silently skipped the annotated `__all__: list[str] = [...]`
  form (`ast.AnnAssign`), so `aeat/core/__init__.py` was never registered as a
  facade at all.
- Added `_dunder_all_assignment_value()` recognising both `ast.Assign` and
  `ast.AnnAssign` targets naming `__all__`; `discover_facades()` now consumes
  it uniformly for both forms.
- Confirmed via `rg` there are zero augmented `__all__ += [...]` /
  `.extend([...])` / `.append(...)` forms anywhere under `src/aeat`, so no
  additional handling was required for that shape; only two other
  `__init__.py` files use the annotated form and both are empty
  (`list[str] = []`), so only `aeat.core` was affected in practice.
- Added `dev/tests/test_import_hygiene_scan.py` (real-behavior: exercises the
  actual `src/aeat` tree, no fixtures/mocks) asserting `aeat.core` is now
  discovered as a facade with `Modelo` / `CasillaId` in its `all_names`, plus
  unit coverage of the new helper's plain/annotated/unrelated/bare-annotation
  cases.
- Re-ran the scanner before/after the fix on the current tree: Family-1
  cross-package-private-import counts are unaffected (834 non-test / 2439
  total both before and after — that classification does not depend on facade
  discovery). The fix-strategy classification changes: `needs_promotion`
  drops from 18 to 5 pairs; all 13 eliminated pairs belong to `aeat.core`
  (`Modelo`, `OUT_OF_SCOPE_OBLIGATIONS`, `Period`, `PeriodError`,
  `PostFilingEventKind`, `ResultDisposition`, `STRICT_FROZEN_CONFIG`,
  `TaxDomain`, `UNMODELED_OBLIGATIONS`, `classify_post_filing_event_kind`,
  `post_filing_event_is_actionable`, `resolve_active_bucket_id`,
  `result_disposition_is_refund`) and are now correctly classified as
  `already_in_facade` (simple consumer rewrite, not a promotion). The
  remaining 5 `needs_promotion` pairs are genuine (their owning packages'
  `__init__.py` files have no `__all__` at all, or use the plain form with the
  symbol genuinely absent).

## Outcome

`ruff check` and `ruff format --check` pass on the touched files; the new
`dev/tests/test_import_hygiene_scan.py` suite (5 tests) passes; the scanner
still exits 0 and its self-report is internally coherent. This Step's actual
deliverable (the ratcheting baseline JSON) remains open; this record captures
only the scanner-correctness precondition and the corrected counts that the
next pass should baseline from.

## Notes

Landed via a HEAD-anchored `git apply --cached` plus a `commit-tree` /
`update-ref` (compare-and-swap) drive rather than a plain `git commit`,
because the shared working tree already carried unrelated live peer WIP in
the same file (an `_UTF_8: Final[str]` lint-consistency refactor from a prior
commit's follow-up) and a huge volume of unrelated staged changes across the
rest of the repository from concurrent campaigns. The peer's in-file WIP and
all other campaigns' staged work were left untouched in the working
tree/index for their own owners to commit. The Step is intentionally left
unchecked (per instruction): this record documents a precondition fix, not
completion of S378's ratcheting-baseline deliverable.
