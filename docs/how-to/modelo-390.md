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
:seed: iva-year-2025
:verify: Confirm the annual summary passed verification before you export it.
@step Open the annual Modelo 390 work unit for 2025.
aeat --format json app modelo work create --modelo 390 --year 2025 --period 0A
@capture work_unit_id result.work_unit_id
@step Calculate the annual summary from the year's ledger and the filed 303 quarters.
aeat --format json app modelo work calculate {work_unit_id}
@capture calculation_revision_id result.calculation_revision_id
@expect result.casilla_values["iva.anual.cuota-devengada-total"] == "1470.00"
@expect result.casilla_values["iva.anual.reconciliacion.devengada-303"] == "1470.00"
@expect result.casilla_values["iva.anual.cuota-deducible-total"] == "105.00"
@expect result.casilla_values["iva.anual.reconciliacion.deducible-303"] == "105.00"
@expect result.casilla_values["iva.anual.resultado-regimen-general"] == "1365.00"
@expect result.casilla_values["iva.anual.reconciliacion.resultado-303"] == "1365.00"
@step Verify the annual draft; the four filed 303 quarters satisfy the cross-period gate.
@result aeat --format json app modelo work verify {calculation_revision_id}
@expect result.granted_verificado_completo == true
@expect result.completeness_status == "complete"
@expect exit_code == 0
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
@step Record the local filed marker for one 303 quarter, in its obligation window.
@static aeat app modelo work file --modelo 303 --year 2025 --period 1T
```

The second way is to capture or reconcile the official AEAT justificante for each
quarter. `live filed pull-sources` reads filed declarations from AEAT and refuses
when AEAT authentication is not configured (it needs a Cl@ve identity matching
the active profile), so it is a live read shown as a display frame. `reconcile
file` reads a local justificante PDF and never contacts AEAT, but it needs the
real receipt:

```{cli-sequence} modelo-390-external-evidence
@step Pull the filed sources straight from AEAT (a live read).
@static aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A
@step Or reconcile a local justificante PDF against the filed quarter.
@static aeat app modelo reconcile file --modelo 303 --year 2025 --period 1T --file ./303-2025-1T-justificante.pdf
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

For each Modelo 303 period, list revisions with `aeat app modelo work revisions
--modelo 303 --year 2025 --period 1T` and inspect the selected revision with
`aeat app modelo work revision --modelo 303 --year 2025 --period 1T --select
filed`.

If no filed revision exists locally, inspect the current or verified revision
instead with `--select latest-verified` or `--select current`.

Repeat that review for `2T`, `3T`, and `4T`. Pay attention to the values that
Modelo 390 reconciles from Modelo 303:

- `iva.cuota-devengada-total`
- `iva.cuota-deducible-total`
- `iva.resultado-regimen-general`
- `iva.compensacion-generada-periodo`

If a 303 return was filed outside Cadrumo, capture or reconcile the official
evidence before you rely on local values, with `aeat app live filed pull-sources
--modelo 390 --year 2025 --period 0A` or `aeat app modelo reconcile file --modelo
303 --year 2025 --period 1T --file ./303-2025-1T-justificante.pdf`.

Live filed capture is read-only. Reconciliation reads the justificante or
declaration file you supply. These commands help you compare local and external
filing evidence, but the current Modelo 390 calculation path does not make a
fresh AEAT remote-state check a blanket prerequisite for calculation.

For IVA compensation history, use the IVA wallet commands - they support the
compensation carry-forward review; they are not a general Modelo 390
reconciliation gate: inspect the balance with `aeat app modelo iva-wallet balance
--as-of-year 2025`; seed an opening balance with `aeat app modelo iva-wallet seed
--filing-year 2024 --period 4T --amount 0 --confirm`; fix a wrong seed with `aeat
app modelo iva-wallet correct --filing-year 2024 --period 4T --amount 1200.50
--reason "fix opening balance" --confirm`; and review the AEAT-side history with
`aeat app live iva-wallet history` or `aeat app live iva-wallet pull-history
--from-year 2024 --to-year 2025`.

`pull-history` requires both `--from-year` and `--to-year`; it reads filed
Modelo 303 history from AEAT and refuses when AEAT authentication is not
configured.

Use `seed` only when you have a real opening compensation balance from before
the local Modelo 303 history. If you seeded a wrong amount, `correct` overwrites
it (it refuses once an already-filed Modelo 303 has consumed that basis).

## Inspect the annual work unit

Check the saved annual target and its bindings, casillas, and formulas. Add
`--missing` to the bindings listing to focus on unfilled fields. The sequence
below creates the annual draft and inspects its structure; the full-value chain
that folds in the four filed quarters is the "Create, calculate, and verify"
sequence above:

