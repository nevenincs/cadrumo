---
tags:
  - '#audit'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bcaa84939d5ad665cd428a8ca0f2ad2ea463eea0ca289789ebecd500b67e4e91'
related: []
---
# `calculation-chain-integrity` audit: what is a modelled IVA settlement regimen, and what only looks like one

Written for `W06.P08.S57`, so a reader surveying the IVA surface does not mistake two things for modelled settlement regimenes and file their absence as a gap.

Both look like regimenes by name. Neither is one, and they are not-one for different reasons — which is the part worth keeping.

## Used goods, art objects, antiques, travel agency: printed-invoice notice phrases

These four appear in the tree only as `InvoiceLegalMention` members (`domain/invoices/_enums.py:157-160`):

    TRAVEL_AGENCY_REGIME, USED_GOODS_REGIME, ART_OBJECTS_REGIME, ANTIQUES_COLLECTORS_REGIME

They are RD 1619/2012 art. 6.1.n and 6.1.o **fixed legal notices** — literally-quoted phrases the issuer must print on the invoice when the regime applies. The enum's own docstring is explicit that they are evidence of what the issuer PRINTED, and that deriving one from our own `iva_category` classification "would fabricate evidence of compliance nobody observed on the document."

Verified at HEAD: none of the four appears in `IvaCategory`, and none appears on the IVA ledger's regimen surfaces. A search of `domain/iva/_schema.py` and `application/aggregation/_iva_ledger.py` for REBU, bienes usados or agencias de viajes returns nothing.

**So the absence is correct by design, not a modelling gap.** These regimes change how a margin is computed; nothing in the tree computes those margins, and the notice enum makes no claim that anything does. Adding them as `IvaCategory` members would assert a settlement treatment the engine does not implement — the wrong-category-is-worse-than-absent failure this campaign keeps meeting.

## Group-member rollup: filing topology, not a regimen

`per_grupo_member` is a cross-member fan-in **grouping**, not a treatment. `application/calculations/_per_grupo_member_keys.py` describes it as the 353-from-322 cross-member aggregation: the grupo's aggregate return sums each member's own figures.

That is a statement about *who files what into which return* — topology — and it is orthogonal to how any individual operation is settled. A member's operations are classified by the same categories and rates whether or not the member belongs to a grupo; the grouping decides where the totals land.

It surfaces as a **grouping** on a `previous_filing` binding selector rather than as a category or treatment axis, which is exactly right and is also why the reconciliation-pair enumeration has to read it as a second declaration site (`W06.P08.S39`).

## What IS a modelled regimen axis

For contrast, and to give the boundary a positive edge: `IvaCashAccountingTreatment` (`domain/iva/_schema.py:89`) is the shape a real modelled regimen takes here. It is a typed axis **crossed with** the category rather than a fan-out of category members, and it carries real settlement consequence — `W06.P08.S33` records which apartado of LIVA art. 163 duodecies puts each excluded category outside it.

`W06.P08.S56` follows that precedent deliberately: cross the new rate axis with the four already-modelled regimenes only, rather than fanning categories out per regimen.

## Why this is recorded rather than left to inference

A reader comparing `InvoiceLegalMention`'s seven members against `IvaCategory` sees four regime names on one side and none on the other, and the natural reading is that four regimes are unmodelled. They are unmodelled, but the right conclusion is "these are notices, and nothing here claims to settle them" rather than "four categories are missing."

The register this campaign inherited filed a structurally identical shortfall once already — the four-of-ten clave table in `W06.P08.S42` — so recording the scope boundary at the point of confusion is what converts a recurring false finding into a settled one.
