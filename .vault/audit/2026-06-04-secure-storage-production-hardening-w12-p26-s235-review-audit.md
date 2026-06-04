---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S235]]'
---

# `secure-storage-production-hardening` `W12.P26.S235` Review

## S235-001 | PASS | Borrador binding remains manifest discovery

`src/aeat/application/modelo/_borrador_binding.py` owns the application decision
to consume a selected Modelo 100 borrador snapshot for calculation binding
inputs. It validates registry capability, calculation axis, snapshot lifecycle,
and caller-precedence rules, then returns typed binding values and source-mesh
provenance. Durable snapshot storage remains delegated to the live borrador
snapshot repository and runtime secure-object backend.

## S235-002 | PASS | User-facing refusals are locale-backed

Raw `Modelo100BorradorBindingError` messages in the reviewed surface were moved
to `application.modelo.borrador_binding.errors.*` locale leaves with structured
context. The bucket-mismatch refusal no longer echoes actual bucket identifiers;
it reports the bounded active-bucket mismatch instead. Locale leaves were
authored through `python -m aeat.locales set` and verified with the locale audit.

## S235-003 | PASS | RAG duplication search confirms resolver split

`vaultspec-rag search "modelo borrador binding storage boundary" --type code
--port 8766 --max-results 12` clustered the command/result models, application
resolver, dedicated tests, shared decimal parser, and package exports around
`_borrador_binding.py`.

`vaultspec-rag search "borrador capable binding profile source calculation"
--type code --port 8766 --max-results 12` found the calculation binding
pipeline in `_actions.py`, profile binding in `_profile_binding.py`, and
borrador-source resolution in `_borrador_binding.py`. No duplicate secure
storage backend or second borrador binding owner was found.

## S235-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_borrador_binding.py` passed with 21 tests.
- `python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Disposition: close `AFR-133` as `manifest-discovery`.
