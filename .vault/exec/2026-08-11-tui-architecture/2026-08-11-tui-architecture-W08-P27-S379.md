---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:799910324d694fac7aa1c6efeeae1d038e661b9379219acbd0542048edefe8fc'
step_id: 'S379'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Build AEAT Sync overview, profile-census, filed-declaration, notification, evidence-comparison, and reconciliation screens with explicit pull and supported push actions

## Scope

- `src/cadrumo/entrypoints/tui/aeat_sync/`
- Exact `tui.aeat_sync.*` keys in the four supported catalogues.

## Changes

- Kept six mounted, host-neutral screens projection-only, with source availability, freshness, and local-versus-AEAT contradictions rendered independently.
- Replaced operator-facing AEAT Sync strings and enum labels with authored locale lookups; protected taxpayer values do not appear in the mounted views.
- Admitted only exact registered action-operation pairs to the host handoff, made unavailable and unknown pairs visible refusals, and kept notification-document access fail-closed.
- Made the TUI fixture enter through `project_aeat_sync_workspace`, so the public projector derives each notification's unique opaque selection key from its private admission coordinate. The fixture no longer direct-constructs an invalid public projection.
- Retained mounted Textual coverage for all six routes, redaction, source/freshness, host handoff, refusal behavior, and four-catalogue status-key resolution.

## Verification

- `uv run --no-sync pytest -q -o addopts='' src/cadrumo/application/aeat_sync/tests src/cadrumo/entrypoints/tui/aeat_sync/tests` -> `25 passed`
- Four-catalogue `tui.aeat_sync.*` key-set parity -> `en=es=ca=hu=111`
- `uv run --no-sync ruff format --check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync ruff check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync ty check src/cadrumo/entrypoints/tui/aeat_sync && uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/aeat_sync` -> `pass`
- `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/aeat_sync --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `0 clones`
