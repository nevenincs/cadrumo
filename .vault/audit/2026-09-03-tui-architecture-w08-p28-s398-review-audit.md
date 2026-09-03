---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f667815b8361bb9ba5439a362fa85534072c6f1b98fd28befa5b9c66eebdee08'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

Reviewed the S398 immutable installed-workbench snapshot assembly, root-service injection, authoritative-return refresh, launcher composition boundary, and focused proof suite.

## Findings

### refresh-withdrawal-regression | high | A later edit restored stale search retention after a failed authoritative refresh

Resolved. The failure branch again clears the installed service before setting `workbench.search.refresh_unavailable`; the focused regression proves the former service is no longer queryable after a real child dismissal.

### missing-installed-provider | high | A bare root session previously started without an authoritative search generation

Resolved. The launcher now requires a caller-supplied current-projection provider; the bare module entry refuses visibly with the sanitized `workbench.search.composition_required` code when no such provider exists. It does not install an empty or unavailable search service.

### stale-search-after-refresh-failure | high | A failed authoritative refresh could retain and serve the previous document generation

Resolved. The root now withdraws the service before exposing the sanitized refusal code, so the palette cannot query or navigate a stale generation after the owner child returns.

### installed-provider-source | medium | The subsequent installed-session composition must supply the required current-projection provider

The existing repository contains no production owner that can honestly reconstruct all public Ledger, Declarations, filing-history, reconciliation, notification, and Modelo projections without creating a new raw authority. S398 therefore binds the explicit provider seam and fails closed until the installed session supplies it; composing the source is intentionally reserved for S384.

## Recommendations

- S384 should supply one coherent provider from the session's already-public projection dependencies at initial composition and on authoritative child return.
- Preserve the required provider contract and visible refusal until that source is available; do not replace it with raw storage, network acquisition, inferred facts, or an empty index.
