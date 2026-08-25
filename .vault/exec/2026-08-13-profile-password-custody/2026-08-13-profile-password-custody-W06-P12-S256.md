---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:887fdcb943a421e45d4728dd902e2bb06197f9821c2b9245c61a32c3d63b0895'
step_id: 'S256'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Separate volatile workstation free-memory diagnostics from deterministic golden state while preserving real registry-integrity failures and host-health evidence

## Scope

- `docs/_sequences/contracts/workstation-setup/ and src/cadrumo/application/diagnostics.py and src/cadrumo/core/observability/`

## Description

- Verify the central golden policy masks only three exact free-capacity coordinates.
- Prove two fresh workstation executions compare clean through the real sequence runner.
- Retain deterministic total-memory, registry-integrity, thresholds, and host-health evidence under comparison.
- Refresh and check only the workstation page golden through the owner CLI after S258 added grade facts.
- Run page coherence, diagnostics/config-check, parser/compare, Ruff, ty, and formal review.

## Outcome

Workstation goldens no longer pin volatile free RAM, free VRAM, or the repeated contention binding-free value. Every other byte fact remains exact, and a tampered registry-integrity verdict still produces a divergence.

The real double-run and tamper class passes two integration tests; focused mask tests pass seven tests; parser/compare passes 61 tests; diagnostics/config-check selection passes four tests; workstation owner check and coherence are clean; Ruff and ty pass.

## Notes

Central policy and regression provenance is concurrent commit `6c43ddb406`. The closure refresh changes only the owner-generated `install-confirm` golden and incorporates both the intended masked text leaves and S258's truthful registry grade-count facts.
