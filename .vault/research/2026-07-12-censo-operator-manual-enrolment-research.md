---
tags:
  - '#research'
  - '#censo-operator-manual-enrolment'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:052ff451a302b460b75094a6b7d6b363495b23fbe600edb00a3b379cdae14e1e'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-adr]]"
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
  - "[[2026-07-12-censo-operator-manual-enrolment-audit]]"
---

# `censo-operator-manual-enrolment` research: `accepted retirement grounding and current documentation residual`

This research records why the accepted operator-manual decision is the safe
architecture and identifies the remaining shipped wording that still implies a
retired Censo live read.

## Findings

### The live Censo route is a prohibited write path, not an incomplete reader

The authenticated investigation established that the configured launcher returned
HTTP 404 and that AEAT exposes no consulta-only census projection. The data-bearing
surface is the multi-step Censos WEB ZKoss modification tool. Its session-rekeyed
AU channel carries panel activity and submission traffic together, so a
never-submit guard would be heuristic rather than structural. Evidence:
`file:.vault/adr/2026-07-11-censo-operator-manual-enrolment-adr.md:14-58`.

The accepted decision is therefore grounded in the permanent prohibition on live
AEAT mutation, not a preference to defer a scraper. The safety rule forbids live
submission and requires any external write surface to be guarded:
`file:.codex/rules/aeat-safety-legal-gates.md:7-15`. The retired G313/CLI option
is explicitly superseded rather than silently left dormant; a future genuine
consulta-only endpoint would require a new ADR.

### The replacement path is present and preserves the honest posture

The current `CensoSyncService` no longer captures, compares, or applies a Censo
snapshot. It derives the surviving home-office ratio from encrypted,
operator-declared `vivienda_office` facts written through `config profile edit`.
Nothing stamps the two AEAT-verified Censo source tags, so the calendar keeps its
`censo.enrolment_unverified` posture. Evidence:
`file:src/aeat/application/user_profile/_censo_sync.py:1-17` and
`file:src/aeat/application/user_profile/_censo_sync.py:41-92`.

An exact current search found no active reference to the retired
`config profile censo pull`, `compare`, `apply`, or `show` family in the product
source, documentation, development tree, or tests. The current Censo how-to,
live-read guide, and activity-start skill correctly direct operators to
`config profile edit` and the taxpayer's Modelo 036 copy:
`file:docs/how-to/censo-update.md:10-14`,
`file:docs/how-to/read-live-aeat-data.md:50-58`, and
`file:src/aeat/_data/agent/skills/inicio-actividad/SKILL.md:44-60`.

### One stale documentation residual remains

`docs/how-to/authenticate-with-aeat.md:1-3` still says authentication may be
used for “pulling Modelo 036 census information.” That is false after the accepted
retirement and can direct an operator toward a non-existent live Censo workflow.
It is the current remaining documentation residual; it keeps P02.S05 open, but
does not reopen the retired scraper. The correction requires the mandated
documentation workflow and must disclose the operator-declared, non-official
evidence tier.

## Conclusion

The accepted ADR remains grounded and current: the application must not drive the
AEAT modification tool, and the operator-declared profile path is the only Censo
enrolment route. This record repairs the feature's research linkage while retaining
the outstanding documentation task as genuine work.

## Sources

- `file:.vault/adr/2026-07-11-censo-operator-manual-enrolment-adr.md:14-123`
- `file:.vault/plan/2026-07-11-censo-operator-manual-enrolment-plan.md:14-43`
- `file:src/aeat/application/user_profile/_censo_sync.py:1-116`
- `file:docs/how-to/authenticate-with-aeat.md:1-3`
- `file:docs/how-to/censo-update.md:10-14`
- `file:docs/how-to/read-live-aeat-data.md:50-58`
- `file:src/aeat/_data/agent/skills/inicio-actividad/SKILL.md:44-60`
