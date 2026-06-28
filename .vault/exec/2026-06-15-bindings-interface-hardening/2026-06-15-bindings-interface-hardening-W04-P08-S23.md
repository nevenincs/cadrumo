---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S23'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# expose the binding provenance on BindingRowPayload and BindingPreviewRowPayload and convert bindings list from the list[dict[str,object]] bag to the typed payload

## Scope

- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`

## Description

- Add `legal_refs` and `source_refs` tuple fields to `BindingRowPayload` and `BindingPreviewRowPayload`, defaulting to empty tuples, mirroring the casilla provenance half.
- Type `ModeloBindingsListResult.bindings` as `tuple[BindingRowPayload, ...]`, replacing the untyped `list[dict[str, object]]` bag.
- Rewrite `_binding_list_rows_for_report` to build typed `BindingRowPayload` rows carrying the binding's `source`, `readiness`, `typed_enum`, `input_channel`, `borrador_capable`, and the `legal_refs` / `source_refs` pulled from the registry binding rows the report already resolves.
- Carry `legal_refs` / `source_refs` onto each `BindingPreviewRowPayload` in the preview handler.

Modified files: `src/aeat/entrypoints/cli/_modelo_payloads.py`, `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`.

## Outcome

The bindings list and preview JSON payloads are now strictly typed and carry the binding's legal grounding at parity with casillas. Provenance is sourced from the registry binding definition (the `ModeloBindingRow` already exposes `legal_refs` / `source_refs`), not invented. A new conformance test asserts the typed shape and non-empty provenance.

## Notes

The CLI `source` field renders the typed `BindingSourceKind` value as its string (the registry row's `source` is already the hydrated enum). No persistence boundary touched here — this is the operator-facing read surface; the encrypted-carrier provenance landed in P07.
