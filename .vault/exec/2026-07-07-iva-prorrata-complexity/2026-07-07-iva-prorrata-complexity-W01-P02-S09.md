---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
body_hash: 'sha256:73c0ca6f466cbc6d4af0cf7d558d3217e6e7c52d09a1d6d75055e1a725b8f82e'
step_id: 'S09'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Verify the interruption seed against a worked example with a genuine gap and no averaged percentages

## Scope

- `src/aeat/domain/prorrata_register/tests/`

## Description

- Add the art-105.Cinco interrupted-seed verification against a hand-constructed multi-year register with a GENUINE interruption gap (2020/2021/2022 active, 2023 interrupted, 2024 resumes), whose expected figure is derived from the independently-stated volumes per the art-105.Cinco ADR.
- Assert the seed uses the three ACTIVE años (2022, 2021, 2020), skipping the 2023 gap - never the three calendar years.
- Assert the seed is the GLOBAL percentage over the aggregate volumes (15.000 con / 22.000 total -> 69% rounded up per art-102.Dos) and NOT the average of the three definitive percentages ((90+50+50)/3 = 63,33 -> 63), proving the mechanism is not the percentage-average shortcut the ADR forbids.
- Assert insufficient active history yields a visible advisory rather than a fabricated percentage.

## Outcome

- Modified files: `src/aeat/application/calculations/tests/test_prorrata_interrumpida_seed.py` (new).
- 3 verification tests pass; ruff / ruff-format / ty clean.
- The expected 69% is hand-derived from the independently-stated register volumes; the anti-average assertion is the load-bearing non-tautological check.

## Notes

- The seed is application-layer (it consumes the compute substrate), so its worked-example verification lives under `application/calculations/tests/` rather than the plan-row's `domain/prorrata_register/tests/` hint; the domain-walk unit tests (skip-gap, last-three-active, unsettled-skip) sit in `domain/prorrata_register/tests/` from S08.
- No AEAT worked example bundled for an interrupted-activity prorrata case; per the art-105.Cinco ADR the alternative is a hand-constructed register whose expected figure is the substrate's global computation over independently-stated volumes, made non-tautological by the anti-average and skip-gap structural assertions.
