---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1231a806265dfe18be993c1dace72f5b5bf0176d5bf17e535a820e632db22c4b'
step_id: 'S22'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Emit typed verdicts from workflow refusal branches

## Scope

- `src/cadrumo/application/workflow/_engine.py`

## Description

- Enumerate every workflow refusal and operational-abort producer with semantic
  RAG, `fd`, `rg`, AST inspection, and direct source tracing.
- Replace persisted workflow deadline and site-health adapter records with
  strict workflow-owned projections containing locale-neutral facts only.
- Emit canonical `PreconditionVerdict` records from all fifteen failed-step
  producers, including explicit no-recovery outcomes where no live corrective
  action exists.
- Bind draft build failure to `operator.modelo.work.calculate` with unresolved
  `work_unit_id`, and bind draft readiness and validation failures to
  `operator.modelo.verification_report.list` with unresolved
  `calculation_revision_id`.
- Remove write-time translation markers and rendered summaries from workflow
  result production; validate every persisted summary against a closed locale
  identity set.
- Advance workflow-run persistence from committed strict schema v2 to strict
  schema v3 and reject v2 envelopes rather than retaining a compatibility
  reader.
- Add model rejection, encrypted roundtrip, output-language invariance, exact
  producer-matrix, and live command/input-schema resolution proofs.

## Outcome

All fifteen workflow failed-step producers now persist a closed summary locale
identity, typed stable facts, and a canonical precondition verdict. Three
producer conditions expose actions that resolve through the canonical operator
catalogue; the remaining conditions report terminal, safety, or
operator-decision no-recovery outcomes. Persisted obligation facts omit
`applies_because` and raw recovery commands. Persisted site-health facts omit
URL, HTML, and detected marker strings.

The expanded workflow/modelo and live action-schema selection passed 81 tests.
The focused AST producer-matrix and live action-schema selection passed 9 tests.
Exact S22
files passed Ruff, formatting, `git diff --check`, forbidden-pattern scanning,
and strict basedpyright with zero diagnostics. Repository-wide basedpyright was
also run and remains red only in concurrent work outside this step's ownership.

The implementation is intentionally left open. `W04.P06.S21`,
`W04.P06.S22`, and `W04.P06.S23` must close together after the S23 renderer and
locale catalogue consume these identities.

## Notes

A delegated read-only census accidentally closed S22 by invoking the mutating
plan-step command. The plan owner was notified immediately, and S22 was reopened
with the sanctioned VaultSpec CLI. No hand edit was made to plan state; S21,
S22, and S23 are all still unchecked.

Full-repository strict type checking reported fifteen diagnostics in concurrent
work under modelo export, prior domiciliation, verification, user-profile,
profile-health, and invoice normalization. None names an S22-owned file. An
exact file-scoped strict check for the S22 implementation and tests completed
with zero errors, warnings, or notes.
