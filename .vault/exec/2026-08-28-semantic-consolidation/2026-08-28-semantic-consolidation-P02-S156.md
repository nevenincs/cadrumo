---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7a82c6af2cd13754416bf6c5fac769df04a55a0208351562b078b6124dca02b7'
step_id: 'S156'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Elide the rendered finding message instead of refusing it, and state the workflow reason-class bound once, clearing the config and modelo payload modules

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/application/workflow/events.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `M` `src/cadrumo/application/workflow/events.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` a 600-character finding message now stores 500 ending ` [...]`; 5000 likewise; 500 unchanged
- `verify:` `reason_class` accepts 64, refuses 65, from one declaration
- `verify:` `pytest payload gate -n 0 -m ""` -> pass (7); outstanding modules 4 -> 2

## Notes

`FindingPayload.message` capped at 500 and REFUSED above it. That message is not
authored: it is `tr(finding.message_locale_key, **finding.message_facts)`, a
locale template with taxpayer data substituted, so its length is set by the
household rather than by a writer.

`core/prose_elision.py` exists for exactly this and names it in the first
sentence of its own docstring -- "a diagnostic, finding, or issue whose message
is assembled from taxpayer data has a length nobody authored... when such a
message crosses its field's cap the model raises, and a NON-BLOCKING advisory
becomes a blocking failure." The finding payload had not adopted it. The
consequence is worse than a truncated string: a refused payload drops the
finding, so the verification results with MOST to say are the ones the operator
would not have seen.

Probed: 600 and 5000 characters now store 500 with the visible ` [...]` marker.

The domain finding carries no `message` field at all, only the locale key and
its facts, so this cap is not a restatement of anything -- it is the only
declaration of how long a rendered finding may be, and it was the wrong KIND of
declaration rather than a duplicate one. Worth separating: not every gate finding
is a duplication, and this one would have been missed by looking for a canonical
counterpart.

`reason_class` was the plain case: the same `min_length=1, max_length=64` on the
workflow event and again on the CLI payload that projects it. Declared once, on
the event.

Both modules then declared nothing further and the gate said so on its own.
Outstanding is 2, from 11 when this phase started.

Neither P02.S03 nor P02.S05 is complete and neither is marked. S03 still asks for
the imported-evidence match invariant to move to the filing-record model; S05
still has `_overview_payloads.py`, whose four remaining declarations are
coherence validators rather than bounds.
