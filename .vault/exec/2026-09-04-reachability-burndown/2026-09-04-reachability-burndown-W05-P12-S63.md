---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:7e1c17ff6c111cd275538a0a5955051d68f0275436097413b247f5b20b6948b2'
step_id: 'S63'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire the remaining reachable collaboration audit emitters so the event history records the acts it was built for: counter-sign emits on the counter-signer's bucket after the receipt is written, decrypt emits on the recipient's bucket after the envelope opens, and the collab recipient add and remove commands emit when trust is granted and revoked, each resolving the active bucket once and constructing the registry from it rather than through the bucket-resolving factory so the same identifier reaches both the repository and the event

## Scope

- `src/cadrumo/entrypoints/cli/config/_collab.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py`
- `M` `src/cadrumo/entrypoints/cli/config/_collab.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync ruff check src/cadrumo` -> `pass`
- `verify:` both CLI modules import clean

## Notes

Five of the six collaboration emitters are now wired. The sixth,
`emit_collab_review_only_workspace_opened_event`, is left deliberately: there is
no producer to emit from, because the review-only workspace has no opener. That
is the same gap recorded beside it, so wiring the emitter would mean inventing
the flow rather than instrumenting it.

The recipient commands previously obtained their repository through a factory
that resolved the active bucket internally, so the command never held the
identifier. Both now resolve it once and construct the registry from it, which
keeps the repository and the audit event on the same bucket by construction
rather than by two independent lookups.
