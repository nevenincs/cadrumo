---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2799d403e85f98b003cf18641e457e927c0ae6925b2ee894c5150b826da73d3c'
step_id: 'S106'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate config-reset exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/application/_config_reset_repository.py`
- `src/cadrumo/application/config_reset.py`

## Description

- Migrate the four journal ownership refusals to the registered configuration-boundary key.
- Migrate the corrupt-journal, unconfirmed-reset, pointer-identifier and vanished-target refusals to their registered keys.
- Delete the duplicated sentences from the two lookup refusals that already declared a key.

## Outcome

- Both declared modules carry no operator-facing prose refusal; a rescan returns nothing.
- Every migration reused a key already registered against its error class, so no new locale leaf was required in any catalogue.
- The ownership refusals previously encoded which artefact was unowned in the sentence itself. The operation and bucket identities now ride the context beside the specific ownership fact that failed, so a consumer can distinguish the four cases without parsing text.
- The reset service suite passes seven tests and the CLI reset selection seventeen, both serially, and both modules are lint clean.

## Notes

- Executed file by file with a test run between each.
- One migrated context exceeded the line limit and was wrapped; caught by lint before anything ran.
- No carry-forward.
