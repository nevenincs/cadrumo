# The filing workflow

This page covers the filing workflow's two building blocks - the work unit
(the saved workspace for one filing target) and the calculation revision
(one saved calculation result) - and how create, calculate, verify, file,
and export choose between them. Use it after completing the quickstart if
you want to understand how the tool organises and stores your filing work
between steps.

## Before you start

You need an active profile, and the tool needs your master-key passphrase.

Create a profile first if you do not have one (see
[Set up your taxpayer profile](profile-setup.md)). Pass `--quiet` for the
non-interactive form (a bare `profile create NAME` opens an interactive wizard).
A profile that will reach `export` must carry a name and surnames, or `export`
refuses with "requires the operator name":

```{cli-sequence} filing-spine-create-profile
```

Every profile-scoped command needs the master-key passphrase; the tool
prompts for it.

The CLI emits help, results, and refusals in Spanish.

## The filing chain

The command-line interface is the same one used in the quickstart. Run the four
commands in order, from the profile above:

```{cli-sequence} filing-spine-chain
:verify: Confirm the chain verifies and exports a local fichero.
```

The `--activity-start-date` in the profile above scopes out the prior-period
dependency for this first filing, so `verify` reports `complete` and `export`
writes the `.boe`. Without it, `verify` blocks on an unresolved cross-period
dependency on the prior period and `export` refuses. To file a period that
folds in a real prior period, import that prior filing's evidence first; see
[Reconcile a filing](reconcile.md).

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

```{cli-sequence} filing-spine-visible-target
:verify: Confirm the visible target addresses the same saved work across reads.
```

If no saved work exists yet, create it first with `aeat app modelo work create`
(the chain and visible-target sequences above run the full form). Running the
same create command again does not create a duplicate. It returns the existing
saved work for that filing.

## How a filing gets its ID

The tool assigns a unique reference number to each filing workspace. For most
use you do not need to know or remember it. The tool finds your work
automatically from the modelo, year, and period you type.

The tool knows which version of the official tax rules applies to each form and
period. You do not need to choose this manually. Use `--revision` only when
support or an error message asks you to target a specific ruleset version.

To see the reference number for a saved filing:

```{cli-sequence} filing-spine-work-list
:verify: Confirm the saved filing appears in the work list.
```

After you have the `work_unit_id`, address the same saved work by ID:

```{cli-sequence} filing-spine-address-by-id
```

Prefer the visible target for hand-run commands. Use the reference number when
Cadrumo reports that more than one filing matches the same modelo, year, and period.

## A work unit is one filing in progress

A work unit is the saved workspace for one filing target. It is the thing that
connects later commands to the same local filing work.

For example, `aeat app modelo work create` creates or reuses the work unit for
Modelo 303 Q1 2026 (the chain sequence above runs the full form).

The tool keeps a record of your filing work. That record links to:

- the latest calculated draft
- the verified draft, if you have verified one
- the filed record, if you have marked one as filed locally

No separate command "switches" the current work unit. The active profile is
global, but the filing work is selected on each command. To work on a different
filing, pass a different visible target or pass a different `work_unit_id`:

```{cli-sequence} filing-spine-other-target
```

## A calculation revision is one saved result

A calculation revision is one saved calculation result inside a work unit. It
has its own reference number, the calculation-revision-id, which `calculate`
creates and which is separate from the work-unit-id.

When you run `aeat app modelo work calculate`, Cadrumo saves a draft calculation
revision (the chain sequence above runs it).

Running calculation again does not overwrite the old result. Every saved
calculation is immutable: earlier revisions stay on disk exactly as they
were, identified by their exact contents, so you can compare revisions and
go back. If your transactions or manual values changed, the tool creates a
new saved calculation alongside the old; if nothing changed, it reuses the
same result. The tool updates your filing record to reflect the latest
calculated draft. A saved revision is a record of one attempt, not a verdict
- its numbers commit to nothing until you verify and file it.

List the saved calculation revisions for a filing with `aeat app modelo work
revisions`, and show the current revision's persisted values with `aeat app
modelo work revision` (the visible-target sequence above runs both).

If you need to view one specific saved calculation, type its reference number
after the command:

```{cli-sequence} filing-spine-revision-by-id
```

Reference numbers to know:

- the filing workspace reference - from `aeat app modelo work list`
- the saved calculation reference - from `aeat app modelo work revisions`
- the rules version reference - shown in status output; you rarely need this
- a run reference - only appears when a command was interrupted mid-way

## How verify, file, and export choose a revision

Most commands start from the visible filing target and then choose the relevant
calculation revision under that work unit.

Verification defaults to the current draft revision; run it with `aeat app modelo
work verify` (the chain sequence above runs it).

Local filing defaults to the current verified revision:

```{cli-sequence} filing-spine-file
:verify: Confirm the filing is recorded locally and nothing is submitted to AEAT.
```

`work file` records a local filed marker. It does not submit anything to AEAT.

Export defaults to the filed revision if one exists. Otherwise, it uses the
current verified revision; run it with `aeat app modelo export` (the chain
sequence above runs it).

Export refuses a plain draft. The upload file is the artefact that leaves
the tool for AEAT, so it is built only from a revision that passed the
completeness check (or one already recorded as filed) - the gate that stops
an incomplete or inconsistent draft from becoming a filing by accident.

The `.boe` extension is a naming convention. The tool writes the file to the
`--output` path you choose and always produces a fixed-width fichero-BOE text
file, whatever extension you give it.

Each command automatically picks the most appropriate saved calculation:

- `verify` uses the latest draft
- `file` uses the latest verified draft
- `export` uses whichever was marked as filed; if none was filed, it uses the
  verified draft

If you need a different saved calculation, use `--select` with the visible
target:

```{cli-sequence} filing-spine-select
:verify: Confirm each selector resolves the draft, verified, and filed revisions.
```

You can also pass exact IDs on commands that accept them:

```{cli-sequence} filing-spine-exact-ids
```

For the complete option list, see the [CLI reference](../cli/index.rst).

## Rename, discard, or review a filing's history

Manage or review the lifecycle of a work unit as it progresses:

- `rename`: Add or update a friendly display name for the work unit:
  
  ```{cli-sequence} filing-spine-rename
  :verify: Confirm the work unit carries the new display name.
  ```

- `history`: Review all actions the tool has taken on this filing, in order:
  
  ```{cli-sequence} filing-spine-history
  :verify: Confirm the history lists the actions taken on this filing.
  ```

- `discard`: Mark the filing workspace as discarded. The tool records this
  action in the history log. Use this if you created the workspace by mistake
  or want to replace it with a fresh one:
  
  ```{cli-sequence} filing-spine-discard
  :verify: Confirm the workspace is marked discarded with its reason.
  ```
  
  The `--reason` text is for your own records only. It is not sent to AEAT.

## Resume an interrupted filing

If a command was interrupted halfway through (for example, because your
connection dropped while the tool was reading live AEAT data), you can check
and restart it:

- `runs`: List recent flow runs, from most recent to oldest:
  
  ```{cli-sequence} filing-spine-runs
  :verify: Confirm recent flow runs are listed newest first.
  ```

- `resume`: Restart an interrupted command using the filing details or the
  reference number shown in the error message:
  
  ```{cli-sequence} filing-spine-resume
  ```

## When to use exact IDs

Use modelo, year, and period for all normal work.

Use the exact reference number when:

- Cadrumo tells you that more than one filing matches the same modelo, year,
  and period (Cadrumo refuses to guess; it prints candidates for you to choose)
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
