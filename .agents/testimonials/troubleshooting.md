# Testimonial — `docs/how-to/troubleshooting.md`

- **Doc path:** `docs/how-to/troubleshooting.md`
- **Persona:** A user whose local setup broke, following the diagnose/repair guide (config check → repair → doctor → reset paths), running every documented command non-interactively.
- **Date:** 2026-06-18

This page is symptom-organised: you find your error in a heading and run the commands beneath it. I walked every documented command in heading order, synthesising a throwaway profile where a command needed an active one (the page sends a profile-less user to `profile-setup.md`, off-page).

## Walkthrough

### "This operation requires an active profile"

**`aeat config profile status`** (no profile yet)
- Expected: tool tells me what it thinks is active.
- Actual: `Sin perfil configurado. Ejecuta `aeat config profile create NAME` para empezar.` plus `next_action aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>`.
- Verdict: OK (app) / DOC-ISSUE MINOR — output is Spanish; an English reader hits Spanish before reaching the "Output appears in the wrong language" section far below.

**`aeat config repair profile`**
- Expected: repair the active-profile pointer.
- Actual: a key/value report — `dry_run True`, `cleared_pointer False`, `repairable_by_clearing_pointer False`, `next_action aeat config profile create ...`. Nothing to repair with no profile.
- Verdict: OK.

**`aeat config repair profile --clear-active --yes`**
- Expected (from doc framing): this is the apply form that clears the pointer.
- Actual: still `dry_run True`, `cleared_pointer False`. With no profile there is nothing to clear, but `--yes` reporting `dry_run True` is confusing — the doc presents `--clear-active --yes` as the real run.
- Verdict: DOC-ISSUE MINOR — `--clear-active` only acts "when it points at unreadable profile state" (per `--help`); the doc doesn't say the run is a no-op (and reports dry-run) when the pointer is already clean.

**`aeat config switch <profile-name>`** (tried `someprofile`, none exist)
- Expected: switch to a good profile.
- Actual: `Refused. Perfil desconocido: someprofile. Ejecuta 'aeat config profile list' para ver los perfiles registrados.`
- Verdict: OK — graceful, instructive refusal.

*(Setup step, off-page)* **`aeat config profile create persona ...`**
- Bare form refused: `El asistente guiado necesita una terminal interactiva...` then offered `--quiet --tax-id ...`. `--quiet --tax-id 12345678Z --activity freelance` created and activated the profile. Note: the page never warns that a master-key passphrase is required; the harness pre-set `AEAT_SECRET_PASSPHRASE`, so a real non-interactive user would be blocked at the passphrase prompt with no on-page warning.

### A calculation refuses because the ledger is not ready

**`aeat app ledger preflight --year 2026 --period 1T`**
- Expected: preflight report naming blocking rows.
- Actual: `period 1T 2026 / checked 0 / issues 0 / ready true`.
- Verdict: OK.

**`aeat app ledger status`**
- Expected: ledger readiness.
- Actual: bucket totals and row counts (all 0), in Spanish (`Filas`, `Activas`, `Pendientes de revisión`).
- Verdict: OK (app) / DOC-ISSUE MINOR (Spanish output).

### A required value is missing

**`aeat app modelo bindings list --modelo 303 --year 2026 --period 1T --missing`**
- Expected: list of still-missing values for the form.
- Actual: clean table, `binding_count 15`, English column headers (`binding_id`, `source`, `readiness`, `input_channel`). Best-behaved command on the page.
- Verdict: OK.

### The period token is rejected

**`aeat app ledger status --year 2026 --period 0A`** → OK (annual accepted).
**`aeat app ledger preflight --year 2026 --period 03`** → OK (`period 03 2026 / ready true`).
**`aeat app ledger preflight --period 1T`** (bare token, no year)
- Expected (doc quotes it verbatim): `Period token '1T' needs a year on this command. Add --year (e.g. --period 1T --year 2024).`
- Actual: `Invalid value` is NOT raised — instead the generic Click error `Missing option '--year'.`
- Verdict: DOC-ISSUE MAJOR — the page's documented year-fix message does **not** appear on `ledger preflight` (its own example command). The documented message *does* appear on `modelo work calculate` and `overview status` (verified: `El token de periodo '1T' necesita un año en este comando. Añada --year ...`). So the page attributes a friendly message to a command that gives a bare `Missing option '--year'`.

