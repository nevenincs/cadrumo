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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The expose the binding provenance on BindingRowPayload and BindingPreviewRowPayload and convert bindings list from the list[dict[str,object]] bag to the typed payload and ## Scope

- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_discovery_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
