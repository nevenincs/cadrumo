---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ed8cf0f76b006d028f70b96b56f6792f225d9ed4c0e5dfd7e0a8cd1f513b34bf'
step_id: 'S74'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Correct Modelo 036 human-filing wording and route its source and export reconsideration paths exactly.

## Scope

- `.vault/reference/`
- `.vault/exec/`
- `.vault/plan/`

## Description

- Reconfirm the official 2025 BOE authority and AEAT procedure presentation routes.
- Trace the canonical M036 lifecycle, portal boundary, optional receipt field, and producer vocabulary with semantic discovery and exact-symbol confirmation.
- Correct the authority reference and S12 outcome without changing the no-local-filing boundary.
- Route source-connectivity participation through `W02.P04.S73` and any future filing artifact through `W02.P04.S28`.
- Run the focused portal, lifecycle, and registry checks and validate the Vault feature surface.

## Outcome

The reference and original S12 record now describe the shipped surface accurately:
Cadrumo records an operator-declared Modelo 036 filing made through Sede or in
person at an AEAT office, but never creates, renders, submits, or dispatches an
M036 artifact. `sede_justificante` is optional electronic-receipt evidence; an
absent value does not make an office filing unrecordable.

The non-filing disposition is unchanged. Source-connectivity participation begins
with `W02.P04.S73` and can enter the existing source-casilla plan only through
real evidence or an ADR-authorized disposition. A future filing artifact remains
owned by `W02.P04.S28` in the existing export-authority plan. These independent
routes prevent a source decision or local record from becoming a filing promise.

## Notes

No production code changed. Vaultspec-RAG found the existing lifecycle service as
the sole behavioral home and exact search confirmed the CLI is only its thin
boundary; this correction deliberately adds no parallel model, writer, or route.

`vaultspec-core vault check all --feature registry-completeness-closure` passed
with the stale feature index warning; regenerating the index resolved it. The
focused lifecycle/portal/worklist run is intentionally not a green gate: the
worklist's all-registry filing assertion remains expected-failing for unresolved
rows, and two lifecycle tests now observe the unrelated mandatory
`profile.bucket.created` event created during profile setup before the refused
M036 command. Those tests still expect an empty event catalogue. The M036
implementation was not changed by this Step.
