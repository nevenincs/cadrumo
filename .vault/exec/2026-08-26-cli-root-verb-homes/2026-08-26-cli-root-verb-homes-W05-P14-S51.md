---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:0ea8d63a652c04fae7c709a4cb86bbc0dc47b0087674a494c4b07d4bea577e94'
step_id: 'S51'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# RULED: rename `app modelo reconcile history` to `list`, sweeping specs, token, handler, envelope identity, locale keys, harness documents and the documented sequence

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_nonwork_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_m036_command_shape.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py`
- `M` `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `M` `src/cadrumo/application/modelo/reconciliation.py`
- `M` `dev/quality/modelo_workspace_action_denominator.py`
- `M` `src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_persona_scope.py`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/personas/cadrumo-reconciler.md`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/skills/cadrumo-reconciliar/SKILL.md`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `docs/how-to/reconcile.md`
- `R` `docs/_sequences/contracts/how-to/reconcile/reconcile-history.seq -> reconcile-list.seq`
- `R` `docs/_sequences/how-to/reconcile/reconcile-history.json -> reconcile-list.json`
- `verify:` `python -c "...COMMAND_GRAPH..."` -> `reconcile family is import/list/pull; 294 leaves, 64 declarations`
- `verify:` `pytest four campaign gates` -> `22 passed`
- `verify:` `pytest test_documented_command_conformance.py -m integration` -> `pass`
- `verify:` `python -m dev.docs.sequences check --page how-to/reconcile` -> `clean`
- `verify:` `python -m dev.locales scaffold --check` -> `ok`

## Notes

Raised for a ruling rather than decided here, because a verb rename is
operator-facing and the campaign's precedent for that is an operator decision --
`mirror` became `archive push` that way, and S41's own row was written "NEEDS A
RULING before execution". The operator ruled for `list`.

The evidence was genuinely two-sided and both sides were put. FOR `list`: the
handler's own docstring said "List past reconciliations", it calls
`list_modelo_reconciliations`, it returns a count plus rows rather than an event
chain, `--work-unit-id` is an optional filter rather than a subject, and zero of
the 33 `list` leaves in the tree take a subject argument. FOR `history`: the rows
carry `event_id` and are genuinely past events, and the implicit subject is the
active profile, which would have paralleled `app live iva-wallet history`.

A detail that arrived after the ruling supports it: the existing translations of
`history_help` in all four catalogues already read "List" / "Lista" / "Llista" /
"Listázza". The prose had been describing a `list` for as long as the key
existed.

The payload classes keep their names. `ModeloReconciliationHistoryResult` and
`ModeloReconciliationHistoryRowPayload` mirror the application-layer
`ModeloReconciliationHistoryEntry`, which names the DATA -- a recorded
reconciliation -- not the verb. Renaming only the CLI half would desynchronise
them from the type they project.

The positional token was the trap again: renaming the spec key, both help keys,
the handler target and the envelope identity all succeeded while `token="history"`
sat untouched, exactly as in S45. It was flipped by line with an assertion, and
only the graph rebuild would have caught it otherwise.
