---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:5f67fae77a325efbeb769a2e262588b686a40e7beaa900529bc1025f84eb04d9'
step_id: 'S28'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Run the locale parity, translation honesty, and scaffold check gates green for the substrate key namespaces

## Scope

- `src/cadrumo/locales/`

## Description

- Run the locale test suite: parity, translation honesty, dynamic-prefix registry coverage, placeholder self-echo, and language-override inventory gates all green for the substrate namespaces (44 passed).
- Run the scaffold drift check; remove the two orphaned wizard answer-queue error leaves the prompter retirement left behind, through the locales CLI across all four catalogues, and land the removal as its own explicit-pathspec commit.
- Re-run the drift check: zero extras remain.

## Outcome

Every substrate key namespace (`flows.*`, `application.flows.*`, `wizard.*`, the status-page and copy-slot registrations) is green across parity, honesty, coverage, and drift gates. The orphaned-leaf cleanup previously deferred to a post-merge sweep was retired early in the same pass.

## Notes

- Owner triage: the remaining drift-check and audit reds are one missing key, `application.wizard.notices.modify_descendants_via_door`, referenced by a peer campaign's uncommitted descendant-door notice; the peer sets that key in their commit. No substrate namespace is affected.
