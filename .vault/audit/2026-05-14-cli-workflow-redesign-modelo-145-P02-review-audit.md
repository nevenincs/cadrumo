---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-p02-s07-s10-exec]]'
---



# `cli-workflow-redesign` Code Review


MODELO-145-P02-001 | BLOCKING | Repair stale registry schema mutation test

`test_modelo_file_rejects_empty_filing_grade_evidence` replaced an obsolete
single-reference `legal_refs` string. The committed Modelo 130 fixture now has
a longer legal reference list, so the test no longer mutated the copied TOML
and did not raise.

Resolution: fixed the mutation target to match the current committed Modelo
130 legal reference list, restoring the intended load-time failure.

MODELO-145-P02-002 | MEDIUM | Make Modelo 145 communication vocabulary mandatory

The first P02 validator pass made filing/deadline/live/portal rejection depend
on a revision voluntarily declaring a communication surface. A bad Modelo 145
registry could still choose normal filing vocabulary. That left the ADR
constraint opt-in rather than enforced.

Resolution: validator closure now requires Modelo 145 revisions to declare a
communication or payer-delivery application link and applies the forbidden
filing, deadline, live, portal, and filing-schedule checks to Modelo 145 even
when a bad TOML omits communication vocabulary. Added a regression test proving
Modelo 145 without communication vocabulary is rejected.

MODELO-145-P02-003 | MEDIUM | Keep communication vocabulary scoped to Modelo 145

The first fix still allowed any non-145 modelo with casillas to validate using
communication or payer-delivery surfaces instead of filing, weakening ordinary
filing validation and drifting beyond the Modelo 145-only ADR boundary.

Resolution: communication and payer-delivery application links are now accepted
only for Modelo 145. Non-145 modelos continue to require filing semantics for
casilla-bearing revisions unless a future ADR explicitly extends communication
vocabulary to another model.

Follow-up review: no blocker, high, or medium issues remain in the P02 scope.
The reviewer confirmed non-145 communication revisions are rejected and the
same communication revision validates only when the modelo id is `145`.
