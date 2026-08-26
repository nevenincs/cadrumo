# Prepare the annual Modelo 390 IVA summary

Use this guide when the active profile must prepare Modelo 390, the annual
Impuesto sobre el Valor Anadido (IVA) summary. Modelo 390 is an annual return,
but part of its review depends on the same year's periodic Modelo 303 IVA
self-assessments.

Cadrumo does not submit Modelo 390 to the Agencia Estatal de Administración
Tributaria (AEAT). Export creates a local fichero-BOE file that you upload
through the official AEAT channel yourself.

## The filing task

Modelo 390 is the annual summary of your quarterly IVA filings. To prepare it:

1. Prepare and review the four quarterly Modelo 303 periods first.
2. Create a Modelo 390 draft for the annual period (`--period 0A`).
3. Calculate the annual summary from your year's ledger and the 303 values.
4. Review the calculated totals against your quarterly records.
5. Verify the draft is complete.
6. Export the annual file.
7. Upload the file at the AEAT portal yourself and keep the justificante.

The rest of this guide walks through these steps with the checks each one
needs. To understand how the tool organises the filing work behind the
commands, read
[The filing workflow](filing-spine.md)
after this guide.

## Create, calculate, and verify the annual draft

**Requirement:** a valid taxpayer profile. Create one with `aeat config profile
create <name>`. See [Set up your taxpayer profile](profile-setup.md).

The preparation below files the four 2025 Modelo 303 quarters locally, so the
annual summary can fold them in, then creates the Modelo 390 draft for 2025,
calculates it, and verifies it. The example uses 2025 because the annual return
needs the year's four quarters already filed:

```{cli-sequence} modelo-390-annual-2025
:verify: Confirm the annual summary passed verification before you export it.
```

Verify grants verified-complete and reports non-blocking advisories: the four
quarters are filed locally but carry no external AEAT justificante yet, so the
tool discloses that the annual reconciliation rests on local-only evidence. That
disclosure is correct - a locally-filed quarter is honest evidence for the
annual fold-in, and the advisory tells you where an official justificante would
strengthen the record. In this example the four quarters charged 1470.00 of IVA
between them (420 + 315 + 210 + 525) and the year carries 105.00 of deductible
input IVA (one evidenced purchase, 500 base at 21%), so the annual cuota
devengada is 1470.00, the deducible total is 105.00, and the régimen-general
result is 1365.00 (1470.00 − 105.00) - the full annual IVA equation, each figure
matching the sum of the quarters (the reconciliation invariant). Input IVA counts
only once the purchase carries linked invoice evidence. The rest of this guide
explains each stage and the checks around it.

## Setup steps before you start

Start with the local filing context:

- [Set up your taxpayer profile](profile-setup.md) and check the active profile.
- Check the census facts in your profile first with
  [Maintain Modelo 036 census facts in your profile](censo-update.md).
- Use [Plan your filing calendar](filing-calendar.md) to confirm the annual
  filing window.
- Confirm the annual period token with
  [Period tokens and dates](filing-calendar.md#period-tokens-and-dates).
  Modelo 390 uses `--period 0A`.
- [Import or add your transactions](import-bank-statements.md), then
  [classify them](classify-transactions.md). The annual ledger totals depend on
  the active profile's classified IVA rows.
- Prepare the same year's Modelo 303 periods first. Standard quarterly profiles
  use `1T`, `2T`, `3T`, and `4T`; monthly IVA-liquidation cases need extra
  review because the current Modelo 390 bindings are modelled against the
  quarterly 303 periods.
- Finish the Modelo 303 review path before relying on its values. See
  [Prepare a Modelo 303 IVA filing](modelo-303.md).

Modelo 390 combines two kinds of values:

- annual IVA ledger aggregates for the full filing year (binding source
  `ledger_iva_aggregation`)
- 303-derived values pulled from the same year's quarters (binding source
  `relation_prefill`, reported by verification findings as
  `origin=registry_relation`), where the registry names the 303 casillas and
  periods that feed the annual summary

