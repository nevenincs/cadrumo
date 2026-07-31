---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:055ba19e8e56f90ac1dd1b81db62fb362e6226d81310a2793d55f26a5f024c0d'
step_id: 'S16'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Make verify_source_catalogue accumulate absent companion binaries into one loud advisory naming the missing set and the aeat[corpus-sources] install hint

## Scope

- `src/aeat/domain/calculations/registry/_corpus_catalogue.py`

## Description

- Make `verify_source_catalogue` accumulate absent companion binaries into ONE loud advisory naming the missing set and the `aeat[corpus-sources]` install hint (`CORPUS_SOURCES_INSTALL_HINT`).
- Keep a NON-companion missing file (extracted text, normative html) a hard `RegistryValidationError` exactly as before.
- Commit `5a725a6fb9`.

## Outcome

- Split installs degrade loudly and instructively; full installs behave byte-identically.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit before reporting.
