---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:c6abbc358fae5ccaadb235e60a47727fb7cb60c7ea05251d9d5b7936fe2827e5'
step_id: 'S17'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Require every current and future CLI root, group, and leaf to be declared exactly once through CommandSpec with no decorator, registrar, callback-metadata, generated-resource, or path-catalogue escape hatch and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Require every current and future CLI root, group, and leaf to be declared exactly once through CommandSpec with no decorator, registrar, callback-metadata, generated-resource, or path-catalogue escape hatch

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_command_loading_contract.py`

## Description

- Extend the universal production-source authority scanner across imported and aliased
  registrars, reflective decorators, callback metadata, target/import catalogues,
  nested assignments, and constant-key dictionary mutation.
- Keep runtime projection privilege exclusive to the CommandSpec compiler and allow
  only the exact same-object error-boundary callback wrapper outside it.
- Add adversarial plants for every supported bypass spelling and retain dynamic live
  graph exact-set enforcement as the runtime backstop.

## Outcome

Every current and future CLI node remains exactly once in CommandSpec authority. The
scanner rejects decorator, registrar, callback metadata, generated resource, route/path,
package-target, import-gate, alias, and constant-reflection escape hatches. Six focused
tests and Ruff pass; independent review approved the final monotone scanner.

## Notes

Review found and resolved an overbroad error-wrapper exemption, registrar false positives,
reflection alias gaps, and a possible constant-propagation oscillation. Runtime-computed
reflection remains outside sound static analysis and is caught by live graph parity. No
harness or client shipping file was modified.
