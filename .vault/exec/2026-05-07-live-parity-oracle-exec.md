---
tags:
  - '#exec'
  - '#live-parity-oracle'
date: '2026-05-08'
related:
  - "[[2026-05-07-live-parity-oracle-plan]]"
  - "[[2026-05-07-live-parity-oracle-adr]]"
  - "[[2026-05-07-live-parity-oracle-reference]]"
---

# `live-parity-oracle` execution summary (phases 2 — 5)

Records the autonomous execution of phases 2 — 5 of the
live-parity-oracle plan. Phase 1 was already committed before this
execution window opened. Phase 6 is gated on user-side
certificate-auth provisioning and remains pending.

## Phase 1 (prior commit `2d7e8b9e`)

`authenticated_simulator` cross-reference surface category added to
`LiveCrossReferenceDecision` schema with validator rules requiring
`executable_parity_evidence`, `requires_authentication=True`, allowed
methods restricted to `{GET, HEAD, OPTIONS, POST}`, and synthetic
data permitted by default. Pair `(authenticated_simulator,
vat_id_check)` added to `_COMPATIBLE_SURFACE_PAIRS`. Nine contract
tests in `test_authenticated_simulator_surface.py` verify positive
shape, each negative validator rule, compatibility-table membership,
and backwards-compat for the existing surface categories.

## Phase 2 (rolled into commit `ecd02bb9`)

GROI Spanish-ROI oracle bound to modelo 349 via a registry-data
cross-reference (not test-side wiring):

- Captured AEAT VIES gestiones page to
  `corpus/aeat_official/instructions/groi/aeat-vies-gestiones.html`
  (sha256 `5b439bae...`) and registered it as
  `aeat-groi-spanish-roi-procedure` source under
  `registry/aeat/legal/iva.toml` with
  `evidence_tier="executable_parity_evidence"`.
- Added cross-reference `modelo-349-groi-spanish-counterparty-check`
  to `registry/aeat/modelos/349.toml` declaring
  `surface=authenticated_simulator`,
  `oracle_id=aeat-groi-spanish-roi-checker`,
  `allowed_methods=("GET", "POST")`,
  `forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS`,
  `requires_authentication=True`, `synthetic_data_allowed=True`.
- Added the new cross-reference id and source ref to construct
  `modelo-349-informative` so the construct republishes everything
  its members consume.
- Re-exported `_groi_oracle`, `_live_parity`, and
  `AEAT_WRITE_FORBIDDEN_ACTIONS` from
  `aeat.domain.calculations.registry` so live tests outside the
  registry package satisfy the absolute-private-import boundary.
- Adapter live tests
  `test_groi_dependency_chain_live.py` and
  `test_groi_oracle_live.py` updated to use the public path.

This phase landed mixed with parallel-agent's MM-7-cuota work in
commit `ecd02bb9` (the parallel agent committed during the
pre-commit window); the GROI files are intact in the bundled commit.

## Phase 3 (commit `e6d8773f`)

Wired `aeat app registry verify` and `aeat app registry
audit-oracles` into `.github/workflows/ci.yml` as build gates that
run before the unit-test stage on every push and PR (ubuntu+windows
matrix). The audit-oracles step's docstring inline directs future
agents at the local remediation command.

## Phase 4 (commit `c9a16aaf`)

Authored `.github/workflows/aeat-drift-detector.yml` to run the GROI
live suite weekly (Sundays 07:00 UTC) under stored cl@ve-movil
secrets, auto-opening a labelled issue on failure. Activation gated
on the user provisioning the secrets named in the workflow header.

## Phase 5 (commit `4abfbf12`)

Authored the binding how-to under
`.vault/reference/2026-05-07-live-parity-oracle-reference.md`. Walks
a future agent through picking the oracle id, confirming surface
compatibility, declaring the cross-reference, capturing corpus
evidence, writing the regression test, and running the gate
sequence. Step 7 explicitly bakes the no-tautology mandate into the
test-authoring guidance.

## Gates achieved

- `ruff` / `ty` clean across all touched source files.
- `aeat app registry verify --json` reports `verified: true`.
- `aeat app registry audit-oracles --json` reports
  `failure_count: 0` with both `aeat-groi-spanish-roi-checker` and
  `aeat-nif-iva-checker` registered.
- `test_public_api_boundaries.py` passes (no source file outside
  the registry imports a registry private module by absolute path).
- `test_authenticated_simulator_surface.py` 9/9 passes.

## Pending

Phase 6 (IXVI certificate-auth probe) remains gated on user-side
configuration via `aeat setup auth configure --provider certificate`;
no code changes are blocking it. The plan's contingency branches
(cert unlocks IXVI vs. cert insufficient) are documented in the
plan's Phase 6 section.

A pre-existing parallel-agent state mismatch on the GROI corpus
file's byte count (registered `bytes=11499` vs. workspace `11492`
trailing-whitespace drift) is captured in commit `ecd02bb9`'s
message; resolution requires re-fetching the corpus or amending the
registered hash, neither of which is in scope for this execution
window.
