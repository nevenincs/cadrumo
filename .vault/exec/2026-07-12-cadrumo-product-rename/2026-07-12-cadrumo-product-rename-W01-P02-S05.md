---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S05'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Add the immutable canonical CADRUMO tuple and authority-boundary vocabulary

## Scope

- `.vault/adr/2026-07-12-cadrumo-cli-executable-adr.md`
- `src/cadrumo/core/product_identity.py`
- `src/cadrumo/core/tests/test_product_identity.py`

## Description

- Re-read the accepted rename research, superseded parent ADR, binding executable ADR, active plan, existing S05 record, implementation, tests, and current `HEAD`.
- Re-ground the live authority with semantic discovery, whole-file reads, and targeted exact searches.
- Remediate the S05 audit finding by binding `repository` unambiguously to the owner-qualified source repository slug `nevenincs/cadrumo` while preserving every other tuple field.
- Verify the runtime value against the binding ADR and the real root and companion `pyproject.toml` URL consumers; no separate short repository identifier is introduced because no consumer needs one.
- Run the direct real-behavior identity tests and focused Ruff, formatting, and Ty gates before closing the Step through the plan CLI.

## Outcome

`src/cadrumo/core/product_identity.py` is the sole authored runtime identity authority for this Step. Its public API is:

- `ProductIdentity`, an immutable `NamedTuple` whose fields cover identity-context display name, sentence-prose name, package, distribution, CLI, owner-qualified repository slug, MCP server/executable/tool/resource identities, plugin identifier, environment prefix, companion distributions, and companion namespace.
- `PRODUCT_IDENTITY`, with `display_name="CADRUMO"`, `prose_name="Cadrumo"`, lowercase `cadrumo` machine identifiers, `cli_executable="aeat"`, `repository="nevenincs/cadrumo"`, `mcp_executable="cadrumo-mcp"`, `environment_prefix="CADRUMO_"`, both `cadrumo-data-*` companion distributions, and the `cadrumo_data` namespace.
- `IdentityReferent`, a closed `StrEnum` with only `CADRUMO_PRODUCT` and `AEAT_AUTHORITY`.
- `AEAT_AUTHORITY_SHORT_NAME="AEAT"`, the retained legal short name for the external authority referent.

The module has no dependency on settings, environment state, storage, outer layers, or a former product package. It contains no import alias, executable alias, environment fallback, namespace fallback, or migration path. The binding ADR now distinguishes the short package/distribution identifier `cadrumo` from the owner-qualified repository slug. Root and companion project metadata already use the corresponding GitHub URL, and the direct contract test now guards that projection from the runtime authority.

## Notes

- Pre-edit inspection initially found the S58 owner's plan reopen. S05 implementation proceeded only on clean paths and was held uncommitted until S58 landed; the plan and record were then re-read from the new `HEAD` before S05 was reopened and closed through the CLI.
- Nine direct production-object and real metadata-consumer tests passed. Ruff lint and format checks passed on both identity files.
- Ty passed on the S05 production source and direct test. ADR, plan, and vault synchronization checks passed after the record and plan were updated.
- The S07 alias-gate audit finding remains deliberately out of scope and unchanged.
