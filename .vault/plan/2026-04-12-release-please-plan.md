---
tags:
  - "#plan"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: Release-please LOCAL-only autorelease — Plan
related:
  - "[[2026-04-12-release-please-research]]"
  - "[[2026-04-12-release-please-adr]]"
issue: wgergely/aeat#60
---

# plan: release-please local-only autorelease

## phases

### phase-1 — config files (1 step)

1. **task-1 — write config + manifest + changelog seed.**
   - Create `release-please-config.json` with the shape pinned in
     the ADR (release-type python, changelog-sections with all
     project-relevant types visible, `extra-files` pointing at
     `src/aeat/__init__.py`).
   - Create `.release-please-manifest.json` with `{ ".": "0.1.0" }`.
   - Create `CHANGELOG.md` with header, `## [Unreleased]` block,
     and hand-curated `## [0.1.0] - 2026-04-12` block backfilling
     conventional commits from `git log main`. Drop merge commits
     and non-conventional messages. Group by section.
   - Create `RELEASING.md` at repo root documenting the
     `just release` / `just release-apply` workflow.

### phase-2 — just recipes (1 step)

2. **task-1 — add `release` and `release-apply` recipes to justfile.**
   - `[unix]` and `[windows]` bodies for both.
   - Both recipes pin `release-please@16`, invoke via `npx --yes`,
     and guard on Node availability with a clean error message.
   - `release` uses `--dry-run --debug`, writes to
     `var/release/release-please.log`, prints a summary, never
     touches the working tree.
   - `release-apply` verifies `main`, clean tree, and the presence
     of the log, then interactively prompts the operator to edit
     the version surfaces and land a commit + tag. No push.
   - `var/release/` is .gitignored? Check — if `var/` is not
     already ignored, add `var/release/` to `.gitignore`.

### phase-3 — CLAUDE.md mandate (1 step)

3. **task-1 — add conventional-commits section to CLAUDE.md.**
   - Hard mandate: all commits on all branches must use
     `<type>(<scope>): <subject>`.
   - Document type → CHANGELOG-section mapping.
   - Document the local release workflow and link to `RELEASING.md`
     and the ADR.

### phase-4 — test tripwire (1 step)

4. **task-1 — add `tests/test_release_config.py`.**
   - `@pytest.mark.unit` only.
   - Pydantic v2 models for config and manifest (`extra="forbid"`).
   - Assertions: valid JSON, required keys, manifest has one entry,
     CHANGELOG exists and non-empty, three version surfaces agree.

### phase-5 — gates + records (1 step)

5. **task-1 — run gates, land commit, write exec records + review.**
   - `just lint && just typecheck && just test && just hooks` all
     green on Windows. Fix root causes; never skip.
   - Verify `ls .github/workflows/` contains NO
     `release-please.yml`.
   - Write `.vault/exec/2026-04-12-release-please/` step records
     and a phase summary.
   - Run `vaultspec-code-review` skill; file the audit record.
   - Commit `chore(release): add release-please local workflow
     (#60)` with conventional prefix.

## plan review (self-review, 2026-04-12)

Plan checks out against the ADR and the research doc. Spot-checks:

- **Scope boundary holds.** Nothing touches in-flight feature branch
  territory. The only `pyproject.toml` edit is optional (add a
  comment section — not needed, so skipped entirely). No
  `[tool.pytest]` changes — sibling branch owns that section.
- **No GitHub Actions file is proposed anywhere.** Verified against
  the issue's hard constraint. `just lint`/`hooks` run locally.
- **Version source of truth is unambiguous.** Pydantic-backed test
  enforces three-way agreement. Drift becomes a test failure, not
  a silent bug.
- **Cross-platform recipes follow the established
  `[unix]`/`[windows]` pattern** used across the justfile.
- **CHANGELOG backfill is bounded.** One hand-curated block. No
  future-dated entries. No unreleased placeholder content.
- **Test location exception is justified in the ADR**, so the
  code reviewer will find a paper trail.
- **Pydantic mandate honoured.** Config parsing in the test uses
  pydantic v2 models with `extra="forbid"`.

**Outcome: APPROVED. Proceeding to execution.** No blockers. No
unresolved questions. No user input required.

## risks + mitigations

- **npx resolves a wrong release-please major.** Mitigation: pin
  to `release-please@16` explicitly in both recipes.
- **Developer lacks Node.** Mitigation: recipe guards with
  `command -v node` / `Get-Command node` and prints install
  guidance.
- **`gh auth token` absent / expired.** Mitigation: recipe surfaces
  the error from `gh` verbatim; `RELEASING.md` documents the
  prerequisite.
- **CHANGELOG backfill drops a PR the reviewer cares about.**
  Mitigation: explicit hand-review step in the exec log; the
  reviewer diffs the seed against `git log --format='%s' main`.
