---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:cdc41a8e0d0fa0d71fa629df5ebe80a731712ae68142c7e1f1c521ecb72bb039'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S56 IVA raw provider retirement review`

## Scope

Independent review of W04.P17.S56 against the accepted governed-fact catalogue ADR, discovery ledger, adapted-family normalization reference, S30 execution and audit, and the S56 retirement ledger. The review covered the deleted `dev/registry/compiler/iva.py` and raw `rates.toml` and `recargo-rates.toml` inputs; the changed retained IVA and recargo authority projections; the retirement census; provider registration; focused tests; and production stale-path searches. It also checked that the separate local-grounding and resource-repository work remains assigned to S57.

## Findings

### stale-iva-rate-module-docstring | low | Resolved: the retained projection now states its authority-only contract

The initial review found that `rates.py` described `load_iva_rate_table` as a raw TOML validator. The repaired header now names the published `iva-rate-schedule` fact projection and explicitly says it does not read authoring TOML. The implementation agrees: it reads the installed validated authority only.

### s56-raw-provider-retirement | low | No code-path defect found in the reviewed deletion boundary

`iva-rate-schedule` and `iva-recargo-by-applied-rate` are authored mapping facts with typed selectors, temporal windows, legal or source evidence, and authored ownership. The provider registry has no IVA raw-adapter registration, the old development compiler and both raw inputs are absent, and the negative census rejects their reintroduction across production and development compiler sources. Retained `load_iva_rate_table` and `load_recargo_rate_table` project the installed validated authority only; they contain no authoring-tree reader, parser, cache, or compatibility route. The legal-catalogue `iva-rates.toml` references are evidence declarations rather than the retired raw schedule and remain correctly distinct.

The `IvaRateTableRepository` and IVA-local grounding paths remain explicit S57 work. The repository delegates to the authority projection and performs no TOML read, so it is not a surviving raw provider or a false S56 closure. S56's ledger continues to name the repository only as a caller; its deletion condition remains governed by S57.

## Recommendations

Close S56 with the current negative census and focused provider coverage. Regenerate and verify the signed authority artifact before treating runtime IVA projection suites as passed: the local worktree lacks `authority.json`, causing the domain IVA suites to fail in global fixture setup before their test bodies run. Do not restore a raw reader, adapter, or compatibility fallback to work around that missing artifact. Keep S57 independent until the local grounding and repository removal conditions are demonstrated.

## Final verdict

Clear to close W04.P17.S56. No legacy IVA or recargo raw provider, raw schedule, parser, cache, provider registration, or raw-reader documentation remains in the reviewed boundary. The focused negative-census test, Ruff, and compilation pass; broader runtime validation remains limited only by the pre-existing missing signed authority artifact.
