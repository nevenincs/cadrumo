# Derived `classify --from-csv` oracle inputs

These CSVs are **derived**, not hand-authored: each row pairs a corpus
transaction's content-addressed `transaction_id` with the classification the
ground-truth oracle (`../ground-truth.manifest.json`) assigns to it. They are the
batch-classification companion to the corpus and feed
`aeat app ledger classify --from-csv`.

- `bbva-business-eur.classify.csv` — `transaction_id,classification,category_id`
  for every non-MIXED row of `../bbva-business-eur.csv` (MIXED rows are omitted
  because bulk classify needs a `business_pct` those rows resolve interactively).

## Provenance + drift guard

`transaction_id` is `derive_transaction_id(raw)` over the imported corpus row, so
the file is stable as long as the source CSV's amounts, dates, and narratives are
unchanged. `test_ledger_classify_fixture.py` regenerates the expected rows from
the corpus + oracle on every run and asserts byte-equality with this committed
file — if the corpus changes, the test fails loudly and the fixture must be
regenerated. Never hand-edit these rows.
