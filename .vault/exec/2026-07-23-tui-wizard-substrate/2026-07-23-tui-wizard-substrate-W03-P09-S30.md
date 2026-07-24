---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S30'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Run the full src collect-only and suite gates with owner-distinguished triage of the results and ## Scope

- `src/cadrumo/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the full src collect-only and suite gates with owner-distinguished triage of the results

## Scope

- `src/cadrumo/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Run full-tree collect-only: clean (13689 collected, zero errors), re-confirmed independently at the pushed retirement HEAD.
- Run the full `src/cadrumo` suite with complete on-disk log capture: 59 failed, 13630 passed.
- Re-run every failure near the campaign surface sequentially before triage; classify each failure signature by owner.
- Fix the four campaign-owned failures and land them as their own explicit-pathspec commits: module `pytestmark` placement in the TUI app, status screen, copy-assembly, and localized-failure test modules; per-test domain markers folded into module marks; one absolute self-import replaced with a path-relative catalogue root; a follow-up import-order fixup.

## Outcome

Collect-only is clean and the campaign surface is fully green across two passes. First pass: 59 failed / 13630 passed; four campaign-owned failures fixed. Settled-tree second pass after the peer landings: 41 failed / 13679 passed in parallel, reduced to a sequential-confirmed residual entirely outside this campaign's surface after a further conformance sweep — the acceptance-wall catalogue re-pointed at the substrate-era guarding tests (three walls, gate now fully green), the override-seam, skip, mock, monkeypatch, placeholder-parity, typed-output-language, docstring (own modules), and relative-import gates all green on substrate files, and one genuine production crash-safety defect found and fixed by the real-behavior status-gate rewrite (SQLAlchemy-wrapped session refusal defeating the zone guard). The residual reds are other campaigns' inventory/ratchet gates (enumerated below), recorded for the fix-forward lanes that own them.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- Campaign-owned (FIXED): `pytestmark` after the type-only block in `test_flow_tui_app.py`, `test_status_screen.py`, `test_copy_assembly.py`; missing module mark plus function-level domain markers in `test_localized_failure_surface.py`; `import cadrumo` absolute self-import in `test_copy_assembly.py`.
- Peer-owned cascade (single root): a peer campaign's uncommitted `ApoderadoRepresentedNifInvalidError` lacks its error-registry row and its locale keys (`cli.config.auth.apoderado.*`, four keys across all catalogues, plus `application.wizard.notices.modify_descendants_via_door`). That one gap explains the docs-build reds, the locale parity/audit/translation-resolve reds, the acceptance-wall cascade (including a worker crash on the wall sub-runs), the auth-parametrized config-reset-recovery reds, and the lazy-import unclassified edges from the same in-flight files. The gate's own diagnostic names the concurrent-process condition.
- Pre-existing other-lane red at committed HEAD: the campaign-metadata comment gate flags wording in `src/cadrumo/tests/test_data_size_budget.py` (corpus lane's file); not touched by this campaign.
- Settled-tree residual (sequential-confirmed, all outside this campaign's surface): descendant/cotejo docstring cross-links and module test-coverage plus the apoderado positional-`tr` raises (the profile-setup peer lane); `_per_grupo_member_keys` docstrings (calculations lane); registry reviewability/record-design/relation-closure/loader-reviewability, invoice validators, and the M100 Madrid roles pin (registry lanes); CLI module-size, codebase size budgets, hashing adoption, utf8 enrollment, any-param rationale, sensitive-persistence write inventory, and the campaign-metadata comment in the data-size-budget gate (other lanes' ratchet baselines at shared HEAD). Each fix-forward lane owns its baseline; signatures preserved in the on-disk suite logs.
