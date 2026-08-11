---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:dbb86e831311b45f3872b2fcdbe5ffd0c0f6b49a4a0c9b570c18c5d480684c52'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S04 binding export derivation review`

## Scope

Formal read-only review of the unstaged `W01.P02.S04` change in `_export.py` and `test_casilla_field_kind_enrollment.py` against the `casilla-schema` plan, research, canonical-derivations ADR, registry-authority rule, quality gates, and shared-worktree rule. Semantic discovery used `vaultspec-rag` before exact source inspection. The review examined fixed- and row-binding re-derivation, the real bundled Modelo 720 regression, canonical ownership, and test truthfulness. Unrelated shared worktree changes were excluded.

The production change is narrow and correctly located in the existing facade-exported `derive_export_layouts_from_bindings` authority. It makes the fixed-selector path follow the row-selector path's existing idempotence contract: a resolved record that already contains the binding-kind field for the same binding is preserved rather than derived a second time. No new derivation, compatibility alias, or competing ownership surface is introduced.

The new Modelo 720 regression loads the real bundled authority, resolves the 2025 `0A` snapshot through production code, observes 43 binding fields, checks field-id uniqueness, and proves a second derivation returns the resolved layouts unchanged. It has no fake, mock, stub, patch, monkeypatch, skip, xfail, copied fixture row, or mirrored derivation logic. Independent production-path probes also proved idempotence for the real fixed-binding Modelo 131 snapshot and the real row-binding Modelo 349 snapshot.

## Findings

### s04-binding-export-derivation-review | medium | The scoped test module is red because three row-binding fixtures use an inadmissible encoding

`test_casilla_field_kind_enrollment.py` constructs three real `ExportRecordDefinition` fixtures with `encoding="utf-8"`. The production model requires an `ExportEncoding` member, and the closed enum admits ASCII, CP1252, ISO-8859-1, ISO-8859-15, and Latin-1, not UTF-8. Those tests therefore fail during model validation before exercising the row-binding behavior they claim to verify. The new Modelo 720 regression passes, and independent real-authority probes show the row path is idempotent, so this is not evidence of a production defect in the S04 guard. It is nevertheless an actionable verification failure in the scoped test file: the focused module reports 2 passed and 3 failed, leaving the committed row-binding regressions unable to protect the derivation contract.

## Recommendations

Change the three invalid row-binding fixtures to use a real admitted `ExportEncoding` member appropriate to their ASCII-only synthetic records, then rerun the complete scoped test module. Do not weaken the production model or add string coercion or compatibility behavior. Preserve the new real-authority M720 regression and the single canonical derivation owner.

## Verification

- New M720 regression alone: 1 passed in 18.81 seconds.
- Complete scoped test module: 2 passed, 3 failed in 21.23 seconds. All failures occur at `ExportRecordDefinition` construction because `encoding="utf-8"` is not an `ExportEncoding` member.
- Real-authority idempotence probe: M720 2025 `0A`, fixed selectors, 43 binding fields, idempotent; M131 2025 `1T`, fixed selectors, 97 binding fields, idempotent; M349 2025 `1T`, row selectors, 13 binding fields, idempotent.
- Scoped Ruff: exit 0, all checks passed.
- Scoped BasedPyright: exit 0, zero errors, warnings, and notes.
- Scoped `git diff --check`: exit 0.
- Canonical-owner check: the change remains inside the existing facade-exported `derive_export_layouts_from_bindings`; no duplicate production derivation or authority declaration was added.

Verdict: **CHANGES REQUESTED.** The production S04 derivation change and real M720 regression are semantically sound, idempotent for both fixed and row bindings, and free of duplicate authority or compatibility restoration. S04 cannot honestly close while its focused test module is red and the three row-binding regressions do not reach their asserted behavior.
## Resolution

The MEDIUM finding is resolved. The three row-binding fixtures now import and use the canonical `ExportEncoding.ASCII` member. This is an admitted production encoding suitable for the fixtures' ASCII-only content; it does not weaken model validation, add coercion, or restore compatibility behavior. The complete owning module now reaches every asserted fixed- and row-binding behavior and passes 5 tests.

Resolution verification:

- Complete scoped test module: 5 passed in 19.21 seconds.
- Scoped Ruff: exit 0, all checks passed.
- Scoped BasedPyright: exit 0, zero errors, warnings, and notes.
- Scoped `git diff --check`: exit 0.
- Exact diff review: only the canonical enum import and three fixture-value replacements were added to resolve the finding; production logic and the real M720 regression are otherwise unchanged.

Final verdict: **PASS.** The sole finding is closed. `W01.P02.S04` may honestly close: fixed- and row-binding derivation are idempotent, the real bundled M720 regression proves resolved binding fields survive re-derivation without duplication, all owning tests execute, and no duplicate authority, compatibility restoration, test double, or mirrored business logic was introduced.
