---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a5db17a08327a7c656098e6d3bbde8761887c2ac529030d50438aba1f4a706b1'
step_id: 'S12'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Re-adjudicate Modelo 303 deadlines, remove every non-owner copy, preserve the 2024 cutover, and materialise every supported monthly and quarterly row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303/`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_303_registry.py`

## Description

- Search the code and decision corpora with Vaultspec RAG before editing and repeat the redeclaration audit after implementation.
- Reuse `select_revision`, its shared period-token matcher, and the registry ownership validator as the only ownership authorities.
- Preserve the period-sensitive 2024 boundary and materialise only dates and payment cutoffs present in bundled official AEAT calendars.
- Keep the Step open while filing-year 2026 month `12` depends on the unpublished 2027 calendar/payment cutoff.

## Outcome

The canonical M303 deadline corpus is complete for all selected periodic coordinates in supported filing years 2022-2026. The final `(2026, "12")` monthly row is owned by revision `2026-y-siguientes`, opens 2027-01-01, closes 2027-02-01 after the statutory terminal day falls on Saturday, and carries the officially published 2027-01-27 direct-debit cutoff. Its source closure reuses the bundled M303 procedure and governing IVA deadline authority; no future-calendar inference helper was added.

The 2024 period-sensitive cutover remains unchanged and canonical. Every coordinate resolves through `select_revision`, every construct includes its authored row, and the focused M303/M322/M349/M353 plus engine suite passes as part of the 164-test feature run. Step `W02.P04.S12` is complete.

## Verification

- Mandatory pre-edit Vaultspec RAG code and vault searches located the existing `select_revision`, ownership validator, deadline projection, period authority, ADR, plan, and prior S12 record.
- Post-edit Vaultspec RAG returned the same canonical authorities and the focused regression only. Exact `rg` confirmation found no selector, resolver, cadence authority, filing-year horizon, enum, or code map declared in the M303 data/test surface.
- Focused M303 validator/deadline tests: `6 passed`.
- Ruff on the focused M303 test module: passed.
- `git diff --check`: passed.

## Review

Final review confirms official-source provenance, canonical owner placement, construct/source closure, and the complete 68-coordinate M303 supported-year census. Vaultspec RAG plus exact-symbol confirmation found no redeclared selector, resolver, parser, cadence authority, horizon, or deadline catalogue.
