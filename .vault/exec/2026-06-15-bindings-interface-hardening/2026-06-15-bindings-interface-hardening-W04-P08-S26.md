---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S26'
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
     The S26 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The add documented-command and json-schema conformance tests covering the typed bindings list payload and the --modelo Choice refusal and ## Scope

- `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
- `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add documented-command and json-schema conformance tests covering the typed bindings list payload and the --modelo Choice refusal

## Scope

- `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`
- `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Add three real-CLI integration tests in `test_modelo_registry_surface.py`: the `--modelo` Choice refuses an unknown code with the accepted set, the `--help` surface renders the accepted modelo codes, and the `bindings list` JSON payload is the typed shape carrying `legal_refs` / `source_refs` (with a non-empty-provenance assertion against Modelo 100).
- Add two real-CLI tests in `test_modelo_calculation_through_real_cli.py`: the malformed-numeric `--binding` refusal (decimal channel refuses, names binding/flag/value) and the enum-channel acceptance (anti-tautology companion proving the refusal is channel-specific).
- Add a focused unit test `test_calculate_binding_channel.py` exercising the `_binding_input_channel` discriminator against the live Modelo 200 revision (enum routes enum, decimal routes decimal, unknown refuses with the accepted set).
- Rely on the pre-existing no-allowlist conformance gates (`test_json_schema_conformance.py`, `test_documented_command_conformance.py`), which already bind the `modelo.bindings.list` / `.preview` schemas and the documented verbs; re-ran both green after the payload re-typing.

Modified/added files: `src/aeat/entrypoints/cli/tests/test_modelo_registry_surface.py`, `src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py`, `src/aeat/application/modelo/tests/test_calculate_binding_channel.py`.

## Outcome

All new tests pass (5 integration + 3 unit). The two conformance gates stay green (141 passed) with the re-typed `ModeloBindingsListResult.bindings`; the non-integration CLI suite passes (82) and full-tree collection shows 0 errors. No mocks, no tautologies — expected values are the registry's own declared shapes and the typed-channel contract.

## Notes

The new tests live in the existing topology-correct `tests/` folders rather than new conformance modules: the JSON-schema and documented-command gates already enforce the envelope/verb contract generically (no per-payload edit needed for the typed re-shape), so the focused additions target the provenance fields, the Choice refusal, and the channel coercion that those generic gates do not assert. The `_binding_input_channel` import triggers the same accepted `reportPrivateUsage` pyright warning as the sibling `_decimal` test — the established in-tree private-helper test convention.
