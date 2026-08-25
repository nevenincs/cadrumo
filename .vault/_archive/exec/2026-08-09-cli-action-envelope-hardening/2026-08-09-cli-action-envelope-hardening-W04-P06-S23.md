---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b7180f08ef21276744947e547ca9ec8cd0baa76664151975790f1a00dfd9ea60'
step_id: 'S23'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Remove English string-equality recovery matching from work-run rendering

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py`
- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `src/cadrumo/entrypoints/cli/_common.py`
- Direct workflow-run renderer and locale-catalogue tests

## Description

- Project closed S21 workflow summary identities as ephemeral
  `tr(summary_locale_key, **typed_details)` presentation.
- Project typed workflow obligation, stage, details, and site-health facts in
  the run payload without restoring persisted or free-form prose.
- Resolve persisted precondition verdicts through the canonical operator
  action catalogue and reconciled live CLI schema, including declared binding
  provenance and unresolved required arguments.
- Remove English translation defaults and legacy command reconstruction from
  work-run help and rendering.
- Add real English, Spanish, Catalan, and Hungarian CLI coverage with one
  locale-independent structural digest and independently localized summaries.
- Add fail-closed resolution proofs and AST guards against translation
  defaults, persisted-prose matching, untyped detail lookup, free-form next
  actions, raw CLI literals, and prose fallback.
- Verify every closed workflow summary identity and its interpolation
  placeholders across all four locale catalogues.

## Outcome

Workflow-run output now exposes one stable machine envelope in every supported
locale. Only the human `summary` value changes by locale; obligation facts,
typed details, site-health facts, canonical action target, live CLI path,
binding provenance, and missing required arguments remain structurally
identical. Actions fail closed when an identifier is absent from the canonical
catalogue, required bindings are insufficient, or binding provenance is not
declared.

Focused S23 validation passed five tests. The combined workflow application
lane passed 61 tests and the CLI refusal/resume/renderer lane passed 23 tests.
Ruff lint and formatting, diff whitespace, locale scaffold parity, and the full
locale audit passed. Independent Terra xhigh review returned PASS with no S23
finding. Repository-wide strict typing remained red on fourteen diagnostics in
concurrent files outside the S23 surface; none names an S23-owned file.

## Notes

An initial broader workflow collection was blocked by a concurrent stale import
of `cross_period_clean_state_next_action` in modelo verification code. The six
unblocked workflow modules passed 61 tests; the separately exercised CLI lanes
passed 23 tests.

During locale validation, a process identifier was reused after the owned
scaffold check completed. A subsequent stop request targeted that stale
identifier and interrupted a peer's read-only `rg` process. No file or Git
state was changed. The incident was disclosed immediately, and no further
process termination was attempted.
