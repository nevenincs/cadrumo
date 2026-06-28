---
tags:
  - '#research'
  - '#inventory-management'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-27-modelo-100-renta-full-calc-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-research]]'
  - '[[2026-04-27-security-storage-audit-audit]]'
---

# `inventory-management` research: `autonomo inventory and amortization ledgers`

Research covers the M100 foundations for actividad economica inventory and
amortization, the newly merged secure-persistence work from #216, and current
BOE consolidated legal anchors for LIS/LIRPF/RIRPF.

## Findings

The existing M100 foundations are intentionally thin. `_amortization.py`
already exposes a strict frozen `AmortizationCategory`, closed `AssetClass`,
and a 33-row LIS art. 12.1.a lineal table. `_inventario.py` exposes a strict
frozen `InventoryRecord` and closed `ValuationMethod` without LIFO. The Anexo
D normal surface keeps `0155` variacion de existencias and `0173`
amortizacion del inmovilizado as caller-supplied inputs. The computation for
`0190` subtracts signed `0155`, so a positive closing-stock increase reduces
deductible expenses and a negative variation increases them.

BOE verification used the consolidated LIS text `BOE-A-2014-12328`, latest
published update shown by BOE on 2026-03-21. LIS art. 12.1.a contains the
lineal amortization table with 33 rows. The repository table matches the row
count and the representative coefficients needed for #453 acceptance:
industrial buildings 3 percent with 68 years, external transport 16 percent
with 14 years, and information-processing equipment 25 percent with 8 years.
The issue text's worked example says "edificios industriales 4%"; the BOE
table and repository both say 3%. The implementation must keep BOE as source
of truth and make the test explicit so the discrepancy is visible.

The issue text cites LIS art. 12.5 for libertad de amortizacion, but the
current LIS structure places general freedom hooks in art. 12.3 and reduced
size business incentives in arts. 101-102. The implementation should name the
feature as an opt-in "libertad de amortizacion" flag, cite the actual BOE
articles, and preserve the same basis cap as ordinary lineal amortization.

LIS art. 17.1 refers valuation to Código de Comercio criteria corrected by
LIS. For inventory practice this keeps tax valuation tied to admissible
accounting criteria; the existing model already admits FIFO, PMP, and coste
medio while structurally excluding LIFO. #453 needs an explicit refusal path
for user input that tries `lifo`, because CLI users can type it even if the
enum cannot represent it. The v1 movement model does not yet store opening
quantities or stock layers, so it can compute signed variation from explicit
closing stock or signed movement values but not claim full method-specific
FIFO/PMP/coste-medio layer valuation until the scheduled persistence/UX audit.

LIRPF art. 28.1 says net income from economic activities is determined under
Corporate Income Tax rules subject to IRPF special rules. LIRPF art. 30 and
RIRPF art. 30 govern estimation directa simplificada, including the separate
simplified amortization table and the 5 percent difficult-to-justify expense
cap. #453 therefore scopes the new ledger derivation to Anexo D normal by
default; simplified-mode support can reuse the data later but should not
silently apply the LIS art. 12.1.a table where the simplified table is legally
required.

#216 has been merged into this branch and adds a database and encrypted storage
substrate. The issue nevertheless directs Path A only. The security audit says
new persisted business state needs schema versioning, path governance, and
clear classification. The pragmatic path for #453 is schema-versioned JSON
under the user's config directory with test-time path injection, while
documenting that a future migration can move these ledgers into #216's governed
backend without changing the public `aeat.domain.profile.assets` and
`aeat.domain.profile.inventory` APIs.

Multi-actividad scope needs separate inventory ledgers keyed by
`actividad_id`. Assets can be allocated to an activity through an optional
activity id and allocation ratio. Shared assets should be computed once per
asset and allocated by ratio for an Anexo D aggregate; cumulative amortization
must remain capped at total cost basis, not per activity copy.

The needed Anexo D derivations are:

- `0155`: inventory variation, computed as closing stock minus opening stock
  for a year/activity ledger. This matches the existing M100 formula contract.
- `0173`: amortization of fixed assets, computed from the asset ledger and
  amortization ledger for the filing year.
- `0190`, `0195`, and `0205`: existing computed casillas continue to work once
  `0155` and `0173` are supplied or overridden.

Backwards compatibility requires leaving direct caller-supplied aggregates in
place. When ledgers are explicitly provided, ledgers should win for `0155` and
`0173`; otherwise the existing provided values remain untouched.