**`aeat app ledger preflight --year 2026 --period 2026Q1`** (calendar shape)
- Expected: refusal; calendar shapes not accepted.
- Actual: `Invalid value: Periodo '2026Q1' no reconocido. Use un token AEAT: 1T-4T (trimestres), 0A (anual), 01-12 (meses), e indique el año con --year ...`
- Verdict: OK — instructive (Spanish).

### Output appears in the wrong language

**`aeat --language en config profile create --help`**
- Expected: help text in English.
- Actual: English help (`Initialize a new active profile`, English option descriptions). Works.
- Verdict: OK.

**`AEAT_OUTPUT_LANGUAGE=en aeat config profile status`** (env var)
- Actual: command output flips to English (`Next step: ...`). Works.
- Verdict: OK.

### A live read from AEAT refuses

**`aeat config auth status`** / **`aeat config auth test`**
- Expected: show stored-credential state without contacting AEAT.
- Actual: both report `configured False / authenticated False / available False` plus active-profile health. `auth test` adds `persisted_session_present False`. Both local, no network.
- Verdict: OK.

**`aeat config repair connectivity`**
- Expected: check the tool can reach the AEAT Sede (the only network step).
- Actual: `Destino navegador / Estado ok / Estado HTTP 200 / Marcadores healthy`. Real network probe ran.
- Verdict: OK.

**`aeat config auth diagnostics list`** → `row_count 0` (no failures yet). OK.
**`aeat config auth diagnostics show nonexistent-id`** → `Refused. Diagnóstico de autenticación no encontrado: nonexistent-id.` OK (graceful).
**`aeat config auth diagnostics report nonexistent-id --phone-state app_prompted_not_accepted`** → same graceful "not found" refusal; the `--phone-state` enum value was accepted. OK.

### The diagnostic toolbox

**`aeat app overview status`**
- Actual: full Spanish workspace narrative (profile, no movements, empty invoice register, no drafts, encrypted storage readable) plus a "Qué escribir ahora" next-steps block.
- Verdict: OK (app) / DOC-ISSUE MINOR (Spanish).

**`aeat config repair logs --lines 50`**
- Actual: prints log path (`...\persona-trbl-fg\storage\logs\aeat.log`) and recent DEBUG/INFO lines. As promised.
- Verdict: OK.

**`aeat config repair integrity objects`** → `readable 3 / unreadable 0` with per-namespace breakdown. OK.
**`aeat config repair integrity registry`** → `ok True / issues 0`. OK.

**`aeat config repair quarantine --dry-run`** → `dry_run true / would_quarantine 0 / would_retain 3`. OK.
**`aeat config repair quarantine --yes`** → `dry_run false / quarantined 0 / retained 3`. Non-destructive as documented. OK.

**`aeat app ledger participation <transaction-id>`** (tried `tx_nonexistent`)
- Expected: which finalized revisions used the transaction.
- Actual: `Integrity. El runtime de almacenamiento no está listo... No hay una sesion de bucket activa. Ejecuta aeat config switch NAME para desbloquear un perfil.` — refused for "no active bucket session" even though a profile is active and `ledger status` accesses the same bucket fine.
- Verdict: APP-ISSUE MAJOR (session inconsistency, see Finding 4).

**`aeat app ledger participation rebuild`**
- Expected: rebuild the participation index (doc says "safe to regenerate at any time").
- Actual: `Usage: aeat app ledger participation [OPTIONS] [TRANSACTION_ID] COMMAND ...` then `Invalid value: El prefijo de id 'rebuild' contiene caracteres no hexadecimales (permitidos: 0-9, a-f).` The word `rebuild` is bound to the optional `TRANSACTION_ID` positional instead of dispatching to the `rebuild` subcommand. Fails identically before and after `config switch`.
- Verdict: APP-ISSUE BLOCKER — the documented command is uninvokable as written (see Finding 3).

**`aeat config repair reset-progress --yes`** (throwaway profile)
- Expected: removes saved interrupted-command progress.
- Actual: `Integrity. ... No hay una sesion de bucket activa. Ejecuta aeat config switch NAME...` — refused, same as participation. Also refuses with `--dry-run`. The page documents only `--yes` and never mentions a session prerequisite or the `--dry-run` flag that `--help` exposes.
- Verdict: APP-ISSUE MAJOR + DOC-ISSUE MINOR (see Findings 4 & 5).

### Prepare a privacy-safe support request / Next steps
- Prose + cross-links only; no commands. The privacy-scrubbing checklist (strip NIF/CIF/DNI/NIE/NII, names, paths) is clear and the issue-tracker link is correct. OK.

## Findings

