---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S335'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S335 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The durable maintenance gate one  -  vault check all CI-equivalent runs on every commit to chore branch and ## Scope

- `blocks merge if structural drift surfaces`
- `.github/workflows/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# durable maintenance gate one  -  vault check all CI-equivalent runs on every commit to chore branch

## Scope

- `blocks merge if structural drift surfaces`
- `.github/workflows/`

## Description

- Assess-first: read the seven existing `.github/workflows/` files; confirmed no job runs `vaultspec-core vault check all` today (net-new gate, not verify-close).
- Add `vault-drift-gate` job to a new `.github/workflows/durable-maintenance-gates.yml`, running `uv run --no-sync vaultspec-core vault check all` after `uv sync --frozen`.
- Trigger on push to `chore/**` (every commit to a chore campaign branch) and on `pull_request` into `main` (so a merge is gated once the check is marked required in branch protection).
- Mirror the repo's multi-workflow conventions: pinned action SHAs (`checkout`, `setup-uv`) copied verbatim from `ci.yml`, `contents: read` permissions, cancel-in-progress concurrency.
- Verify the verb resolves: `vaultspec-core vault check` subcommand tree lists `all`; a full `vault check all` run executes to completion.

## Outcome

Net-new blocking gate landed as the `vault-drift-gate` job. The command exists and runs. The workflow YAML parses (safe_load) and is pure ASCII. Existing workflows are untouched.

A live `vault check all` on the current worktree exits 1 (53 errors, 146 warnings) - pre-existing structural drift in `.vault/adr` H1 status tokens and related files, owned by other campaigns, not introduced here. The gate is therefore expected to report RED until that standing drift is remediated (governed by S195/S196); this is the gate doing its job, surfacing real drift. Promotion to a required merge check and remediation of the standing drift are the follow-on, not part of authoring the gate.

## Notes

Plan checkbox for this Step was flipped in the working tree via the plan CLI but the plan-file commit is deferred: the plan markdown carries unstaged peer WIP (an 11-line comment-block removal) and the shared index holds 51 peer-staged files (including a staged test deletion), so neither a pathspec nor a no-pathspec commit of the plan could avoid sweeping foreign work. Only the workflow file and this exec record were committed, by explicit pathspec.
