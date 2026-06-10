# Prepare a Modelo 303 IVA filing

Use this guide when the active profile must prepare Modelo 303. Modelo 303 is
the Spanish IVA/VAT self-assessment (`autoliquidacion`) used here to calculate
standard quarterly IVA filings; SII-enrolled profiles use monthly Modelo 303
periods. The registry's official title is "Modelo 303. Impuesto sobre el Valor
Anadido. Autoliquidacion."

`aeat` does not submit Modelo 303 to AEAT. Export creates a local file that you
upload through the official AEAT channel yourself.

## Before you create the draft

Start with the pieces that decide whether Modelo 303 applies and which data can
be calculated:

- [Set up your taxpayer profile](profile-setup.md) and check the active
  profile. Modelo 303 depends on IVA facts such as `--iva-regime`,
  `--iva-sii-enrolled`, `--iva-redeme-enrolled`, ROI/OSS enrollment, activity
  and residence facts, and the active profile bucket.
- If you use AEAT census data, [link Modelo 036 census information](censo-update.md)
  before calculating. Censo facts can affect profile readiness and local
  classifications.
- [Plan your filing calendar](filing-calendar.md) and confirm the period token
  with [Understand filing periods](filing-periods.md). Standard non-exempt
  profiles use quarterly periods such as `1T`; SII-enrolled profiles use
  monthly periods such as `01`.
- [Import or add your transactions](import-bank-statements.md), then
  [classify them](classify-transactions.md). Modelo 303 needs enough IVA detail
  on business rows to route ledger amounts to the right IVA boxes.
- If calculation reports missing inputs, use
  [Review and supply calculation inputs](review-calculation-values.md) before
  forcing manual values into the filing.

## What Modelo 303 calculates

Modelo 303 calculates a period IVA self-assessment: IVA charged to customers
minus deductible IVA paid, plus declared adjustments and prior-period
compensation, to produce the result, payment, refund, and carry-forward
casillas for the period.

In ordinary ledger-backed cases, calculation can combine:

- IVA charged to customers (`IVA repercutido`) from classified income and sales
  rows.
- Deductible IVA paid on purchases and expenses (`IVA soportado`) from
  classified supplier rows.
- IVA categories, rates, directions, taxable bases, IVA amounts, business
  percentage, currency/FX support, and intracommunity/reverse-charge treatment
  recorded on ledger rows.
- Profile facts, including IVA regime and profile-derived values that the
  registry binds into the form.
- Prior Modelo 303 IVA compensation state, when the target period needs pending
  compensation from the previous period.
- Explicit operator inputs, only where the registry or command help says a
  value cannot be derived from the profile, ledger, constants, or saved history.

Do not read that list as "every Modelo 303 box comes from the ledger." Many
casillas remain manual, profile-derived, registry-derived, or sourced from
prior filing history rather than transaction rows.

Classification matters because the calculation does not guess whether a row is
business, personal, mixed-use, deductible, domestic, exempt, intracommunity, or
reverse-charge. Rows that are unclassified or missing required IVA fields can
block calculation or produce missing binding guidance.

## Create the work unit

Create or reuse the saved workspace for the active profile, modelo, filing year,
period, and registry revision:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
```

The command is idempotent for the same visible target. If a work unit already
exists for the active profile, Modelo 303, year, period, and resolved registry
revision, `aeat` returns it instead of creating a duplicate.

Use the same visible target on the later commands:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
```

For routine work, the visible target (`--modelo`, `--year`, `--period`) is all
you need. Reference-number workflows are covered in
[The filing workflow: work units and calculation revisions](filing-spine.md).

## Check the ledger period

The period you pass to the work unit controls the ledger window used by
calculation. Calculation selects ledger rows for the requested modelo, year,
and period through registry bindings and period conversion. The ledger and
modelo surfaces share one grammar: pass the AEAT token with `--year`. For
example, `--year 2026 --period 1T` is the first quarter; monthly token `01`
with `--year 2026` is January.

Check that period before calculating:

```bash
aeat app ledger preflight --year 2026 --period 1T
aeat app ledger status --year 2026 --period 1T
```

The row window uses the transaction operation date: `raw.value_date` when
available, otherwise `raw.booked_date`. The ledger row must also be in an
active lifecycle state and carry enough classification, direction, business
percentage, IVA category/rate/amount, and currency/FX information for the
registry binding that needs it.

The calculation path also runs ledger tax-readiness checks for registry
revisions that use ledger IVA aggregation. Preflight can catch missing IVA
facts, unclassified rows, non-declarable categories, unsupported currencies,
and similar issues before a draft is trusted. Regimen simplificado is treated
differently: those profiles provide the simplificado casillas manually instead
of satisfying the ordinary IVA ledger aggregation preflight.

