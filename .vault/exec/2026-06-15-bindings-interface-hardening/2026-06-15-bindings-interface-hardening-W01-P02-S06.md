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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The wire the dead typed_enum schema field to a real consumer or delete it outright per no-legacy-compatibility, with the deletion test asserting no module reads it and ## Scope

- `src/aeat/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
