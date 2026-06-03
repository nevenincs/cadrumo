# Common filing recipes

These recipes assume the basics: a working `aeat` command (check with `aeat --version`), an active profile (your saved taxpayer identity and settings — created with `aeat config profile create <name>`, switched with `aeat config profile switch <name>`, inspected with `aeat config profile status`), and ledger data to file against. If you're new to the tool, start with the [Tutorial](../tutorials/index.md) to build your first modelo (a numbered Spanish tax form, such as 303 for quarterly VAT) from start to finish, then read the [pipeline Explanation](../explanation/index.md) for the concepts behind the verbs. These recipes don't re-teach either; they assume you know the lifecycle and want to get a specific job done.

## Related guides

These recipes assume a working setup. For the setup itself and the fast path, see:

- [Set up your taxpayer profile](profile-setup.md) - create a profile and switch between several.
- [Import and classify a bank statement](import-bank-statements.md) - load your ledger so a modelo can calculate from it.
- [Quickstart](quickstart.md) - the four-command path to a modelo file.
- [Plan your filing calendar](filing-calendar.md) - see which modelos are due and when.
- [Reconcile a filing against its justificante](reconcile.md) - check a filed return against the AEAT receipt.
- [Diagnose and repair your local setup](troubleshooting.md) - when a command refuses or data looks wrong.

## How to read a recipe

Each recipe states a goal, then gives ordered, copy-pasteable steps built from stable `aeat` verbs. Use `aeat config ...` for local setup and diagnostics, and `aeat app ...` for the tax workflow over the active profile. Discover specifics live — `aeat app modelo describe <modelo>` for revision IDs, `aeat app modelo casillas <modelo>` for casilla (numbered form box) IDs, and `--help` on any verb — rather than relying on values hard-coded in a recipe that may change between releases.

Recipes pass identifiers from one step to the next. `aeat app modelo work create` returns a `work_unit_id` (the handle for one form-year-period filing); `aeat app modelo work calculate` returns a `calculation_revision_id` (the handle for one draft calculation of that filing). Copy each ID from one command's output into the next. Any unambiguous prefix of an ID works in place of the full string; an ambiguous prefix stops the command and lists the candidates so you can pick one.

For the full flag reference on any verb, see the [CLI reference](../cli/index.rst) rather than these recipes.

## Two invariants every recipe inherits

**The app never submits to AEAT.** Every recipe ends at a local export: `aeat app modelo export` writes a fichero-BOE file (the fixed-width text file that AEAT, the Spanish Tax Agency — Agencia Estatal de Administración Tributaria, accepts for upload) to disk; it never contacts AEAT. You upload that file yourself in the AEAT portal. For the reasoning behind this design, see the [pipeline Explanation](../explanation/index.md).

**Global flags go before the command group.** Place `--language`, `--format json`, `--profile`, and the other global flags before `app` or `config`, not after the verb. For example, `aeat --format json app modelo work calculate ...` returns machine-readable output; the same flag placed after `calculate` is rejected. With `--format json`, calculation output carries both a flat `casilla_values` map and a typed `observations` list with `legal_refs` and `source_refs` links back to the governing law. For the full exit-code table and output-schema contract, see the [CLI reference](../cli/index.rst).

## The filing spine

These recipes assume an active taxpayer profile and an imported, classified ledger. To set those up, see the [Tutorial](../tutorials/index.md) for `aeat config profile` and `aeat app ledger import` / `classify`.

The filing spine is the same for every modelo: `create`, `calculate`, `verify`, then `export`. Each verb persists state to the active profile's encrypted bucket. No verb in this spine submits to AEAT. `aeat app modelo work file` is an internal lifecycle marker, and `export` writes a local file. You file the exported fichero-BOE file yourself at [sede.agenciatributaria.gob.es](https://sede.agenciatributaria.gob.es).

Period tokens differ by verb. The filing spine composes `--year` and `--period` separately, so pass `--period 1T` (or `0A` for annual, a two-digit month, or a modelo-declared token), not `--period 2024`. A bare four-digit period is rejected with the list of accepted tokens.

