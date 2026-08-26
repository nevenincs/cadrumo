---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b840f5c32170bcf517592a2533ea4851fd50739eab4e698fd53a1508cb5eaa40'
step_id: 'S03'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and define the exact five-command machine-secret inventory, command-model registration, safe field and type schemas, conditional restore variants, and conformance API

## Scope

- `src/cadrumo/entrypoints/cli/_machine_secret_contract.py`

## Description

- Ground the inventory boundary through semantic source and accepted-decision discovery, then confirm all five live command identities and payload models by exact search.
- Declare one immutable, exact command inventory with dotted schema identities and canonical Click path tokens.
- Publish field names and JSON scalar types without secret values, defaults, examples, or invocation-derived facts.
- Model the restore payload doors as mutually exclusive variants selected only by public `artifact` option presence.
- Add idempotent command-local payload-model registration with exact field-order, field-name, and `SecretStr` conformance.
- Expose lookup, registration snapshots, and missing-registration evidence for later metadata and exact-set conformance gates.

## Outcome

The CLI now has one transport-independent authority naming every scalar-secret adopter and the strict payload shape each adopter must expose. Metadata work can project the immutable declarations without importing command implementations, while migration Steps can register their command-local models without introducing an import cycle or duplicating the inventory.

## Notes

Focused Ruff, BasedPyright, and unit tests pass. The first default xdist invocation lost a worker before test execution while peers were running concurrent suites; the required serial rerun exposed missing repository markers, which were added, and then completed all four tests successfully. No product failure was hidden.

S01 was concurrently editing the canonical secure-input module. This Step deliberately imports no S01 symbols; it requires only that later command-local payload models remain Pydantic `BaseModel` subclasses with `SecretStr` fields. Full live-tree adoption and metadata parity remain assigned to S04, S05, and S06 through S10.
