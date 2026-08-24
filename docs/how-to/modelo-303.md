# Prepare a Modelo 303 IVA filing

Use this guide when the active profile must prepare Modelo 303. Modelo 303 is
the Spanish IVA self-assessment (`autoliquidacion`) used here to calculate
standard quarterly IVA filings; monthly IVA-liquidation profiles such as REDEME
or large-company taxpayers use monthly Modelo 303 periods. Voluntary SII
enrolment alone remains quarterly. The registry's official title is "Modelo 303.
Impuesto sobre el Valor Anadido. Autoliquidacion."

Cadrumo does not submit Modelo 303 to the Agencia Estatal de Administración
Tributaria (AEAT). Its registry carries the filing layout, but `export`
currently refuses because the product has no reviewed AEAT product/software
identity authority with which to stamp the envelope. Read the calculated box
values back and enter them through the official AEAT channel yourself.

The tool needs a master-key passphrase and prompts for it.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your
profile](profile-setup.md) walks through it step by step.

## The complete first-quarter chain

This is the full path from a classified, evidenced ledger to a filed quarter for
a first-period filer. The preparation below sets up a self-employed profile,
classifies the quarter's income and expense rows, and attaches the supplier's
purchase invoice as encrypted evidence. The sequence then creates the draft,
calculates it, verifies it, and records the local filed marker. Each
load-bearing detail is explained under the sequence.

The Modelo 303 export step refuses until reviewed product/software identity
authority is available. Enter the calculated box values at the AEAT portal, as
[File your modelo at the AEAT portal](file-at-aeat.md) describes.

```{cli-sequence} modelo-303-first-quarter
:verify: Confirm the draft verifies, files locally, and the export refuses.
```

Load-bearing details:

- Create the profile with `--quiet` for the non-interactive form. A bare
  `aeat config profile create me` opens an interactive wizard. The profile MUST
  carry `--name` and `--surnames`, or filing later refuses with "requires the
  operator name".
- `--activity-start-date 2026-01-01` scopes the prior-period dependency out for
  a first period. Without it, verify blocks on the previous quarter.
- `ledger add --amount` is the GROSS amount (`--taxable-base` + `--iva-amount`).
  Here `1000 + 210 = 1210` and `500 + 105 = 605`. The tool enforces that the
  taxable base plus IVA equals the gross to the cent.
- A deductible-expense row needs `--category-id`. List the valid ids with
  `aeat app ledger categories`. The example uses `material_oficina`.
- Calculation charges 210.00 of IVA on the sale (`IVA repercutido`) and deducts
  105.00 on the purchase (`IVA soportado`), so casilla 71 (Resultado final) is
  105.00, the IVA due for the quarter. The deductible IVA counts at calculate
  time; the attached invoice evidence is what lets the row be *filed*, not what
  changes the figure.
- Attach the purchase invoice as evidence *before* you verify. Verification
  finalizes the revision and captures a snapshot over the contributing rows, so
  the evidence must already be on the expense row. A locked row cannot take a
  late attachment.
- `verify` reports `completeness complete` and `granted true`, and `work file`
  writes the local filed marker. `export` refuses because its envelope cannot
  be stamped without reviewed product/software identity authority.
- Casilla 65 ("% atribuible a la Administración del Estado") resolves to 100
  automatically for a común-territory profile, so casilla 66 and the headline
  casilla 71 (Resultado final) carry the full régimen-general result. This tool
  supports común-territory profiles only; foral regimes are refused at profile
  creation.

The rest of this guide explains each step and the checks around it.

## Before you create the draft

Start with the pieces that decide whether Modelo 303 applies and which data can
be calculated:

- [Set up your taxpayer profile](profile-setup.md) and check the active
  profile. Modelo 303 depends on IVA facts such as `--iva-regime`,
  `--iva-sii-enrolled`, `--iva-redeme-enrolled`, ROI/OSS enrollment, activity
  and residence facts, and the active profile.
- Check your census facts before calculating - see
  [Maintain Modelo 036 census facts in your profile](censo-update.md). Censo
  facts can affect profile readiness and local classifications.
