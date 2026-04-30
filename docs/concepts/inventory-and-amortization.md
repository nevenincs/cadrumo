# Inventory and amortization ledgers

For actividades económicas in estimación directa normal, AEAT can derive two
Modelo 100 Anexo D normal aggregates from explicit local ledgers:

- `0155` variación de existencias
- `0173` amortización del inmovilizado

The canonical Kent-facing CLI surface is:

```text
aeat data ledgers assets ...
aeat data ledgers inventory ...
```

## Storage and security

Ledger records use the secure persistence substrate from #216. The assets,
amortization, and inventory files are encrypted `FINANCIAL` envelopes under
the local AEAT config directory, with file locks around writes:

- `assets-ledger.envelope.json`
- `assets-amortization-ledger.envelope.json`
- `inventory-ledger.envelope.json`

The envelope stores ciphertext, classification metadata, and encryption
metadata. Asset descriptions, SKU names, movement ids, and amounts are not
written as plaintext ledger JSON.

## Assets and amortization

`AssetRecord` is a strict, frozen Pydantic record. It stores the asset id,
description, LIS art. 12.1.a `AssetClass`, acquisition date, activity
allocation, and VAT decomposition:

- `taxable_base`
- `vat_rate`
- `vat_amount`
- `deductible_vat_ratio`
- `gross_total`
- `cost_basis`

The amortizable `cost_basis` is the VAT-exclusive base plus non-deductible VAT.
For example, a EUR 1,000 laptop with 21% VAT and 50% deductible VAT has an
amortizable basis of EUR 1,105.

Kent records assets with:

```text
aeat data ledgers assets add pc-2024 \
  --description "work pc" \
  --asset-class electronica.equipos_tratamiento_informacion \
  --taxable-base 1000.00 \
  --vat-rate 21.00 \
  --deductible-vat-ratio 0.50 \
  --acquisition-date 2025-01-01
```

He can preview before writing an amortization entry:

```text
aeat data ledgers assets amortization preview --asset pc-2024 --year 2025
```

and then persist it:

```text
aeat data ledgers assets amortization apply --asset pc-2024 --year 2025
```

The calculation uses the BOE LIS art. 12.1.a table. A custom
`--useful-life-years` value is allowed only when it does not exceed the
maximum LIS coefficient for the asset class. Cumulative amortization is capped
at cost basis. Future-year ledger entries do not reduce a prior-year preview.

`--libertad-amortizacion` is explicit and still capped by remaining basis.
Kent must provide the legal basis for the accelerated election in his records.

## Inventory

`InventoryLedger` is a strict, frozen Pydantic record per activity and tax
year. It stores the valuation method, opening stock, optional opening stock
layers, and dated movements.

Kent creates a ledger with:

```text
aeat data ledgers inventory create retail \
  --year 2025 \
  --valuation-method fifo \
  --opening-stock 100.00 \
  --opening-quantity 10 \
  --opening-unit-cost 10.00 \
  --sku ssd
```

Movements are explicit and idempotent by `--movement-id`:

```text
aeat data ledgers inventory movement add \
  --actividad retail \
  --year 2025 \
  --movement-id buy-1 \
  --date 2025-02-01 \
  --kind purchase \
  --sku ssd \
  --quantity 10 \
  --unit-cost 20.00 \
  --vat-rate 21.00
```

Valuation can be previewed without writing:

```text
aeat data ledgers inventory valuation preview --actividad retail --year 2025
```

FIFO consumes the oldest stock layers first. PMP and `coste_medio` compute a
weighted-average cost over available stock. A movement that would drive stock
negative is refused instead of clamping the closing value. LIFO is refused at
input parsing with a structured error citing LIS art. 17.

## Modelo 100 Anexo D

For Anexo D normal, asset amortization feeds casilla `0173` and inventory
variation feeds casilla `0155` as:

```text
existencias finales - existencias iniciales
```

Existing callers that pass explicit Anexo D aggregates still work through the
formula layer. The ledger path exists so Kent can derive those aggregates from
reviewable local records instead of hand-maintained totals.

Kent previews the ledger-derived Anexo D inputs with:

```text
aeat data ledgers anexo-d preview --modelo 100 --year 2025 --actividad retail
```

## Legal references

- LIS art. 12.1.a: linear amortization table
- LIS art. 12.5: accelerated amortization elections where applicable
- LIS art. 17: inventory valuation boundary and LIFO exclusion
- LIRPF art. 28: business activity net income rules
- RIRPF art. 30: simplified-estimation boundary; simplified estimation uses a
  separate amortization table
- BOE-A-2014-12328
