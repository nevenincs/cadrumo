---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S05'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add the immutable canonical CADRUMO tuple and authority-boundary vocabulary

## Scope

- `src/cadrumo/core/product_identity.py`

## Description

- Re-read the accepted rename research, superseded parent ADR, binding executable ADR, active plan, existing S05 record, implementation, tests, and current `HEAD`.
- Re-ground the live authority with semantic discovery, whole-file reads, and targeted exact searches.
- Verify that the import-light immutable identity tuple distinguishes sentence prose, identity contexts, machine identifiers, the human CLI, and the Spanish authority without aliases or fallbacks.
- Run the direct real-behavior identity tests and focused Ruff, formatting, and Ty gates before closing the Step through the plan CLI.

## Outcome

`src/cadrumo/core/product_identity.py` is the sole authored runtime identity authority for this Step. Its public API is:

- `ProductIdentity`, an immutable `NamedTuple` whose fields cover identity-context display name, sentence-prose name, package, distribution, CLI, repository, MCP server/executable/tool/resource identities, plugin identifier, environment prefix, companion distributions, and companion namespace.
- `PRODUCT_IDENTITY`, with `display_name="CADRUMO"`, `prose_name="Cadrumo"`, lowercase `cadrumo` machine identifiers, `cli_executable="aeat"`, `mcp_executable="cadrumo-mcp"`, `environment_prefix="CADRUMO_"`, both `cadrumo-data-*` companion distributions, and the `cadrumo_data` namespace.
- `IdentityReferent`, a closed `StrEnum` with only `CADRUMO_PRODUCT` and `AEAT_AUTHORITY`.
- `AEAT_AUTHORITY_SHORT_NAME="AEAT"`, the retained legal short name for the external authority referent.

The module has no dependency on settings, environment state, storage, outer layers, or a former product package. It contains no import alias, executable alias, environment fallback, namespace fallback, or migration path. No implementation change was needed: S87 had already added the independently consumable contextual casing values and their direct contract test.

## Notes

- Pre-edit status and scoped diff inspection found no overlap on the S05 record, plan, identity source, identity tests, or binding ADR. Concurrent `RELEASING.md`, documentation, S58-record, audit, and agent-evaluation work remained excluded.
- Six direct production-object tests passed. Ruff lint passed and both identity files were already formatted.
- Ty passed on the S05-owned production source. A broader diagnostic run also reported the deliberate read-only assignment in the still-open S07 test; that test-owned suppression is left to S07 and was not hidden or cross-edited here.
- The current source and tests were re-read after verification. This closeout changes only the S05 execution evidence and the plan checkbox.
