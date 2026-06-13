---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-b step-2

## scope

Plan row B2: catch the empty-profile / missing-required-answer state
in `aeat config status` and emit a clean translated message instead
of leaking the pydantic `ValidationError`.

Also folds in a regression fix uncovered while testing B2: the A1
strictness sweep on `ProfileRecord` made
`ProfileRecord.model_validate(<dict-with-ISO-datetime-string>)`
reject the rehydrated workflow state. The same applied to
`DeclarationPointer`.

## changes

`src/aeat/entrypoints/cli/_config.py`:

- `config_status` checks for missing `tax.id` / `activity` and short-
  circuits with a translated `cli.config.status.empty_profile` line.
- Defensive `try`/`except ValidationError` around
  `project_answers(SETUP_FLOW, values)` for the rare case the answers
  model still rejects.

Locale catalogues: `cli.config.status.empty_profile` added to es, en,
ca, hu (ca/hu carry the English text for now; B6 captures the
intentional-identical state explicitly).

`src/aeat/application/profile/_actions.py`: introduces a
`_coerce_profile_record` helper that round-trips a rehydrated dict
through `model_validate_json` so the strict-mode `ProfileRecord` can
accept an ISO-8601 string `updated_at`. Used by `set_profile_values`
and `clear_profile_values`.

`src/aeat/application/workflow/_models.py`: same JSON round-trip
treatment for `WorkflowState.active_profile_record` and
`update_declaration_pointer` so they survive under the A1+A2
strictness sweep.

## verification

`aeat config status` against an empty sandbox emits the translated
"Sin perfil configurado…" message and exits 0 (no traceback).

`pytest src/aeat/application/auth/ src/aeat/application/workflow/
src/aeat/application/review/ src/aeat/application/profile/
src/aeat/entrypoints/cli/test_config_setter.py` returns 297 passed
plus one pre-existing failure
(`test_config_help_lists_the_new_surfaces` asserts the old
`setup` CLI verb name; a concurrent stream renamed it to `init` and
owns the corresponding test update).
