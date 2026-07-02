---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S238'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S238 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R7-MARC-D3 modelo bindings list without --year --period flags returns binding ids for an arbitrary revision (often the latest) and ## Scope

- `copy-paste of those ids into work calculate fails with unknown registry binding ids`
- `either narrow the unfiltered output to the work-unit-current revision OR surface a warning that filtering is needed`
- `src/aeat/entrypoints/cli/_modelo.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-MARC-D3 modelo bindings list without --year --period flags returns binding ids for an arbitrary revision (often the latest)

## Scope

- `copy-paste of those ids into work calculate fails with unknown registry binding ids`
- `either narrow the unfiltered output to the work-unit-current revision OR surface a warning that filtering is needed`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Ground the testimonial with `vaultspec-rag` against the Modelo bindings discovery and work-calculate revision mismatch surfaces.
- Keep `modelo bindings list` broad for discovery, but emit a typed warning `Notice` when `--year` or `--period` is missing.
- Mirror the same notice into text output so non-JSON operators see the copy-paste risk before using binding ids with `work calculate`.
- Add real CLI regression coverage for unscoped, partially scoped, and fully scoped `bindings list` calls.
- Refresh the Modelo 100 missing-filter fixture expectation to match current real profile-derived binding resolution.
- Add English, Spanish, Catalan, and Hungarian locale leaves for the warning and suggestion.

## Outcome

- Closed. `app modelo bindings list --modelo 303` now warns that the listing is not scoped by `--year, --period` and may include binding ids from a revision that does not match the work unit used by `work calculate`.
- Closed. JSON output carries the warning through the shared `notices` envelope with code `modelo.bindings.list.unscoped_revision`; the typed result payload remains unchanged and has no bespoke notice field.
- Closed. Text output renders a `notice	warning	modelo.bindings.list.unscoped_revision	...` row derived from the same `Notice` object.
- Closed. `app modelo bindings list --modelo 303 --year 2026 --period 1T` emits no scope warning.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The live owner was `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`, not the stale plan-row pointer to `src/aeat/entrypoints/cli/_modelo.py`.
- Review found no code issues. Residual risk is limited to translation wording quality beyond placeholder/interpolation parity; semantic review was English-focused.
- Validation: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_modelo_registry_bindings_surface.py src/aeat/entrypoints/cli/tests/test_bindings_list_missing_filter.py -m integration -q` passed with 20 tests.
- Validation: `uv run --no-sync pytest -m unit src/aeat/core/i18n/tests/test_placeholder_parity.py -q` passed.
- Validation: `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py::test_success_envelope_carries_shared_spine src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py::test_registered_schema_has_no_bespoke_notice_field src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py::test_error_document_shares_the_success_spine -q` passed.
- Validation: `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo_discovery_cli.py src/aeat/entrypoints/cli/tests/test_modelo_registry_bindings_surface.py src/aeat/entrypoints/cli/tests/test_bindings_list_missing_filter.py` passed.
- Validation: `uv run --no-sync python -m aeat.locales scaffold --check` and `uv run --no-sync python -m aeat.locales audit` passed for all four locale files.
