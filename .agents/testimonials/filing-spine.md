# Testimonial — `docs/how-to/filing-spine.md`

- **Doc path:** `docs/how-to/filing-spine.md`
- **Persona:** A user trying to understand how the tool organises filing work — work units, drafts, calculation revisions, and filed records.
- **Date:** 2026-06-18
- **Environment:** non-interactive shell, `BASE=/tmp/persona-fs-fg`, passphrase pre-set by harness, CLI invoked as `uv run --no-sync aeat ...`.

---

## Walkthrough

### 1. Opening block, command 1: `work create` (BEFORE any profile)
- **Command:** `aeat app modelo work create --modelo 303 --year 2026 --period 1T`
- **Expected:** Page says "Use this guide after completing the quickstart"; opening block presents this as the first runnable command. I expected it to create a work unit.
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** DOC-ISSUE, MAJOR. The page never states a profile must exist first, and the refusal is Spanish-only. (See Finding 1, 2.)

### 2. Prerequisite recovery (not on this page): create a profile
- **Command:** `aeat config profile create persona --tax-id 12345678Z` → blocked (interactive wizard), then `aeat config profile create persona --quiet --tax-id 12345678Z`
- **Expected:** N/A — recovery from the refusal above.
- **Actual:** First form refused with `El asistente guiado necesita una terminal interactiva...` and instructed the `--quiet` flag form; `--quiet` form then succeeded (`estado creado`, `next aeat app modelo work create`).
- **Verdict:** OK (app refusal graceful and instructive), but underscores Finding 1 — none of this is on the page.

### 3. Opening block command 1 (after profile): `work create`
- **Command:** `aeat app modelo work create --modelo 303 --year 2026 --period 1T`
- **Expected:** Creates a work unit for 303/2026/1T.
- **Actual:** `status created`, `work_unit_id 9c46...abfa…fce`, `state borrador`, `revision_id 2023-y-siguientes`. Also printed an unannounced overdue/recargo warning: `AVISO: plazo voluntario vencido (Art. 27 LGT)...` (`days_overdue 59`, `recargo_pct 3.00`).
- **Verdict:** OK (creation works). The recargo warning is reasonable but unmentioned by the page (NIT).

### 4. Opening block command 2: `work calculate`
- **Command:** `aeat app modelo work calculate --modelo 303 --year 2026 --period 1T`
- **Expected:** Saves a draft calculation revision.
- **Actual:** OK — `calculation_revision_id f547...fa9`, `state borrador`, full casilla table printed (all 0.00 with no transactions).
- **Verdict:** OK.

### 5. Opening block command 3: `work verify`
- **Command:** `aeat app modelo work verify --modelo 303 --year 2026 --period 1T`
- **Expected:** Page (line 151) says "Verification defaults to the current draft revision" — implies it just verifies the draft.
- **Actual:** `completeness_status blocked`, `granted_verificado_completo false`, `finding_count 3`, all `cross_period_dependency_unclean` blocking findings:
  ```
  cross-period dependency is not clean: modelo=303 year=2025 period=4T origin=previous_filing_binding ... blockers=missing_observation, missing_current_filing_record
  ```
- **Verdict:** APP-behaves-correctly but DOC-ISSUE, MAJOR — the page presents verify as a frictionless happy-path step and never warns it can block, nor that the very next command depends on it succeeding. (See Finding 3.)

### 6. Opening block command 4: `export`
- **Command:** `aeat app modelo export --modelo 303 --year 2026 --period 1T --output $BASE/modelo-303.boe`
- **Expected:** Page's opening block presents this as the natural 4th step, producing a `.boe` file.
- **Actual:**
  ```
  Invalid value: current revision is still draft; verify it before exporting or select a verified revision explicitly
  ```
  No file written.
- **Verdict:** DOC-ISSUE, MAJOR — **the page's own opening four-command block does not run end-to-end** in a clean environment. (See Finding 3.)

### 7. `work status` (visible target)
- **Command:** `aeat app modelo work status --modelo 303 --year 2026 --period 1T`
- **Expected:** Shows the saved work and its reference number.
- **Actual:** OK — full record incl. `current_calculation_revision_id`, `short_*` ids, state, plazo/recargo fields.
- **Verdict:** OK.

### 8. `work revisions` (visible target)
- **Command:** `aeat app modelo work revisions --modelo 303 --year 2026 --period 1T`
- **Expected:** Lists saved calculation revisions.
- **Actual:** OK — `revision_count 1`, table of revision ids + state.
- **Verdict:** OK.

