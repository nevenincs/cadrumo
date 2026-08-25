---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f93fe40aa89c22172aa2434f0f1cda118f0dcdb3eb705c5d5df261790f57d987'
step_id: 'S97'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate workflow exception precondition and continuation producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/application/workflow/_models.py`
- `src/cadrumo/application/workflow/_engine.py`
- `src/cadrumo/application/workflow/_profile_bucket_scan.py`
- `src/cadrumo/application/workflow/_deadline_stage.py`
- `src/cadrumo/application/workflow/_resume.py`

## Description

- Scan the five declared workflow modules for operator-facing prose refusals.
- Migrate the resumed-from run-id guard and the verify-target guard to their registered message keys with machine facts.

## Outcome

- Four of the five declared modules carried no operator-facing prose refusal and needed no change; the models, bucket-scan, deadline-stage and resume modules were already clean.
- The resumed-from guard had spelled out the expected run-id shape and echoed the rejected value in a sentence. It now carries the field, the value and a shape-validity fact.
- The verify-target guard had named its own requirement in prose. It now carries the workflow identity and an explicit-target fact.
- Both reuse message keys already registered against their error classes, so no new locale leaf was required in any catalogue.
- The workflow suite passes one hundred and twenty-two tests serially and the package is lint clean.

## Notes

- This step was executed file by file with a test run between, rather than as one sweep. That was a deliberate correction of the method used on the preceding residual-Modelo step, where a package-wide regular-expression sweep produced a large failure spike that took several rounds to recover.
- Three failures in the workflow suite are unrelated peer breakage in profile-record readability, confirmed by reading the tracebacks: the assertions concern a profile health state rather than either migrated guard, and neither failing path reaches the engine module.
- No carry-forward: the declared scope holds no remaining operator-facing prose refusal.
