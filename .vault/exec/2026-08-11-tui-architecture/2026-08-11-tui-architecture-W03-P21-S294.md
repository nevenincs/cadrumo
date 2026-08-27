---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:de5e87727fe55d4dde5d72a072232371705dbeb374b965e662c11a340201d2ab'
step_id: 'S294'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the modelo 347 contraparte record truncating a multi-counterparty declaration to a single counterparty, which needs a per-row binding family built rather than rewired: its export record carries manual scalar casilla fields with no repeat marker, and unlike modelo 184 no resolver produces row-indexed contraparte values at all, the row type being consumed only by threshold validation; build the per-row binding family and resolver on the pattern the 349 operador rows already establish, wire the export record onto it, and prove a real multi-counterparty declaration emits one occurrence per counterparty

## Scope

- `the modelo 347 contraparte bindings and export record`
- `a new per-row contraparte resolver enrolled in the calculate mesh`
- `and a real multi-counterparty M347 export parity test`

## Changes

- `A` `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml` -- grounded RD 1065/2007 arts. 33 and 34
- `A` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml`
- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py` -- `operation_clave` field, `m347_operation_clave`, `contraparte_clave` grouping, `_build_contraparte_clave_rows`, grouping-scoped cohort/observation-source union
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py` -- parameterized `operation_clave_validator`, `M347_OPERATION_CLAVES`/`M349_OPERATION_CLAVES`
- `M` `src/cadrumo/domain/modelos/_row_models.py` -- narrowed `_M347_CLAVE_OPERACION` to `Literal["A".."G"]`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_m347_operation_clave.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_contraparte_clave_row_grouping.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_m349_rows_unaffected_by_contraparte_clave_extension.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_modelo_347_contraparte_clave_bindings.py`
- `M` `src/cadrumo/core/corpus_text.py` -- resolves an anchor verbatim before canonicalising (fixes a pre-existing 114-collision corpus-wide defect this Step's grounding surfaced)
- `M` `src/cadrumo/core/aggregation.py` -- new `BindingSourceKind.M347_THIRD_PARTY_OPERATION`, grounded on RD 1065/2007 art. 33.1; added to `INVOICE_BINDING_SOURCE_KINDS`
- `M` `src/cadrumo/application/aggregation/_source_mesh.py` -- new member added to the `deterministic_lock` precedence tier
- `M` `src/cadrumo/application/invoices/_source_resolver.py` -- new member added to `_OWNED_SOURCES`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py` -- new member registered in both selector-model and validator dispatch tables
- `M` `src/cadrumo/application/modelo/_data_inventory.py` -- new member added to `_LIVE_OBSERVATION_SOURCE_KINDS`
- `M` `src/cadrumo/application/state_projection.py` -- new member added to the readiness locale-key and operator-action projections (new locale key `cli.app.modelo.bindings.readiness.operacion_tercero`)
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/bindings/0001-counterpart-summary.toml` -- retargeted `source` to `m347_third_party_operation`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0001-counterpart-summary.toml` -- retargeted `source`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/bindings/0002-contraparte-clave.toml` -- retargeted `source`
- `M` locale catalogues (es/en/ca/hu): `docs.casilla.binding_source.m347_third_party_operation`, `flows.modelo_review.filter.option.binding_source.m347_third_party_operation`, `cli.app.modelo.bindings.readiness.operacion_tercero`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`, `test_invoice_measure_classification.py`, `test_modelo_347_registry_bindings.py`, `src/cadrumo/application/aggregation/tests/test_precedence_ladder_conformance.py`, `src/cadrumo/application/invoices/tests/test_source_resolver.py` -- updated to the honest source declaration
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass` (registry loads clean)
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy" src/cadrumo/application/aggregation/tests/test_precedence_ladder_conformance.py` -> `pass` (251 passed)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/entrypoints/cli/tests/test_modelo_readiness_action_projection.py` -> `pass` (36 passed)
- `verify:` `grep -rn 'm347_third_party_operation' src/cadrumo/_data/registry` -> 8 bindings declare it (all six the finding named, plus the two pre-existing 2011-2024 declarante-summary bindings retargeted in the same sweep)

## Notes

**Step is NOT complete; do not check it.** Delivered a working, tested,
corpus-grounded slice of the per-row binding family (nif/nombre/clave/
importe for claves A and B on the `2025-y-siguientes` revision, sharing one
row sequence across both invoice directions), but the plan row's own scope
also names the export record repoint and a real multi-counterparty EXPORT
parity test, neither of which is built. `m347-declarado`'s export record
still carries scalar `kind = 'casilla'` fields with no `repeat` marker, so
nothing consumes these bindings into a fichero yet -- the truncation the
Step exists to stop is not yet stopped, only the resolver-side capability to
stop it is now real and tested.

Explicitly deferred, stated rather than silently dropped:
- Claves C-G: each needs a fact `m347_operation_clave` cannot classify from
  `source_kind` alone (filer type, cobro-por-cuenta-de-terceros nature, or a
  mediación-de-agencia-de-viajes flag under RD 1619/2012, per the CLAVE
  classification table in the reference doc).
- The quarterly transmisiones representation gap (its own audit document,
  `2026-08-26-tui-architecture-modelo-347-contraparte-quarterly-transmisiones-representation-gap-audit`),
  now grounded against RD 1065/2007 art. 34.1.i) but not resolved.
