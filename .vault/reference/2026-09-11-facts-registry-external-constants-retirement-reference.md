---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:0f11bfc667e5db20f81ce53750835fab5204b1e5624a45d095e09c9f5d37570b'
related: []
---
# `facts-registry` reference: external constants retirement

This audit examined `src/cadrumo/core/external_constants.py`, the statutory fact fragments in `src/cadrumo/_data/registry/aeat/facts`, the retirement ledger, and the focused retirement gate after checkpoint `6915716bb6`.

## Summary

The statutory Python fact adapter is retired: `dev/registry/compiler/statutory_constants.py` has no live file or registration, and the legally grounded scalar and mapping declarations resolve from authored fact fragments. No production caller directly imports a remaining legal scalar or mapping declaration from `external_constants.py`; the existing fact-context boundaries resolve typed facts with explicit effective dates and preserve provenance.

`external_constants.py` must not be removed as a module. It remains the typed owner of unrelated operational configuration, encodings, MIME types, remote surface values, and output-language configuration. The retirement target is only the residual legal duplicate declarations and obsolete model-routing aliases.

Two live imports still prevent that bounded deletion. `RETENCIONES_MODELOS` is a CLI aggregation-routing choice in `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`; it belongs behind a public aggregation/provider-classification API. `IVA_REGIME_MODELOS` is a calendar-coverage gate in `src/cadrumo/application/overview/calendar_warnings.py`; it must derive from the registry applicability or calendar-policy owner. Neither is a legal scalar or mapping fact and neither may be fabricated as one merely to complete the deletion.

`COUNTERPART_MODELOS` and `FOREIGN_ASSET_MODELOS` have no live production consumers and are deletion-ready with the legally migrated declarations.

The focused census gate `dev/registry/tests/test_facts_external_constants_retirement.py` is stale, rather than evidence of missing legal migration. Its ledger count, consumer inventory, and technical-preservation inventory disagree with current source after the derived annual-cap removal. Rebuild the ledger and its assertions atomically with the two routing migrations and source deletion; do not weaken the census gate.

Reusable resolution patterns are `src/cadrumo/domain/contribuyente/family_fact_context.py` for closed fact-id/date-axis mappings and strict payload typing, `src/cadrumo/domain/modelos/modelo_fact_context.py` for composition-boundary context injection, `src/cadrumo/domain/transactions/retencion_facts.py` for domain facade resolution with legal-reference checks, and `src/cadrumo/application/modelo/_objective_estimation_advisory.py` for application findings that forward fact provenance.
