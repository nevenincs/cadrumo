---
tags:
  - "#research"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: Release-please LOCAL-only autorelease — Research
related:
  - "[[2026-04-12-release-please-adr]]"
  - "[[2026-04-12-release-please-plan]]"
issue: wgergely/aeat#60
---

# research: release-please local-only autorelease

## problem statement

The project merges at a high cadence and currently produces zero release
artefacts: no `CHANGELOG.md`, no tags, no coherent version bumps. GitHub
Actions is permanently disabled on this repo per project policy
(`#github_actions_disabled`), so the standard "release-please GitHub
Action" path is off the table. We need a way to compute release metadata
(next version, changelog entries) from conventional commit history on a
developer's machine, with zero CI dependency and no automatic pushes.

## current repo state (2026-04-12)

- Version present in **two** places:
  - `pyproject.toml` → `[project] version = "0.1.0"`
  - `src/aeat/__init__.py` → `__version__ = "0.1.0"`
- Both agree on `0.1.0`. The `0.0.1-scaffolding` milestone name is
  decorative; the actual source-of-truth version is already at `0.1.0`.
- No `CHANGELOG.md`, no `RELEASING.md`, no `.release-please-manifest.json`,
  no `release-please-config.json`.
- Conventional commits are followed in practice on every merged PR:
  `feat(...)`, `fix(...)`, `chore(...)`, `docs(...)` — verified across
  the last 40 commits on `main`.
- A legacy `.github/workflows/ci.yml` exists on disk (leftover from
  `#31`), but the Actions account is blocked. It never runs. It is out
  of scope for this issue.
- The `justfile` already uses `set windows-shell := ["pwsh.exe", ...]`
  and the `[unix]` / `[windows]` recipe pattern. New recipes must
  follow the same cross-platform shape.

## release-please tool survey

### release-please-cli (chosen)

Google-maintained (`@googleapis/release-please`). npm-distributed. Runs
as `npx release-please release-pr ...`.

Relevant subcommands for a LOCAL workflow:

- `release-pr` — computes the next release based on conventional
  commits since the last tag, produces a PR diff (version bumps +
  CHANGELOG entries).
- `manifest-pr` — same, but reads `.release-please-manifest.json` as
  authoritative state (recommended for monorepos and when the version
  lives outside `pyproject.toml`).
- `manifest-release` — after the release PR is merged, tags the
  release.

Relevant flags (verified via Context7 docs, `release-please@16`):

- `--token` — **required**. GitHub token with repo read access.
  `gh auth token` supplies it locally.
- `--repo-url` — **required**. `wgergely/aeat`.
- `--target-branch main` — the branch to compute against.
- `--dry-run` — prepare but do not take action. Prints what the PR
  would contain without opening one.
- `--debug` / `--trace` — print verbose diagnostics. Essential for
  local use where we want the operator to *see* the computed result.
- `--release-type python` — tells release-please to bump
  `pyproject.toml` (and `__init__.py` if `version-file` points there).
- `--config-file` / `--manifest-file` — point at local config paths
  (defaults already match what this issue creates).

**Network reality check.** `release-please` is not a pure-local
computation tool: it always reaches the GitHub API to enumerate commits
since the last tag. This is acceptable because:

- it is *read-only* in `--dry-run` mode (no PR created, no tag
  created, no write operations);
- the token comes from `gh auth token`, which is a developer's
  personal credential — not a CI secret;
- no content is pushed to the remote; nothing happens on
  `wgergely/aeat` as a side effect of running `just release`.

"Local-only" in this project means **"no Actions, no automatic pushes,
human-gated"**, not "air-gapped". The ADR pins this definition.

### release-please GitHub Action (rejected)

Out of scope by policy. GitHub Actions is disabled.

### python-semantic-release (rejected)

Python-native. Would avoid the `npx` dependency. Rejected because:

- The project has invested in the Google conventional-commits dialect
  already and release-please is the canonical tool for that dialect.
- python-semantic-release is opinionated about tagging + pushing
  (it *wants* to push). Disabling push is awkward.
- release-please's manifest mode makes the local dry-run +
  human-apply workflow clean.

### semantic-release (nodejs, rejected)

Geared toward npm publishing; heavyweight plugin graph; no first-class
Python support.

### release-it (rejected)

Generic; no conventional-commits-to-CHANGELOG computation out of the
box without extra plugins.

## conventional-commits → changelog section mapping

The standard `changelog-sections` set that release-please ships with:

