---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S463'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Reconcile W20 custody rows with the D1 `config switch` contract

## Scope

- `.vault/plan`

## Description

- Grounded the current operator command against the accepted D1 decision and its landing commit.
- Added the D1 operator-surface ADR to the successor plan's authorizing chain.
- Rewrote W20 custody rows S451, S457-S461 from the superseded `config unlock` spelling to the code-led `config switch` contract.

## Outcome

The plan now correctly names `aeat config switch` as the sole profile-selection command.
`aeat config unlock --help` fails as required by D1, while `aeat config switch --help`
resolves successfully. No `unlock` alias or new storage-facing command was introduced.

## Notes

This is a planning-record correction, not a production-code change. The follow-on
W22 steps retain the regression, locale, documentation, and audit work needed to
keep the hard rename true over time.
