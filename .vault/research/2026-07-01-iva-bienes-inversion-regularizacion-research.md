---
tags:
  - "#research"
  - "#iva-bienes-inversion-regularizacion"
date: "2026-07-01"
modified: '2026-07-17'
body_hash: 'sha256:4a4f74e99553d0049b52dad3744acecfa774b467b807efd1a104ee7ef58f3550'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-21-m390-iva-carry-boxes-adr]]"
  - "[[2026-06-03-m303-cross-period-carry-continuity-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
---

# `iva-bienes-inversion-regularizacion` research: `IVA regularizacion de deducciones por bienes de inversion (LIVA arts 107-110)`

Scope: issue #349 (P2). The multi-year capital-goods deduction-regularization mechanism
(LIVA arts. 107-110) is not modelled. Present at HEAD (`debf1b2c1`): the four legal entries
`ley-37-1992:art-107/108/109/110` grounded to bundled consolidated LIVA text
(`src/aeat/_data/registry/aeat/legal/iva.toml:1006-1082`, all reviewed, reviewed_by operator);
a dedicated manual casilla `iva.regularizacion-inversiones`
(`303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml:265`) and the official
form casilla 43 (`...part-002.toml:280`), both `input_kind = manual`, grounded to arts. 107-110.
Missing: the per-good cross-year register, the art-109 annual comparison, the art-110 disposal
case, and the feed into casilla 43 / M390.

## Findings

### F1 - Register data largely exists as `AssetRecord` (income-tax purpose), on the wrong axis for LIVA

`aeat.domain.contribuyente.assets.AssetRecord`
(`src/aeat/domain/contribuyente/assets/__init__.py:95`) already carries `acquisition_date`,
`taxable_base`, `iva_rate`, `iva_amount`, and `deductible_iva_ratio` (`:117`, the fraction of
input IVA the contribuyente may deduct, 0-1) - the initial-year prorrata proxy. It persists
encrypted, bucket-local, `FINANCIAL` sensitivity through `PROFILE_ASSETS_LEDGER_NAMESPACE`
(`src/aeat/adapters/persistence/storage/_namespace_registry.py:306`) via
`src/aeat/adapters/persistence/profile/assets.py`.

Not directly reusable as the LIVA register authority: (a) its `AssetClass` StrEnum
(`__init__.py:39-74`) is the LIS art. 12.1.a amortization-coefficient taxonomy (obra civil,
maquinaria, mobiliario), orthogonal to the LIVA mueble-4yr / inmueble-9yr regularization window
of art. 107; (b) its population (every depreciable affected asset) is a superset of the LIVA
population (only capital goods whose input IVA was deducted under prorrata below 100%, above the
art. 108 concept threshold); (c) it holds a static acquisition record, whereas LIVA needs a
per-year definitive prorrata-percentage series to compare against. It is the right
cross-reference target (avoid double data-entry), not the right authority.

### F2 - Cross-year persistence is proven twice; the register is durable primary state, not a rebuildable cache

Two templates. (a) `AssetRecord` above - durable, authoritative, cross-year primary input. (b)
The IVA-compensation history
`aeat.domain.iva_compensation._carry_forward.IvaCompensationPeriodState`
(`src/aeat/domain/iva_compensation/_carry_forward.py:46`) is one record per filed period,
persisted at `IVA_COMPENSATION_HISTORY_NAMESPACE` (`AUDIT` sensitivity) through
`SecureBoundRepository` (`src/aeat/application/calculations/_iva_compensation_history.py:1`),
with a pure FIFO projection `build_iva_compensation_carry_forward_report`. The register follows
that shape (one record per bien de inversion, plus a per-year prorrata snapshot). Unlike the
participation index (`ledger-participation-index-is-derived-rebuildable`), it is authoritative
primary input the operator declares - NOT rebuildable - so it needs a full save/load/equality
plus anti-tautology roundtrip (`aeat-roundtrip-discipline`).

### F3 - The registry is the wrong home for the per-good facts (regulatory-authority rule)

`aeat-registry-authority-flow` and `aeat-schema-central-config` reserve the registry for
regulatory values compiled from the TOML authoring tree into strict schema. A per-taxpayer list
of owned capital goods and their acquisition-year prorrata percentages is taxpayer data, not
regulatory authority. The regulatory constants the mechanism needs - the 4/9-year windows, the
over-10-point gate, the /5 and /10 divisors - DO belong in the registry (grounded in arts.
107/109); the per-good facts do not. Decision (1) splits cleanly: constants in registry, facts
in a profile-scoped encrypted register.

