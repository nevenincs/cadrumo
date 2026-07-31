---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:0ab5e1c513c55169fd4cc9e5f058b629043de9ae28a970c32cfd7cdf6f3687f8'
step_id: 'S20'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Verify per-sector prorrata against a worked example with a greater-than-50-percentage-point sector spread

## Scope

- `src/aeat/domain/prorrata_register/tests/`

## Description

- Confirm no bundled AEAT worked-example oracle for a two-sector differentiated-sectors prorrata ships (`src/aeat/_data/corpus/manual_oracles/` carries only the whole-entity Modelo 303 prorrata-general regularización example and unrelated modelos), and record that absence explicitly in the verification test docstring.
- Author the hand-constructed-register verification `src/aeat/application/aggregation/tests/test_sectores_diferenciados_verification.py` (the S09/S15 pattern) that composes the whole differentiated-sectors lifecycle end to end: settle two sectors' prior-year (2025) definitives from their OWN annual volumes (comercio 90%, arrendamiento 20% — a 70-point spread; common-use 40%), seed each 2026 provisional from that sector's prior definitive, persist the seeded 2026 register (per-sector entries + common entry + sector definitions), aggregate a 2026 ledger with one purchase per sector plus one common-use purchase, and assert each deducible cuota apportions at its own sector percentage and the common-use input at the art. 104.Dos common percentage.

## Outcome

The per-sector percentages and the common-use split verify end to end against the hand-constructed register (no bundled two-sector oracle exists, stated in the docstring). The deducible interiores cuota resolves to 10.50*90% + 10.50*20% + 10.50*40% = 15.750, with the anti-tautology gate proving it is NOT any single declared percentage applied across the 31.50 soportado (not 28.35 at 90%, not 12.60 at 40%, not 6.30 at 20%); the two sector percentages carry a >50-point spread; bases stay full and devengado is untouched. The percentages flow from the register's own settled volumes (via `settle_sector_definitive` → `compute_prorrata_definitiva_anual`) and the routing they drive is the production aggregation path, so the claim under test is the per-sector routing + common-use split, not the already-verified con/total definitive substrate. ruff, ruff format, and ty clean; the test passes under `-n0`.

## Notes

- No fabricated regulated figures: the sector percentages are derived from chosen annual volumes through the production settlement substrate, not hand-copied from a formula, and the anti-tautology assertions guard against a single-percentage collapse. Values were chosen so the per-sector total (15.750) does not coincide with any single declared percentage across the total soportado.
- The scaffolder placed the step scope at `domain/prorrata_register/tests/`, but the verification is genuinely end-to-end (register lifecycle + ledger aggregation routing) and needs the encrypted-runtime + repository fixtures, so it lives under `application/aggregation/tests/` (the S15 especial-oracle home), consistent with the plan's "or application/aggregation/tests/" allowance.
- The art. 101.Dos AEAT-authorised common-deduction regime and its +20% void test remain deferred per the ADR (recorded as an authorisation case in the S16 art-101 legal notes); this verification covers the core per-sector routing the ADR's D1/D2/D3 decided.
- Campaign-close reconciliation (W04.P05.S26): the plan Verification "Oracle grounding" bullet is amended to state sectores is proven by a law-derived scenario through the production path (no bundled AEAT two-sector oracle), so the plan claim now matches what this step shipped. The W04.P05.S25 anti-dormant proof additionally drives the per-sector routing through the operator `ProrrataRegisterService.declare_sector` + `--sector`-tagged rows.
