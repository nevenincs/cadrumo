---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b495324ec2c6bb607885df90be66e5c699372c014fbea0f2be870f7cc0566bcc'
step_id: 'S56'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Examine app diagnostics and the ledger action verbs; tighten the diagnostics group help, which named neither of its two subjects

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `python -m dev.locales scaffold --check` -> `ok`
- `verify:` `pytest four campaign gates` -> `22 passed`

## Notes

**`app diagnostics` is not a second home for workflow runs.** `app diagnostics
runs` lists local LLM inference run-timing records; `app modelo work runs` lists
persisted `WorkflowResult` rows. Same word, different entities.

What the family does have is terse leaf names -- `runs`, `latency`, `errors`,
`run-health` -- none of which says it is scoped to on-host LLM inference. That
is adequately handled at the point of use: every one of those leaves states the
scope in its own help ("recent local LLM runs"), which is the standard S37 and
S47 set. The group help did not: it read "Local-only operator run-health and
session diagnostics", naming a shape rather than either of its two subjects. It
now names both -- on-host LLM inference runs, and persisted AEAT session
staleness -- in all four catalogues.

The root placement was considered and left. Observability of the app's own work
is neither configuration nor tax work, and with only two roots permitted, `app`
fits it better than `config`, which would file runtime telemetry under setup.

**`attach` versus `link` is principled, and the parameters prove it.** Both take
`transaction_id` positionally, as the single-subject rule requires. `attach`
takes `--attachment-ids` / `--purchase-invoice-evidence-id` and binds stored
evidence OBJECTS; `link` takes `--invoice-id` and binds a catalogue RECORD
reference. Document payload versus record reference, and `AttachmentStore`
grounds the first word in the domain vocabulary.

**`split`, `merge` and `classify` are structural verbs the contract already
carves out.** `merge` declares no positional subject, which would breach the
subject-is-positional rule for a single-subject verb -- but the contract exempts
verbs that act on a set or destroy the subject, and names `split` and `merge`
explicitly.
