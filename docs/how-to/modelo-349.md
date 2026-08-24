# Prepare a Modelo 349 recapitulative declaration

This page covers the Modelo 349 filing: recording the intra-community
operations it lists, checking your counterparties' EU VAT numbers, and
running the create-calculate-verify-export chain. Modelo 349 is the
informative recapitulative declaration of intra-community operations; the
registry's official title is "Modelo 349. Declaración Informativa.
Declaración recapitulativa de operaciones intracomunitarias."

Modelo 349 declares no cuota: it is a pure listing. The declaration carries
one summary block (how many intra-community operators you dealt with and for
what amounts) and one detail row per operator - country code, EU VAT number,
name, operation key, and base - plus rectification rows when you correct a
previously declared period.

`aeat` does not submit Modelo 349 to AEAT. Export creates a local file that
you upload through the official AEAT channel yourself.

## Before you create the draft

**Requirement:** a valid taxpayer profile with intra-community (ROI) activity,
and the intra-community invoice records the declaration lists. Create a profile
with `aeat config profile create <name>`. See [Set up your taxpayer
profile](profile-setup.md).

- Check applicability and cadence. Modelo 349 is quarterly (`1T`-`4T`) or
  monthly (`01`-`12`) depending on your profile and operation volumes; the
  calendar surfaces which applies to you:

  ```{cli-sequence} modelo-349-applicability
  :verify: Confirm the modelo's applicability and cadence read back.
  ```
- Record the operations as invoice records, not bare ledger rows. The 349
  listing is built from your invoice catalogue: issued invoices to EU
  operators feed the entregas side, received invoices from EU suppliers feed
  the adquisiciones side. Each invoice needs its counterparty's country and
  EU VAT number. See [Manage invoices](manage-invoices.md) and
  [Attach invoices and receipts](ledger-evidence.md).
- Verify each counterparty's EU VAT number against the VIES register before
  relying on it with `aeat app live verify nif-iva ESB12345678`. An invalid or
  unregistered number is the most common 349 correction later; checking now is
  cheaper. This is a live read-only command - see [Check AEAT notifications and
  live observations](check-aeat-notifications.md).

## Create, calculate, and verify

The preparation below records two intra-community issued invoices - a goods
supply to a German customer and a service to a French one - then creates the
draft, aggregates the invoices into the declaration, and verifies it:

```{cli-sequence} modelo-349-first-quarter
:verify: Confirm the recapitulative declaration passed verification before you export it.
```

Calculation aggregates the period's invoice records into the summary casillas
and builds the per-operator detail rows. With the two invoices above, the
summary reports two intra-community operators (`decl.numero-operadores`) for a
total of 8000 euros of operations (`decl.importe-operaciones`), and verify
grants verified-complete. Inspect what was bound and what is missing, then
show the built rows:

```{cli-sequence} modelo-349-inspect
:verify: Confirm the aggregated declaration's bindings and detail rows read back.
```

The per-operator row fields (country code, EU VAT number, name, operation
key, base) come from the invoice records; a missing counterparty fact on an
invoice surfaces here as a missing row value. Fix the invoice record rather
than forcing a manual value - the listing must match your invoice evidence.

## Rectify an earlier period

When an already-declared operation changes (a corrected invoice, a credit
note), the later 349 declares the rectification: the rectification rows name
the rectified year and period, the corrected base, and the base previously
declared. Record the correction on the invoice record for the original
operation; the rectification rows aggregate from there.

## Export and file

Attempt the verified declaration export. The current authoritative layout
cannot encode every applicable required casilla, so the command refuses rather
than producing a partial file:

```{cli-sequence} modelo-349-export
:verify: Confirm export refuses when required casillas would be omitted.
```

After you file at the portal, record the local marker, then
[reconcile against the justificante](reconcile.md). The marker needs a pending
filing obligation, so the preparation below declares the intra-community
obligation on the profile first:

```{cli-sequence} modelo-349-file
:verify: Confirm the local filed marker records the quarter without claiming AEAT accepted it.
```

The marker is optional and only applies while the obligation window is open.
Until the required-casilla layout is complete, read the verified values and
present them through the AEAT portal; do not treat a partial export as a finish
line.

Modelo 349 runs alongside your periodic Modelo 303: the same intra-community
operations that appear here also feed the 303's intra-community boxes. Keep
the two consistent by fixing the underlying invoice and ledger records, not
the declarations. See [Prepare a Modelo 303 IVA filing](modelo-303.md).

## Next steps

- [Manage invoices](manage-invoices.md)
- [Prepare a Modelo 303 IVA filing](modelo-303.md)
- [Plan your filing calendar](filing-calendar.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filing](reconcile.md)
