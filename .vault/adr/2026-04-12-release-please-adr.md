---
tags:
  - "#adr"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: Release-please LOCAL-only autorelease — ADR
related:
  - "[[2026-04-12-release-please-research]]"
  - "[[2026-04-12-release-please-plan]]"
issue: wgergely/aeat#60
status: accepted
---

# adr: release-please local-only autorelease

## context

Per `[[2026-04-12-release-please-research]]`: the project needs release
hygiene (version, CHANGELOG, tags) but cannot use GitHub Actions. Every
merge without this in place loses release-notes signal that nobody will
reconstruct later.

## decision

1. **Tool:** adopt `release-please-cli` (`@googleapis/release-please`,
   pinned to `release-please@16`) invoked via `npx --yes` from a
   `just release` recipe. Rejected alternatives: the GitHub Action
   (policy), python-semantic-release (tooling friction),
   semantic-release / release-it (weaker fit).

2. **Operation mode:** **LOCAL-ONLY and HUMAN-GATED.** "Local-only"
   means *no GitHub Actions workflow ever, no automatic pushes, no
   remote tag creation*. It does **not** mean "air-gapped":
   release-please walks the GitHub API (read-only) to enumerate
   commits since the last tag. The developer's personal token from
   `gh auth token` is the auth principal. Nothing is written to the
   remote as a side effect of `just release`.

3. **Two recipes:**
   - `just release` — runs release-please in `--dry-run --debug`
     mode, writes the full output into
     `var/release/release-please.log`, prints a summary, and exits.
     Nothing on the filesystem is bumped. Nothing is committed.
     Nothing is tagged. This is the *review* step.
   - `just release-apply` — prints the human-review checklist
     (read the log, verify next version, verify CHANGELOG delta,
     confirm working tree is clean on `main`) and then lands the
     edits as a `chore(release): vX.Y.Z` commit and creates a
     local annotated tag `vX.Y.Z`. The tag is **not** pushed.
     The recipe prints the suggested `git push origin main --tags`
     command but never runs it.

4. **Config files:**
   - `release-please-config.json` at repo root:
     - `"release-type": "python"`
     - `"packages": { ".": { "package-name": "aeat", ... } }`
     - `"changelog-sections"` with `feat`, `fix`, `perf`, `revert`,
       `docs`, `refactor`, `chore`, `test`, `build`, `ci` all
       visible (we override the upstream defaults that hide most
       of these — we want the full scaffolding trail).
     - `"include-component-in-tag": false`
     - `"separate-pull-requests": false`
     - `"draft": false`, `"prerelease": false`
     - `"changelog-path": "CHANGELOG.md"`
     - `"extra-files": ["src/aeat/__init__.py"]` to keep
       `__version__` in lockstep with `pyproject.toml`.
   - `.release-please-manifest.json`:
     ```json
     { ".": "0.1.0" }
     ```
     One key, one value. Seeded at the *current* on-disk version
     (`0.1.0`) — not at `0.0.1` as the issue tentatively suggested
     — because `pyproject.toml` and `__init__.py` already agree on
     `0.1.0`. The `0.0.1-scaffolding` milestone name is decorative
     and out of scope.

5. **Version source of truth:** `pyproject.toml [project].version`
   is the canonical version. `src/aeat/__init__.py __version__` is
   a *mirror* kept in sync by release-please via `extra-files`. A
   unit test (`tests/test_release_config.py`) asserts the three
   surfaces (`pyproject.toml`, `__init__.py`, manifest) agree at
   every commit. Any drift fails the test. We deliberately do not
   refactor `__init__.py` to read from `importlib.metadata` in this
   issue: the diff would touch production code and widen scope
   beyond release scaffolding.

6. **CHANGELOG seed:** `CHANGELOG.md` is created with a
   "Keep a Changelog" / release-please-compatible header, an
   `## [Unreleased]` placeholder, and one hand-curated
   `## [0.1.0] - 2026-04-12` section backfilling the conventional
   commits present on `main`. Commits that are not conventional
   (`"push"`, `"update lock"`, `"merge conflict fix"`) and merge
   commits are dropped from the seed. Every entry cites its PR
   number where available.

7. **Conventional-commits mandate:** a new section in `CLAUDE.md`
   makes conventional commits a hard project rule for every
   commit on every branch. The section documents the type →
   CHANGELOG-section mapping and the local release workflow.
   No commit-message linter is added in this issue — explicit
   non-goal per `#60`.

8. **Test location exception:** `tests/test_release_config.py`
   lives at the top-level `tests/` directory, not colocated under
   `src/aeat/`. Rationale: it validates project-meta files
   (`pyproject.toml`, the manifest, `CHANGELOG.md`) that do not
   belong to any `aeat.*` subpackage. Colocating it would require
   inventing a synthetic `aeat.release` subpackage just to host
   the test, which contradicts the
   `#src_layout_mandate` intent (the mandate concerns production
   code, not meta-config validation).

9. **Pydantic discipline:** per the project pydantic mandate,
   the test loads the two JSON config files into pydantic v2
   models defined inline in the test module
   (`ReleasePleaseConfig`, `ReleasePleaseManifest`). `model_config
   = ConfigDict(extra="forbid")` so typo'd keys are rejected.
   Models are local to the test because no production code
   consumes them.

## consequences

- Release hygiene lands immediately. The first `just release`
  invocation after merge will propose `v0.2.0` (driven by the
  accumulated `feat(...)` commits).
- No Actions footprint; the ban holds.
- Developers must have Node available on PATH for `npx`. Documented
  in `RELEASING.md`. Absence produces a clean error in the recipe.
- The `__init__.py` mirror is a gotcha: hand-editing `__version__`
  without the matching `pyproject.toml` change will now fail
  `tests/test_release_config.py`. Documented in `RELEASING.md`.
- The unit-test exception (top-level `tests/`) is narrow and
  justified; it does not set precedent for production code.
- Backfilling CHANGELOG by hand introduces a one-time reviewer
  burden. Mitigated by keeping the seed terse (one line per PR).

## non-goals

- GitHub Actions workflows of any kind.
- Commit-message linting (commitlint, gitlint, prek hook).
- PyPI publishing.
- Pre-release versioning (alpha/beta/rc).
- Auto-pushing tags.
- Refactoring `__init__.py` to derive `__version__` from
  `importlib.metadata`.
