---
tags:
  - '#research'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:49173ffde3043dcd810abe721a0b5597f106ad7311a6856990cac5ab52919d6a'
related: []
---

# `unreachable-capability` research: `why unreachable shipped modules exist`

A reachability audit proved that a large block of the `cadrumo` wheel cannot be
reached from any shipped entrypoint. This research answers the next question:
why does each of those modules exist. At the audit snapshot, deletion was
explicitly out of scope. The live follow-up has since applied a deletion
disposition to the producerless SII/VERI*FACTU reader trio; the historical
classification below remains useful for the other findings. The finding that
matters is that almost none of the remaining inventory is abandoned code — 38
of 91 findings are complete capability that was never connected to a surface,
and 16 more are finished work waiting on one navigation decision. Only 10
findings across the whole tree are superseded or displaced.

Ninety-one findings spanning 155 modules were classified individually against
the live source, git history, the open plans, and the registry declarations.
Every module was read; none was judged from its filename.

## Findings

### The audit tool was wrong five ways, and the corrections moved the number

The classification pass doubled as an adversarial test of the audit that
produced it, and three independent analysts found five distinct defects. All
five are fixed in `dev/audit/unreachable_code.py` and covered by tests.

The walk rooted only at the `cadrumo` distribution's `[project.scripts]`. It
missed `__main__.py` module execution, so `python -m cadrumo.entrypoints.tui`
was invisible despite a live subprocess test at
`src/cadrumo/entrypoints/tui/tests/test_module_execution.py:36`. It missed the
sibling workspace distribution entirely: `src/cadrumo-harness/pyproject.toml:37`
declares `cadrumo-mcp`, which reaches `application/command_search`,
`application/corpus_search`, `core/spanish_stemming`, `core/fts_query` and
`core/concept_lifecycle` through the MCP server. It counted empty
`importlib.resources` package markers under `src/cadrumo/_data/` as code.

Correcting these dropped the unreachable count from 155 modules to 115 and
raised reachable coverage to 1945 of 2061 shipped modules. A sixth correction
was added rather than accepting a false clear: rooting the devtools `__main__`
would have laundered dev-only code as product-reachable, so modules reachable
only by `python -m` and never by a console script are now reported separately
as module-exec-only. Twenty-six modules sit in that category.

### The single largest cause is one unmade decision, not decay

Sixteen findings, and the whole `entrypoints/tui` block, share one root cause
recorded in the source itself: `src/cadrumo/entrypoints/tui/app.py:12` states
the root app deliberately mounts no area because no navigation model has been
decided. The profile journey, the secret and credential surfaces, the guided
flows, the Modelo editor and the six Modelo lifecycle actions are all finished
and tested behind that unmounted root.

This is tracked, not forgotten. The open rows are `W06.P13.S73` in the
2026-08-11 TUI architecture plan, which joins all five areas, and `W06.P13.S92`
in the TUI interface plan, which mounts the Modelo area whose C1 to C4 cohort
gates all closed on 2026-08-31. Roughly 5,700 lines of operator capability are
gated on that one decision.

### Thirty-eight findings are capability that works and was never wired

These are the incorporation candidates, and several are one verb away from an
operator. Ranked by value and readiness:

- **Rental property income**, `src/cadrumo/domain/fincas/` with
  `adapters/persistence/profile/fincas.py`. Eleven modules and roughly 1,800
  lines implementing LIRPF art. 23 deductible expenses, amortisation, the
  art. 23.2 reducción tiers and art. 85 imputation, with about 1,400 lines of
  registry-grounded tests. The five `rental_*` tables already exist in every
  profile database through `Base.metadata.create_all` at
  `src/cadrumo/adapters/persistence/storage/sql/engine.py:284`. It is blocked
  deliberately and visibly, not by neglect: `src/cadrumo/_data/source_connectivity/census.toml`
  marks `fincas.annual-aggregates` as `grounding_blocked` pending official
  evidence, due 2026-11-30.
- **AEAT Renta WEB Open cross-check**, the three-module unit of
  `adapters/outbound/aeat/sede/renta_web_open.py`, its safety layer, and
  `domain/calculations/registry/renta_web_open_oracle.py`. The registry already
  declares the wiring: an `application_links` row names that module as a
  `portal` surface consumer for Modelo 100 revision 2025. This is the
  independent oracle the calculation-grounding rule requires, and
  `aeat app live verify` is a ready host.
