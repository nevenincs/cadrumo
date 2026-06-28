---
step_id: "S1"
tags:
  - "#exec"
  - "#live-iva-compensation-wallet"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-adr]]"
---

# live-iva-compensation-wallet #551 S1 — ADR first-period bootstrap amendment

## What was done

Appended a "First-period bootstrap" section to
`.vault/adr/2026-05-19-live-iva-compensation-wallet-adr.md`.

The section covers:

- Three bootstrap scenarios: true first-period, mid-career carry-in, mid-year tool switch.
- LIVA art. 99.5 (Ley 37/1992) grounding for zero-first-period being legally certain.
- The bootstrap state shape: `status=seeded`, `expediente_id=manual-seed`.
- The `first_period_zero` divergence variant definition.
- The CLI seed contract distinguishing `--amount 0` (true first-period) from `--amount X` (carry-in).

## Verification gate

`vault check all` ran. Pre-existing 2129 errors from other campaigns; no new errors
introduced by this document change.

## Files touched

- `.vault/adr/2026-05-19-live-iva-compensation-wallet-adr.md` (appended ~80 lines)
