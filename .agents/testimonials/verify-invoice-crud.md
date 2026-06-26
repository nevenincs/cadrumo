# Testimonial: verify INVOICE management surface (rich catalogue lifecycle)

Persona: naive-but-thorough user. Followed `docs/how-to/manage-invoices.md` and the
invoice sections of `docs/how-to/ledger-evidence.md`. Real CLI, isolated persona env
under `/tmp/verify-invoice-crud`, profile `verify-user` (tax-id 12345678Z).

Overall verdict: **PASS** — the full rich-catalogue invoice lifecycle works end-to-end,
every documented refusal fires correctly, and the slim `invoice add` store and the rich
`catalogue` store are fully distinct. One minor cosmetic observation noted (no severity).

---

## Setup

### Create profile
- Command: `aeat config profile create verify-user --quiet --accept-defaults --tax-id 12345678Z`
- Expected: profile created and set active.
- Actual: `profile verify-user / estado creado / active_profile verify-user`, EXIT=0.
  (First attempt without `--tax-id` correctly refused with an instructive message naming
  the missing flag.)
- Verdict: OK.

---

## Rich catalogue lifecycle (manage-invoices.md "Feed a calculation from the catalogue")

### catalogue create --kind issued --operation-type E
- Command: `... catalogue create --kind issued --counterparty-nif DE345678901 --counterparty-name "Kunde GmbH" --invoice-number EU-CAT-001 --invoice-date 2026-02-10 --taxable-base 2000 --iva-rate 0 --country-code DE --operation-type E`
- Expected (per doc): creates linkable catalogue invoice, prints a long id.
- Actual: `invoice_id 5f6226984e838fa553b9647364c5e3199cb833d79c8932072b9a67bc39eabc17 / kind issued / grand_total 2000.00 / linked_transaction_ids (empty)`, EXIT=0.
- Verdict: OK.

### catalogue create --kind received --operation-type A
- Command: `... catalogue create --kind received ... --invoice-number EU-CAT-002 ... --taxable-base 1500 --iva-rate 0 --country-code FR --operation-type A`
- Expected: creates received catalogue invoice.
- Actual: `invoice_id 7520ec65...d3ae / kind received / grand_total 1500.00`, EXIT=0.
- Verdict: OK.

### catalogue create --kind received (domestic, --iva-rate 21, no op-type) [ledger-evidence.md example]
- Command: `... catalogue create --kind received --counterparty-nif A58818501 --counterparty-name "Papelería Sol SL" --invoice-number 2026-0142 --invoice-date 2026-03-10 --taxable-base 100.00 --iva-rate 21`
- Expected: creates invoice; grand total derived from base + IVA.
- Actual: `invoice_id d45a1198...7025 / grand_total 121.00`, EXIT=0. (100 + 21% correctly computed.)
- Verdict: OK.

### catalogue list
- Command: `... catalogue list`
- Expected: lists all catalogue copies.
- Actual: `count 3` with one row per invoice (id, kind, nif, number, date, total), EXIT=0.
- Verdict: OK.

### catalogue view <full-id>
- Command: `... catalogue view 5f6226984e...bc17`
- Actual: full invoice detail block, EXIT=0.
- Verdict: OK.

### catalogue view <prefix>
- Command: `... catalogue view 7520`
- Expected: resolves unambiguous prefix.
- Actual: full detail of EU-CAT-002, EXIT=0.
- Verdict: OK.

### catalogue remove <full-id> --yes
- Command: `... catalogue remove d45a1198...7025 --yes`
- Expected: removes invoice.
- Actual: prints removed-invoice block, EXIT=0; subsequent `view` of that id refuses
  ("Factura del catálogo no encontrada", EXIT=1). Removal confirmed.
- Verdict: OK.

### catalogue remove <prefix> --yes
- Command: `... catalogue remove 7498 --yes`
- Actual: removed (block printed); confirming `view 7498` after refuses (EXIT=1).
- Verdict: OK.

---

## Refusal probes

### Unknown id (view)
- Command: `... catalogue view ffffffff...ffff`
- Actual: `Error. Factura del catálogo no encontrada: ffff...`, EXIT=1.
- Verdict: OK (clean refusal, no traceback).

