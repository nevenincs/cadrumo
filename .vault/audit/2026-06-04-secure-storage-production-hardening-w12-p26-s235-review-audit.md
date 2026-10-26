---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:f6c4f11a4208dc57af708bd405ed1ac900acc68b3aeb07c802b28cb3b7c75f6b'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S235` Review

## S235-001 | PASS | Borrador binding is a remote-mirror secure-object consumer

The retired module owned the application decision
to consume a selected Modelo 100 borrador snapshot for calculation binding
inputs. It validates registry capability, calculation axis, snapshot lifecycle,
and caller-precedence rules, then returns typed binding values and source-mesh
provenance. When no repository is injected it constructs the bucket-bound live
borrador snapshot repository, whose durable records are FINANCIAL
`Envelope[Borrador100Snapshot]` payloads persisted through the runtime
secure-object backend. Disposition is therefore `remote-mirror`, not
manifest-only discovery.

## S235-002 | PASS | User-facing refusals are locale-backed

Raw `Modelo100BorradorBindingError` messages in the reviewed surface were moved
to `application.modelo.borrador_binding.errors.*` locale leaves with structured
context. The bucket-mismatch refusal no longer echoes actual bucket identifiers;
it reports the bounded active-bucket mismatch instead. Locale leaves were
authored through `python -m aeat.locales set` and verified with the locale audit.

## S235-003 | PASS | Storage degradation is diagnosed, not swallowed

`ClassificationError`, `DecryptionError`, and `EnvelopeVersionError` raised by
the live repository path are caught only at the source-mesh adapter boundary and
converted through the shared storage-degradation diagnostic helper. That helper
logs the exception at debug level with exception info and returns a structured
`storage_degraded` reason to the calculation source pipeline.

## S235-004 | PASS | Validation

- the historical check passed.
- the historical check passed.
- the historical check passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S235` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed after the adjacent S236 export keys landed.

Disposition: close `AFR-133` as `remote-mirror`.