- The 2011-2024 revision (needs the same buildout; both revisions carry
  only the thin declarant-summary placeholder today).
- The export layout repoint and its parity test.
- ~~A source-declaration auditability gap...~~ RESOLVED: both the
  pre-existing declarante-summary bindings (both revisions) and the new
  contraparte-clave bindings now declare the honest combined-direction
  `BindingSourceKind.M347_THIRD_PARTY_OPERATION`, grounded in RD 1065/2007
  art. 33.1's undifferentiated "operaciones" concept. Two-bindings-per-field
  was investigated and found non-viable: each casilla binds to exactly one
  `BindingId` in the export layout, so a competing pair would need either an
  arbitrary export-layer pick or a merge concept the registry does not have.
  Enrolled through every consumer surface a grep found: the LOCK precedence
  tier, `_OWNED_SOURCES`, both bindings-dispatch tables, the data-inventory
  live-observation classification, and the readiness locale-key/operator-
  action projections (new locale key, all four languages). A grep for the
  new source kind now finds every one of the six named bindings (plus the
  two 2011-2024 bindings retargeted in the same sweep) -- the auditability
  property the change exists for.

Structural grounding for the cohort/union fix, restated per instruction: the
diseño de registro's only sequence split is REGISTRO DE DECLARADO versus
REGISTRO DE INMUEBLE -- two different record layouts sharing the type-2
marker, disambiguated by their own discriminator field. CLAVE OPERACIÓN at
position 82 is a single-value field WITHIN one declarado record, not a
record-type discriminator, so a counterparty with both an adquisición and an
entrega necessarily emits TWO declarado records (one per clave, since one
record cannot carry two clave values), and both are the SAME record type in
the SAME physical stream. There is no warrant in the diseño for two
independent row-index sequences by invoice direction; RD 1065/2007 art.
33.1's "se computarán de forma separada las entregas y las adquisiciones"
governs separate THRESHOLD ACCOUNTING per direction, a different axis from
the physical record stream.

M349 invisibility proven directly, not assumed: `test_m349_rows_unaffected_
by_contraparte_clave_extension.py` pins the exact row output of the real,
unmodified `2020-y-siguientes` operador-adquisicion bindings and a refusal
case through the production `validate_invoice_binding_definition` entry
point, both before and after the cohort-key and observation-source changes.

A pre-existing, corpus-wide defect was found and fixed along the way (not
this Step's own scope, landed by a peer once reported): 21 hyphenated
anchors in the RD 1065/2007 sidecar and 114 colliding anchor keys across 12
bundled sidecars could not be cited at all, because anchor canonicalisation
stripped hyphens and collided distinct articles (e.g. `#a3-3` and `#a33`).
Found while grounding arts. 33/34; reported rather than worked around;
fixed in `core/corpus_text.py` by trying a verbatim anchor match before the
canonical one.