1. **[BLOCKER][APP] `aeat app ledger participation rebuild` cannot be invoked as documented.**
   Repro: `aeat app ledger participation rebuild` → `Invalid value: El prefijo de id 'rebuild' contiene caracteres no hexadecimales`. The command group has an *optional* positional `TRANSACTION_ID` that precedes the `rebuild` subcommand, so the parser binds `rebuild` to the argument and the transaction-id validator rejects it. Fails with and without a prior `config switch`.
   Fix: make `participation` dispatch the `rebuild` subcommand ahead of the optional positional (e.g. move the list to `participation show <id>` / `participation list <id>`, or special-case the subcommand name), so the documented invocation reaches the subcommand.

2. **[MAJOR][DOC] The quoted year-fix message is wrong for `ledger preflight`.**
   The page (lines 87–91) quotes `Period token '1T' needs a year on this command. Add --year ...` right after listing `ledger preflight` as a `--period` command. Repro: `aeat app ledger preflight --period 1T` → generic `Missing option '--year'.`, NOT the quoted message. The friendly message is produced by `modelo work calculate` and `overview status` (verified), not by `ledger preflight`/`ledger status`.
   Fix: either attribute the quoted message to the commands that actually emit it, or note that ledger `--period` commands emit a plain `Missing option '--year'` instead.

3. **[MAJOR][APP] Bucket-session requirement is inconsistent across diagnostic commands.**
   In one identical environment with an active profile, `ledger status`, `overview status`, `repair integrity objects`, and `repair quarantine` all open the bucket and succeed, but `ledger participation <id>` and `repair reset-progress` refuse with `No hay una sesion de bucket activa. Ejecuta aeat config switch NAME...`. Running `config switch persona` first does not change the outcome for those two.
   Fix: make participation/reset-progress acquire the bucket session the same way the working diagnostic commands do, or document the exact prerequisite.

4. **[MINOR][DOC] `reset-progress --dry-run` is undocumented.**
   `--help` shows `--dry-run / --no-dry-run`, but the page documents only `aeat config repair reset-progress --yes`. For a command the page labels "destructive," a naive user should be told they can preview with `--dry-run` first (consistent with the project's dry-run-before-apply discipline elsewhere on the page).
   Fix: add `aeat config repair reset-progress --dry-run` as the preview step, mirroring the quarantine pattern.

5. **[MINOR][DOC] No passphrase warning + Spanish-before-the-language-fix.**
   (a) The brief's check: the page never warns that a master-key passphrase is required. A real non-interactive user (no `AEAT_SECRET_PASSPHRASE`) would be blocked at a hidden prompt on the very first command. (b) Every command on the page emits Spanish output/refusals, but the "Output appears in the wrong language" fix sits two-thirds down the page; a stranded English reader meets Spanish first.
   Fix: a one-line note near the top — "Commands need your master-key passphrase; set `AEAT_OUTPUT_LANGUAGE=en` (or pass `--language en`) if output is Spanish" — would pre-empt both.

6. **[MINOR][DOC] `config repair profile --clear-active --yes` silently reports `dry_run True` when there is nothing to clear.**
   The doc presents `--clear-active --yes` as the apply form, but on a clean/absent pointer it returns `dry_run True / cleared_pointer False` with no explanation that the clear only fires when the pointer points at unreadable state.
   Fix: note that `--clear-active` acts only when the active pointer is unreadable, and that a no-op reports `dry_run True`.

7. **[NIT][DOC] Profile creation prerequisite is fully off-page.**
   The first symptom sends a profile-less user to `profile-setup.md` for `create`, but `create` itself requires `--quiet`/`--accept-defaults` non-interactively (`El asistente guiado necesita una terminal interactiva`). Not strictly this page's job, but the first-symptom path dead-ends for a non-interactive user without that hint.

## Testimonial

Following the page felt mostly smooth: the symptom-as-heading layout let me jump straight to a fix, and the read-only diagnostics (`auth status/test`, `integrity`, `quarantine --dry-run`, `connectivity`) behaved exactly as promised — graceful, instructive refusals, no scary crashes. But two of the toolbox commands let me down: `participation rebuild`, which the page calls "safe to regenerate at any time," simply won't run as written (the parser eats `rebuild` as a transaction id), and `reset-progress` refused with a bucket-session error that other commands in the same shell didn't hit. The Spanish output everywhere, before the language fix appears far down the page, made the early steps harder to trust. The app delivered on the diagnostic *reads* but not on the two index/reset *actions* the page promised.

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 3 / 5
- **Findings by severity:** BLOCKER 1, MAJOR 2, MINOR 3, NIT 1 (total 7)