```{cli-sequence} modelo-390-inspect
:verify: Confirm the annual work unit's bindings and formulas read back.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2025-01-01
@setup aeat --format json app modelo work create --modelo 390 --year 2025 --period 0A
@setup aeat --format json app modelo work calculate --modelo 390 --year 2025 --period 0A
@step List every saved work unit on the profile.
aeat app modelo work list
@step Check the annual ledger window.
aeat app ledger preflight --year 2025 --period 0A
@step Inspect the annual work unit's status and bindings.
aeat app modelo work status --modelo 390 --year 2025 --period 0A
aeat app modelo bindings list --modelo 390 --year 2025 --period 0A --missing
@step List the annual casillas.
aeat app modelo casillas 390 --period 0A
@step Track the IVA compensation wallet across the year.
aeat --format json app modelo iva-wallet balance --as-of-year 2025
@step Explain how each annual formula is computed, with its legal references.
@result aeat --format json app modelo formulas 390 --period 0A --explain
@expect exit_code == 0
```

The binding list shows ledger IVA aggregation bindings (source
`ledger_iva_aggregation`) and 303-derived bindings (source `relation_prefill`,
their ids prefixed `modelo-390-prev-303-`). Treat the 303-derived rows as values
that must be reviewed against the prior 303 periods. Do not assume `work
calculate` scans every local 303 work unit, every calculation revision, or every
local filing record automatically.

## Supply reviewed 303-derived values if needed

Check the annual ledger window before calculation with `aeat app ledger preflight
--year 2025 --period 0A` and `aeat app ledger status --year 2025 --period 0A`.

The annual calculation uses the annual ledger window for 390 ledger-backed IVA
aggregates. For 303-derived values, the registry defines the binding IDs and the
source periods. If those binding values are not already available to the
calculation, inspect the missing binding list and supply reviewed values
explicitly, for example `aeat app modelo work calculate --modelo 390 --year 2025
--period 0A --binding modelo-390-prev-303-cuota-devengada-total=<sum-from-303>
--binding modelo-390-prev-303-cuota-deducible-total=<sum-from-303> --binding
modelo-390-prev-303-resultado-regimen-general=<sum-from-303>`.

Use reviewed numbers, not placeholders. If the reviewed 303 history is missing
or inconsistent, stop and repair the 303 evidence before continuing. For
casilla-level review and binding mechanics, see
[Review and supply calculation inputs](review-calculation-values.md).

## Review the annual calculation

Inspect the saved annual revision with `aeat app modelo work revisions --modelo
390 --year 2025 --period 0A` and `aeat app modelo work revision --modelo 390
--year 2025 --period 0A`.

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
spreadsheet review loop when you need a wider calculation surface, then
`compute` and `verify` on the same target with `aeat config google sync calc
export --modelo 390 --year 2025 --period 0A`.

The spreadsheet workflow is a review surface; it does not submit to AEAT.

## Export and file

The verify step in the sequence above promoted the annual draft to
`verificado_completo`. If verification instead reports
`cross_period_dependency_unclean` blocking findings, each named 303 quarter is
missing filed evidence - establish it first (see "What each Modelo 303 quarter
needs before you verify" above), then verify again. Verification does not prove
that AEAT has accepted the filing. Inspect the stored verification report when
you need the detailed result with `aeat app modelo verification-report list
--calculation-revision-id <calculation-revision-id>` and `aeat app modelo
verification-report view <verification-report-id>`.

Export the verified or locally filed revision with `aeat app modelo export
--modelo 390 --year 2025 --period 0A --output ./modelo-390-2025.boe`.

Upload the exported file through AEAT's official channel - the full checklist
is in [Upload your exported modelo at the AEAT portal](file-at-aeat.md). After
filing, record the local marker, review your filing records, and reconcile the
justificante: record the marker with `aeat app modelo work file --modelo 390
--year 2025 --period 0A`, review filing records with `aeat app modelo
filing-record list` and `aeat app modelo filing-record view <filing-record-id>`,
and reconcile with `aeat app modelo reconcile file --modelo 390 --year 2025
--period 0A --file ./390-2025-justificante.pdf`.

`work file` is an internal local marker. It does not submit anything to AEAT. If
the annual return was filed outside this local workflow, import an external
filing record only from official evidence with `aeat app modelo filing-record
import <work-unit-id> --evidence-kind aeat_justificante_pdf --evidence-id
<justificante-or-capture-id> --set <casilla>=<value>`.

If a verification or export workflow creates an evidence bundle, inspect and
archive it with the audit commands: `aeat app modelo audit show <bundle-id>`,
`aeat app modelo audit check <bundle-id>`, `aeat app modelo audit export
<bundle-id> --output ./modelo-390-evidence.zip`, and `aeat app modelo audit
replay <bundle-id>`.

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
