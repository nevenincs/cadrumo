# Check that a filing is ready

Verification tells you whether a draft's box values pass the registry rules.
Readiness asks an earlier question: is everything the calculation depends on
in place — profile facts, transaction data, and earlier filings? Use the
commands in this guide before you calculate, and again before you export, so
nothing silent is missing underneath a clean-looking draft.

## Run the readiness report

Report whether the active profile is ready for one modelo, year, and period:

```bash
aeat app modelo readiness --modelo 303 --year 2026 --period 1T --revision-id <revision-id>
```

Find the revision id first — it is listed by:

```bash
aeat app modelo describe 303 --year 2026 --period 1T
```

The report covers two things:

- **Profile readiness** — every profile fact the modelo requires. Each
  missing fact is listed by its section and field key, so you know exactly
  what to fill in with `aeat config profile edit`.
- **Ledger readiness** — for ledger-fed modelos, the same source checks as
  `aeat app ledger preflight`, listing each transaction that blocks the
  period and why.

Readiness does not check box-level completeness of a draft — that is what
`aeat app modelo work verify` does. See
[Verify a filing](verification-reports.md).

## Check what this filing depends on

Some modelos fold in values from other filings — an annual summary reads its
quarters, a cross-modelo box reads another form's result. List the
registry-declared dependencies for a filing year:

```bash
aeat app modelo work dependencies --year 2026
```

Narrow to one modelo, or to one modelo and period:

```bash
aeat app modelo work dependencies --year 2026 --modelo 390
aeat app modelo work dependencies --year 2026 --modelo 390 --period 0A
```

`--period` requires `--modelo`. With both set, the command also evaluates the
current blockers for that exact filing — for example an earlier period whose
official evidence is still missing — so you see what must be resolved before
this period can safely build on the ones before it. For the background, see
[Building on earlier filings](../explanation/building-on-earlier-filings.md).

## Audit the lifecycle of a modelo

Stream every recorded lifecycle event — calculations, verification passes
and refusals, filings, amendments, imports — for one modelo:

```bash
aeat app modelo history --modelo 303 --year 2026
```

Add `--period` to narrow to one period. This is the modelo-wide audit trail;
for the event stream of a single workspace, use
`aeat app modelo work history` — see
[How the tool organises your filing work](filing-spine.md).

## Compare two filing years

See how this year's figures moved against last year's, box by box:

```bash
aeat app modelo compare --modelo 100 --year 2024 --year 2025
```

Pass `--year` exactly twice. Each row shows the box, its label and section,
both values, the difference, and the percent change; all-zero rows are
omitted from the text output. The comparison uses the most recent verified
revision of each year and falls back to the latest draft when no verified
revision exists — a year compared from a draft is flagged `BORRADOR` in the
output.

Use the comparison as a sanity check before filing: an unexpected jump in a
box is worth tracing back to its transactions before you export.

## Trace a value to its legal basis

Every computed value carries its grounding, and you can surface it at each
review stage:

- `aeat app modelo formulas 303 --period 1T --explain` — the formula behind
  each computed box with its legal and source references. See
  [Review and supply calculation inputs](review-calculation-values.md).
- Verification findings name the legal references behind each rule — see
  [Verify a filing](verification-reports.md).
- `aeat app review queue --explain` — pending findings with their legal
  references. See [Work through the review queue](review-queue.md).

## Next steps

- [Verify a filing](verification-reports.md) — box-level verification of the
  draft.
- [Review and supply calculation inputs](review-calculation-values.md) —
  fill missing values readiness or verification surfaced.
- [Building on earlier filings](../explanation/building-on-earlier-filings.md)
  — how cross-period dependencies work.
- [How the tool organises your filing work](filing-spine.md) — workspaces,
  revisions, and per-workspace history.
- [CLI reference](../cli/index.rst) — full option reference.
