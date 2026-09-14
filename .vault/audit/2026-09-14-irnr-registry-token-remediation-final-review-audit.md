---
tags:
  - '#audit'
  - '#irnr-registry-token-remediation'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:3371a8af2e5790d507e6ac32ef1a756e5d8500c8e19587f6d2519cd7f829236b'
related:
  - "[[2026-09-14-irnr-registry-token-remediation-authority-path-reference]]"
---
# `irnr-registry-token-remediation` audit: `registry token remediation final review`

## Scope

Reviewed the opaque IRNR core token contracts, validated registry projections, convenio rate semantics, Modelo 210 payer applicability, migrated test consumers, focused validation evidence, and the final core collection gate. Unrelated worktree changes and unrelated refactor failures were excluded.

## Findings

### convenio-rate-projection | high | String-backed governed rates were refused

Resolved. `resolve_convenio_override` expected an already-materialized `Decimal`, while the validated override fact contract publishes canonical decimal text. `src/cadrumo/domain/calculations/registry/convenio.py` now centralizes strict projection and validates required, forbidden, finite, and unit-interval rate semantics for both compiled rows and resolved facts.

### payer-mode-applicability | high | Code-specific payer mode was not enforced by row construction

Resolved. `Modelo210AgrupacionRentaRow` projected payer tokens but did not consult the registry declaration that binds code 35 to its required mode. `required_m210_payer_mode_for_code` now exposes that governed relationship, and both transaction and detail-row validation consume the same typed result.

### stale-token-consumers | medium | Tests retained the deleted enum contract

Resolved. Core, application, domain, persistence, CLI, and development-registry tests now obtain tokens from the validated catalogue, candidate compiler authority, or compiled convenio rows. Static scans find no member access, enum iteration, direct construction, token identity assertions, or `carries_rate` use for the affected axes.

### formula-semantic-token | medium | Formula runtime retained a hard-coded income token and broken error name

Resolved. The Art. 24.6 branch now resolves its EU/EEA-resident token from fact 0080, and the unsupported convenio-kind diagnostic references the resolved override.

### resolved-override-predicates | medium | Four-way semantic coverage was incomplete

Resolved during independent review. An owner-level registry test now resolves real governed rows for flat replacement, ceiling, domestic-tariff allocation, and exemption, then asserts every `ResolvedConvenioOverride` predicate together with its rate presence.

## Recommendations

No open lane findings remain. Keep new tests on the public resolver/catalogue surfaces and preserve the final core collection gate so core token identity cannot regain ownership of registry membership.
