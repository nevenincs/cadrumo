---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:9887045af28780d0b1e0ddf937eb5e636b18275f06119fe2c1ed1290aed37733'
step_id: 'S801'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# Introduce StandardPeriodCode StrEnum covering the standard period codes (1T through 4T, 1P through 4P, 0A, 01 through 12) at canonical home `src/aeat/core/_period.py`. Refactor PeriodCode in `src/aeat/domain/calculations/registry/_schema.py` to validate via StandardPeriodCode plus extended/ad-hoc/event regex patterns. Sweep all consumer sites in one atomic commit per atomic-relocation-coordination ADR. Tag commit subject relocation:StandardPeriodCode

## Scope

- `src/aeat/core/_period.py`

## Description

## Outcome

## Notes