| Commit type | CHANGELOG section          |
| :---------- | :------------------------- |
| `feat`      | Features                   |
| `fix`       | Bug Fixes                  |
| `perf`      | Performance Improvements   |
| `revert`    | Reverts                    |
| `docs`      | Documentation              |
| `style`     | Styles                     |
| `chore`     | Miscellaneous Chores       |
| `refactor`  | Code Refactoring           |
| `test`      | Tests                      |
| `build`     | Build System               |
| `ci`        | Continuous Integration     |

The default hides `chore`, `style`, `refactor`, `test`, `build`, `ci`
from the rendered CHANGELOG unless `"hidden": false` is set per
section. For this project we override the hidden flags to surface
`chore`, `refactor`, `test`, and `build` — they carry meaningful
scaffolding history that we want visible.

## version source of truth — decision material

Two live locations today, both at `0.1.0`. Options:

1. **Keep `pyproject.toml` as canonical, remove duplication in
   `__init__.py`.** `__version__` would instead be derived via
   `importlib.metadata.version("aeat")`. Clean, modern, no drift
   possible. Requires a code change in `__init__.py`.
2. **Treat both as managed by release-please.** release-please's
   `extra-files` mechanism can keep multiple files in sync. Drift is
   prevented by the tool, not by architecture.
3. **Keep `__init__.py` as canonical, let `pyproject.toml` read
   from it.** Hatchling supports `version = { attr = "..." }`. More
   invasive.

The ADR picks option (2): keep both files, let release-please manage
both via `extra-files`, and add a unit-test tripwire so the manifest,
`pyproject.toml`, and `__init__.py` are asserted consistent. Rationale:
zero code refactor, release-please already owns the bumping, and the
test catches drift regardless of cause.

## changelog backfill strategy

Parse `git log --format='%s' <root>..main` on `main`, group by
conventional-commit type, and hand-write a seeded
`## [0.1.0] - 2026-04-12` block into `CHANGELOG.md`. This is a
one-time operation — future entries land via `just release`.

Commits that don't follow the conventional-commits shape (e.g.
`"push"`, `"update lock"`, `"merge conflict fix"`) are dropped from
the seed rather than forced into a bucket. Merge commits
(`"Merge pull request ..."`) are also dropped; the underlying
`feat(...)` / `fix(...)` messages already appear elsewhere in the log.

## just-recipe shape (cross-platform)

The project's established pattern (see the `db-migrate`,
`gcloud-install`, `gsuite-bootstrap-sa` recipes): separate `[unix]`
and `[windows]` recipe bodies, each a self-contained shell script.
New recipes:

- `release` — wraps `npx release-please release-pr ... --dry-run
  --debug` and tees output into `var/release/release-please.log`.
- `release-apply` — reads the log, instructs the human operator on
  the edits to apply, then lands a `chore(release): vX.Y.Z` commit
  and creates a local `vX.Y.Z` tag (no push).

Pinning: `release-please@16` is the current major as of 2026-04.
Pin to `release-please@16` (not a floating latest) so future npm
registry changes don't alter behaviour. `--yes` disables npx's
interactive install prompt.

## test strategy

One `@pytest.mark.unit` test at `tests/test_release_config.py`
asserts:

- `release-please-config.json` is valid JSON and contains the required
  keys (`release-type`, `packages`, `changelog-sections`).
- `.release-please-manifest.json` is valid JSON and contains exactly
  one entry keyed `"."`.
- `CHANGELOG.md` exists at repo root and is non-empty.
- The version in `pyproject.toml`, `src/aeat/__init__.py`, and the
  manifest are all equal.

The test lives at repo top-level `tests/` rather than colocated under
`src/aeat/` because it validates project-meta files, not subpackage
code. This is the exception called out in the issue; the ADR
documents it explicitly.

Data shapes are loaded via pydantic v2 models (per project pydantic
mandate) defined inline in the test module — they are not part of
any public `aeat.*` subpackage because no production code consumes
them.

## open questions (resolved before ADR)

- **Q:** Does release-please require network even in `--dry-run`?
  **A:** Yes. It walks the GitHub API for commits since the last tag.
  Accepted and documented above.
- **Q:** How does release-please handle a repo with *no* prior tag?
  **A:** It treats the entire `main` history as the first release
  window and proposes the version from the manifest. Perfect for
  our zero-tag state.
- **Q:** Can the Windows recipe use `npx` directly?
  **A:** Yes. `npx` is provided by any modern Node/npm install; on
  Windows it resolves via `pwsh`'s PATH. The recipe assumes Node is
  installed — add a `command -v` / `Get-Command` guard for a clean
  error message.