The 303-derived inputs depend on each quarter's filed evidence. Verification
hard-blocks until that evidence is present (see "What each Modelo 303 quarter
needs before you verify" below). The CLI does not guarantee that remote AEAT
history is current, captured, or reconciled.

The implemented 390 registry bindings include 303 quarter sums for annual
devengada, deducible, and regimen-general result reconciliation. They also
include compensation values copied or summed from the same year's 303 periods.

(what-each-modelo-303-quarter-needs-before-you-verify)=
## What each Modelo 303 quarter needs before you verify

Modelo 390 verification depends on the four quarterly Modelo 303 returns.
`work calculate` for Modelo 390 produces a draft, but `work verify` hard-blocks
with `cross_period_dependency_unclean` blocking findings until each 303 quarter
(`1T`, `2T`, `3T`, `4T`) has stored *filed* evidence. A calculated or verified
303 draft is not enough: the gate reports
`blockers=missing_observation, missing_current_filing_record` for every quarter
that lacks a filed record.

Establish each quarter's evidence one of two ways before you verify Modelo 390.

The first way is to mark each 303 quarter as filed locally, while its AEAT
filing-obligation window is open. Prepare and verify each quarter (see
[Prepare a Modelo 303 IVA filing](modelo-303.md)), then record each one with the
local filed marker, repeating for `1T`, `2T`, `3T`, and `4T`. `work file`
records the filing locally only; it does not submit to AEAT, and it refuses
outside the obligation window:

```{cli-sequence} modelo-390-file-quarter
```

The second way is to capture or reconcile the official AEAT justificante for each
quarter. `live filed pull-sources` reads filed declarations from AEAT and refuses
when AEAT authentication is not configured (it needs a Cl@ve identity matching
the active profile), so it is a live read shown as a display frame. `reconcile
file` reads a local justificante PDF and never contacts AEAT, but it needs the
real receipt:

```{cli-sequence} modelo-390-external-evidence
```

If you cannot establish a quarter's evidence, do not force the annual return
past the block. Repair the missing 303 evidence first, or report the gap.

## Check each visible filing target

Use the same active profile for every command. Inspect the four 303 filing
targets before you work on the annual target, repeating the `work status` check
for each of `1T`, `2T`, `3T`, and `4T`, and list all saved work with `work list`
to see the broader filing surface (the inspect sequence under "Inspect the
annual work unit" below runs `work list` and the annual `work status`).

No command switches a current filing target for you. To move from one quarter
to another, change `--period`. To move from the quarterly 303 review to the
annual 390 review, change both `--modelo` and `--period`.

## Review the 303 values that feed Modelo 390

For each Modelo 303 period, list its saved revisions and inspect the filed one.
These reads resolve the year's filed 303 quarters, which the single-seed
documentation sandbox reproduces in the annual chain above, so here they are
shown as display frames. If no filed revision exists locally, inspect the current
or verified revision instead with `--select latest-verified` or `--select
current`:

```{cli-sequence} modelo-390-review-303
```

Repeat that review for `2T`, `3T`, and `4T`. Pay attention to the values that
Modelo 390 reconciles from Modelo 303:

- `iva.cuota-devengada-total`
- `iva.cuota-deducible-total`
- `iva.resultado-regimen-general`
- `iva.compensacion-generada-periodo`

If a 303 return was filed outside Cadrumo, capture or reconcile the official
evidence before you rely on local values, with the `live filed pull-sources` or
`reconcile import` commands shown under
[What each Modelo 303 quarter needs](#what-each-modelo-303-quarter-needs-before-you-verify)
above. Live filed capture is read-only; reconciliation reads the justificante or
declaration file you supply. The current Modelo 390 calculation path does not
make a fresh AEAT remote-state check a blanket prerequisite for calculation.

For IVA compensation history, use the IVA wallet commands; they support the
compensation carry-forward review but are not a general Modelo 390 reconciliation
gate. Inspect the balance with the `iva-wallet balance` frame in the inspect
sequence above. Seed an opening balance, or fix a wrong seed, or review the
AEAT-side history with the following commands. Seeding and correcting mutate
stored history, and the history reads reach AEAT, so they are shown as display
frames:

```{cli-sequence} modelo-390-wallet
:verify: Confirm the opening compensation balance seeds.
```

`pull-history` requires both `--from-year` and `--to-year`; it reads filed
Modelo 303 history from AEAT and refuses when AEAT authentication is not
configured. Use `seed` only when you have a real opening compensation balance
from before the local Modelo 303 history.

## Inspect the annual work unit

Check the saved annual target and its bindings, casillas, and formulas. Add
`--missing` to the bindings listing to focus on unfilled fields. The sequence
below creates the annual draft and inspects its structure; the full-value chain
that folds in the four filed quarters is the "Create, calculate, and verify"
sequence above:

```{cli-sequence} modelo-390-inspect
:verify: Confirm the annual work unit's bindings and formulas read back.
```

The binding list shows ledger IVA aggregation bindings (source
`ledger_iva_aggregation`) and 303-derived bindings (source `relation_prefill`,
their ids prefixed `modelo-390-prev-303-`). Treat the 303-derived rows as values
that must be reviewed against the prior 303 periods. Do not assume `work
calculate` scans every local 303 work unit, every calculation revision, or every
local filing record automatically.

## Supply reviewed 303-derived values if needed

Check the annual ledger window before calculation with the `ledger preflight`
and `ledger status` frames in the inspect sequence above.

The annual calculation uses the annual ledger window for 390 ledger-backed IVA
aggregates. For 303-derived values, the registry defines the binding IDs and the
source periods. If those binding values are not already available to the
calculation, inspect the missing binding list and supply reviewed values
explicitly. The reviewed sums come from your own 303 review; the example below
passes the ones this guide's year produces (1470.00 devengada, 105.00 deducible,
1365.00 régimen-general), and its preparation only creates the annual draft, so
the annual ledger totals stay at zero while the reconciliation casillas carry the
supplied figures:

```{cli-sequence} modelo-390-supply-binding
:verify: Confirm the supplied 303-derived values land on the annual reconciliation casillas.
```

Use reviewed numbers, not placeholders. If the reviewed 303 history is missing
or inconsistent, stop and repair the 303 evidence before continuing. For
casilla-level review and binding mechanics, see
[Review and supply calculation inputs](review-calculation-values.md).

## Review the annual calculation

Inspect the saved annual revisions with the `work revisions` and `work revision`
frames in the inspect sequence above.

Compare the annual totals with the 303 reconciliation values:

- `iva.anual.cuota-devengada-total` should be reviewed against
  `iva.anual.reconciliacion.devengada-303`.
- `iva.anual.cuota-deducible-total` should be reviewed against
  `iva.anual.reconciliacion.deducible-303`.
- `iva.anual.resultado-regimen-general` should be reviewed against
  `iva.anual.reconciliacion.resultado-303`.

If the annual ledger totals and 303-derived reconciliation values diverge, do
not force the 390 to pass first. Review the annual ledger window, each 303
revision, any official justificantes, and the supplied 390 bindings. Use the
spreadsheet review loop when you need a wider calculation surface, then `compute`
and `verify` on the same target. The spreadsheet export reaches Google, so it is
shown as a display frame:

```{cli-sequence} modelo-390-sheets-export
```

The spreadsheet workflow is a review surface; it does not submit to AEAT.

## Export and file

The verify step in the sequence above promoted the annual draft to
`verificado_completo`. If verification instead reports
`cross_period_dependency_unclean` blocking findings, each named 303 quarter is
missing filed evidence; establish it first (see
[What each Modelo 303 quarter needs](#what-each-modelo-303-quarter-needs-before-you-verify)
above), then verify again. Verification does not prove that AEAT has accepted the
filing. Inspect the stored verification report by id when you need the detailed
result:

```{cli-sequence} modelo-390-verification-report
```

Export the verified or locally filed revision. Export needs the four filed 303
quarters' evidence, which the single-seed sandbox demonstrates in the annual
chain above, so the export and the post-portal steps here are display frames:

```{cli-sequence} modelo-390-export-file
```

Upload the exported file through AEAT's official channel; the full checklist is
in [File your modelo at the AEAT portal](file-at-aeat.md). Review your
filing records with `filing-record list` and `filing-record view`. `work file`
is an internal local marker; it does not submit anything to AEAT. The listing
below runs in a sandbox that filed nothing, so it reports no records; your own
listing carries one row per filing you recorded. If the annual return was filed
outside this local workflow, import an external filing record only from official
evidence. That import needs the official receipt, and the evidence-bundle read
beneath it addresses a bundle by id, so both stay display frames:

```{cli-sequence} modelo-390-records-audit
:verify: Confirm the local filing records read back.
```

## What Modelo 390 does not check for you

The current implementation supports Modelo 390's annual 303 reconciliation in
the registry, but it does not enforce every operational policy you might want
for a dependable annual filing workflow.

Use these limits when deciding how much evidence to review:

- Modelo 390 does not look at all local filing history regardless of state.
  303-derived resolution is keyed by modelo, filing year, and period.
- The calculate-time resolver and the verify gate treat 303 evidence
  differently. The resolver that prefills 303-derived values does not apply a
  lifecycle-state filter, so `work calculate` can produce a draft. The verify
  gate is stricter: it blocks until each 303 quarter has a filed record or a
  captured/reconciled AEAT justificante (see "What each Modelo 303 quarter needs
  before you verify").
- The annual `work calculate` path should not be treated as a general "latest
  active 303 revision" selector. Use `work revision --select filed`,
  `latest-verified`, or exact revision IDs when you need a specific 303 value.
- Local `work file` records, AEAT captured filed observations, and justificante
  reconciliation are related but separate evidence surfaces. The current CLI
  does not require them to be in sync before every Modelo 390 calculation.
- Missing 303 history can leave 390 303-derived bindings unavailable or force
  operator-supplied reviewed values. Calculation can still produce a draft, but
  verify blocks until the missing quarters have filed evidence.
- Remote AEAT state is not binding unless you explicitly capture or reconcile
  it in the workflow you are running.

For a conservative annual close, calculate and review every 303 period, reconcile
official evidence where available, inspect the 390 303-derived bindings, and
verify the annual draft before export. If the CLI does not expose the check you
need, report that gap instead of documenting it as enforced behavior.

## Next steps

- [Prepare a Modelo 303 IVA filing](modelo-303.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Review calculations with Google Sheets](review-with-google-sheets.md)
- [How to reconcile a filed Modelo against its justificante](reconcile.md)
- [The filing workflow](filing-spine.md)
- [Diagnose and repair your local setup](troubleshooting.md)
- [CLI reference](../cli/index.rst)
