---
tags:
  - '#research'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:79932c109ea90615ef91e3e674f4a3ebd2a9e975d07646d6cef00146db2168f6'
related: []
---
# `calculation-chain-integrity` research: scoping the Modelo 390 annual under-modelling

Scoping only. Nothing here proposes a design; the purpose is to size the work and record what it is NOT, so a future campaign starts from measurement rather than from the category comparison that first drew attention.

## The size, measured from the bundled diseño

The 2024 M390 record design carries **375 distinct box numbers**. The registry's `2010-y-siguientes` revision carries **22 casillas**, 16 of them bound.

That is not a rounding gap; it is the annual return modelled at roughly six per cent of its declared surface.

## What the 22 model, and what they do not

The registry models the settlement spine — the devengado and deducible aggregates and the annual result — and it models them by **tier**, not by the axes the diseño actually splits on. The diseño splits goods from services and splits by rate, in places where the registry carries one combined casilla.

## The official section inventory

From the same workbook, the substantive sections are:

| § | title |
|---|---|
| 5 | Operaciones Reg. Gral. |
| 6 | Operaciones Reg. Simplificado |
| 7 | Resultado liquidación anual |
| 8 | Tributación razón de territorio |
| 9 | Resultado de las liquidaciones |
| 10 | Volumen de operaciones |
| 11 | Oper. Específicas |
| 12 | Prorratas |
| 13 | Reg. Deducc. Diferenciados |

The registry's 22 casillas sit almost entirely in §5 and §7. Sections 6 and 8 through 13 are essentially unmodelled.

## What this is NOT, established by `W06.P08.S46`

The finding that prompted this — four ledger-IVA categories on the quarterly side with no annual counterpart (`domestic_reverse_charge`, both exports, `intra_community_supply`) — is **not** the under-modelling.

Those four appear on the annual form in **§10 Volumen de operaciones**, casillas `[103]` and `[125]` among them: a turnover disclosure, not a liquidación. The annual settlement genuinely does not carry per-category export or intra-community devengado lines the way the quarterly return does, so the registry is not dropping settlement figures.

Recording that distinction is the point of scoping this separately. Reading the category comparison as the gap leads to adding devengado bindings for boxes the annual liquidación does not have — inventing settlement lines out of a turnover section.

## Candidate shape of the campaign

Offered as a starting frame, not a plan:

1. §10 Volumen de operaciones — the section the category comparison actually points at, and the one with a live consumer today (it is where the four concepts are annually reported).
2. §12 Prorratas — the domain substrate already exists (`domain/iva/_prorrata.py` implements LIVA arts. 102-106); this is a binding-and-casilla exercise rather than new computation.
3. §6 Reg. Simplificado — carries its own devengado lines including inversión del sujeto pasivo at `[1084]`, so it is settlement rather than disclosure.
4. §5 rate and goods/services splits — the per-rate-per-window work `W06.P08.S54`/`S55` just made expressible, and where `S48`/`S50` warn the reconciliation parity gate needs per-leg roles.

## Dependencies worth stating up front

- The per-leg split in §5 will drop the intracom concept out of the reconciliation parity comparison unless the roles are handled deliberately; `W06.P08.S50` now reddens if that happens rather than letting the intersection shrink silently.
- Any new annual casilla bound to ledger IVA joins the parity gate automatically, so its category set must match its quarterly counterpart's or the gate fires — which is the intended behaviour and should be treated as a design constraint rather than an obstacle.
