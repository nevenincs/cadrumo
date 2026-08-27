---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:001e8bd9783d53746fd3bc5e64ff24666348cae7d4f23c9043b630018d38e611'
step_id: 'S302'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Establish whether the modelo 347 declarado provincia and pais field is correctly modelled before giving it a per-row source: the diseño declares positions 77 to 80 as a compound field whose first half is a numeric Spanish province code and whose second half is a two-letter alphabetic country code for non-establishment non-residents, while the export field declares one four-character value with a digit-string policy that cannot render letters at all, so the alphabetic half is unrepresentable as declared; determine whether the field needs splitting or its policy widening, then source the country half from the counterparty country the observation already carries and record the province half as an absent domain fact, and prove a multi-counterparty declaration renders each counterparty's own value rather than the first one's

## Scope

- `the modelo 347 declarado export field declaration and its value policy in both revisions`
- `the contraparte row bindings`
- `and a multi-counterparty country-code export parity test`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/export/0002-record-m347-declarado.toml` -- split f009 into f009a (provincia, offset 77 length 2, scalar casilla, absent domain fact) and f009b (pais, offset 79 length 2, `kind = 'binding'`); added `row_field_casilla_ids.country_code`
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/export/0002-record-m347-declarado.toml` -- same split
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/casillas/cdecl.ejercicio__ccontraparte.pais-codigo.toml` -- new `contraparte.provincia-codigo` casilla (manual, unbound); `contraparte.pais-codigo`'s `export_refs` repointed to f009b
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/casillas/cdecl.ejercicio__ccontraparte.pais-codigo.toml` -- same
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/{2011-2024,2025-y-siguientes}/bindings/0002-contraparte-clave.toml` -- new `modelo-347-contraparte-row-pais-codigo` binding, `row_field = "country_code"`, sourced from `InvoiceObservation.country_code` (already carried, no domain-model change needed)
- `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/{2011-2024,2025-y-siguientes}/constructs/0001-informative.toml` -- `rd-1065-2007:art-33` added to construct legal_refs; `contraparte.provincia-codigo` enrolled in `casilla_ids`
- `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py` -- `_observation` gained `country_code` param; `test_conditional_money_fields_stay_scalar_and_are_not_fabricated` updated (`country_code` now bound, `provincia-codigo` confirmed still conditional); new `test_each_counterparty_renders_its_own_country_not_the_first_ones`
- `verify:` `uv run --no-sync python -c "from cadrumo.domain.calculations.registry.authority import bundled_authority; bundled_authority()"` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -m unit -k "347 or invoice or binding_selector or counterpart or clave or contraparte or m349 or legal_grounding or source_kind or taxonomy" src/cadrumo/application/invoices/tests/test_source_resolver.py src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py` -> `pass` (298 passed)

## Notes

Determination (per this Step's own text): SPLIT, not policy-widen -- `contraparte.pais-codigo`'s casilla was already correctly scoped (`data_type = "country_code"`); the export field's single 4-character `digit-string` span was the defect, conflating a numeric provincia half with an alphabetic pais half. Provincia has no source anywhere in `Invoice`/`InvoiceObservation` and is declared an absent domain fact, matching the record's other conditional gaps, rather than a fabricated lookup.

Built together with S304 (the residency-gate removal) in one change, per the ADR's Considered options: the gate makes `pais-codigo` unbuildable, and `pais-codigo` incompleteness makes the gate unsafe to open alone.
