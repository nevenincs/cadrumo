# Ledger corpus — recargo-equivalencia retailer (cross-profile sibling)

A second, smaller hand-authored corpus for a **different taxpayer in a different
profile bucket**, exercising the **cross-profile runtime-pegged ledger** goal and
the **recargo de equivalencia regime** end-to-end. It is the regime
counterpart to the Marta autónoma corpus, where the same RE purchase category is
an unexpected non-declarable recargo-equivalence preflight issue rather than an
expected retailer-regime acquisition cost.

## Taxpayer

**Comercio Minorista García** — NIF `23456789J` — a small retail shop under
**régimen de recargo de equivalencia** (IVA), estimación directa simplificada
(IRPF). Distinct NIF + bucket from Marta so cross-profile isolation is real.

## The RE regime (what the oracle encodes)

- **Purchases from wholesalers** (`Compra mercaderia ... con recargo`): the
  supplier charges IVA (21%) **plus** recargo de equivalencia (5.2%). The retailer
  deducts **neither** — the full gross is the acquisition cost (compras de
  mercaderías) for renta. `iva_declarable=false`, `iva_deductible=false`,
  `iva_category=recargo_equivalencia`.
- **Retail sales** (`Cobro ventas TPV`): the retailer charges IVA to the
  consumer but does **not** file M303 for the retail activity (IVA is settled via
  the RE paid to suppliers). Income still feeds renta actividad.
  `iva_declarable=false`.
- **Other expenses** (rent, utilities, gestoría): a RE retailer cannot deduct
  input IVA on these either; the gross is the renta cost.

This contrasts with `ledger-corpus/` (Marta), where a `recargo_equivalencia`
purchase row is surfaced as a **non-declarable recargo-equivalence preflight
issue** for a non-retailer persona. Same IVA category, different persona
rationale; both remain outside IVA ledger aggregation.

## Files

- `bbva-retail-eur.csv` — raw BBVA-layout export, 44 rows, 2025 H1.
- `ground-truth.manifest.json` — the retailer oracle (first-match-wins rules).
