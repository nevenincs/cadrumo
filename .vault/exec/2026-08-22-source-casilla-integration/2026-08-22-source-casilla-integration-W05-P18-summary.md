---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1a59eba10429bef3c9897813c445690bac5cef6f70caffc3b2543b59a61b38e8'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` `W05.P18` summary

W05.P18 is closed as a reviewed terminal Modelo 193 `ingress_blocked`
contributor-expense boundary, not as a connected source or source-owned export
route.

- Modified: `.vault/plan/2026-08-22-source-casilla-integration-plan.md`
- Modified: `src/cadrumo/_data/source_connectivity/census.toml`
- Modified: `dev/source_connectivity/tests/test_m193_deferral.py`
- Created: `2026-08-25-source-casilla-integration-m193-row-source-grounding-research.md`
- Created: `2026-08-22-source-casilla-integration-W05-P18-S104.md`
- Created: `2026-08-22-source-casilla-integration-W05-P18-S105.md`
- Created: `2026-08-22-source-casilla-integration-W05-P18-S106.md`
- Created: `2026-08-22-source-casilla-integration-W05-P18-S107.md`

## Description

S104 grounded the official Article-26.1.a expense record and separated it from
direct manual entry. S105 retained the bounded owner, expiry, and reopening
predicate; S106 proved no connected M193 expense lifecycle, persistence,
provenance, replay, review, or source-owned repeated-record export exists.
S107 reconciles the three independent approvals and closes that current state.

The census preserves the 2026-12-31 expiry and the 2026-11-30 follow-up.
Direct manual `gasto.*` fields and the separate withholding lifecycle remain
available, but neither is a contributor-expense source owner. The dormant
`gasto193` versus `gasto193_contributor` mismatch remains an explicit reopening
prerequisite. The independent S107 final review is intentionally handed off.
