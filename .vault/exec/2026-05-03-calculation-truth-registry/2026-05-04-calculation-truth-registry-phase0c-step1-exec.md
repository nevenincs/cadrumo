---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
  - '[[2026-05-04-live-filing-data-capture-research]]'
  - '[[2026-05-04-calculation-truth-registry-phase-0c-review-audit]]'
---



# `calculation-truth-registry` `phase0c` `step1`

Hardened live filed-declaration capture persistence and added registry-backed
submitted-file artefact parser coverage.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_schema.py`
- Created: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- Created: `src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`
- Created: `tests/fixtures/aeat-sede/submitted-files/modelo-130-2026-1T-redacted.txt`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`
- Modified: `.vault/audit/2026-05-04-calculation-truth-registry-phase-0c-review.md`

## Description

Filed-declaration artefacts now persist through the encrypted blob store with
`FINANCIAL` classification. Normalized filed-declaration observations now
persist as encrypted `FINANCIAL` envelopes. The live capture CLI reports
encrypted storage references instead of local artefact file locations.

The observation store exposes explicit load methods for decrypting artefacts
and observations through the storage API. Its tests prove roundtrip behaviour
and assert that filing bytes, identity values, expediente ids, and casilla
values are absent from disk plaintext.

Submitted-file parser coverage now reads a committed redacted Modelo 130
submitted-file artefact. The test parses it through the registry export layout,
checks the submitted-file declaration context, and verifies all observed
casilla values without defining a casilla schema in the test.

The previous-filing binding coverage now also proves that an encrypted
observation-store roundtrip can feed the Modelo 130 binding resolver after
decryption.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py -q`
- `uv run pytest src/aeat/entrypoints/cli/auth/test_auth_cli.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/test_observation_store.py -q`
- `uv run aeat app registry verify --json`
- `uv run pytest src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/adapters/outbound/aeat/sede/test_no_write_surface.py -q`
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/_observation_store.py src/aeat/entrypoints/cli/registry.py`
- `uv run ty check src/aeat/adapters/outbound/aeat/sede/test_declarations.py src/aeat/adapters/outbound/aeat/sede/_observation_store.py src/aeat/entrypoints/cli/registry.py`
- `git diff --check`

Focused and Phase 0C validation passed. Registry verification reports the
Modelo 130 registry as verified. Live capture was retried but stopped before
browser startup because the Cl@ve session is expired, so live-captured
submitted-file fixture coverage remains open in the plan.
