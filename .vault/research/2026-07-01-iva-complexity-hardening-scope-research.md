---
tags:
  - '#research'
  - '#iva-complexity-hardening-scope'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-07-01-iva-complexity-hardening-scope-adr]]'
  - '[[2026-06-19-silent-zero-base-aggregation-adr]]'
  - '[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-06-09-modelo-iva-routing-carry-adr]]'
---

# `iva-complexity-hardening-scope` research: `IVA complexity hardening umbrella #345: verify-first scoping of children #346/#347/#348`

Verify-first pass over the IVA umbrella epic #345 (four needs-design children).
Two of three children (#346, #348) are substantially ALREADY MODELLED and should
CLOSE as largely-done; one (#347) carries a single genuine ADR-grade gap - the
prorrata-definitiva annual regularizacion - which the accompanying ADR scopes.

## Findings

### Per-child verdict table

| Child | Verdict | Evidence | Recommendation |
| --- | --- | --- | --- |
| #346 tipos + exento/sujeto/no-sujeto matrix + deductibility | ALREADY-MODELLED | `domain/iva/_schema.py:IvaCategory` (21/10/4/0 + exempt/not-subject/no-sujeta), `IvaExemptionArticle`, `_data/registry/aeat/iva/rates.toml` temporal `pct` windows, `_prorrata.py:classify_input_deduction` | CLOSE largely-done; residual bounded Ley 7/2024 food-rate windows |
| #347 prorrata general + especial + regularizacion anual (arts 102-106) | SPLIT: general/especial DONE, regularizacion anual ADR-GRADE | `_prorrata.py` vs. M303 casilla 44 `input_kind = "manual"`, no feed, no prorrata `BindingSourceKind` | Author ADR for the regularizacion-anual mechanism (this feature) |
| #348 ISP + intracomunitarias + OSS/IOSS cross-checks | ALREADY-MODELLED | `_classification.py` R01-R23, `_oss.py:OssIossRegime`/`regime_allows_deduction`, routing-carry + silent-zero ADRs | CLOSE largely-done; optional bounded M369-M303 scope predicate |

### #346 tipos + exento/sujeto/no-sujeto matrix + deductibility (ALREADY MODELLED)

- Tipos: `IvaCategory` carries DOMESTIC_GENERAL_21 / REDUCED_10 / SUPER_REDUCED_4 /
  ZERO. The rate engine is temporal: `IvaRateRecord` (`_schema.py`) carries pct plus
  effective_from/effective_until windows, loaded from `registry/aeat/iva/rates.toml`
  via `_rates.py:load_iva_rate_table`. A rate such as the temporary 5% is a dated pct
  value in a window, not a new category - so the 5% tipo is representable data, not an
  architecture gap.
- Exento/sujeto/no-sujeto matrix: DOMESTIC_EXEMPT (with the `IvaExemptionArticle`
  art-20 sub-article discriminator, per `2026-06-03-iva-exemption-article-adr`),
  DOMESTIC_NOT_SUBJECT, and OPERACION_NO_SUJETA cover the matrix; rules R04 (immovable
  exempt), R30 (Canarias/Ceuta/Melilla out of TAI), R12/R16/R22 (place-of-supply
  not-subject) route into it. `CUOTA_LESS_M303_IVA_CATEGORIES` encodes which bear no
  M303 cuota by law.
- Deductibility: `_prorrata.py:classify_input_deduction` implements per-input
  deductibility under prorrata especial (100/0/general); the exemption-article
  discriminator routes no-derecho-a-deduccion operations.
- Residual (BOUNDED, not ADR): confirm the Ley 7/2024 temporary food-rate windows
  (super-reduced 5% then 0% for staples across 2023-Sep 2024) are populated as
  `IvaRateRecord` windows in `rates.toml` (the bundled table shows ES 21/10/4/0 for
  2024-2025). A missing historical food micro-window is a registry DATA edit grounded
  in the Manual practico IVA transitional schedule, corpus-cross-checked per
  `legal-grounding-verifies-bundled-authoritative-corpus`, not a design change.

### #347 prorrata (arts 102-106): general/especial done, regularizacion anual is the gap

- general + especial + sectoral (ALREADY MODELLED): `_prorrata.py` implements
  art-102.Uno/.Dos (`compute_prorrata_general`, ROUND_CEILING), art-103
  (`classify_input_deduction`, `is_especial_mandatory` +10% rule), art-9.1.c sectoral
  separation (`requires_sectoral_separation`, 50-pp spread), and the
  PROVISIONAL/DEFINITIVA lifecycle (`ProrrataKind`) plus canonical `ProrrataReference`
  ids. `2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr` is the accepted
  authority.
- regularizacion anual (arts 105-106) is the GENUINE ADR-GRADE GAP: the substrate
  computes percentages but is NOT wired into the calculate mesh. There is no prorrata
  `BindingSourceKind` (confirmed by grep of `application/aggregation/_source_mesh.py`
  and `core/aggregation.py`), and M303 casilla 44 (Regularizacion prorrata por
  porcentaje definitivo - Cuota,
  `_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-002.toml`
  id 44) is `input_kind = "manual"`. The mechanism - apply the PRIOR year definitive
  percentage provisionally across the year quarters, then REGULARISE in Q4/annual
  against the CURRENT year actual annual volumes, feeding casilla 44 and the M390
  annual field - is a cross-period structure akin to the IVA-wallet, not a bounded
  mirror.
- This gap is already named and deferred by two ADRs.
  `2026-06-19-silent-zero-base-aggregation-adr` defers M303 prorrata volumes on
  CORRECTNESS grounds: a per-period base_amount_sum binding ships a wrong deducible
  percentage for any trader with exempt-without-right operations, so a faithful
  mechanism needs the provisional-percentage carry + Q4 regularisation model (genuine
  design). `2026-07-01-iva-bienes-inversion-regularizacion-adr` (#349) is BLOCKED on
  this same prorrata-definitiva source for its automatic casilla-43 feed. This ADR is
  the parent both are waiting on.

### #348 ISP + intracomunitarias + OSS/IOSS cross-checks (ALREADY MODELLED)

- ISP: `IvaCategory.DOMESTIC_REVERSE_CHARGE` (rules R01 construction art-84.Uno.2.f,
  R02 waste, R03 electronics) and INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE (R11
  goods art-13, R13 EU B2B services art-84.Uno.2.a); `requires_reverse_charge` on the
  result. M303 reverse-charge cuota routing landed in
  `2026-06-09-modelo-iva-routing-carry-adr`.
- Intracomunitarias: INTRA_COMMUNITY_SUPPLY (R10 art-25 exempt),
  INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE, INTRA_COMMUNITY_TRIANGULATION
  (informativa, cuota-less); M349 surface exists.
- OSS/IOSS: `_oss.py` carries OssIossRegime (external/union/import), IossFilerRole
  (HAC/610/2021 art-2), DeductionScope, REGIME_PERIODICITY, and the LIVA-grounded
  `regime_allows_deduction` predicate (art-163 vicies/tervicies/octovicies: no
  deduction inside the M369 autoliquidation, recovery via M303 for establecidos).
  Rules R16-R23 route Exterior/Union/IOSS supplies. Modelo 369 is the autoliquidation
  surface.
- Cross-checks: `2026-06-19-silent-zero-base-aggregation-adr` added an M390
  `ledger_iva_aggregation` import-deducible binding plus a reconciliation predicate
  flagging divergence between the ledger total and the reconciliacion-303 total.
- Residual (BOUNDED, optional): an explicit M369-to-M303 deduction-scope verification
  predicate that surfaces if an operator attempts to deduct an OSS/IOSS cuota inside
  the M369 autoliquidation (`regime_allows_deduction` returns False there). The domain
  predicate exists; wiring it as a registry verification_predicate is a bounded
  registry edit, not ADR-grade. A follow-up note on #348, not a blocker to closing it.

### Method / grounding notes

- Grounded via `vaultspec-rag --type vault`, then rg/read to pin exact symbols per
  `aeat-rag-discovery`. Registry revisions read for BOTH inline and fragmented forms
  per `registry-revision-content-inline-or-fragmented` (M303 2023-y-siguientes is
  fragmented; casilla 44 read from the fragmented casillas file). Rate values confirmed
  to live in `registry/aeat/iva/rates.toml`, not as Python literals
  (`aeat-schema-central-config`).

### Peer-WIP and scope boundary

- No source files were edited; only the two new `.vault/` documents for this feature
  were authored. `git status` shows unrelated modified `.vault/adr/*.md` (docs/date
  churn), untouched here.
- #350 (2026 franquicia IVA) is out of scope and untouched. #349 (bienes-inversion
  regularizacion, arts 107-110) shipped a first slice this session (3fd0d5ffe) and is
  referenced only as the downstream consumer blocked on #347 prorrata-definitiva source.
