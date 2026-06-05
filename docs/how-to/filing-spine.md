# How filings, work units, and calculation revisions fit together

Use this guide when you already know the basic modelo flow and want to
understand what `aeat` saves between commands.

The common command-line interface is the same one used in the quickstart:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

`--modelo`, `--year`, and `--period` are the normal way to name the filing you
are working on. Use that shape for routine create, calculate, verify, file,
export, status, history, and revision commands.

## Start with the visible filing target

A filing target is the filing as you see it:

- the active profile
- the modelo code
- the filing year
- the period

For example, `--modelo 303 --year 2026 --period 1T` means "Modelo 303, first
quarter of 2026, for the active profile."

That same visible target works across the normal workflow:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 1T
aeat app modelo work revisions --modelo 303 --year 2026 --period 1T
aeat app modelo work revision --modelo 303 --year 2026 --period 1T
```

If no saved work exists yet, create it first:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
```

Running the same create command again does not create a duplicate. It returns
the existing saved work for that filing.

## How the visible target becomes an ID

`aeat` stores each saved filing workspace under a `work_unit_id`. This ID is not
a UUID and not a workflow run ID. It is a 64-character SHA-256 identifier.

The ID is derived from:

- the active profile's storage bucket
- the modelo
- the filing year
- the period
- the registry revision for that modelo and period

The registry revision is the ruleset `aeat` uses for that modelo period. For
most commands you do not need to choose it. `aeat` resolves it from the modelo,
year, and period. Use `--revision` only when you need to target a specific
registry revision.

To see the saved work ID, list or inspect work:

```bash
aeat app modelo work list
aeat app modelo work status --modelo 303 --year 2026 --period 1T
```

After you have the `work_unit_id`, address the same saved work by ID:

```bash
aeat app modelo work status <work-unit-id>
aeat app modelo work calculate <work-unit-id>
aeat app modelo work revisions <work-unit-id>
```

Prefer the visible target for hand-run commands. Use the ID when an automation
has already stored it, or when `aeat` reports that more than one saved work item
matches the same modelo, year, and period.

## What a work unit is

A work unit is the saved workspace for one filing target. It is the thing that
connects later commands to the same local filing work.

For example, this command creates or reuses the work unit for Modelo 303 Q1
2026:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
```

The work unit stores filing-level metadata. It also points to important saved
records, such as:

- the current calculation revision
- the filed calculation revision, if you marked one as filed locally
- the current local filing record, if one exists

No separate command "switches" the current work unit. The active profile is
global, but the filing work is selected on each command. To work on a different
filing, pass a different visible target or pass a different `work_unit_id`:

```bash
aeat app modelo work status --modelo 303 --year 2026 --period 2T
aeat app modelo work status <another-work-unit-id>
```

## What a calculation revision is

A calculation revision is one saved calculation result inside a work unit.

When you run calculate, `aeat` saves a draft calculation revision:

```bash
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
```

Re-running calculation does not edit the old result. It saves another revision,
or reuses the same one if the inputs and outputs are identical. The work unit's
current calculation pointer moves to the draft that the command saved or
reused.

List the saved calculation revisions for a filing:

```bash
aeat app modelo work revisions --modelo 303 --year 2026 --period 1T
```

Show the current revision's persisted values:

```bash
aeat app modelo work revision --modelo 303 --year 2026 --period 1T
```

If you need to inspect one exact calculation, pass its
`calculation_revision_id`:

```bash
aeat app modelo work revision <calculation-revision-id>
```

Do not confuse the IDs:

- `work_unit_id` identifies the saved filing workspace
- `calculation_revision_id` identifies one saved calculation result
- registry revision ID identifies the modelo ruleset, such as
  `2019-y-siguientes`
- workflow run ID identifies an interrupted workflow run, not a filing or a
  calculation

## How verify, file, and export choose a revision

Most commands start from the visible filing target and then choose the relevant
calculation revision under that work unit.

Verification defaults to the current draft revision:

```bash
aeat app modelo work verify --modelo 303 --year 2026 --period 1T
```

Local filing defaults to the current verified revision:

```bash
aeat app modelo work file --modelo 303 --year 2026 --period 1T
```

`work file` records a local filed marker. It does not submit anything to AEAT.

Export defaults to the filed revision if one exists. Otherwise, it uses the
current verified revision:

```bash
aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe
```

These defaults are command-specific. They are not a general "latest revision"
rule.

If you need a different saved calculation, use `--select` with the visible
target:

```bash
aeat app modelo work revision --modelo 303 --year 2026 --period 1T --select latest-draft
aeat app modelo work revision --modelo 303 --year 2026 --period 1T --select latest-verified
aeat app modelo work revision --modelo 303 --year 2026 --period 1T --select filed
```

You can also pass exact IDs on commands that accept them:

```bash
aeat app modelo work verify <calculation-revision-id>
aeat app modelo work file <calculation-revision-id>
aeat app modelo export <work-unit-id> --revision <calculation-revision-id> --output ./modelo-303.boe
```

For the complete option list, see the [CLI reference](../cli/index.rst).

## When to use exact IDs

Use modelo, year, and period unless you have a reason to be more exact.

Exact IDs are useful when:

- an automation already stored a `work_unit_id` or `calculation_revision_id`
- you need to replay or inspect one saved calculation
- the same visible target is ambiguous because multiple active work units match
- support or audit work needs the exact saved record shown in command output

If a visible target is ambiguous, `aeat` refuses to guess and prints candidate
work units. Choose one candidate by passing its `work_unit_id`, or narrow the
target with the registry `--revision` when that is the intended distinction.

## Next steps

- [Quickstart: produce a modelo file](quickstart.md) - the shortest path from
  profile to exported file.
- [Review and supply calculation inputs](review-calculation-values.md) - how to
  inspect saved values, missing bindings, and manual inputs.
- [Review calculations with Google Sheets](review-with-google-sheets.md) - how
  to inspect calculation workbooks outside the terminal.
- [Reconcile a filing](reconcile.md) - how to compare a filed modelo with its
  justificante.
- [Command reference](../cli/index.rst) - exact flags and selector options.
