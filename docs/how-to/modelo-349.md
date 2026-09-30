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

- Check applicability and cadence. Modelo 349 applies when your profile
  declares intra-community operations. Cadrumo files it quarterly (`1T`-`4T`)
  unless the profile declares
  `--iva-intracommunity-operations-exceed-50000-eur`. Declare it when your
  intra-community supplies of goods and services, excluding IVA, exceed 50,000
  euros in the quarter or in any of the four quarters before it (art. 81 of the
  IVA regulation); the filing is then monthly (`01`-`12`).
  The following command reports whether Modelo 349 applies to your profile and
  why. A profile that has not declared its intra-community operations reports
  `applicable` false with the verdict `incomplete`, as the example shows.
  Declare them with `aeat config profile edit --does-intracomunitario`:

  ```{cli-sequence} modelo-349-applicability
  :verify: Confirm the applicability verdict and the profile facts it rests on read back.
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
  cheaper. This is a live read-only command - see [Read AEAT notifications and other live data](check-aeat-notifications.md).

## Create, calculate, and verify

The example starts with two intra-community issued invoices recorded - a goods
supply to a German customer and a service to a French one. It then creates the
draft, aggregates the invoices into the declaration, and verifies it:

```{cli-sequence} modelo-349-first-quarter
:verify: Confirm the recapitulative declaration passed verification before you export it.
```

Calculation aggregates the period's invoice records into the summary casillas
and builds the per-operator detail rows. With the example's two invoices, the
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

Export the verified declaration. The command writes a local file in the
official layout, including the per-operator detail rows, for you to upload
through the AEAT channel. It refuses to overwrite an existing file unless you
add `--replace`, and refuses when the output folder does not exist:

```{cli-sequence} modelo-349-export
:verify: Confirm export writes the local file and flags it as not official filing evidence.
```

After you file at the portal, record the local marker, then
[reconcile against the justificante](reconcile.md). The marker needs a pending
filing obligation, so the example starts with the intra-community operations
declared on the profile, as `aeat config profile edit --does-intracomunitario`
does:

```{cli-sequence} modelo-349-file
:verify: Confirm the local filed marker records the quarter without claiming AEAT accepted it.
```

The marker is optional and only applies while the obligation window is open.

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