### Empty id (view "")
- Command: `... catalogue view ""`
- Actual: `Error. Se requiere un identificador de factura.`, instructive, no traceback.
- Verdict: OK.

### Ambiguous prefix
- Command: `... catalogue view 7`  (and `view d`)
- Expected: refuse, naming the colliding candidates.
- Actual: `Error. El prefijo de identificador de factura 7 es ambiguo; coincide con: 7520..., 7498...` plus a `candidates:` list, EXIT=1. Same for `d` (3 candidates).
- Verdict: OK.

### Remove without --yes
- Command: `... catalogue remove <id>` (no --yes)
- Actual: `Invalid value: Debes pasar --yes para eliminar una factura`, EXIT=2.
- Verdict: OK.

### Remove unknown id
- Command: `... catalogue remove aaaa...aaaa --yes`
- Actual: `Error. Factura del catálogo no encontrada: aaaa...`, EXIT=1.
- Verdict: OK.

### Bad --operation-type S (catalogue cannot feed M349 yet)
- Command: `... catalogue create ... --operation-type S`
- Expected (per doc): refused, lists supported E, A, T.
- Actual: `Invalid value: --operation-type S todavía no puede alimentar el Modelo 349 desde el catálogo; admitidos: E, A, T.`, EXIT=2. Matches the doc text (Spanish).
- Verdict: OK.

### Invalid --operation-type Z (not an M349 code)
- Command: `... catalogue create ... --operation-type Z`
- Actual: `Invalid value: --operation-type debe ser uno de: E, S, T, R, A, I, M`, EXIT=2.
- Verdict: OK (accepted set surfaced).

### Duplicate identity
- Command: re-run `catalogue create` for EU-CAT-001 (same kind/nif/number/date).
- Actual: `Invalid value: an invoice with the same identity already exists in the catalogue`, EXIT=2.
- Verdict: OK.

### Unsupported IVA rate (--iva-rate 15)
- Command: `... catalogue create ... --iva-rate 15`
- Expected (ledger-evidence.md): only 0, 4, 10, 21 accepted.
- Actual: `Invalid value: iva_rate is not a recognised IVA percentage`, EXIT=2 — refused.
- Verdict: OK (refused correctly). Minor: message does NOT enumerate the accepted set
  (0, 4, 10, 21) the way the doc describes the allowed values, unlike the
  --operation-type messages which do list theirs. No severity — refusal is correct and
  the doc states the set; just a small instructive-surface inconsistency.

---

## Two distinct stores (manage-invoices.md "Two ways to hold an invoice")

### Slim invoice add
- Command: `... invoice add --kind issued --counterparty-nif B12345678 --counterparty-name "Cliente SL" --invoice-number FAC-2026-001 --invoice-date 2026-02-15 --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --total-amount 1210`
- Actual: `invoice_id 5abb430c38c44528 / source_kind collectible_invoice`, EXIT=0.
  Note: short 16-char id, distinct shape from the 64-char catalogue id.
- Verdict: OK.

### Distinctness checks
- `invoice list` -> `count 1`, only `5abb430c38c44528` (the slim record).
- `catalogue list` -> contains 0 occurrences of the slim id `5abb430c38c44528`.
- `invoice view 5f6226...bc17 --kind issued` (catalogue id into slim store)
  -> `Refused. no invoice record matches '5f6226...'`, refused.
- `catalogue view 5abb430c38c44528` (slim id into catalogue store)
  -> EXIT=1, not found.
- Verdict: OK — the slim `invoice add` store and the rich `catalogue` store are fully
  separate, exactly as the docs claim.

---

## Summary

Every documented catalogue verb (create issued/received with --kind and --operation-type,
list, view by id and by prefix, remove by id and by prefix with --yes) works and matches
the docs. Every documented refusal fires cleanly with exit code 1 (not-found / ambiguous)
or 2 (validation), with no raw tracebacks anywhere. The slim and rich stores are distinct.
Single non-blocking cosmetic note: the unsupported-IVA-rate error does not enumerate the
accepted set, whereas the operation-type errors do.