### 9. `work revision` (visible target)
- **Command:** `aeat app modelo work revision --modelo 303 --year 2026 --period 1T`
- **Expected:** Shows the current revision's persisted values.
- **Actual:** OK — full key-figure + casilla dump.
- **Verdict:** OK.

### 10. Idempotent re-create
- **Command:** `aeat app modelo work create --modelo 303 --year 2026 --period 1T` (second time)
- **Expected:** Page (line 45): "Running the same create command again does not create a duplicate. It returns the existing saved work."
- **Actual:** OK — `operation modelo.work.reuse`, `status reused`, same `work_unit_id`. Claim verified.
- **Verdict:** OK.

### 11. `work list`
- **Command:** `aeat app modelo work list`
- **Expected:** Shows reference numbers for saved filings.
- **Actual:** OK — `work_unit_count 1`, one row with `short_work_unit_id 5004dbfb7fce` and full id.
- **Verdict:** OK.

### 12. By-ID forms: `status / calculate / revisions <work-unit-id>` and `revision <calculation-revision-id>`
- **Commands:** `work status <WID>`, `work calculate <WID>`, `work revisions <WID>`, `work revision <CRID>`
- **Expected:** Page (lines 67–71, 136): address saved work by ID.
- **Actual:** OK — all four resolve correctly; re-`calculate <WID>` reused the same revision (matches "If nothing changed, it reuses the same result").
- **Verdict:** OK.

### 13. `work file` (visible target)
- **Command:** `aeat app modelo work file --modelo 303 --year 2026 --period 1T`
- **Expected:** Page (line 157): "Local filing defaults to the current verified revision."
- **Actual:**
  ```
  Invalid value: current revision 'f547...fa9' is in state 'borrador'; filing requires a verified-complete revision
  ```
- **Verdict:** APP-correct, DOC-ISSUE MINOR — unreachable on this page's happy path because verify is blocked; page never says `file` needs a verified revision to exist. Error message is clear.

### 14. `--select` selectors
- **Commands:**
  - `work revision ... --select latest-draft` → OK, returns the draft.
  - `work revision ... --select latest-verified` → `Invalid value: "no calculation revision in state 'verificado_completo'"`
  - `work revision ... --select filed` → `Invalid value: 'work unit has no selectable filed_calculation_revision_id'`
- **Expected:** Page (lines 187–189) lists all three as usable examples.
- **Verdict:** OK for `latest-draft`; the other two error because nothing is verified/filed. Errors are accurate; the page presents all three without noting the prerequisite (MINOR).

### 15. `rename`
- **Command:** `aeat app modelo work rename --modelo 303 --year 2026 --period 1T --name "Q1 VAT draft"`
- **Expected:** Adds a friendly display name.
- **Actual:** OK — `name Q1 VAT draft`.
- **Verdict:** OK.

### 16. `history`
- **Command:** `aeat app modelo work history --modelo 303 --year 2026 --period 1T`
- **Expected:** All actions in order.
- **Actual:** OK — `event_count 4`: created, calculation.created, verification.refused, work_unit.renamed.
- **Verdict:** OK.

### 17. `runs`
- **Command:** `aeat app modelo work runs`
- **Expected:** Recent flow runs, newest first.
- **Actual:** OK — `run_count 0` with header row.
- **Verdict:** OK.

### 18. Alternate-target `status` (page line 99, "work on a different filing")
- **Command:** `aeat app modelo work status --modelo 303 --year 2026 --period 2T`
- **Expected:** Page presents this as the way to look at a different filing.
- **Actual:**
  ```
  Invalid value: Ninguna unidad de trabajo activa coincide con este modelo, ano y periodo. Ejecute primero aeat app modelo work create.
  ```
- **Verdict:** APP-correct, DOC-ISSUE NIT — the example targets a filing that does not exist yet, so a literal reader gets an error. Spanish message embeds the English command path.

### 19. `resume` (visible target)
- **Command:** `aeat app modelo work resume --modelo 303 --year 2026 --period 1T`
- **Expected:** Restart an interrupted command.
- **Actual:** `Invalid value: No se encontró ejecución de flujo de trabajo para el modelo 303 período 2026 1T. Ejecute el flujo al menos una vez antes de reanudar.`
- **Verdict:** OK — correct refusal (nothing was interrupted); message clear, though Spanish-only.

