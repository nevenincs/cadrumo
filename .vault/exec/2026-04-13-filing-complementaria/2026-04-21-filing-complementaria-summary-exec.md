---
tags:
  - "#exec"
  - "#filing-complementaria"
date: 2026-04-13
modified: '2026-04-13'
title: Filing Complementaria / Amendment Engine — Execution Summary
related:
  - "[[2026-04-13-filing-complementaria-research]]"
  - "[[2026-04-13-filing-complementaria-adr]]"
  - "[[2026-04-13-filing-complementaria-plan]]"
---

# execution summary

## delivered

- Added the new amendment engine under `aeat.application.filing` with strict pydantic v2
  types:
  `AmendmentKind`,
  `CasillaChange`,
  `CasillaDelta`,
  `FilingAmendment`,
  and `build_complementaria(...)`.
- Added additive public exports from `aeat.application.filing`.
- Persisted built amendments to the existing file-backed submission substrate
  under an `amendments/` directory.
- Extended `aeat.adapters.outbound.aeat.export` with `AmendmentSubmissionResult` and
  `SubmissionEngine.submit_amendment(...)`.
- Routed amendment submission through the existing submitter transport while
  keeping dry-run as the default and preserving the manual/live gate.
- Added `aeat filing complementaria build` and
  `aeat filing complementaria submit`.
- Added unit coverage for amendment build logic, submission wiring, CLI round
  trips, and a live-marked dry-run-only amendment submission test gated by
  `requires_live_enabled()`.

## legal/runtime guardrails shipped

- `130` maps to `complementaria`.
- `390` maps to `sustitutiva`.
- `303` allows only pre-rectificativa periods; monthly `2024-09+` and
  quarterly `2024Q3+` are rejected as out of scope for #93.
- Complementarias that reduce liability are rejected.
- Live tests remain dry-run only; no automated test path performs a remote
  write.

## notable implementation notes

- The existing submission stack expected mapping-backed draft values, while the
  real filing engine emits tuple-backed `FilingValue` records. The transport and
  preflight seams were widened so real filing drafts can now flow through the
  submission engine safely.
- The current `Modelo130Submitter` carries amendment metadata through the
  transport boundary but still logs the final AEAT form-control mapping as a
  transport gap. This matches the issue scope note that the browser field map is
  not the primary deliverable of #93.

## verification

- `just lint`
- `just typecheck`
- `just test`
- `just hooks`

All four gates passed on this worktree after implementation.
