---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S13'
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
     The S13 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
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
     The fix any latent malformed registry TOML the new build gate surfaces so the full registry suite collects and builds clean and ## Scope

- `src/aeat/_data/registry/aeat/modelos/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# fix any latent malformed registry TOML the new build gate surfaces so the full registry suite collects and builds clean

## Scope

- `src/aeat/_data/registry/aeat/modelos/`

## Description

- Run the full registry test suite (the 2745-test registry `tests/` directory, which exercises snapshot construction across every modelo), the committed-registry validation tests (`test_committed_registry.py`, `test_catalogue_verification.py`, `test_referential_integrity.py`), and `pytest --collect-only -q src/aeat`, to surface any latent malformed registry TOML the now-authoritative build gate would reject.
- Inspect the only invoice-binding modelo (M349) and the detail-record / previous_filing modelos (232, 720, 184, 360, 130, 100) to confirm their bindings are conformant to the lifted op/fact invariants.

## Outcome

No latent malformed registry TOML surfaced. The bundled registry was already conformant to the lifted build-time invariants (the M349 invoice bindings declare scalar facts without grouping and row facts with grouping; the detail-record families use the `row_field`/`rows` shape; previous_filing ops match the supported set). The committed-registry validation passes (76 tests), the full registry suite passes (2745 tests excluding two owner-distinct peer failures), and full-tree collect-only reports 15955 tests with zero collection errors. No TOML change was required.

## Notes

Two full-registry-suite failures are owner-distinct peer churn, not this surface: `test_config_repair_report_includes_registry_integrity_check` fails on an `ImportError` for `build_config_repair_report` (a symbol removed/renamed by the concurrent graceful-degradation campaign in `aeat.application.diagnostics`), and `test_validator_rejects_invoice_binding_without_typed_selector` was updated in P03 to assert the new precise field-named diagnostic. No registry data was modified in this Step.
