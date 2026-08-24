---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0a1a252a4d318e1babbf9ca40309061988ae1d17c9646b9c3d1729353a81675d'
step_id: 'S17'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

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
