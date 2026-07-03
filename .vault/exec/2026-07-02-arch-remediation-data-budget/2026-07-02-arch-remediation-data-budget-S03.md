---
tags:
  - '#exec'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-data-budget-plan]]"
---

# Extend the packaging gate to assert the wheel contains the required data roots plus py.typed, the BIP-39 wordlist, and external_constants.toml so the exclude cannot silently strip functional payload

## Scope

- `src/aeat/tests/test_wheel_content_boundary.py`

## Description

- Extend the content-boundary gate to assert the required functional payload survives the exclude: the `_data` roots (corpus, registry, terminology, agent), `py.typed`, the BIP-39 wordlist, and `external_constants.toml`.

## Outcome

The exclude cannot silently strip functional payload — both directions of the boundary are asserted against the built wheel.

## Notes
