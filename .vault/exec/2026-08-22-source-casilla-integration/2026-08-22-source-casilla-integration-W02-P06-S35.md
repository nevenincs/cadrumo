---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5589acbb27a792d17dabd3ca87b26a6bfaf944551fa905ade44bc2518a17b57d'
step_id: 'S35'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# record the adjudicated inventory disposition and re-fetchable evidence

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Re-read the accepted inventory mapping decision and its official-source grounding before evaluating the census disposition.
- Compare the canonical `inventory.stock-valuation` row with live inventory repository, readiness, projection, and ingress capability declarations.
- Resolve all three typed Modelo 100 destination candidates against the validated registry and verify every recorded locator remains re-fetchable.
- Retain the existing `connect_candidate` disposition because complete `0181` acquisition cost and provenance-bearing explicit-closing authority remain implementation prerequisites.
- Exercise the focused census governance, destination ownership, and registry inventory gates without changing the already-canonical census row.

## Outcome

The canonical census row already records the adjudicated state exactly, so no data correction was made. It owns five independently discoverable capabilities: the encrypted inventory repository, readiness declaration, 2025 split-variation helper, ledger creation ingress, and movement ingress. Its three typed destination candidates resolve the 2025 Modelo 100 semantic roles for `0177`, `0181`, and `0182` without encoding revision continuity beyond the accepted year.

The row correctly remains `connect_candidate`, not `connected`. The accepted decision forbids binding the current IVA-exclusive purchase subtotal to `0181` and requires complete acquisition cost plus provenance, continuity, and conflict diagnostics before an explicit closing value can become authoritative. The review condition, campaign owner, bounded follow-up owner, 2026-10-31 deadline, and completion criterion preserve those blockers and authorize the later vertical slice without claiming it already exists.

All five capability locators and all three grounding references resolve to current lines and identify the stated symbols or behavior. The focused destination and registry inventory checks passed: five tests passed.

## Notes

The complete source-connectivity comparison and four discovery-dependent focused tests could not run to completion because unrelated concurrent command-spec work made the ingress walker refuse `src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py:204` as structurally unresolved. The failure occurs before inventory census comparison and matches the shared-worktree discovery blocker recorded by the preceding inventory review. It was preserved rather than repaired outside S35 scope. Five independent focused checks passed, including typed destination ownership and deterministic registry inventory coverage. No production, registry, or census data changed.
