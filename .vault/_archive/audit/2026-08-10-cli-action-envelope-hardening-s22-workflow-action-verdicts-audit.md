---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b826fd315508a6497bd34b19745b6194e2309dd8d84099dab7b56b055abe8970'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `s22 workflow action verdicts`

## Scope

Independent fresh-current review of `W04.P06.S22`, including the narrow S21
v3 persistence correction carried by the current source: workflow refusal
producers, closed locale-neutral run records, secure envelope version lineage,
resume projection, public workflow facade, and the current unstaged
15-producer AST guard in `test_engine.py`. S23 rendering is intentionally not
reviewed as complete; S21 and S22 remain open pending that step.

## Findings

### schema-version-description | low | Resolved stale v2 decoder wording

The initial review found that `_persistence.py` described the v3
workflow-run format as v2. The owner corrected it to the version-neutral exact
current-contract wording. The active authoritative namespace remains v3 in
`_namespace_registry.py`; header-first validation in `_persistence.py`
continues to reject the committed v2 inner envelope before typed hydration.
The documentation finding is resolved.

Verdict: **PASS**. No open finding remains.
The producer inventory is complete for the reviewed current sources:
`_deadline_stage.py`, `_engine.py`, and `_engine_recording.py` emit 15 literal
failed steps, each with `PreconditionVerdict`; the only recovery actions are
builder failure to `operator.modelo.work.calculate` with missing
`work_unit_id`, plus draft-not-ready and validation failure to
`operator.modelo.verification_report.list` with missing
`calculation_revision_id`. All other reviewed failure paths carry an explicit
terminal, safety, or operator-decision no-recovery outcome. The persisted
projection uses `WorkflowObligationFacts` and `WorkflowSiteHealthFacts`, and
the producer sweep found no write-time `tr`, raw command, or additional action
identifier in the reviewed run-record paths.

Validation boundary: the focused real-storage suite across `test_engine.py`,
`test_models.py`, `test_persistence.py`, `test_resume.py`, and
`test_run_persistence_roundtrip.py` passed 78 tests. The targeted S21/S22
implementation-and-test BasedPyright invocation reported 0 errors, 0 warnings,
and 0 notes. Scoped Ruff lint and format checks passed; scoped
`git diff --check` passed. The full-repository BasedPyright gate was not run in
this review because concurrent unrelated worktree changes are outside this
exclusive S22 surface. The reviewed tests use production imports and the real
encrypted repository path; the new AST guard and persistence anti-tamper tests
contain no mock, stub, monkeypatch, skip, or xfail shortcut.

## Recommendations

- Keep S21 and S22 open until S23 removes the remaining renderer-side
  string-equality recovery logic and proves typed v3 records render without
  restoring presentation-bearing persistence fields.
