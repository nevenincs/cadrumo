---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:ca62c1e401fd5bda50272cb6d1cff0ffa4a7f74153da2f1eca19cb0000eeb550'
step_id: 'S27'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
---

# `cross-period-filing-clean-state` `W02.P05.S27` exec - dependency inventory export

## Description

Exposed the inventory report types and inventory function through the calculation package public interface.

## Outcome

Application consumers can import the inventory surface from `aeat.application.calculations` without traversing private implementation modules.

## Notes

This preserves the existing hexagonal boundary rule for top-level package consumers.