### Confirm you're ready to file

Goal: verify the profile and ledger are tax-ready for one modelo before you start.

1. Run `aeat app overview status` to confirm the profile, ledger, and modelo readiness flags.
2. Run `aeat app ledger preflight --period <YYYY-MM>` to confirm the classified ledger is tax-ready. Income is classified by direction, so incoming transactions need no category and aren't flagged as missing.
3. Run `aeat app modelo readiness --modelo <code> --revision-id <id> --year <YYYY> --period <token>`. This reports the modelo readiness and a ledger-preflight sub-result in one envelope. With no active profile, it refuses with a no-active-profile message.

### File a quarterly return

Goal: produce a local fichero-BOE file for one modelo, year, and period.

1. Create the work unit: `aeat app modelo work create --modelo <code> --year <YYYY> --period <token> --revision <revision-id>`. The output status is `created` or `reused`; the verb is idempotent on the (modelo, year, period, revision) key and prints a 64-character work unit id.
2. Persist a draft calculation: `aeat app modelo work calculate <work_unit_id>`. The verb pulls classified ledger transactions through the modelo bindings and prints a new calculation revision id, the `borrador` (draft) state, and the casilla observations with their `legal_refs` and `source_refs`. Supply explicit values with repeatable `--casilla CASILLA=DECIMAL` and `--binding KEY=VALUE` flags when a casilla isn't ledger-derived.
3. Verify the draft: `aeat app modelo work verify <calculation_revision_id>`. On success the revision transitions to `verificado_completo`. If verification isn't granted, the revision is left unchanged, the report explains the missing inputs or blocking findings, and the command exits non-zero.
4. Export the file: `aeat app modelo export <work_unit_id> --output <path>`. The verb writes a local AEAT-compatible fichero-BOE file from the most recent verified-complete or filed revision and prints `output_path`, `byte_size`, `file_sha256`, `format`, and a `bucket_event_id`. If no exportable revision exists, it refuses and tells you to run `verify` first.
5. File the exported file manually at [sede.agenciatributaria.gob.es](https://sede.agenciatributaria.gob.es).

### Record an internal filing marker

Goal: mark a verified revision as filed in your own records, separate from submitting to AEAT.

1. File the revision: `aeat app modelo work file <calculation_revision_id>`. The verb marks a verified revision as internally filed and appends the line `filing_disambiguation (internal only — does not submit to AEAT)`.
2. Submit to AEAT yourself at [sede.agenciatributaria.gob.es](https://sede.agenciatributaria.gob.es). The CLI never contacts AEAT.

### Find the right modelo, casillas, or work unit

Goal: look up modelo metadata or locate an existing work unit before you calculate.

1. Describe a modelo: `aeat app modelo describe <modelo>`.
2. List a modelo's casillas: `aeat app modelo casillas <modelo>`.
3. Preview which bindings the ledger fills, and which are missing: `aeat app modelo bindings list --modelo <code> --year <YYYY> --period <token> --missing`.
4. List your work units: `aeat app modelo work list`. Inspect one with `aeat app modelo work status <work_unit_id>`, and list its calculation revisions with `aeat app modelo work revisions <work_unit_id>`.

## File a quarterly IVA modelo 303

Goal: produce a verified, internally filed modelo 303 for one quarter and export the fichero-BOE file for filing with AEAT.

The lifecycle threads two distinct handles. `create`, `calculate`, and `export` operate on the `work_unit_id`. `verify` and `file` operate on the `calculation_revision_id` that `calculate` emits. Conflating the two is the most common error, so copy each identifier as the command prints it.

Filing here is internal only. The `file` verb marks the revision `presentado` inside the app and never submits to AEAT. The export writes a local fichero-BOE file. Submit to AEAT yourself, outside the app.

### Before you start

Confirm an active taxpayer profile exists. Every lifecycle verb refuses without one.

```
aeat config profile create <name>
```

Confirm the axis values for 303 - the valid periods, the current revision id, and the casilla and binding counts.

```
aeat app modelo describe 303
```

For a quarterly filing, use a quarter token (`1T`, `2T`, `3T`, or `4T`) and the current revision `2023-y-siguientes`.

### Steps

1. Create the work unit. This provisions the `(modelo, year, period, revision)` key and prints a 64-character `work_unit_id`. Re-running returns the existing unit with status `reused`, so the command is safe to repeat.

   ```
   aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2023-y-siguientes
   ```

2. Calculate a draft revision. Pass the `work_unit_id` as the positional argument, plus your input values. Each run writes a fresh draft revision (state `borrador`) and prints a new `calculation_revision_id`.

   ```
   aeat app modelo work calculate <work_unit_id> --casilla CASILLA=DECIMAL --binding KEY=VALUE
   ```

3. Verify the revision. Pass the `calculation_revision_id`, not the `work_unit_id`. On success the revision moves to `verificado_completo`. On failure the command exits non-zero and reports the missing inputs or blocking findings. Treat a failed verify as a stop-and-fix gate: `file` and `export` both refuse an unverified revision.

   ```
   aeat app modelo work verify <calculation_revision_id>
   ```

4. File the verified revision. This marks it `presentado` inside the app. It does not submit to AEAT.

   ```
   aeat app modelo work file <calculation_revision_id> --notes "..."
   ```

5. Export the fichero-BOE file. Pass the `work_unit_id` and a required output path. Without `--revision`, export selects the most recent verified-complete or filed revision. The command reports `output_path`, `byte_size`, `file_sha256`, and `format`.

   ```
   aeat app modelo export <work_unit_id> --output <path>
   ```

### Common variations

- If you don't know the casilla numbers, list them first. `--casilla` accepts the casilla id, the registry record number, or the BOE-printed box number.

  ```
  aeat app modelo casillas 303
  ```

- If `calculate` fails on a missing binding, list the bindings the formula still requires.

  ```
  aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing
  ```

- If you lost the `calculation_revision_id`, list the revisions for the work unit and take the latest.

  ```
  aeat app modelo work revisions <work_unit_id>
  ```

- If you need a specific revision exported - a superseded one that auto-selection excludes - name it explicitly.

  ```
  aeat app modelo export <work_unit_id> --output <path> --revision <calculation_revision_id>
  ```

- If you need machine-readable output, set `--format json` on the root command. The envelope carries the same identifiers.

  ```
  aeat --format json app modelo work calculate <work_unit_id> --casilla CASILLA=DECIMAL
  ```

- If you want English output, set `--language en` on the root command. The default CLI language is Spanish.

  ```
  aeat --language en app modelo describe 303
  ```

- To file a different quarter, repeat the lifecycle with `--period 2T`, `3T`, or `4T`. Monthly filers (SII) use a month token (`01` through `12`) instead.

- To label who performed each action, add `--by "operator name"` to any lifecycle verb. The label is recorded into the bucket lifecycle event.

- If `create` refuses the modelo as not applicable to the active profile's taxpayer type, override the guard.

  ```
  aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2023-y-siguientes --allow-not-applicable
  ```

## Produce an annual summary modelo (modelo 390)

Goal: build, verify, and export an annual IVA summary - modelo 390 - for a given year.

Calculate and file all four quarterly 303 work units for the same year first, so their data is available when you calculate the 390. For why the annual summary draws on the quarterly filings, see the [pipeline Explanation](../explanation/index.md).

With the four 303 filings in place, run these steps.

1. Create the 390 work unit. The period token is `0A` (annual), and the revision is `2010-y-siguientes`.

   ```
   aeat app modelo work create --modelo 390 --year 2025 --period 0A --revision 2010-y-siguientes
   ```

   The output reports whether the run created a new work unit or reused an existing one, and names the `work_unit_id`. Re-running with the same modelo, year, period, and revision is safe - it reuses the existing work unit.

2. Calculate the draft. Pass the `work_unit_id` from the previous step. The 390's bound aggregation pulls the quarterly 303 observations automatically, so no override flags are needed.

   ```
   aeat app modelo work calculate <work_unit_id>
   ```

   The output shows the casilla table and names the new `calculation_revision_id` in the `borrador` (draft) state. To re-inspect drafts later, use `aeat app modelo work revisions <work_unit_id>`.

3. Verify the draft. Pass the `calculation_revision_id`.

   ```
   aeat app modelo work verify <calculation_revision_id>
   ```

   On a pass, the revision transitions to `verificado_completo`. On a failure, the verb exits with code 1, leaves the revision unchanged, and lists the missing inputs or blocking findings. If verification fails for missing 303 data, confirm the four quarterly filings are calculated and filed, then re-run.

4. File the revision internally. Pass the `calculation_revision_id`.

   ```
   aeat app modelo work file <calculation_revision_id>
   ```

   This marks the revision as filed inside the app and emits the `filing_disambiguation (internal only — does not submit to AEAT)` line. It does not contact AEAT. You file the return with AEAT outside the app.

5. Export the fichero-BOE file. Pass the `work_unit_id` and an output path.

   ```
   aeat app modelo export <work_unit_id> --output ./modelo-390-2025.txt
   ```

   Export picks the most recent filed or verified-complete revision. To target a specific draft, add `--revision <calculation_revision_id>`. The output reports `output_path`, `byte_size`, `file_sha256`, and `format` for the written file. Export is local-only and never contacts AEAT.

To list every revision recorded for the year, run `aeat app modelo history --modelo 390 --year 2025`.

## Apply a censo update to the active profile

Goal: pull the AEAT-reported modelo 036/037 census data into the active profile, replacing the profile's prior AEAT-sourced census facts.

These steps assume an active profile is selected. Each `censo` verb operates on whichever profile is active and takes no profile argument. If no profile is active, every verb refuses with a no-active-profile error.

1. Confirm the active profile:

   ```
   aeat config profile show
   ```

   To switch first, list the profiles and select one:

   ```
   aeat config profile list
   aeat config profile switch <name>
   ```

2. Enable live AEAT reads. `censo refresh` performs a live authenticated AEAT fetch (sede G313), gated by the `AEAT_LIVE_TESTS_ENABLED` environment variable. Set it to the exact literal string `1`. Any other value, including `true`, `yes`, or `on`, leaves the gate closed and `refresh` refuses.

3. Pull the AEAT census into a new snapshot:

   ```
   aeat config profile censo refresh
   ```

   `refresh` prints the `snapshot_id`, the capture timestamp, and a fact count. It stores a new active snapshot and records a `CENSO_REFRESHED` event in the profile's history. If AEAT publishes no census for the operator's NIF, `refresh` reports a censo-not-available error - confirm the certificate is registered against the NIF, then retry.

4. Inspect the captured snapshot:

   ```
   aeat config profile censo show
   ```

   `show` prints the `snapshot_id`, capture timestamp, state, and one line per census fact. To inspect an earlier snapshot, pass `--snapshot-id <prefix>`; the prefix matches the `snapshot_id`.

5. Preview the divergences before writing anything:

   ```
   aeat config profile censo compare
   ```

   `compare` prints summary counts (diverging, censo-only, profile-only) followed by one line per tracked field, showing the AEAT value alongside the current profile value. Review this output - `apply` overwrites without an interactive prompt.

6. Apply the snapshot to the active profile:

   ```
   aeat config profile censo apply
   ```

   `apply` stamps the snapshot's census facts onto the profile, replacing any prior facts sourced from the AEAT census read. Facts entered manually or through the wizard stay untouched. The command prints the `snapshot_id`, the written and unchanged counts, and one line per affected field, then records a `CENSO_APPLIED` event. To apply a specific snapshot, pass `--snapshot-id <prefix>`. If the profile record is absent, `apply` refuses with a conflict error.

Each verb also emits a typed JSON envelope under `--format json` on the root command, for scripted use.

With live reads disabled, `refresh` cannot run, but `show`, `compare`, and `apply` still work against a previously captured snapshot. Before any snapshot exists, `show`, `compare`, and `apply` refuse with a censo-not-available error - run a successful `refresh` first.

## Verify and export a computed modelo for filing

Goal: verify an already-computed modelo revision, then export it to an AEAT-compatible fichero-BOE file you file outside the application.

These steps assume an active profile. All three verbs run locally; none contacts AEAT.

Pass the `calculation_revision_id` to `verify` and `file`; pass the `work_unit_id` to `export`. Passing one where the other is expected is the most common error here. See the [CLI reference](../cli/index.rst) for the full identifier contract.

1. Verify the draft revision:

   ```
   aeat app modelo work verify <calculation_revision_id>
   ```

   The command checks the draft against the verified-complete contract and emits a verification report. On success the revision moves to state `verificado_completo`. On failure the revision stays unchanged and the command exits with code 1; the report lists the missing inputs or blocking findings.

   Add `--by "<actor>"` to set the operator label, or `--language en` to force English output.

2. Export the verified revision to a local fichero-BOE file:

   ```
   aeat app modelo export <work_unit_id> --output <path>/modelo.txt
   ```

   `--output` is required; there's no default path. The command picks the latest filed revision, or the latest verified-complete revision if none is filed, and writes the file. The output reports `output_path`, `byte_size`, `file_sha256`, `format`, `modelo`, `filing_year`, `period`, `work_unit_id`, `calculation_revision_id`, and `bucket_event_id`.

   If the work unit has no verified-complete or filed revision, export refuses with `No exportable revision` and points you back to verify. Run step 1 first.

To export a specific revision instead of the auto-selected one, pass `--revision <calculation_revision_id>`. Superseded revisions never auto-select, so name one explicitly with `--revision` when you need it.

### Optional: mark the revision internally filed

To record an internal filing marker before export, run:

```
aeat app modelo work file <calculation_revision_id>
```

This step is optional. Export accepts a verified-complete revision directly, so the minimal path is verify, then export. `file` marks an internal record only; it does not submit to AEAT. Add `--notes "<text>"` to annotate the record, or `--by "<actor>"` to set the operator label.

The default output language here is Spanish. Pass `--language en` on `verify` or `file` for English summaries; `export` has no output-language flag.

## Knowledge and discovery surfaces

These recipes assume you already have an active profile and know your way around `aeat app`. For deeper context, use these surfaces.

- **Concepts and pipeline reasoning** — [the pipeline Explanation](../explanation/index.md): the mental model of profile, ledger, calculate, and verify; and why the tool never files on your behalf.
- **Flags, exit codes, and output schemas** — [the generated CLI reference](../cli/index.rst): the global flags, the exit-code table, the per-command flag reference, and the retired-surface redirect table.
- **Terminal discovery** — run `--help` at any level (`aeat --help`, `aeat config --help`, `aeat app --help`) to list subcommands without leaving the terminal.

### Goal: find out why a form applies to you

To decompose a modelo's applicability against your active profile, run:

```
aeat app overview explain <modelo>
```

To evaluate a specific year, add `--year <year>`. The verb is local-only and never contacts AEAT. It surfaces the applicable flag, the registry-backed rationale, the governing `legal_refs`, and the profile facts the decision depends on. It needs an active profile.

### Goal: trace a value back to the law

To list the registry formulas behind a modelo, run `aeat app modelo formulas <modelo>`. To include the `legal_refs` and `source_refs` columns, add `--explain`.

To inspect the local legal-norm corpus while you work, use the registry verbs:

```
aeat app registry citations list
aeat app registry manuals list
```

Both groups also offer `view` and `verify`, and `manuals` adds `rules`. These read your local reference data; none of them reach AEAT.

### A note on language

The generated CLI reference renders help strings in English. The running CLI honors your active output-language setting (`--language`, or `AEAT_OUTPUT_LANGUAGE`: `es`, `en`, `ca`, or `hu`), and a clean install with no profile defaults to Spanish. Your terminal output can therefore differ in language from the English examples in the reference. To match the documented examples for one session, set the language per invocation:

```
aeat --language en app overview status
```

### If you arrived from older tooling

Retired command roots redirect you forward. The retired-surface table in the [generated CLI reference](../cli/index.rst) lists every retired command root and the canonical verb it points to.
