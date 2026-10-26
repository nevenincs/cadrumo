---
tags:
  - '#reference'
  - '#cross-period-seeding'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:cbc11f914527f701570fb070f071fb1444e2d7d7cf010cb025f80e45103b69a9'
related: []
---

# `cross-period-seeding` reference: `Cross-period seeding test ownership`

The code search and the accepted cross-period clean-state decision were used to
separate registry reasoning from real persistence setup.  The registry test
support already owns the published tree and grounded observations, while the
profile adapter tests own encrypted repository construction and external-filing
seeding.

## Summary

The former root test helper mixed seventeen first-party imports: core values,
registry/domain calculations, application lifecycle/import actions, and profile
persistence adapters.  The root `cadrumo.tests` lane is intentionally core-only,
so a domain-aware or adapter-backed seeder cannot remain there.

`resolved_revision`, `cross_period_source_groups`, and
`source_casilla_values` are pure registry/domain fixture calculations and now
live in the registry test package beside the published-tree and grounded-
observation helpers.  `seed_clean_cross_period_sources` is a real encrypted
profile integration fixture: it belongs with profile persistence tests and
continues to call the application workflow doors while binding concrete
repositories there.  Its fixed timestamp and seeded external identity stay
with that persistence scenario.  Consumers name those defining modules
directly; no package initializer, alias, forwarding module, or facade is
introduced.

The cross-period clean-state ADR requires complete upstream filings, local
observations, and official evidence rather than fabricated values.  The moved
seeder preserves that behavior by creating sources through the external import
action and then persisting registry-grounded observations.
