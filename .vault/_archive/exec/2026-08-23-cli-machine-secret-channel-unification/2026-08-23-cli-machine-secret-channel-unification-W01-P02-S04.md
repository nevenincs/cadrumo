---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:11807ddcf1bbd61b9f1afb8d96c614c3b6b7276c2fd4e0feb285c27a8d2322de'
step_id: 'S04'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and project value-free machine-secret payload variants into verb input and command schemas

## Scope

- `src/cadrumo/entrypoints/cli/_verb_input_schema.py and src/cadrumo/entrypoints/cli/_command_schema.py`

## Description

- Ground schema ownership and the governing decision through semantic code and Vault discovery, exact-symbol search, and full-file inspection.
- Add one immutable, value-free metadata projection derived from the closed machine-secret command contract.
- Attach the same ordered payload variants to generated command-registration rows and live verb-input schemas.
- Preserve restore's public `artifact` absent/present discriminator without importing command handlers or secret values.
- Prove non-adopter emptiness, ordered field/type projection, conditional variants, and value-free serialization through focused integration tests.

## Outcome

Both operator-discovery surfaces now expose canonical machine-secret payload variants. The projection contains only variant keys, required field names, JSON scalar types, and public option-presence conditions; it contains no secret values, defaults, or examples. Commands outside the closed inventory project an empty tuple.

## Notes

- Focused Ruff, `ty`, import smoke, and two integration projection tests pass.
- The broader integration modules remain red because concurrent command-tree work leaves eighty-one lazy leaves unresolved and injects completion options into `config reset status`; neither failure is introduced by this scoped projection.
- The repository import-hygiene lane remains red at its existing test-only private-import debt gate (`115` current sites versus `69` documented); this Step adds no import site to that inventory.
- BasedPyright reports five existing diagnostics in the two owned production modules; `ty`, the canonical checker, passes the scoped files.