- [Plan your filing calendar](filing-calendar.md) and confirm the period token
  with [Period tokens and dates](filing-calendar.md#period-tokens-and-dates).
  Standard non-exempt
  profiles use quarterly periods such as `1T`; monthly IVA-liquidation profiles
  such as REDEME or large-company taxpayers use monthly periods such as `01`.
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

When you add a row by hand, pass the GROSS amount on `--amount` and the IVA
detail explicitly with `aeat app ledger add`. The complete-chain sequence above
runs this from the seed ledger.

`--amount` is `--taxable-base` plus `--iva-amount`, and the tool refuses the row
if they do not match to the cent. A deductible-expense row also needs a
`--category-id`; list the valid ids with `aeat app ledger categories`.

## Create the work unit

Create or reuse the saved workspace for the active profile, modelo, filing year,
period, and registry revision. This needs an active profile; create one first
if you have none with `aeat config profile create`, then open the work unit with
`aeat app modelo work create`. Both run in the complete-chain sequence above.

The command is idempotent for the same visible target. If a work unit already
exists for the active profile, Modelo 303, year, period, and resolved registry
revision, Cadrumo returns it instead of creating a duplicate.

Use the same visible target on the later commands, for example `aeat app modelo
work status`.

For routine work, the visible target (`--modelo`, `--year`, `--period`) is all
you need. Reference-number workflows are covered in
[The filing workflow](filing-spine.md).

## Check the ledger period

The period you pass to the work unit controls the ledger window used by
calculation. Calculation selects ledger rows for the requested modelo, year,
and period through registry bindings and period conversion. The ledger and
modelo surfaces share one grammar: pass the AEAT token with `--year`. For
example, `--year 2026 --period 1T` is the first quarter; monthly token `01`
with `--year 2026` is January.

Check that period before calculating:

```{cli-sequence} modelo-303-ledger-period
:verify: Confirm the quarter's ledger reads back ready to calculate.
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

Cadrumo does not silently choose a quarter from today's date. The work unit's
`--year` and `--period` are the target.

## Calculate the draft

Run calculation for the same target with `aeat app modelo work calculate`. The
complete-chain sequence above runs this.

Calculation resolves the registry revision for that work unit, reads the active
profile's ledger for the target period, resolves profile and
prior-filing bindings, runs the registry formulas, and saves a draft calculation
revision. At this point the ledger slice is not frozen. The draft stores the
calculated casilla values, typed observations/provenance, binding and input
snapshots, and the contributing `source_transaction_ids`.

Re-running calculation does not edit the previous revision; it saves or reuses
a content-equivalent revision and moves the work unit's current calculation
pointer.

If the command reports missing bindings or missing casillas, inspect them
before adding values:

```{cli-sequence} modelo-303-inspect-boxes
:verify: Confirm the draft's missing bindings and the modelo's required casillas read back.
```

Only provide `--binding`, `--casilla`, `--relation`, or Modelo 303-specific
flags when the registry/help output identifies the value you are supplying. For
example, inspect the IVA compensation wallet before relying on a prior
compensation amount:

```{cli-sequence} modelo-303-wallet
:verify: Confirm the IVA compensation wallet seeds and reads back its balance.
```

Use `--amount 0` only for a true first Modelo 303 period with no previous
pending IVA compensation.

## Review the calculated values

List the saved revisions, then show the current revision's persisted values:

```{cli-sequence} modelo-303-revision
:verify: Confirm the saved revisions and the current revision's values read back.
```

The revision view exposes the revision id and state, persisted casilla values,
typed observations where available, formula ids, operands, legal/source
references, source transaction ids, and, after verification, ledger snapshot and
evidence fields.

For a spreadsheet review loop, see
[Review calculations with Google Sheets](review-with-google-sheets.md). For
manual inputs, bindings, offsets, and revision selection, see
[Review and supply calculation inputs](review-calculation-values.md).

## Verify and file

Verify the selected calculation with `aeat app modelo work verify`. The
complete-chain sequence above runs verify and file end to end.

Verification checks the selected draft against the verified-complete contract.
The report exposes the calculation revision id, completeness status, whether
verification was granted or blocked, resolved and missing casillas, findings
with legal/source references where available, and the next action.

On successful verification, Cadrumo captures ledger filing snapshot and evidence
over the draft's `source_transaction_ids` and stores it on the verified
revision. That evidence lets later staleness checks detect whether a
contributing ledger row changed or disappeared. It is not a general lock on the
whole ledger, and it does not freeze unrelated rows.

`aeat app modelo export` refuses for Modelo 303 while Cadrumo has no reviewed
AEAT product/software identity authority. That identity is a product-release
fact, not taxpayer or presenter data, so the command never guesses it from the
active profile. No upload file is produced without that authority.

Read the verified figures back with `aeat app modelo work revision` and enter
them at the AEAT portal. Verification, the local filed marker, and the evidence
capture described above all still apply.

If you need to mark the verified revision as filed in local history after you
submit through AEAT, record the local marker with `aeat app modelo work file`.
`work file` is an internal local marker, not an AEAT submission.

## Periods, carry-forward, and special cases

Modelo 303 supports quarterly and monthly period tokens in the registry. The
profile determines which cadence appears in the filing calendar: ordinary
non-exempt profiles are quarterly, while monthly IVA-liquidation profiles such
as REDEME or large-company taxpayers are monthly. Voluntary SII enrolment by
itself does not switch Modelo 303 from quarterly to monthly.

The source-backed behavior is:

- A visible target is always profile + modelo + year + period, with the
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

- [The filing workflow](filing-spine.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Plan your filing calendar](filing-calendar.md)
- [Reconcile a filing](reconcile.md)
- [Diagnose and repair your local setup](troubleshooting.md)
