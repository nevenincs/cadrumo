---
tags:
  - "#exec"
  - "#live-submit-permanently-forbidden"
date: "2026-04-27"
modified: '2026-04-27'
related:
  - "[[2026-04-27-live-submit-permanently-forbidden-adr]]"
  - "[[2026-04-27-live-submit-permanently-forbidden-phase-1-summary-exec]]"
---

# Summary

Closes #432.

This PR hardens charter #116 from "live AEAT writes are heavily gated" to
"live AEAT submission is permanently forbidden". The product direction is
`produce -> verify -> export`; Kent uploads the exported fichero himself in the
AEAT portal.

# What Changed

- Removed the remaining live-submit runtime surface from `aeat.adapters.outbound.aeat.export`.
- Reduced `aeat.adapters.outbound.aeat.auth` live-write gating to permanent refusal.
- Removed live-submit env vars from `Settings` and `env/.env.example`.
- Removed residual live-submit framing from CLI, workflow, observability, docs,
  roadmap, and charter surfaces.
- Added a permanent-forbid regression suite that asserts the dead path stays
  dead.
- Landed the full vaultspec record set for the policy decision and execution.
- Updated charter issue #116 on GitHub to reflect the permanent-forbidden
  mandate and the "no executable AEAT write path" rule.

# Code Paths Excised

- `src/aeat/adapters/outbound/aeat/export/_audit.py` deleted: `103` lines removed.
- `src/aeat/adapters/outbound/aeat/export/_confirm.py` deleted: `138` lines removed.
- `src/aeat/adapters/outbound/aeat/export/_engine.py`: `117` lines removed / `29` added to make
  the engine dry-run-only, reject legacy live kwargs, and refuse before
  preflight.
- `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py`: `37` lines removed / `5`
  added to remove the `Submitter.submit` live-write contract.
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py`: `48` lines removed / `2`
  added to collapse the historical live path.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`: `45` lines removed / `16` added to convert
  `require_live_write()` into permanent refusal and remove live-submit env
  capture.
- `src/aeat/core/errors/_registry.py`: `59` lines removed / `7` added to remove the
  old live-submit error taxonomy and register the simplified permanent-forbid
  surface.
- `src/aeat/application/workflow/_engine.py`: `7` lines removed / `25` added so the public
  workflow API also refuses `dry_run=False` before dispatch.
- `src/aeat/config.py`: `8` lines removed / `1` added to remove live-submit
  settings fields.
- `src/aeat/entrypoints/cli/doctor.py`: `20` lines removed / `5` added to replace the old
  env-var guidance with permanent-forbidden wording.

# Docs, Charter, And ADRs

- New policy ADR:
  - `.vault/adr/2026-04-27-live-submit-permanently-forbidden-adr.md`
- Amended prior ADRs:
  - `.vault/adr/2026-04-18-live-submit-cli-excision-adr.md`
  - `.vault/adr/2026-04-18-auth-provider-abstraction-adr.md`
- Vaultspec records:
  - `.vault/research/2026-04-27-live-submit-permanently-forbidden-research.md`
  - `.vault/plan/2026-04-27-live-submit-permanently-forbidden-plan.md`
  - `.vault/exec/2026-04-27-live-submit-permanently-forbidden/`
  - `.vault/audit/2026-04-27-live-submit-permanently-forbidden-code-review-audit.md`
- Charter and roadmap rewrites:
  - `.vaultspec/rules/rules/aeat-project-mandates.md`
  - `ROADMAP.md`
  - `docs/coverage/kent-capabilities.md`
  - `env/.env.example`

# Security Audit Findings Consumed

- Removed the executable branch that could have produced real live-submit audit
  artifacts and traces.
- Removed `AEAT_LIVE_SUBMIT_ENABLED` / `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN` from
  active configuration and env documentation.
- Clarified AuthProvider as read-only AEAT access for sede walking,
  notifications, and past-filing import; not a future write enabler.

# Validation

- `just lint`
- `just typecheck`
- `just test`
- `just hooks`
- `just test-cov`
- Mandatory code review audit passes:
  - `.vault/audit/2026-04-27-live-submit-permanently-forbidden-code-review-audit.md`
- Active product-surface grep is clean:
  - `rg -n "live_transport_supported|AEAT_ALLOW_LIVE_SUBMIT|AEAT_LIVE_SUBMIT_ENABLED|i-understand-this-is-real|reintroduce.*live|deferred to 1\.0\.0|opt-in to live" src/ docs/ ROADMAP.md .claude/ env/`
  - Remaining matches are only negative tests that assert removed flags stay
    dead; no active runtime or product-doc surface remains.

# PM Follow-Ups

- Apply/verify charter label policy so charter issues link the permanent-forbid
  mandate.
- Add the project-board banner/pinned note pointing to `#432`.
- Sweep older issue bodies that still mention deferred/1.0.0 live submission
  and leave closing comments pointing to `#432` and the new ADR.
