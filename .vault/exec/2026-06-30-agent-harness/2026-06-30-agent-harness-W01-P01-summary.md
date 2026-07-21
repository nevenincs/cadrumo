---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-agent-harness-plan]]"
---

# `agent-harness` `W01.P01` summary

Phase P01 built and wired the operator capability manifest command. All five
steps closed; landed in commit `25534b6aa`.

- Created: `src/aeat/application/operator_surface/_manifest.py`
- Created: `src/aeat/entrypoints/cli/_app_contract.py`
- Created: `src/aeat/entrypoints/cli/_app_contract_payloads.py`
- Modified: `src/aeat/application/operator_surface/__init__.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`

## Description

- S01: Defined `ContractManifestResult`, a strict `OutputSchema` payload
  registered under the stable `contract` envelope key.
- S02: Added `OperatorSurfaceManifest` plus `build_operator_surface_manifest`,
  projecting the cached operator-surface contract; the registered command-schema
  index is injected from the CLI boundary so the application layer never imports
  the CLI schema registry (hexagonal direction preserved).
- S03: Mounted the read-only `contract` command as an `invoke_without_command`
  group-callback that emits the manifest through the shared envelope; no AEAT
  contact, no state mutation.
- S04: Wired the command into the `app` group via the lazy loader (and its
  allowlist), keeping the CLI root surface pinned to `config` and `app`; the
  payload-discovery loader populates the schema registry across all three
  payload-module naming shapes (219 commands resolved).
- S05: Authored the `cli.contract.*` help and summary locale leaves across
  en/es/ca/hu through the locales CLI; scaffold drift check and parity/honesty
  gates are green.

## Outcome

`aeat --format json app contract` emits a valid success envelope (command
`contract`, status `success`) carrying both roots, all 15 mounted command
families with their mutability and intent, the `CALCULATE -> VERIFY -> FILE`
lifecycle, and a 219-entry command-schema index. Text mode renders a localized
summary. Verified by manual invocation and the P02 gates.

## Notes

The locales CLI re-wrapped existing long lines in the four catalogues (its
serializer folds at a narrower width than the committed form); this is the
mandated tool's canonical output and the parity/honesty gates stay green.
