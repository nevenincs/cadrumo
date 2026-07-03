---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S06'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Audit first-period IVA compensation suppression against registry requirements

## Scope

- `src/aeat/application/modelo/_iva_wallet_gate.py`

## Description

- Audit the M303 first-period compensation implementation with RAG grounding.
- Verify that first-period zero suppression is owned by activity-start and
  registry evidence, not by manual seed commands.
- Keep `_iva_wallet_gate.py` unchanged because existing behavior already gates
  established-activity missing-prior-filing cases.

## Outcome

No code change was required in `src/aeat/application/modelo/_iva_wallet_gate.py`.
Worker and reviewer evidence found the first-period authority path covered by
existing code and tests. The related operator text overclaim was fixed under
S08 by commits `c35feaba5` and `5abb0081e`.

## Notes

RAG query used: `M303 iva wallet seed amount zero first period carry forward
first_period_zero`. Re-review found no remaining M303 wording or behavior
blocker.
