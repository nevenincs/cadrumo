---
tags:
  - '#adr'
  - '#prorrata-sectores-diferenciados'
date: '2026-07-07'
modified: '2026-07-17'
related:
  - "[[2026-07-05-cross-period-prorrata-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - '[[2026-07-10-prorrata-sectores-diferenciados-research]]'
---

# `prorrata-sectores-diferenciados` adr: `Sectores diferenciados de actividad (LIVA arts 9.1.c/101): sector assignment, per-sector register orchestration and provisional/definitive lifecycle` | (**status:** `accepted`)

## Problem Statement

LIVA art. 101 (bundled `ley-37-1992.html`, `#a101`) requires a taxpayer who carries on
economic activities in **differentiated sectors** to apply the deduction regime
**separately** for each sector (art. 101.Uno). The sectors themselves are defined by
art. 9.1.c (letras a', b', c', d'): distinct CNAE groups whose general prorrata
percentages differ by more than 50 percentage points (letra a'), plus the
special-regime activities (simplificado, agricultura/ganadería/pesca, oro de inversión,
recargo de equivalencia — letra b'), and the art. 20.Uno.18 and arrendamiento-financiero
sectors (letras c', d'). Common-use inputs across sectors are apportioned by the
art. 104, apartados dos y siguientes common percentage (art. 101.Uno último párrafo).

At HEAD the substrate carries the sectoral primitives — `requires_sectoral_separation`
(the >50pp spread test, `PRORRATA_SECTORAL_SEPARATION_SPREAD_PP = Decimal("50")`),
`ProrrataSector`, `compute_sectoral_prorrata` — and the register keys every entry on
`(ejercicio, sector_id)` with `sector_id` present from birth
(`ProrrataRegisterEntry.sector_id`, "present from birth so sectores land without
migration; the per-sector compute is deferred"). What does not exist: any CNAE/IAE
sector *classification* (callers are told to assign the codes), and any per-sector
register *orchestration* — the landed cross-period mechanism runs whole-entity only
(`sector_id = None`). The parent `cross-period-prorrata` ADR named the deferral:
"sectores diferenciados (art. 9.1.c / 101) per-sector registers beyond the schema slot."

## Considerations

- The art. 9.1.c "sectores diferenciados" test is a **legal judgment** — which CNAE
  groups a taxpayer runs, whether their prorrata percentages diverge by >50pp, and
  whether a special-regime activity is present. It cannot be reliably auto-detected from
  ledger turnover alone; a wrong auto-partition ships a wrong regulated deduction for
  every affected input.
- The register is already sector-keyed, so per-sector orchestration is an *extension*
  over the landed cross-period lifecycle (seed → in-year apportion → 4T regularización),
  run once per `sector_id`, not a new mechanism (`composition-service-no-parallel-write-path`).
- Each ledger input must resolve to *its* sector so the aggregation applies that
  sector's percentage; a common-use input (usable across sectors) resolves to the
  art. 104.Dos common percentage. This is the same routing shape as
  `prorrata-especial`'s per-input classification, one axis deeper (which sector, then
  which use).
- Art. 101.Dos permits an AEAT-**authorised** common deduction regime across the
  art. 9.1.c-letra-a' sectors, void in any year the common-regime deductible total
  exceeds by >20% the sum of the independent regimes. This is an authorisation fact
  (register `authorisation_reference`), and modelling the AEAT authorisation + the +20%
  void test is a distinct slice.
- The register regime enum (`ProrrataRegisterRegime`) is whole-entity today; a sectored
  taxpayer can run general in one sector and especial in another, so regime is naturally
  a per-`sector_id` entry property (which the current keying already supports).

## Considered options

**D1 — How taxpayer sectors are identified and assigned.**

- **Operator-declared sector partition, grounded in the art. 9.1.c letra taxonomy
  (CHOSEN).** The taxpayer declares each differentiated sector (an id, its member
  activity codes, and the art. 9.1.c letra that makes it differentiated) through a
  sector-definition surface on the register. The taxpayer profile MAY carry the
  underlying activity/IAE codes (mirroring the region-Renta `irpf_income_categories`
  precedent), but the *partition* into differentiated sectors is the operator's
  art. 9.1.c judgment. Fail-closed: absent a sector declaration, the register stays
  whole-entity (today's behaviour) — never a silently inferred partition.
- (b) Auto-detect sectors from ledger CNAE activity + the >50pp spread test (REJECTED).
  The spread test is *circular* at declaration time (it needs the very percentages the
  sectors produce), and CNAE membership plus special-regime presence is a judgment the
  ledger cannot carry. Auto-partitioning ships wrong regulated deductions silently.
- (c) A single profile-level activity code as the sector (REJECTED). A taxpayer runs
  multiple activities that group into differentiated sectors in a many-to-one way; one
  profile code cannot represent the partition.

**D2 — How per-sector register entries are orchestrated.**

- **Per-`sector_id` lifecycle over the existing keyed register (CHOSEN).** The register
  already keys `(ejercicio, sector_id)`; the aggregation resolves a provisional
  percentage per sector, routes each ledger input to its sector's percentage (common-use
  inputs → the art. 104.Dos common percentage), and runs the 4T regularización per
  sector. The whole-entity path (`sector_id = None`) is unchanged for non-sectored
  taxpayers.
- A separate per-sector register store (REJECTED) — the sector axis already exists on
  the one register; a second store duplicates the seeding/roundtrip discipline.

**D3 — The per-sector provisional/definitive lifecycle and the art. 101.Dos common
regime.**

- **Each sector runs the full art. 105 lifecycle independently; art. 101.Dos common
  regime deferred (CHOSEN).** Each `sector_id` seeds its provisional from *its own*
  prior-year sector definitive, apportions in-year, and regularises at 4T — the
  cross-period mechanism applied per sector. The art. 101.Dos AEAT-authorised common
  regime (and its +20% void test) is recorded as an `authorisation_reference` case and
  deferred, the register already shaped to admit it.
- Bundle the art. 101.Dos common regime now (REJECTED) — it needs AEAT-authorisation
  modelling and the +20% comparison, enlarging the slice without de-risking the core
  per-sector routing.

## Constraints

- Parent stability: the sectoral compute substrate (`2026-05-12` ADR) and the
  cross-period register (`sector_id` from birth) are stable and consumed, not re-opened;
  this ADR builds per-sector orchestration on the existing keyed schema
  (`no-legacy-compatibility` — no migration, the axis already exists).
- No fabricated partition: a sector partition exists only when operator-declared; the
  fail-closed default is the whole-entity register (`no-silent-under-declaration`).
- Legal grounding: art. 101 and art. 9 are present verbatim in the bundled LIVA
  (`#a101` / `#a9`); art. 9 is already a `legal/iva-flow.toml` entry (autoconsumo 9.1.c
  focus) — the implementation MUST author/extend the art. 101 entry and the art. 9.1.c
  sector-definition grounding with a `corpus_ref` + `required_text` cross-check
  (`registry-calculation-legal-grounding`).
- Secure storage: sector definitions and per-sector register entries are taxpayer facts
  persisting only through the encrypted bucket-scoped substrate
  (`sensitive-financial-data-secure-storage-only`, `aeat-roundtrip-discipline`).
- One aggregation path: per-sector apportionment resolves through the same shared
  resolver set as general/especial, with a parity regression
  (`one-aggregation-path-pull-equals-calculate`).
- Verification: per-sector percentages and the common-use split are proven against an
  AEAT worked example with two differentiated sectors, never hand-computed
  (`no-tautological-calculation-tests`, `verification-grounding-needs-oracle-evidence`).
- Spanish stems: `sector diferenciado`, `sectorizada` (`aeat-spanish-stem-naming`).

## Implementation

A sector-definition surface (operator-declared: sector id, member activity codes, the
art. 9.1.c letra) is added over the register; the taxpayer profile optionally carries the
underlying activity codes. Each ledger input resolves to its `sector_id` (or common-use);
the shared ledger IVA aggregation, already regime-aware after `prorrata-especial`, becomes
sector-aware: it resolves the provisional percentage per sector from the sector-keyed
register and applies each input's sector percentage (common-use → the art. 104.Dos common
percentage). Seeding, in-year apportionment, and 4T regularización run per `sector_id`
over the existing cross-period mechanism. The art. 101 legal entry and the art. 9.1.c
sector-definition grounding are authored into the registry from the bundled corpus. The
art. 101.Dos AEAT-authorised common regime and its +20% void test are recorded as an
authorisation case and deferred with the schema unchanged.

## Rationale

The register was built sector-keyed from birth precisely so this slice needs no
migration; the work is per-sector orchestration and the sector-assignment signal, not new
storage. Operator-declared partition (D1a) is forced by the art. 9.1.c test being a legal
judgment the ledger cannot infer without circularity, and fail-closed-to-whole-entity
keeps a non-sectored taxpayer byte-identical. Running each sector through the landed
cross-period lifecycle (D2/D3) reuses the seeding + regularización discipline verbatim and
keeps the single aggregation path. Deferring art. 101.Dos mirrors the parent and scope
ADRs' bounded-first-slice posture: it needs AEAT-authorisation modelling that does not
de-risk the core per-sector routing.

## Consequences

- Gain: a taxpayer with differentiated sectors deducts each sector's inputs at that
  sector's lawful percentage and apportions common-use inputs correctly, instead of one
  whole-entity percentage across unrelated activities.
- Gain: reuses the sector-keyed register and cross-period lifecycle with no migration.
- Cost accepted: sector partition is operator-declared; art. 101.Dos common regime is
  deferred.
- Difficulty: the two-sector AEAT worked-example oracle must be sourced and bundled
  before the per-sector percentages are trusted (no fabricated expected values); the
  art. 9.1.c letra taxonomy must be grounded, not invented.
- Pitfall: a future agent may auto-partition from CNAE and ship a wrong regulated
  deduction — the fail-closed operator-declared partition is the guard. A second pitfall:
  forgetting the common-use art. 104.Dos slice and routing every input to a single
  sector.
- Pathway: the sector-definition surface and sector-aware aggregation are the landing
  slots for the art. 101.Dos common regime and its +20% void test.

## Implementation footprint

Files the implementation will touch (for wave-clustering; see the ADR-vs-ADR overlap
report):

- `src/cadrumo/domain/prorrata_register/__init__.py` — per-sector orchestration over the
  existing `sector_id` axis; a sector-definition model. **SHARED with `prorrata-especial`
  (especial-complete signal) and `prorrata-art105-cinco-interrupted` (interrupted-year
  representation).**
- `src/cadrumo/application/aggregation/_iva_ledger.py` — sector-aware apportionment
  (route each input to its sector percentage; common-use → art. 104.Dos). **SHARED with
  `prorrata-especial` (regime routing) and `prorrata-art104-tres-exclusions` (exclusion
  filtering) — hottest shared surface.**
- `src/cadrumo/domain/transactions/_models.py` — a sector reference on the ledger row.
  **SHARED with `prorrata-especial` (input_classification) and
  `prorrata-art104-tres-exclusions` (exclusion tag).**
- `src/cadrumo/domain/iva/_prorrata.py` — consume `requires_sectoral_separation` /
  `compute_sectoral_prorrata` (read-mostly). **SHARED (additive) with the sibling ADRs.**
- taxpayer profile model (`src/cadrumo/domain/contribuyente/...`) — optional activity/IAE
  code axis. Mostly unique to this ADR.
- `src/cadrumo/_data/registry/aeat/legal/iva.toml` and `legal/iva-flow.toml` — new
  `[legal."ley-37-1992:art-101"]` entry; art. 9.1.c sector-definition grounding.
  **SHARED (additive, distinct blocks) with the sibling ADRs.**
- `src/cadrumo/_data/registry/aeat/modelos/303/**` — sector-classification metadata.
  **SHARED with `prorrata-especial` and `prorrata-art104-tres-exclusions`.**
- CLI ledger surface / a `prorrata` verb group — sector declaration + per-row sector
  assignment. **SHARED with `prorrata-especial` and `prorrata-art104-tres-exclusions`.**
- `src/cadrumo/core/_prorrata_register.py` — the register regime enum is per-sector already;
  read-mostly. **SHARED (additive) with `prorrata-art105-cinco-interrupted`.**
- `src/cadrumo/core/external_constants.py` — `PRORRATA_SECTORAL_SEPARATION_SPREAD_PP`
  already exists; read-only, no write.
