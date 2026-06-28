# Prepare the annual Modelo 390 IVA summary

Use this guide when the active profile must prepare Modelo 390, the annual
Impuesto sobre el Valor Anadido (IVA) summary. Modelo 390 is an annual return,
but part of its review depends on the same year's periodic Modelo 303 IVA
self-assessments.

`aeat` does not submit Modelo 390 to the Agencia Estatal de Administracion
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
[The filing workflow: work units and calculation revisions](filing-spine.md)
after this guide.

## Setup steps before you start

Start with the local filing context:

- [Set up your taxpayer profile](profile-setup.md) and check the active profile.
- If you use AEAT census data, update the local profile first with
  [Link Modelo 036 census information](censo-update.md).
- Use [Plan your filing calendar](filing-calendar.md) to confirm the annual
  filing window.
- Confirm the annual period token with
  [Understand filing periods](filing-periods.md). Modelo 390 uses `--period 0A`.
- [Import or add your transactions](import-bank-statements.md), then
  [classify them](classify-transactions.md). The annual ledger totals depend on
  the active profile's classified IVA rows.
- Prepare the same year's Modelo 303 periods first. Standard quarterly profiles
  use `1T`, `2T`, `3T`, and `4T`; SII/monthly cases need extra review because
  the current Modelo 390 bindings are modelled against the quarterly 303
  periods.
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
hard-blocks until that evidence is present (see "The 303 evidence the verify
gate requires" below). The CLI does not guarantee that remote AEAT history is
current, captured, or reconciled.

The implemented 390 registry bindings include 303 quarter sums for annual
devengada, deducible, and regimen-general result reconciliation. They also
include compensation values copied or summed from the same year's 303 periods.

## The 303 evidence the verify gate requires

Modelo 390 verification depends on the four quarterly Modelo 303 returns.
`work calculate` for Modelo 390 produces a draft, but `work verify` hard-blocks
with `cross_period_dependency_unclean` blocking findings until each 303 quarter
(`1T`, `2T`, `3T`, `4T`) has stored *filed* evidence. A calculated or verified
303 draft is not enough: the gate reports
`blockers=missing_observation, missing_current_filing_record` for every quarter
that lacks a filed record.

Establish each quarter's evidence one of two ways before you verify Modelo 390:

- Mark each 303 quarter as filed locally, while its AEAT filing-obligation
  window is open. Prepare and verify each quarter (see
  [Prepare a Modelo 303 IVA filing](modelo-303.md)), then:

  ```bash
  aeat app modelo work file --modelo 303 --year 2025 --period 1T
  ```

  `work file` records the filing locally only; it does not submit to AEAT, and
  it refuses outside the obligation window.

- Capture or reconcile the official AEAT justificante for each quarter:

  ```bash
  aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A
  aeat app modelo reconcile file --modelo 303 --year 2025 --period 1T \
    --file ./303-2025-1T-justificante.pdf
  ```

  `live filed pull-sources` reads filed declarations from AEAT and refuses when
  AEAT authentication is not configured (it needs a Cl@ve identity matching the
  active profile). `reconcile file` reads a local justificante PDF and never
  contacts AEAT.

If you cannot establish a quarter's evidence, do not force the annual return
past the block. Repair the missing 303 evidence first, or report the gap.

## Check each visible filing target

Use the same active profile for every command. Inspect the four 303 filing
targets before you work on the annual target:

```bash
aeat config profile status

aeat app modelo work status --modelo 303 --year 2025 --period 1T
aeat app modelo work status --modelo 303 --year 2025 --period 2T
aeat app modelo work status --modelo 303 --year 2025 --period 3T
aeat app modelo work status --modelo 303 --year 2025 --period 4T
```

List all saved work when you need to see the active profile's broader filing
surface:

```bash
aeat app modelo work list
```

No command switches a current filing target for you. To move from one quarter
to another, change `--period`. To move from the quarterly 303 review to the
annual 390 review, change both `--modelo` and `--period`.

## Review the 303 values that feed Modelo 390

For each Modelo 303 period, list revisions and inspect the selected revision:

```bash
aeat app modelo work revisions --modelo 303 --year 2025 --period 1T
aeat app modelo work revision --modelo 303 --year 2025 --period 1T --select filed
```

If no filed revision exists locally, inspect the current or verified revision
instead:

```bash
aeat app modelo work revision --modelo 303 --year 2025 --period 1T --select latest-verified
aeat app modelo work revision --modelo 303 --year 2025 --period 1T --select current
```

Repeat that review for `2T`, `3T`, and `4T`. Pay attention to the values that
Modelo 390 reconciles from Modelo 303:

- `iva.cuota-devengada-total`
- `iva.cuota-deducible-total`
- `iva.resultado-regimen-general`
- `iva.compensacion-generada-periodo`

If a 303 return was filed outside `aeat`, capture or reconcile the official
evidence before you rely on local values:

```bash
aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A
aeat app modelo reconcile file --modelo 303 --year 2025 --period 1T --file ./303-2025-1T-justificante.pdf
```

Live filed capture is read-only. Reconciliation reads the justificante or
declaration file you supply. These commands help you compare local and external
filing evidence, but the current Modelo 390 calculation path does not make a
fresh AEAT remote-state check a blanket prerequisite for calculation.

For IVA compensation history, use the IVA wallet commands. They support the
compensation carry-forward review; they are not a general Modelo 390
reconciliation gate:

```bash
aeat app modelo iva-wallet balance --as-of-year 2025
aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm
aeat app modelo iva-wallet correct --filing-year 2024 --period 4T --amount 1200.50 --reason "fix opening balance" --confirm
aeat app live iva-wallet history
aeat app live iva-wallet pull-history --from-year 2024 --to-year 2025
```

`pull-history` requires both `--from-year` and `--to-year`; it reads filed
Modelo 303 history from AEAT and refuses when AEAT authentication is not
configured.

Use `seed` only when you have a real opening compensation balance from before
the local Modelo 303 history. If you seeded a wrong amount, `correct` overwrites
it (it refuses once an already-filed Modelo 303 has consumed that basis).

## Create the annual work unit

Create or reuse the annual Modelo 390 work unit:

```bash
aeat app modelo work create --modelo 390 --year 2025 --period 0A
```

Check the saved annual target:

```bash
aeat app modelo work status --modelo 390 --year 2025 --period 0A
aeat app modelo work history --modelo 390 --year 2025 --period 0A
aeat app modelo bindings list --modelo 390 --year 2025 --period 0A
aeat app modelo bindings list --modelo 390 --year 2025 --period 0A --missing
aeat app modelo casillas 390 --period 0A
aeat app modelo formulas 390 --period 0A --explain
```

The binding list shows ledger IVA aggregation bindings (source
`ledger_iva_aggregation`) and 303-derived bindings (source `relation_prefill`,
their ids prefixed `modelo-390-prev-303-`). Treat the 303-derived rows as values
that must be reviewed against the prior 303 periods. Do not assume `work
calculate` scans every local 303 work unit, every calculation revision, or every
local filing record automatically.

## Calculate the annual draft

Check the annual ledger window before calculation:

```bash
aeat app ledger preflight --year 2025 --period 0A
aeat app ledger status --year 2025 --period 0A
```

Run the annual calculation:

```bash
aeat app modelo work calculate --modelo 390 --year 2025 --period 0A
```

The calculation uses the annual ledger window for 390 ledger-backed IVA
aggregates. For 303-derived values, the registry defines the binding IDs and the
source periods. If those binding values are not already available to the
calculation, inspect the missing binding list and supply reviewed values
explicitly:

```bash
aeat app modelo work calculate --modelo 390 --year 2025 --period 0A \
  --binding modelo-390-prev-303-cuota-devengada-total=<sum-from-303> \
  --binding modelo-390-prev-303-cuota-deducible-total=<sum-from-303> \
  --binding modelo-390-prev-303-resultado-regimen-general=<sum-from-303> \
  --binding modelo-390-prev-303-compensacion-ultimo-periodo=<value-from-303-4T> \
  --binding modelo-390-prev-303-compensacion-generada-ejercicio-no-97=<sum-from-303-1T-to-3T>
```

Use reviewed numbers, not placeholders. If the reviewed 303 history is missing
or inconsistent, stop and repair the 303 evidence before continuing. For
casilla-level review and binding mechanics, see
[Review and supply calculation inputs](review-calculation-values.md).

## Review the annual calculation

Inspect the saved annual revision:

```bash
aeat app modelo work revisions --modelo 390 --year 2025 --period 0A
aeat app modelo work revision --modelo 390 --year 2025 --period 0A
```

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
spreadsheet review loop when you need a wider calculation surface:

```bash
aeat config google sync calc export --modelo 390 --year 2025 --period 0A
aeat config google sync calc compute --modelo 390 --year 2025 --period 0A --spreadsheet-id <spreadsheet-id>
aeat config google sync calc verify --modelo 390 --year 2025 --period 0A
```

The spreadsheet workflow is a review surface. It does not submit to AEAT.

## Verify and export

Verify the annual draft:

```bash
aeat app modelo work verify --modelo 390 --year 2025 --period 0A
```

If verification reports `cross_period_dependency_unclean` blocking findings,
each named 303 quarter is missing filed evidence. Establish it first (see
"The 303 evidence the verify gate requires" above), then verify again. If
verification reports missing casillas, missing bindings, or other findings, fix
the source data or reviewed inputs and calculate again. Verification promotes a
complete draft to `verificado_completo`; it does not prove that AEAT has accepted
the filing.

Inspect the stored verification report when you need the detailed result:

```bash
aeat app modelo verification-report list --calculation-revision-id <calculation-revision-id>
aeat app modelo verification-report view <verification-report-id>
```

Export the verified or locally filed revision:

```bash
aeat app modelo export --modelo 390 --year 2025 --period 0A --output ./modelo-390-2025.boe
```

Upload the exported file through AEAT's official channel - the full checklist
is in [Upload your exported modelo at the AEAT portal](file-at-aeat.md). After
filing, keep the justificante and reconcile it locally:

```bash
aeat app modelo work file --modelo 390 --year 2025 --period 0A
aeat app modelo filing-record list
aeat app modelo filing-record view <filing-record-id>
aeat app modelo reconcile file --modelo 390 --year 2025 --period 0A --file ./390-2025-justificante.pdf
```

`work file` is an internal local marker. It does not submit anything to AEAT.
If the annual return was filed outside this local workflow, import an external
filing record only from official evidence:

```bash
aeat app modelo filing-record import <work-unit-id> \
  --evidence-kind aeat_justificante_pdf \
  --evidence-id <justificante-or-capture-id> \
  --set <casilla>=<value>
```

If a verification or export workflow creates an evidence bundle, inspect and
archive it with the audit commands:

```bash
aeat app modelo audit show <bundle-id>
aeat app modelo audit check <bundle-id>
aeat app modelo audit export <bundle-id> --output ./modelo-390-evidence.zip
aeat app modelo audit replay <bundle-id>
```

## Current policy limits

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
  captured/reconciled AEAT justificante (see "The 303 evidence the verify gate
  requires").
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
- [The filing workflow: work units and calculation revisions](filing-spine.md)
- [Diagnose and repair your local setup](troubleshooting.md)
- [CLI reference](../cli/index.rst)
