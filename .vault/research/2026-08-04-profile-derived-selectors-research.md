---
tags:
  - '#research'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e66e5de794ffec26abf5a240637b03680603424c5d2044427c8ad5acd83cf22f'
related:
  - "[[2026-07-25-censal-profile-autofill-adr]]"
  - "[[2026-07-01-modelo-100-minimo-descendientes-engine-adr]]"
---

# `profile-derived-selectors` research: `Year-suffixed profile fields, the derived-value blast radius, and why effective-dating is the wrong instrument`

The TUI profile manager renders roughly 173 editable rows for an empty profile and grows
by three rows per filing year without bound. The operator asked for the structural fix
rather than collapsible presentation. This research establishes what actually grows, why
the obvious remedy (moving the year onto each fact's effective-dating window) is both
wrong for these fields and blocked by two standing rulings, and what the evidence favours
instead.

## Findings

### The growth is 22 fields, and 20 of them are not taxpayer data

`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` bakes a filing year into 22
field keys: three six-packs (`descendientes_minimos_aggregate_{2020..2025}`, the same
`_autonomico_` series, `anualidades_sin_minimo_descendientes_{2020..2025}`) plus
`descendientes_menores_3_2024`, `gastos_guarderia_reales_2024`,
`cotizaciones_ss_madre_2024`, and `filing_export.rental_reduccion_art_23_2_tier_2024`.
The scope is a clean bijection with 22 Modelo 100 binding files across revisions
2020-2025; no other modelo participates, no revision binds a sibling year's selector, and
the pattern occurs nowhere else in the tree. Surrounding surfaces: 4 production Python
files, 18 test files (8 carrying an identical four-line seeding block), 4 locale
catalogues at 22 keys each.

Twenty of the 22 are derived. They are injected at calculate time from real
`renta_family.descendiente.{n}.*` facts plus registry Art. 58/61/64 parameters
(`src/cadrumo/application/modelo/_profile_binding.py:806,809`), and
`2026-07-01-modelo-100-minimo-descendientes-engine-adr` records the selector as "a
dangling selector scaffolded ahead of the engine". Only `cotizaciones_ss_madre_2024`
(external payroll data) and `rental_reduccion_art_23_2_tier_2024` (contract
circumstances) are genuine operator input.

### A derived value rendered as an editable row silently overrides the law

`build_profile_overview` (`src/cadrumo/application/user_profile/_overview.py:531`) walks
the SCHEMA, so every declared non-namespace field becomes an editable row. The injectors
deliberately do not overwrite a present key (`_profile_binding.py:206,388,405,413,464`),
and `_profile_fact_index` (`:114-142`) indexes every stored fact unconditionally,
independent of schema declaration. An operator-stored value therefore reaches the index
at `:804` and suppresses the Art. 58 computation at `:809` with no diagnostic.

The consequence cuts both ways and the ADR must weigh both: it is an unaudited channel
that can silently defeat the engine, and it is simultaneously the only way a filer
currently corrects the eligibility defects recorded in
`2026-08-04-minimo-descendientes-eligibility-research`.

### Effective-dating is the wrong instrument, and is blocked twice over

The temporal axis these values need is already carried authoritatively twice — the
registry revision windows carry the law's time axis, the source facts carry the
taxpayer's. A stored window on the derived output would be a third, driftable authority.
It would also leave the value stored and writable, so the override channel survives.

Independently, the mechanism is not wired on the consuming path. Four fact-index builders
disagree: `_profile_fact_index` (`_profile_binding.py:114`) and `facts_to_values`
(`src/cadrumo/application/user_profile/_projections.py:73`) take raw declaration order,
last wins; only `record_to_path_values` (`:174`) and `record_to_effective_facts` (`:217`)
honour `_in_window_order`. A live probe with two facts at one path returned the older
window from the binding resolver and the later one from the projection. The binding
resolver — the exact consumer such a design would rely on — implements no window
ordering.

The caller cost is asymmetric and worth recording precisely. The calculation path is
cheap: the filing year is already in scope at every hop above the lookup, all four
production callers of `resolve_profile_sourced_bindings` hold it, and the instant has an
in-tree precedent (`_profile_binding.py:317`). The projection path is not: 50 direct call
sites across 36 files, exactly one already holding an instant
(`src/cadrumo/application/user_profile/_preflight.py:76`), around 35 with no meaningful
filing instant, and at least three ill-defined — the CLI calendar carries a range not an
instant, portable-bundle import has no filing context, and
`src/cadrumo/application/filing/_review.py:718` fingerprints the projection into a
staleness digest documented as reproducible from `bucket_id` alone. Auth and
output-language would be actively wrong to effective-date.

Two standing rulings govern. `2026-07-25-censal-profile-autofill-plan` step `P03.S31`
ruled that projections do not honour `valid_to`, shipping the
`effective_window_end_not_enforced` warning
(`src/cadrumo/application/user_profile/_validation.py:230-266`) and a test that blesses
it. `2026-05-07-user-profile-backend-schema-adr` ruled that filing reads come from an
immutable snapshot; that pipeline is entirely dormant (`UserProfileSnapshot.from_profile`
and `ProfileSnapshotRequest` have zero production callers) and freezes raw facts rather
than resolved values, so it would not discharge the question even if implemented.

### A partial rollout of windows fails silently

`_in_window_order` sorts an absent `valid_from` as `date.min`
(`_projections.py:30-36,168`). Once any dated fact exists at a path, an undated write
from any of the 13 unmigrated write doors persists without error and never resolves as
effective again. This makes incremental adoption of windows unsafe in a way that does not
announce itself, and is a further argument against reaching for them here.

### The refusal boundary already exists, and it is not where a symbol search would look

`profile_value_refusal` (`src/cadrumo/domain/user_profile/_schema.py:474-510`) is the
declared authority on whether a value may be stored at a field, and its docstring names
two-surface divergence as the failure it exists to prevent. It is nonetheless
VALUE-scoped against a `ProfileFieldDefinition`, and expressly declines to judge absence.
A derived-path rule is PATH-scoped, refuses every value including a clear, and — once the
declarations are deleted — has no `ProfileFieldDefinition` to be asked with.

The codebase already splits that axis: `unknown_field`, the other path-legitimacy
judgment, lives in `ProfileValidationService._validate_one_fact`
(`src/cadrumo/application/user_profile/_validation.py:158-165`) via a `_field_index`
lookup, not in `profile_value_refusal`. Two consumers of `ProfileValueRefusalKind` branch
exhaustively with deliberate no-fallback arms (`_validation.py:78-87`, pinned by test;
`src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:160-169`), so extending that
enum carries reconciliation cost a sibling placement avoids.

### A dormant second as-of channel is already declared

`_ProfileSelector.valid_at`
(`src/cadrumo/domain/calculations/registry/_bindings.py:762`) is declared, populated in
two shipped binding TOMLs, read by zero production code, and asserted by one test
(`src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py:290-294`). Any
design introducing a temporal mechanism on this surface must adopt or retire it rather
than leave a second unread axis beside a new one.

### Option space

Three shapes were weighed. Presentation-only grouping was rejected by the operator and
leaves the override channel open. Effective-dating is addressed above. The remaining
shape declares the derived paths as data — a year-parameterised pattern namespace in the
profile schema, with the injectors owning the computation — which removes the rows
structurally, closes the override channel at a write boundary rather than in the TUI, and
reduces a new filing year to registry work alone. The evidence favours it. The ADR must
settle where the pattern namespace is declared, where the refusal lands relative to the
existing authorities, what becomes of the two genuine operator fields, and the ordering
constraint against the eligibility campaign.

### Not investigated

The per-binding silent-skip class (a live probe selected 16 profile bindings on a thin
profile; 8 resolved to `None` with zero diagnostics, and
`collect_unhandled_source_diagnostics` cannot catch it because `profile` is an enrolled
source kind) is recorded but not costed. The `meses_madre_trabajo_2024` Python attribute,
whose persisted key is already year-less, is a naming companion rather than a schema
concern. `filing_export.declaration_type` is a free-form string where a closed value set
is expected; noted, not pursued.

## Sources

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` — the 22 year-suffixed declarations
- `src/cadrumo/application/modelo/_profile_binding.py:114-142,206,317,388,405,413,464,804-809` — fact index and injectors
- `src/cadrumo/application/user_profile/_projections.py:30-36,73,168,174,217` — the four fact-index builders
- `src/cadrumo/application/user_profile/_overview.py:531` — schema-driven row walk
- `src/cadrumo/application/user_profile/_validation.py:78-87,158-165,230-266` — issue-code map, `unknown_field`, expiry warning
- `src/cadrumo/application/user_profile/_preflight.py:76` — the one caller already holding an instant
- `src/cadrumo/application/filing/_review.py:718` — projection staleness fingerprint
- `src/cadrumo/domain/user_profile/_schema.py:474-510` — `profile_value_refusal`
- `src/cadrumo/domain/calculations/registry/_bindings.py:762` — dormant `valid_at`
- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:160-169` — exhaustive refusal-kind match
