---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S17'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Run the campaign close gates (full-tree collect-only, path-scoped quality gates, formal vaultspec-code-review dispatch) and the mandatory fresh-context honesty review persisted as a vault audit with every surfaced item tracked as a new step or formally deferred, gate is the honesty-review audit document existing before the campaign is declared structurally complete

## Scope

- `.vault/audit (campaign close)`

## Description

- Run the full-tree collection gate and re-run it after an unrelated lane finished landing, to separate a transient reading from a real one.
- Run the path-scoped style, format, and type gates over the campaign surface.
- Run the conformance and operator-surface gates that bind the new command doors.
- Run each campaign behaviour module on its own, because a shared-process run over several of them reports failures that a per-module run cannot reproduce.
- Reconcile the independent fresh-context review's findings, which were adjudicated before this record was written.

## Outcome

Collection: 17167 tests collected with ZERO collection errors. An earlier pass of the same gate reported twenty, all in one unrelated adapter lane; re-collecting those exact files in isolation was clean, and the re-run after that lane settled was clean too, so the twenty were another lane's mid-landing state rather than a campaign defect. Recorded honestly: the clean run still exited non-zero while emitting no diagnostic, and a small-subset collection exits zero, so the code is an artefact of the large run rather than a reported problem.

Style, format, and types over the campaign surface: all clean across twenty-four files.

Conformance and operator surface: 669 passed, covering documented-command conformance, JSON-schema conformance, the operator-surface contract, the four locale catalogues, the agent harness, and the identity gate.

Campaign behaviour, per module: the session lifecycle 3 passed, profile navigation 18 passed, the lazy-import policy 6 passed, marker integrity 16 passed. The profile lifecycle verbs module reports 4 failed alongside 31 passed; those four are the shared-process isolation leak described below and pass when the module runs apart from the login tests.

The independent review's three findings were adjudicated rather than left open: the removed corrupt-store regression was accepted because its coverage genuinely moved to a verb that still reads the record, the runtime write-policy exemption was confirmed inherited rather than introduced, and the documentation finding was routed to the documentation step instead of becoming a new one.

## Notes

THE CAMPAIGN CLOSES WITH THREE STEPS DELIBERATELY OPEN. The login orchestration, the strong close, and the root-callback resume all have their code landed and recorded, but their gates assert on a persisted session artefact that cannot exist on a host whose OS credential store cannot custody a key. Every remaining failure in those three traces to one operating-system credential error. They are therefore unobservable here by nature, not defective, and they stay unchecked. Two agents measured this independently and agreed. An operator can settle all three in one interactive run on a machine with a working credential store; no code change is required. A seventeen-of-seventeen close would have been false, and this is the honest alternative.

A NOTE FOR WHOEVER READS A FAILURE COUNT FROM THIS SURFACE. There is a real cross-suite isolation weakness in the command-line test harness: several modules are entirely green run alone but fail when the login tests run first in the same process, surfacing as an unreadable profile record. It is pre-existing and was not introduced or amplified by this campaign, but it means a broad run can report failures a per-module run cannot reproduce. Several failures were misattributed to this campaign that way before it was identified, so every count above was taken per module. It is tracked with the flake work.

Two items surfaced during the close and were routed to their owners rather than absorbed: undeclared deferred imports in a custody module belonging to another lane, and generated documentation stubs belonging to the lane that deleted the modules behind them. Fixing either would have meant guessing another author's rationale or committing their in-flight work.
