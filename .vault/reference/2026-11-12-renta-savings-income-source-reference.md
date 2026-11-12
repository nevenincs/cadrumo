---
tags:
  - '#reference'
  - '#renta-savings-income-source'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:ee037978469313d2b774daeab1c68322ade73365ae071317428cf29995e1cb47'
related:
  - "[[2026-11-11-renta-savings-income-source-adr]]"
---
# `renta-savings-income-source` reference: `Savings income source code evidence`

Code evidence for `2026-11-11-renta-savings-income-source-adr`, read statically from `lane/calculators` at `c4221a6cdf` (tui `fdd90555bc`). The ADR's first unit (the blocking finding and the prior-carry door) is present; the source family, position record and ledger link are not.

## Summary

### Patterns

- Casillas 0027 and 0029 are manual. No binding targets them; only the 2020 totals consume them (0036 sums 0027 to 0035, then 0038, 0040, 0041): `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/formulas/0001-declarations.toml:623-733`.
- The withholding credit already has a source: binding `renta-retencion-soportada-capital-mobiliario` reads the payer record of class `capital_mobiliario` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:216-217`), resolved by `src/cadrumo/application/aggregation/retencion_soportada_source.py:238`. Payer classes: `src/cadrumo/core/retencion_soportada.py:36,45`.
- The ledger taxonomy carries `capital_mobiliario` (incoming, purpose `capital_mobiliario_yield`) and `ganancias_patrimoniales` (both directions, purpose `capital_gain`): `src/cadrumo/_data/registry/aeat/facts/0081-irpf-ledger-category-taxonomy.toml:20,33-40`; loader `src/cadrumo/domain/transactions/irpf_categories.py:56-163`.
- The blocking finding: fact `src/cadrumo/_data/registry/aeat/facts/0186-irpf-income-family-calculator-coverage.toml:44-47` marks both families not computed; lookup `src/cadrumo/domain/calculations/registry/irpf_income_categories.py:156`; diagnostics fire on family ledger rows or a profile declaration (`src/cadrumo/application/aggregation/income_family_not_computed.py:101-135`); manual clearing is bound to a per-family row-id digest that re-raises on change (lines 57-98, 134; entry helpers 138-171); reason token `src/cadrumo/application/aggregation/source_diagnostic_reason.py:373`; caller `src/cadrumo/application/aggregation/modelo_bindings.py:347`.
- Negative balance carries are closed vocabulary: `PRIOR_CARRY_FAMILIES` in `src/cadrumo/domain/calculations/registry/binding_absence_attestation.py:31-60`. Eight 2022 `previous_filing` bindings at offset -1 read 1263, 1266, 1269, 1270 and 1276, 1279, 1282, 1283 (`revisions/2022/bindings/0001-declarations.toml:1128-1230`); art. 49 remainders are `max(0, opening - applied)` (`revisions/2022/formulas/0001-declarations.toml:1492-1496`).
- The attestation door accepts only those families: `src/cadrumo/application/modelo/carry_family_selection.py:105-173`, `src/cadrumo/application/modelo/carry_amount_statement.py:105,131`, open-carry preflight findings `src/cadrumo/application/modelo/edit_preflight.py:213-299`; persona coverage `src/cadrumo/entrypoints/tests/test_persona_prior_carries.py`.
- The concept vocabulary (intereses to RegistroB11, dividendos and deposit administration expense to RegistroB13) is authored as fact 0187 in the lane worktree but held uncommitted until a production reader exists.

### Legal sources

- Registry legal keys in `src/cadrumo/_data/registry/aeat/legal/irpf.toml`: LIRPF arts. 14, 25, 26, 48, 49, 50, 101 and RIRPF arts. 14 and 96.
- Bundled texts under `src/cadrumo/_data/corpus/normatives/html/`: `ley-35-2006-art-48.html.extracted.md`, `ley-35-2006-art-49.html.extracted.md`, `ley-35-2006.html.extracted.md`, `rd-439-2007.html.extracted.md`.
- Designs and manuals: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/` and `src/cadrumo/_data/corpus/manuals/renta/`.

### Gaps against the ADR

- No savings-income source family or `BindingSourceKind` member; 0027, 0029, the RegistroB11/B13 rows and expenses are unbound.
- No `inversiones.posicion` profile field, no `posicion_ref` on transactions, no classify door for position and concept.
- No reader of the concept vocabulary; no per-payer gross reconciliation, governed savings withholding rate fact, multi-occurrence payer refusal, payer-without-ledger finding or occurrence-count export refusal.
- The non-blocking limitation for 0039, 0043, 0044 and separate per-item not-computed findings are absent; one blocking finding covers each family.
- Current-year art. 49 compensation is outside this slice; only carries and remainders exist.
