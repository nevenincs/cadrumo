# The filing workflow: work units and calculation revisions

Use this guide after completing the quickstart if you want to understand how
the tool organises and stores your filing work between steps.

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

The tool assigns a unique reference number to each filing workspace. For most
use you do not need to know or remember it — the tool finds your work
automatically from the modelo, year, and period you type.

The tool knows which version of the official tax rules applies to each form and
period. You do not need to choose this manually. Use `--revision` only when
support or an error message asks you to target a specific ruleset version.

To see the reference number for a saved filing:

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

Prefer the visible target for hand-run commands. Use the reference number when
aeat reports that more than one filing matches the same modelo, year, and period.

## What a work unit is

A work unit is the saved workspace for one filing target. It is the thing that
connects later commands to the same local filing work.

For example, this command creates or reuses the work unit for Modelo 303 Q1
2026:

```bash
aeat app modelo work create --modelo 303 --year 2026 --period 1T
```

The tool keeps a record of your filing work. That record links to:

- the latest calculated draft
- the verified draft, if you have verified one
- the filed record, if you have marked one as filed locally

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

Running calculation again does not overwrite the old result. If your
transactions or manual values changed, the tool creates a new saved calculation.
If nothing changed, it reuses the same result. The tool updates your filing
record to reflect the latest calculated draft.

List the saved calculation revisions for a filing:

```bash
aeat app modelo work revisions --modelo 303 --year 2026 --period 1T
```

Show the current revision's persisted values:

```bash
aeat app modelo work revision --modelo 303 --year 2026 --period 1T
```

If you need to view one specific saved calculation, type its reference number
after the command:

```bash
aeat app modelo work revision <calculation-revision-id>
```

Reference numbers to know:

- the filing workspace reference — from `aeat app modelo work list`
- the saved calculation reference — from `aeat app modelo work revisions`
- the rules version reference — shown in status output; you rarely need this
- a run reference — only appears when a command was interrupted mid-way

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

Each command automatically picks the most appropriate saved calculation:

- `verify` uses the latest draft
- `file` uses the latest verified draft
- `export` uses whichever was marked as filed; if none was filed, it uses the
  verified draft

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

## Rename, discard, or inspect lifecycle history

Manage or review the lifecycle of a work unit as it progresses:

- `rename`: Add or update a friendly display name for the work unit:
  
  ```bash
  aeat app modelo work rename --modelo 303 --year 2026 --period 1T --name "Q1 VAT draft"
  ```

- `history`: Review all actions the tool has taken on this filing, in order:
  
  ```bash
  aeat app modelo work history --modelo 303 --year 2026 --period 1T
  ```

- `discard`: Mark the filing workspace as discarded. The tool records this
  action in the history log. Use this if you created the workspace by mistake
  or want to replace it with a fresh one:
  
  ```bash
  aeat app modelo work discard --modelo 303 --year 2026 --period 1T --reason "re-creating with correct revision" --yes
  ```
  
  The `--reason` text is for your own records only. It is not sent to AEAT.

## List and resume interrupted execution flows

If a command was interrupted halfway through (for example, because your
connection dropped while the tool was reading live AEAT data), you can check
and restart it:

- `runs`: List recent flow runs, from most recent to oldest:
  
  ```bash
  aeat app modelo work runs
  ```

- `resume`: Restart an interrupted command using the filing details or the
  reference number shown in the error message:
  
  ```bash
  aeat app modelo work resume --modelo 303 --year 2026 --period 1T
  aeat app modelo work resume <run-id-or-work-unit-id>
  ```

## When to use exact IDs

Use modelo, year, and period for all normal work.

Use the exact reference number when:

- aeat tells you that more than one filing matches the same modelo, year,
  and period (aeat refuses to guess; it prints candidates for you to choose)
- you are replaying or inspecting one specific saved calculation
- support asks you to share the exact reference number from the command output

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