`aeat` does not silently choose a quarter from today's date. The work unit's
`--year` and `--period` are the target.

## Calculate the draft

Run calculation for the same target:

```bash
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
```

Calculation resolves the registry revision for that work unit, reads the active
profile's bucket-local ledger for the target period, resolves profile and
prior-filing bindings, runs the registry formulas, and saves a draft calculation
revision. At this point the ledger slice is not frozen. The draft stores the
calculated casilla values, typed observations/provenance, binding and input
snapshots, and the contributing `source_transaction_ids`.

Re-running calculation does not edit the previous revision; it saves or reuses
a content-equivalent revision and moves the work unit's current calculation
pointer.

If the command reports missing bindings or missing casillas, inspect them
before adding values:

```bash
aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing
aeat app modelo casillas 303 --period 1T --required
```

Only provide `--binding`, `--casilla`, `--relation`, or Modelo 303-specific
flags when the registry/help output identifies the value you are supplying. For
example, use the IVA compensation wallet commands before relying on a prior
compensation amount:

```bash
aeat app modelo iva-wallet balance --as-of-year 2026
aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm
```

Use `--amount 0` only for a true first Modelo 303 period with no previous
pending IVA compensation.

## Review the calculated values

List saved revisions:

```bash
aeat app modelo work revisions --modelo 303 --year 2026 --period 1T
```

Show the current revision's persisted values:

```bash
aeat app modelo work revision --modelo 303 --year 2026 --period 1T
```

The revision view exposes the revision id and state, persisted casilla values,
typed observations where available, formula ids, operands, legal/source
references, source transaction ids, and, after verification, ledger snapshot and
evidence fields.

For a spreadsheet review loop, see
[Review calculations with Google Sheets](review-with-google-sheets.md). For
manual inputs, bindings, offsets, and revision selection, see
[Review and supply calculation inputs](review-calculation-values.md).

## Verify and export

Verify the selected calculation:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Verification checks the selected draft against the verified-complete contract.
The report exposes the calculation revision id, completeness status, whether
verification was granted or blocked, resolved and missing casillas, findings
with legal/source references where available, and the next action.

On successful verification, `aeat` captures ledger filing snapshot and evidence
over the draft's `source_transaction_ids` and stores it on the verified
revision. That evidence lets later staleness checks detect whether a
contributing ledger row changed or disappeared. It is not a general lock on the
whole ledger, and it does not freeze unrelated rows.

Export the verified or filed revision:

```bash
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

Export writes a local AEAT-compatible fichero-BOE file and reports the output
path, size, checksum, and IDs. It does not contact AEAT. For ledger-derived
revisions, export expects bundled evidence or a resolvable snapshot reference;
do not treat export as a way to bypass missing evidence.

If you need to mark the verified revision as filed in local history after you
submit through AEAT, use the filing workflow guide:

```bash
aeat app modelo work file --modelo 303 --year 2026 --period 1T
```

`work file` is an internal local marker, not an AEAT submission.

## Periods, carry-forward, and unclear cases

Modelo 303 supports quarterly and monthly period tokens in the registry. The
profile determines which cadence appears in the filing calendar: ordinary
non-exempt profiles are quarterly, while SII-enrolled profiles are monthly.

The source-backed behavior is:

- A visible target is always profile bucket + modelo + year + period, with the
  registry revision resolved from that target unless you pass an exact revision.
- Ledger aggregation is bounded by the work unit period, not by a rolling
  automatic slice.
- Prior IVA compensation is sourced from Modelo 303 previous-filing state or
  seeded wallet history, not guessed from the current ledger.
- Verification/file can carry ledger snapshot and evidence for contributing
  rows; verification output does not print the full ledger contents, but the
  contents needed for evidence are preserved through snapshot/evidence records.

Invalid or unsupported period tokens are rejected, and `4T` is distinct from
annual periods such as `0A`. What was not found in the current Modelo 303
operator surface is a Modelo 303-specific double-accounting reconciliation
across periods beyond date-window filtering, source transaction id handling,
import duplicate diagnostics, and finalized-revision staleness/edit guards.

If you are trying to handle an ambiguous period, a rollover between periods, or
possible double accounting, do not invent a workaround in the Modelo 303 guide.
Use exact work-unit or calculation-revision IDs, inspect the saved revisions,
and check [Troubleshooting](troubleshooting.md). If the CLI does not expose the
check you need, report the gap instead of changing ledger data to make the
filing pass.

## Next steps

- [The filing workflow: work units and calculation revisions](filing-spine.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Plan your filing calendar](filing-calendar.md)
- [Reconcile a filing](reconcile.md)
- [Diagnose and repair your local setup](troubleshooting.md)
