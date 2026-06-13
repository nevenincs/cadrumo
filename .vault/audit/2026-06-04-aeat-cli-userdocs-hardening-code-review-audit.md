---
tags:
  - '#audit'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---


# `aeat-cli-userdocs-hardening` Code Review

## REVIEW-001 | HIGH | Completed plan steps were initially hand-checked outside the VaultSpec plan CLI

The review found completed steps in the plan before a successful `vaultspec-core vault plan step check` run. The direct cause was that `vaultspec-core` was not available as a bare command on `PATH`, while the project-local command was available through `uv run vaultspec-core`.

Resolution: the plan step rows were normalized so the parser could read all steps, then `uv run vaultspec-core vault plan step check` was run for `S01`, `S03`, `S04`, `S05`, `S06`, and `S07`. Each command completed successfully and reported the corresponding step closed.

## REVIEW-002 | HIGH | Mandatory code-review audit artifact was missing

The review found that the execute cycle had performed reviewer work but had not yet persisted the required code-review audit artifact.

Resolution: this audit record now persists the mandatory review findings and their mitigation status for the execute cycle.

## REVIEW-003 | MEDIUM | Reader-review findings were not yet persisted as durable evidence

The review found that the zero-context wireframe, non-technical reader, and technical CLI review outputs were represented in conversation state and plan prose, but not as a standalone audit artifact.

Resolution: a reader-review audit record was added to preserve the persona findings that shaped the mitigation pathway.

## REVIEW-004 | LOW | Exec-summary template contains a body-path contradiction

The review found an inconsistency in the exec-summary template guidance: it requires audit/summary outputs in one location while another body note points at a different subpath. This is an upstream template clarity issue, not a defect in the documentation mitigation plan.

Status: recorded as an upstream VaultSpec template follow-up. No project documentation file was changed for this item.

## REVIEW-005 | INFO | Post-mitigation validation

After mitigation, `uv run vaultspec-core vault plan check` passed for the plan. `uv run vaultspec-core vault plan status` reported 7 of 47 steps complete. A final coverage check confirmed that `S01` through `S07` are the only checked steps and that each has a matching execution record. The no-diff step dry-run for `S02` reported no changes.

## REVIEW-006 | MEDIUM | W02 slice audit evidence was stale before closeout

The W02 closeout review found that this audit still reflected the earlier W01 state after `S08`, `S09`, and `S12` were closed. It also found that W02 editorial-review evidence was represented in execution notes but not persisted in the rolling audit.

Resolution: this entry records the W02 closeout. `S08`, `S09`, and `S12` were closed with `uv run vaultspec-core vault plan step check`. `uv run vaultspec-core vault plan check` passed, and `uv run vaultspec-core vault plan status` reported 10 of 47 steps complete. Coverage validation confirmed the only checked steps are `S01` through `S09` plus `S12`, and each checked step has a matching execution record.

W02 reader review criteria were: task-first handbook routing, no architecture-first navigation, visible profile/censo/ledger/modelo/verify/export/reconcile/troubleshooting paths, explicit non-submission safety boundary, easy glossary/reference access, and visible backlog for missing natural product surfaces. The first review found the verify/export/manual-upload route too implicit, the home page too safety-first, M036 too hidden, some filing labels too ambiguous, and manual-ledger routing too bank-import-centric. The docs were revised. A focused re-review then reported no blockers for closing `S08`, `S09`, and `S12`.

The final W02 review found no critical or high blockers. It noted one low privacy-warning gap in `docs/how-to/index.md`, which was resolved by adding an explicit warning not to paste unredacted log files.

After that final wording change, rerunning `uv run pytest src/aeat/entrypoints/cli/test_educational_docs_conformance.py -m docs` was blocked during import by an unrelated dirty source file, `src/aeat/adapters/persistence/storage/sql/secure_objects.py`, which currently has an unterminated string literal. A Markdown-only validation of the two edited pages found no non-ASCII text, no overlong lines, and no broken relative links.

Residual risks remain open in the plan: `S10`, `S11`, `S13`, and `S14` are not complete, and the Sphinx nitpicky build is not proven because it timed out after 10 minutes without a content failure.

## REVIEW-007 | HIGH | Rejected preview build must not be treated as a single-file build

A preview-only command that excluded `docs/api/**` could render `docs/index.md` quickly into a separate output directory, but that artifact was rejected because it does not represent a supported single-file build and can confuse review by producing non-canonical HTML output.

Resolution: the generated preview directory was removed. The plan now tracks an open implementation step, `S48`, requiring a real single-source-page docs build that writes the requested page into the canonical HTML build output without rebuilding generated API/autodoc surfaces or producing a separate preview artifact.

Observed behavior: Sphinx's selected-file syntax exists, but the current project configuration is not sufficient for reliable single-page review. `sphinx-build ... docs/index.md` invalidated the environment and began reading the full generated API/autodoc tree, then failed in autodoc/Pydantic handling before writing a current canonical `docs/_build/html/index.html`. Therefore the current implementation cannot be confirmed as able to build one requested page quickly.

## REVIEW-008 | INFO | S48 implemented canonical single-page index builds; autobuild remains open

Resolution: `S48` now provides `just docs-page PAGE`, backed by `scripts/build_changed_docs.py --single-page`. The command writes to `docs/_build/html`, keeps generated API/autodoc sources out of the selected source set, forces the generated CLI reference needed by handbook links, uses offline inventory mode, and avoids the rejected `docs/_build/index-preview` output path.

Validation: `just docs-page docs/index.md` completed in about 11 seconds and wrote current handbook copy to `docs/_build/html/index.html`. The built file includes the task chooser, standard prepare-and-export route, censo lifecycle route, and privacy-safe support language. `docs/_build/index-preview` is absent. `uv run python -m compileall scripts/build_changed_docs.py` also passed.

Residual: this is not an autobuild server. The repository has `watchfiles` in the lockfile, but no `sphinx-autobuild`, `docs-watch`, or `docs-serve` recipe. The missing watch/server path is now tracked as open plan step `S49`. For non-root pages, Sphinx may still rewrite the root `index.html` alongside the requested page because the canonical root remains the master document; the index page requested by the user builds as the single requested page.

## REVIEW-009 | MEDIUM | Single-page build initially accepted generated API pages

The mandatory code reviewer found that the generic `docs-page PAGE` recipe could still be aimed at `docs/api` pages. That made the "without rebuilding generated API/autodoc pages" contract porous even though the requested `docs/index.md` use case was valid.

Resolution: `scripts/build_changed_docs.py` now rejects generated API/autodoc targets in `--single-page` mode, and the `docs-page` recipe comment now says the recipe is for non-API documentation sources. The guard was verified by running an API-page invocation and confirming it exits before Sphinx starts.
