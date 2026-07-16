---
orphan: true
---

<!--
Release notes template for Cadrumo. Copy this block, fill it in from the
`just release` dry-run log (conventional-commit groups since the last tag),
and paste it as the GitHub Release body when the tag is pushed. This is a
hand-filled template, not generated automatically — release-please writes
CHANGELOG.md; this template is the longer-form human-readable companion for
the GitHub Release page.
-->

# Cadrumo vX.Y.Z

Released: YYYY-MM-DD
Soak window: YYYY-MM-DD HH:MM UTC → YYYY-MM-DD HH:MM UTC (N hours)

## Highlights

- One or two sentences on the most Kent-visible change in this release.

## Features

- (from `CHANGELOG.md` `### Features` for this version)

## Bug Fixes

- (from `CHANGELOG.md` `### Bug Fixes` for this version)

## Breaking Changes

- None. _(or: enumerate explicitly — pre-1.0 releases may carry breaking
  changes in a minor bump; state the migration step for each.)_

## Upgrade

```
uvx --from cadrumo==X.Y.Z aeat --version
```

or, for an existing install:

```
uv tool upgrade cadrumo
```

## Rollback

If this release regresses, see `RELEASING.md#rollback-procedure`. In short:
the previous version remains installable and this version can be yanked from
PyPI without breaking anyone pinned to an earlier pin.

## Verification

- [ ] `just packaging-smoke` green on Linux/WSL
- [ ] `uvx --from cadrumo==X.Y.Z aeat --version` resolves on a clean machine
- [ ] `pip install cadrumo==X.Y.Z` pulls both exact-version data distributions
      and `aeat app registry verify` runs clean
