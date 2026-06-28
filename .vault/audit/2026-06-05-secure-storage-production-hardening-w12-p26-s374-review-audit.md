---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S374]]'
---

# `secure-storage-production-hardening` `W12.P26.S374` Review

## S374-001 | PASS | CLI root is the bootstrap-custody gate

`entrypoints/cli/__init__.py` owns root dispatch, profile override normalization,
bootstrap-exempt verb recognition, storage write-policy checks, and active bucket
session activation. This is the intended transport gate; it does not construct domain
repositories or bypass the storage runtime.

## S374-002 | PASS | Deprecated `config init` is not mounted

The command tree registers the current lazy `config` module and `app` subtree. Focused
retired-literal tests pass and confirm retired `config init` phrases are absent from
runtime surfaces.

## S374-003 | FIXED | Click deprecated API warning removed

`_verb_path_from_context()` no longer reads the deprecated public
`ctx.protected_args` property. It prefers `ctx.args` for Click 9 compatibility and uses
the internal Click 8 storage only as a warning-free fallback.

## S374-004 | PASS | Profile-bound writes remain centrally guarded

The root callback computes the verb path, applies bootstrap exemptions, then delegates
write-route authorization to `inspect_storage_write_policy`. Explicit database URLs
and root fallback routes remain refused for profile-bound mutation verbs.

## S374-005 | PASS | Validation

- `uv run --no-sync ruff check ...` passed for the CLI root, bootstrap exemption,
  storage write policy, and focused CLI tests.
- `uv run --no-sync pytest -q -m integration -W error::DeprecationWarning:aeat.entrypoints.cli.__init__ ...`
  passed 15 CLI custody/cold-start tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-272`; the CLI root is enrolled as the current bootstrap-custody
gate and no deprecated config-init surface is reintroduced.