### F4 - The feed mechanism has an exact precedent: `IVA_COMPENSATION_ANNUAL_PARTITION`

M390 boxes 97/662 are fed by a registry-declared source kind `iva_compensation_annual_partition`
(`src/aeat/core/aggregation.py:268-272`) that reads a profile-scoped cross-year store and
materialises the box via an application projection
(`src/aeat/application/calculations/_iva_compensation_annual_partition.py`), not a per-casilla
relation copy/sum. The regularizacion feed is the same shape: a registry-declared
`bienes_inversion_regularizacion` source reading the register plus the definitiva prorrata for
the year, materialising casilla 43 (M303, annual/4T) and the M390 regularizacion field
(`390/revisions/2010-y-siguientes/casillas/0001-casillas.toml:159`, box 662-adjacent).
Enrollment is governed by `no-dormant-source-resolvers`: a new source kind is enrolled in the
live mesh OR placed in `DEFERRED_SOURCE_KINDS`
(`src/aeat/application/aggregation/_source_mesh.py:128`) with a live advisory - never left to
resolve silently to zero.

### F5 - The automatic feed is BLOCKED on the deferred prorrata-definitiva source; the annual compute is not

`2026-06-19-silent-zero-base-aggregation-adr` (deferred item M303 prorrata volumes) established
that the general prorrata is NOT a per-period volume sum: LIVA art. 104/104bis applies the PRIOR
year definitive percentage provisionally across the quarters and REGULARISES in Q4 against the
current year actual annual volumes. That provisional-percentage-carry plus Q4-regularisation
model (arts. 102-106) is genuine deferred design. The art-109 compute CONSUMES the current-year
definitive prorrata percentage, so a fully-automatic casilla-43 feed inherits that block. The
art-109 annual single-good compute itself does not: given an acquisition-year percentage and a
current-year definitive percentage as inputs, it is a pure, groundable formula. This is the seam
for a bounded first slice - model the register plus the compute now, surface an advisory-backed
proposed value, defer the hard mesh binding until the prorrata-definitiva source lands.

### F6 - Two legal NUMBERS must be re-confirmed against bundled corpus at execution

The art-107 entry `required_text` includes the over-10-point gate clause (Las regularizaciones
solo se practicaran cuando, entre el porcentaje de deduccion definitivo, `iva.toml:1023`) and the
4/9-year window (regularizarse durante los cuatro; nueve anos si son terrenos o edificaciones,
`iva.toml:1019-1022`). The art-109 entry confirms the procedure and the restara del de la
deduccion efectuada step (`iva.toml:1062`). Per
`legal-grounding-verifies-bundled-authoritative-corpus`, the two load-bearing NUMBERS - the
10-percentage-point threshold and the /5 (mueble) and /10 (inmueble) divisors - must be re-read
verbatim from the bundled `corpus/normatives/html/ley-37-1992-art-107.html` and `-art-109.html`
during execution before any figure is compiled; a bundled figure is a strong default, not a
substitute for confirming the number. The entries carry `corpus_ref` to those files
(`iva.toml:1010`, `:1050`).

### F7 - Art-110 disposal is a distinct, separable case

Art. 110 (`iva.toml:1065`, required_text En los casos de entregas de bienes de inversion durante
el periodo de regularizacion se efectuara una regularizacion) governs the transmision case: a
single final regularizacion for the remaining window years, with deduccion for those years
imputed as if the percentage were 100 (entrega sujeta y no exenta, capped at the amount
originally deducted) or 0 (entrega exenta / no sujeta). It shares the register but is a different
compute from the annual in-use path and is cleanly deferrable to a later slice.

### F8 - No peer WIP on the target surfaces

`git log` and `git status` at HEAD show no uncommitted peer work on
`src/aeat/domain/contribuyente/assets/`, the M303 `2023-y-siguientes` casilla files, or the
IVA-compensation modules (only an untracked, unrelated docs stub for
`_iva_compensation_annual_partition`). The `debf1b2c1` grounding fix is the most recent touch on
casilla 43 and is landed, not in-flight.

### Out of scope / not investigated

- The exact prorrata-definitiva computation (arts. 102-106) - deferred design owned by the
  silent-zero-base ADR; this research consumes it as an input, does not design it.
- The M390 FIFO box-97/662 partition (`2026-06-21-m390-iva-carry-boxes-adr`, `proposed`) - a
  sibling annual-IVA surface; the regularizacion field is distinct from the carry boxes.
- Whether art. 108 bienes de escaso valor exclusion carries a specific euro threshold in the
  current consolidation - confirm at execution against the bundled art-108 corpus.