- **SII and VERI\*FACTU batch ingestion**, `adapters/inbound/einvoice/record_batch.py`
  with its schema derivation and `application/ledger/aeat_record_projection.py`,
  was an incorporation candidate at the audit snapshot. The live follow-up
  retired all three producerless modules because no consumer was ever built.
  The disposition does not remove the classifier: `adapters/inbound/einvoice/shape.py:145`
  still recognises these filing-artifact shapes, and the evidence path refuses
  them before rendered-document fallbacks. The bundled AEAT schemas remain
  available as corpus/reference data.
- **Setup-flow validation and grounding**, the four `application/wizard`
  modules. The most consequential is `flow_validators.py`: nothing calls
  `register_taxpayer_projection_validator`, so cross-field invariants on the
  taxpayer projection are unchecked at review and raw library prose is the
  fallback the module exists to prevent. This absence removes a gate, not a view.
- **Prorrata seeding**, `application/prorrata_register/seed.py`, the canonical
  LIVA art. 105.Uno carried-provisional seed, with its authoring plan closed at
  49 of 49 steps and no caller.

Two smaller ones are near-trivial to close: `verify_csv` in
`adapters/outbound/aeat/verify/` was deliberately relocated out of the domain
and its caller was never re-attached, and
`adapters/outbound/google/calc_sheets_pull_coverage.py` was split out for a size
budget on 2026-08-31 with the call site left behind.

### Only ten findings are genuinely superseded

Six duplicates and three refactor remnants, plus one incomplete scaffold. The
material one is a doubled amendment stack: `domain/filing/amendment.py`,
`adapters/persistence/profile/filing_amendments.py` and
`application/filing/_complementaria.py` implement LGT art. 122 over draft
records, while the live path runs through
`application/modelo/amendment_actions.py` over revision records. Two
implementations of the same article cannot both stand under the no-legacy rule,
so which model is canonical needs adjudication before either is touched.

The rest are small and self-evident. `application/filing/_import.py` names its
own successor in its docstring. `domain/iva/corpus.py` is a name-preserving
forward left by a facade retirement. `application/portals/` duplicates a
projection the live CLI hand-rolls at
`entrypoints/cli/_app_live_portals_cli.py:47`.

### Twenty findings are harness support, and most are correctly placed

Dev tooling may not be imported by `src/cadrumo`, so a fact the product might
ever need must live on the shipped side even when only `dev/` reads it today.
The registry conformance authorities, the filing-export and source-connectivity
authorities, and the coverage and classification folds are all this shape, and
`dev/registry/conformance/manager.py:14` states the rule explicitly. They should
stay. The open question of where that boundary formally sits is already tracked
as `W02.P02.S08` in the registry declaration hardening plan.

Two genuine placement questions did surface. The devtools harness ships inside
the product wheel, and `application/wizard/_translations.py` is a locale gate
that scans the source tree at runtime, which is gate behaviour rather than
product behaviour.

### What was not investigated

Symbol-level findings were out of scope; only module-level findings were
classified. The 1,409 unused symbols inside reachable modules remain
unexamined, and 620 of them are exact-tier. The two placement questions above
were recorded, not answered. Three findings carry low or medium confidence and
name the specific question a reader must settle, most notably
`domain/manuals/rule_id.py`, where whether a manual extraction pipeline still
exists could not be determined.

## Sources

- `dev/audit/unreachable_code.py` — the audit; `just audit-unreachable-code`
- `src/cadrumo/entrypoints/tui/app.py:12` — the unmounted root
- `src/cadrumo/entrypoints/tui/tests/test_module_execution.py:36`
- `src/cadrumo-harness/pyproject.toml:37` — the `cadrumo-mcp` console script
- `src/cadrumo/adapters/persistence/storage/sql/engine.py:284`
- `src/cadrumo/_data/source_connectivity/census.toml` — `fincas.annual-aggregates`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/application_links/0001-modelo-100-renta-web-open-cross-reference.toml:4`
- `src/cadrumo/adapters/inbound/einvoice/shape.py:145`
- `src/cadrumo/entrypoints/cli/_app_live_portals_cli.py:47`
- `src/cadrumo/application/modelo/amendment_actions.py`
- `dev/registry/conformance/manager.py:14` — the src-side layering rule
- `.vault/plan/2026-08-11-tui-architecture-plan.md` — step `W06.P13.S73`
- `.vault/plan/2026-08-11-tui-interface-plan.md` — step `W06.P13.S92`
- `.vault/plan/2026-09-02-registry-declaration-hardening-plan.md` — step `W02.P02.S08`
- `.vault/adr/2026-08-10-casilla-schema-dead-surface-adr.md` — the per-surface
  adjudication precedent this work followed
