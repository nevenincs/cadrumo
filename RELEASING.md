# Releasing

This project uses [release-please](https://github.com/googleapis/release-please)
as a **local CLI tool**. GitHub Actions is permanently disabled on this
repository; there is no release workflow in `.github/workflows/`. Every
release step is initiated from a developer's machine and is
human-gated.

See the architectural rationale in
[`.vault/adr/2026-04-12-release-please-adr.md`](.vault/adr/2026-04-12-release-please-adr.md).

## Prerequisites

- Node.js (for `npx`) on `PATH`. Any recent LTS is fine.
- `gh` CLI authenticated against `wgergely/aeat`
  (`gh auth status` must be green). `just release` uses
  `gh auth token` to hand release-please a read-only GitHub token so
  it can enumerate commits since the last tag.
- Clean working tree on `main`, up to date with `origin/main`.
- All local gates green: `just lint && just typecheck && just test && just hooks`.

## Workflow

### 1. Preview the next release

```
just release
```

This invokes `release-please release-pr` in `--dry-run --debug` mode
and tees the full output into `var/release/release-please.log`. It
does **not** touch the working tree, does **not** commit, does **not**
tag, does **not** push. The command prints a summary of what the
release would contain (computed next version and changelog delta).

Review the log. If the proposed version and changelog entries are
correct, continue to step 2.

### 2. Apply the release locally

```
just release-apply
```

This recipe is **instructional**: it verifies that the working tree
is clean on `main` and that a dry-run log exists, then prints a
numbered checklist the operator follows by hand:

1. Confirm the proposed version from the dry-run log.
2. Update `.release-please-manifest.json`, `pyproject.toml`
   (`[project].version`), and `src/aeat/__init__.py` (`__version__`)
   to the new version.
3. Update `CHANGELOG.md` with the new release block.
4. Stage the four files and create a `chore(release): v<version>`
   commit.
5. Create a local annotated tag `v<version>`.

The recipe itself **does not** edit files, commit, or tag — every
write is performed by the operator. It also **never** pushes. After
the operator lands the commit and tag, the recipe's final line
prints the suggested `git push origin main --tags` command. Running
that command is the operator's explicit, manual choice.

## Conventional commits

Every commit on every branch in this repository **must** use the
conventional-commits format:

    <type>(<scope>): <subject>

Valid `<type>` values: `feat`, `fix`, `perf`, `revert`, `docs`,
`refactor`, `chore`, `test`, `build`, `ci`, `style`.

The type determines the CHANGELOG section:

| Type     | Section                  |
| :------- | :----------------------- |
| feat     | Features                 |
| fix      | Bug Fixes                |
| perf     | Performance Improvements |
| revert   | Reverts                  |
| docs     | Documentation            |
| refactor | Code Refactoring         |
| chore    | Miscellaneous Chores     |
| test     | Tests                    |
| build    | Build System             |
| ci       | (hidden)                 |
| style    | (hidden)                 |

## Version source of truth

The canonical version lives in `pyproject.toml`. release-please also
keeps `src/aeat/__init__.py` `__version__` in lockstep via
`"extra-files"` in `release-please-config.json`, and records the
current version in `.release-please-manifest.json`. All three must
agree at every commit. `src/aeat/tests/test_release_config.py` enforces this
as a `@pytest.mark.unit` tripwire.

Never hand-edit one version surface without the other two — the
unit test will fail.

## Non-goals

- GitHub Actions workflows of any kind.
- Commit-message linting (gitlint, commitlint, prek hook).
- PyPI publishing.
- Pre-release versioning (alpha / beta / rc).
- Auto-pushing tags to `origin`.
