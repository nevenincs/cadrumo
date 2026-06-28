---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# wire the dead typed_enum schema field to a real consumer or delete it outright per no-legacy-compatibility, with the deletion test asserting no module reads it

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Resolve the conflicted `typed_enum` discovery by consumer inventory: `rg` across `src/aeat` found it read at four production call sites — the operator-facing `bindings list` CLI table (`_modelo_discovery_cli.py`), the `ModeloBindingRow` query projection (`_queries.py`), the borrador binding resolver (`_borrador_binding.py`), and the Sheets-pull edit router (`_calc_sheets_pull.py`) — plus it is gated by `test_schema_hygiene.py` and declared across eleven registry TOML files (`censo_event_kind`, `CCAA`, `EstimacionDirectaModalidad`, `LegalEntityForm`).
- Conclude the field is LIVE, not dead; keep it (no-legacy `delete` rule does not apply to a consumed field).
- Add a docstring on the `typed_enum` field documenting it as LIVE, naming its declaring modelos, its consumers, the gate that protects it, and its distinction from the `input_channel` (how a formula consumes the value), so the conflicted-discovery confusion cannot recur.

## Outcome

`typed_enum` is retained with explicit LIVE provenance documentation. The earlier "dead field" reading was a stale half of the conflicted discovery; the resolving evidence (four readers, a gate, eleven declarations) is now recorded in the field docstring.

## Notes

This is the cluster-D enum-hint surface the brief flagged: the field is not the cluster-B "dead schema field" the original ADR feared, so the no-legacy deletion path is correctly not taken. No code path was removed.
