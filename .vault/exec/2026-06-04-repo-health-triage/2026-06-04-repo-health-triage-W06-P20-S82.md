---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S82'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P20.S82 Duplication Ratchet

Scope: `src/aeat`, configured jscpd duplication lane.

## Description

- Run the configured duplication audit against the current shifted worktree.
- Classify the current clone set by affected subsystem.
- Preserve the findings as a ratchet rather than refactoring across unrelated
  domains inside one hygiene row.

## Outcome

`just audit-duplication` completed and reported 36 clone groups across 853
Python files. The current ratchet is 650 duplicated lines, 6,487 duplicated
tokens, and 0.4% duplicated lines.

The largest recurring classes are:

- AEAT Sede NIF/GROI checker shape duplication.
- Registry previous-filing binding and relation validation duplication.
- Registry NIF-IVA/GROI oracle duplication.
- Modelo work CLI rendering/addressing duplication.
- Registry CLI command-output duplication.
- Ledger business-invoice CLI duplication from the current shared worktree.
- Ledger model record duplication.
- Live borrador/censo acquisition duplication.
- Parser/domain error hierarchy duplication.

## Notes

S82 closes as an explicit residual ratchet. The current clone set is too broad
for one safe mechanical edit, and the shared worktree contains concurrent dirty
and untracked CLI/test-topology work that affects the scanner surface.
