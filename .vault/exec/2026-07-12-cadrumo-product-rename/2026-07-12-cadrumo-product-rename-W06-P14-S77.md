---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S77'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Prove no `aeat` import root, second human CLI alias, dual environment reader, namespace fallback, or state migration remains

## Scope

- `compatibility absence gate`

## Description

- Audit the live source tree against the committed Cadrumo product-rename ADR.
- Pin the absence of a retired `src/aeat` package or module.
- Pin the exact console-script map to `cadrumo` and `cadrumo-mcp`, with no former human CLI alias.
- Exercise the existing legacy-dotenv, former-root, database, encrypted-session, namespace, and bundle refusal proofs.
- Keep AEAT authority adapters, registry taxonomy, credentials, endpoints, and legal evidence outside the product-compatibility prohibition.

## Outcome

The compatibility absence gate passes. A fresh subprocess imports `cadrumo`
and refuses `import aeat`; the source tree contains no `aeat` import root. The
package metadata exposes only the human `cadrumo` command and the distinct
`cadrumo-mcp` server command, both bound directly to Cadrumo callables.

Real settings parsing ignores former product-owned `AEAT_*` dotenv controls
while retaining authority-owned AEAT integration settings. Real filesystem and
encrypted persistence tests refuse the former platform root, root and bucket
`aeat.db` files, `.aeat/auth/sessions` objects, former product namespace
prefixes, and `.aeat-bucket.tar.gz` archives without reading, moving,
re-keying, deleting, migrating, adopting, or creating canonical successor
state.

Verification passed:

- `uv run --no-sync ruff check src/cadrumo/tests/test_console_script_imports.py`
- focused compatibility matrix: 35 passed, 2 deselected
- legacy product dotenv proof: 1 passed, 22 deselected

## Notes

An untracked ADR attempted to supersede the committed executable decision and
describe `aeat` as the human command. It is concurrent, unapproved WIP and was
not used as authority or modified. The committed accepted product-rename ADR,
the live immutable identity tuple, and package metadata all require `cadrumo`.

The exec scaffold regenerated the shared feature index while that untracked ADR
was visible, causing the working index to describe the committed ADR as
superseded. That generated index is excluded from this Step's explicit commit
pathspec and must be regenerated only after the external ADR WIP is resolved.
