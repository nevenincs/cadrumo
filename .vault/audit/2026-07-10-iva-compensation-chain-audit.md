---
tags:
  - '#audit'
  - '#iva-compensation-chain'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:fd1702e7fe5c360378d32b2d93e0ef29a89f384240afe41437bc1ae7bc7fc081'
related:
  - "[[2026-05-19-iva-compensation-chain-plan]]"
  - "[[2026-07-05-iva-compensation-chain-audit]]"
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `iva-compensation-chain` audit: `Live closure honesty review`

## Scope

Fresh-context honesty review taken at the close of the `iva-compensation-chain`
plan, after `P03.S01` was checked on an operator-observed live read-only AEAT IVA
wallet verification run on 2026-07-10. Asks whether the plan can honestly declare
structural completion and what residual items the closing run surfaced.

## Findings

### live-closure | low | P03.S01 closed on the audit-sanctioned trigger

The prior `2026-07-05-iva-compensation-chain-audit` deferred `P03.S01` and named
its release condition: "the next operator-observed read-only live verification
run." That run occurred on 2026-07-10. AEAT returned `auth_status=succeeded` /
`auth_provider_kind=clave_movil`; a Cl@ve Movil non-QR confirmation flow cannot
complete without on-device operator approval, so the AEAT-returned auth success is
itself the operator-observed evidence the standing guard requires. The wallet /
cartera read-only surface succeeded and persisted an authority decision for
`2026/1T` selecting `aeat_wallet` with divergence `wallet_only`, so local
recurrence is no longer treated as the final compensation authority — the explicit
`P03.S01` condition. The implementation surface (P01, P02) remains complete and
green.

### standing-guard | low | live-wallet S56 stays a permanent open guard

Closing the chain's tracking step does not check live-wallet `W06.P15.S56`. That
row is by design a permanently-open standing live-verification path and privacy
guard ("Add and keep open ... remains open as a standing live-verification path
and privacy guard"). It is exercised, not completed, by each operator-observed run.
The live-wallet plan stays 101 of 102 by design.

### residual-filed-history | medium | filed_history capture failed with RegistryValidationError

The closing run's `filed_history` surface failed with a `RegistryValidationError`
while building calculation observations from captured filed Modelo 303 declarations
across 2022-2026, while `wallet_cartera` succeeded (the two surfaces are designed
to succeed or fail independently, per live-wallet `W06.P15.S54`). The bundled
registry itself validates cleanly — Modelo 303 snapshots for 2024/2025/2026 build
without error — so the defect is specific to the live filed-history
observation-build path, not a registry-tree defect and not the IVA
compensation-chain implementation. It could not be reproduced offline because it
depends on live-captured filed data. This finding is tracked for the live-wallet
plan, which owns the filed-history capture surface; it does not gate the chain's
wallet-authority dependency. It is consistent with the intermittent per-declaration
filed-history failures already recorded in the `W06.P15.S56` history (the prior
2026-06-05 exercise recorded both surfaces succeeding).

### structural-lint | low | legacy duplicate canonical ids remain, unrepaired

`vault plan status` resolves 9 of 9 with exec records present, but the plan still
carries the legacy `PLAN021` duplicate canonical ids for `S01`/`S02`/`S03` and
`PLAN030` display-path divergence noted by the `2026-07-05` audit. As that audit
directed, these were not hand-repaired in this pass — renaming checked rows changes
historical traceability semantics and belongs to a coordinator-owned vault hygiene
pass.

## Recommendations

- Treat the chain plan as structurally complete at 9 of 9. The wallet-authority
  live dependency is satisfied and honestly recorded.
- Route the `residual-filed-history` finding to the live-wallet plan's
  filed-history capture surface owner: capture the swallowed `RegistryValidationError`
  detail (the CLI surface flattens it to a typed per-surface outcome with an empty
  `failure_context`) so the failing declaration/casilla can be pinned, then add
  live-surface regression coverage. Do not fold this into the chain plan.
- Leave the legacy duplicate-id structural lint to a coordinator-owned hygiene pass.