### 20. `discard`
- **Command:** `aeat app modelo work discard --modelo 303 --year 2026 --period 1T --reason "re-creating with correct revision" --yes`
- **Expected:** Marks the workspace discarded, records it in history.
- **Actual:** OK — `state descartado`, `discard_reason ...`, `discarded_by persona`.
- **Verdict:** OK.

### 21. Help-confirmation of ID/flag forms (lines 195–197)
- `work verify --help` shows `[CALCULATION_REVISION_ID]` + `--select` (page line 195 consistent).
- `export --help` shows both `--revision` (calc revision) AND `--registry-revision` (stable rules version). Page line 56 calls the rules-version flag `--revision`, but the actual flag for that is `--registry-revision`; `--revision` is the calculation revision. (See Finding 4.)
- **Verdict:** DOC-ISSUE MINOR — flag naming mismatch for the "rules version" flag.

---

## Findings

1. **[MAJOR] [DOC]** — Page never states that an **active profile is a prerequisite.** The first command of the opening block refuses with `No hay un perfil activo` in a clean environment. **Repro:** in a fresh `$BASE`, run the page's first command. **Fix:** add a one-line prerequisite ("Complete the quickstart first so an active profile exists") near the top, ideally linking the profile-create step.

2. **[MINOR] [APP/DOC]** — **Master-key passphrase requirement is never mentioned.** The harness pre-sets `AEAT_SECRET_PASSPHRASE`; a naive user in a non-interactive shell without it would be blocked (per the brief, this absence is itself a finding). **Fix:** note that secure storage requires a passphrase and how it is supplied.

3. **[MAJOR] [DOC]** — **The opening four-command block does not run end-to-end.** `verify` returns `blocked` (cross-period dependency unclean for 2025/4T) on a clean 303/2026/1T, so `export` then fails with `current revision is still draft; verify it before exporting`. The page presents create→calculate→verify→export as a linear happy path and never warns verify can block, that export/file require a *verified* revision, or how to clear the cross-period dependency. **Repro:** Walkthrough steps 3–6 above. **Fix:** either pick an example that verifies cleanly, or explicitly state "verify may report blocking findings (e.g. missing prior-period evidence); export/file only work once a revision is verified," and cross-link the reconcile / `live filed pull-sources` recovery the verify output itself suggests.

4. **[MINOR] [DOC]** — **Rules-version flag naming mismatch.** Page line 56 says use `--revision` to "target a specific ruleset version," but the actual flag for the ruleset/registry version is `--registry-revision`; `--revision` (and the page's own line 197) is the *calculation* revision id. Two different concepts share the word "revision" and the page conflates the flag names. **Fix:** name the rules-version flag `--registry-revision` and keep `--revision` for the calculation revision.

5. **[NIT] [DOC]** — **Examples that error for a literal reader.** `work status --period 2T` (line 99) and the `--select latest-verified` / `--select filed` examples (lines 188–189) error in a fresh workspace because the targeted filing/state does not exist. Errors are accurate and instructive, but a reader copy-pasting them gets red text. **Fix:** label these as "only after the target exists / has been verified or filed."

6. **[NIT] [BOTH]** — **Spanish/English mixing.** Every refusal and aviso renders in Spanish (`Refused. No hay un perfil activo`, `AVISO: plazo voluntario vencido`, the cross-period findings are English but profile/status errors are Spanish), while the doc is English. Some Spanish messages even embed the English command path. An English-only reader matching doc prose to terminal output will stumble. **Fix:** out of this page's scope to fix, but worth a doc note that CLI messages are localised to Spanish.

---

## Testimonial

I came to this page to understand how the tool keeps my filing work organised, and conceptually it taught me well: work unit vs. calculation revision vs. filed record is explained clearly, the idempotent re-create and the reuse-when-nothing-changed behaviour both did exactly what the page promised, and the ID-vs-visible-target distinction held up under testing. But the page's own headline four-command block let me down twice — it never warned me I needed a profile first (the first command simply refused), and then `verify` blocked on a 2025 cross-period dependency so `export` flat-out failed, leaving me with no `.boe` file and no guidance on the page about how to get past it. The descriptive sections (status, revisions, revision, rename, history, runs, discard, by-ID forms) all delivered exactly what they claimed; it was the implied happy-path sequencing and the unstated prerequisites that tripped me.

---

## Scorecard

- **Doc clarity:** 3 / 5 (conceptually strong, but the opening example is unrunnable end-to-end and a prerequisite + a flag name are wrong/missing)
- **App capability:** 4 / 5 (every command behaved correctly and refusals were instructive; only the localisation gap and the unreachable happy-path lower it)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2
