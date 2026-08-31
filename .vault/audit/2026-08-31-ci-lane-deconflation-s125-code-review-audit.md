---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7d3e8d462cbdcbb1449ef239ba288dedb642a20191343a93d1ad4655e5727045'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
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

# `ci-lane-deconflation` audit: `P05 S125 code review`

## Scope

Independent review of `P05.S125` at `65a66fe68b74e336505e1eab8ecc9eb461da87de`, against the approved CI-lane plan and size-budget ADR. Reviewed all 18 committed paths, the complete 77-member registry assembly, declaration and aggregate ownership, direct consumer imports, public lazy exports, changed tests, baseline diff, and the S125 execution record. Current `HEAD` was the reviewed commit; the shared worktree carried unrelated concurrent changes, so source findings were derived from immutable commit objects only.

## Findings

### P05 S125 code review | high | registry relocation changes the canonical 77-member iteration order

`src/cadrumo/adapters/persistence/storage/_namespace_registry.py` preserves all 77 namespace definitions but moves `MODELO_EDIT_RECEIPT_NAMESPACE` from index 19 in the former `STORAGE_NAMESPACE_REGISTRY.namespaces` tuple to index 63, after `MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE`. Every member that lay between those positions now has a different iteration position. `StorageHierarchyRegistry` exposes this tuple as part of its hierarchy contract, while the changed tests assert membership and lookups but not the full ordered sequence. P05.S125 is an extraction with no authorized lifecycle or hierarchy semantic change, so restore the former ordering and add a source-backed sequence assertion.

### P05 S125 code review | high | execution evidence contains unreproducible placeholder commands

`.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S125.md` lines 40 through 42 record `ruff check <S125 paths>`, `ruff format --check <S125 paths>`, and a Python size-budget command ending in `...`. The stated lint result and `174/1250` plus `1203/1250` measurement therefore cannot be independently reproduced or matched to the reviewed source set. Replace every placeholder with exact complete commands, enumerate the paths, and include the complete measurement expression and result before advancing the lane.

### P05 S125 code review | low | final repair verification resolves both high findings

Source/test repair `37f1b786154ee6db12643e793af696d8d00c529f` restores `MODELO_EDIT_RECEIPT_NAMESPACE` between `MODELO_RECONCILIATION_RECORDS_NAMESPACE` and `SYNC_RUN_RECORDS_NAMESPACE`. Immutable predecessor comparison confirms the full 77-member sequence is now exactly equal, and `test_secure_object_registry_preserves_the_declared_namespace_sequence` makes that contract explicit with a literal expected key tuple rather than deriving expectations from the registry. Focused `test_namespace_registry.py` passed 30 tests. Record repair `130fdc663f7e8b9cfd6567420dd00822dd89d5ba` supplies all 17 original source/test paths for both ruff gates and a complete two-subject `measure_module_lines` command with `174/1250` and `1203/1250` results. No placeholder remains; neither repair changes the CI-lane plan or `dev/audit/size_budget_baseline.json`. Both prior high findings are resolved.

## Recommendations

- Restore `MODELO_EDIT_RECEIPT_NAMESPACE` to its previous position between `MODELO_RECONCILIATION_RECORDS_NAMESPACE` and `SYNC_RUN_RECORDS_NAMESPACE`; prove all 77 ordered entries equal the predecessor sequence.
- Amend the S125 execution record with exact runnable ruff and size-budget commands, their complete selected paths, and their observed output. Re-review both corrections before P05 advances.

No additional P05.S125 corrective work is required.

The relocation otherwise has the intended ownership shape: `_secure_object_namespaces.py` retains namespace contracts and declarations, `_namespace_registry.py` owns only the aggregate hierarchy and logical-path helpers, direct consumers import the aggregate from its canonical module, and no legacy aggregate/helper facade remains. The commit does not change `dev/audit/size_budget_baseline.json`.

