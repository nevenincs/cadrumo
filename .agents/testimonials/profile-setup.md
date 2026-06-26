# Testimonial — `docs/how-to/profile-setup.md`

**Persona:** A careful first-time user setting up a taxpayer profile, trying both
the interactive and flag-driven paths, then listing / switching / renaming /
duplicating / exporting / importing / deleting profiles and reading history.
**Date:** 2026-06-18
**Base:** `/tmp/persona-profile-setup`

---

## Walkthrough

### `aeat config profile list` (empty state)
- **Expect:** A list of profiles and the active one.
- **Actual:** `active_profile <none>` / `profiles <none>`. Clean.
- **Verdict:** OK.

### `aeat config profile status` (empty state)
- **Expect:** Readiness summary.
- **Actual (Spanish):** `Sin perfil configurado. Ejecuta` aeat config profile create NAME `para empezar.` plus `next_action`.
- **Verdict:** OK (functionally), but output is Spanish while the doc is English — NIT.

### `aeat config switch my-other-profile` (no such profile)
- **Expect:** Switch to another taxpayer.
- **Actual:** `Refused. Perfil desconocido: my-other-profile. Ejecuta 'aeat config profile list' ...` exit=2.
- **Verdict:** OK — graceful, instructive (Spanish).

### `aeat config profile create --help`
- **Expect:** Full flag list with accepted values.
- **Actual:** Renders. All headings/help text Spanish (`Tipo de contribuyente`, etc.).
- **Verdict:** OK.

### Worked example — `create ana-2026 --quiet --accept-defaults --entity-type natural_person --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --irpf-income-categories actividad_economica --activity "diseno grafico" --iva-regime GENERAL --tax-residence-ccaa madrid --output-language en`
- **Expect:** Minimal natural-person profile created.
- **Actual:** `profile ana-2026 / Status created / active_profile ana-2026`. exit=0.
- **Verdict:** OK — the page's flagship example works verbatim.

### `aeat config profile show ana-2026` and `validate ana-2026`
- **Expect:** Stored facts; schema validation.
- **Actual:** `show` prints the full fact set (tax_id redacted to `sha256:...`, output_language en, ccaa madrid, etc.); `validate` → `readiness ready issues=0 / valid True`. exit=0.
- **Verdict:** OK — strong, the app delivers exactly what the page promises.

### `create no-taxid --quiet` (missing required flag)
- **Expect (doc, English):** `Refused. This --quiet run is missing required details. Add these flags and run the command again: --tax-id.`
- **Actual (Spanish):** `Refused. A esta ejecución con --quiet le faltan datos obligatorios. Añade estos flags y vuelve a ejecutar el comando: --tax-id. O ejecútalo sin --quiet desde una terminal interactiva ...` exit=2.
- **Verdict:** DOC-ISSUE (MINOR/MAJOR) — behaviour correct, but the documented English message does not match the Spanish the app emits.

### `create basque ... --tax-residence-ccaa pais_vasco` (foral refusal)
- **Expect (doc, English):** `Invalid value for '--tax-residence-ccaa': Residents in pais_vasco file with the corresponding Hacienda Foral ...`
- **Actual (Spanish):** `Invalid value for '--tax-residence-ccaa': Los residentes en pais_vasco tributan ante la Hacienda Foral correspondiente bajo el Concierto Económico (Ley 12/2002) ...` (with extra sede links). exit=2.
- **Verdict:** DOC-ISSUE — same English-vs-Spanish mismatch; behaviour is correct and helpful.

### `status` / `show` / `validate` (active profile, no name arg)
- **Expect:** Operate on the active profile.
- **Actual:** All three resolve the active profile correctly. exit=0.
- **Verdict:** OK.

### `preflight --modelo 303 --filing-year 2026 --period 1T`
- **Expect:** Names missing fields for that context.
- **Actual:** `readiness ready missing=0 / revision_id 2023-y-siguientes`. exit=0.
- **Verdict:** OK.

### `edit ana-2026 --quiet --address-postcode 28013`
- **Expect:** Postcode updated.
- **Actual:** `Status updated`. exit=0.
- **Verdict:** OK.

### `rename ana-2026 ana-real`
- **Expect:** Visible label changes; active pointer follows.
- **Actual:** `previous_display_name ana-2026 / display_name ana-real`. exit=0.
- **Verdict:** OK.

### `duplicate ana-real ana-copy --display-name "Ana copy"`
- **Expect:** A second profile from the same facts.
- **Actual:** Creates it, then `list` shows `active_profile Ana copy` / `* Ana copy` / `ana-real`. exit=0.
- **Verdict:** APP/DOC note — succeeds, BUT it silently switched the active profile to the copy (doc doesn't say so), AND the profile is addressed by its **display name** `Ana copy`, not the positional token `ana-copy`. This sets up the next failure.

### `delete ana-copy --yes` (verbatim doc command)
- **Expect:** Deletes the duplicated profile.
- **Actual:** `Refused. Unknown profile: ana-copy. Run 'aeat config profile list' ...` exit=2. Only `delete "Ana copy" --yes` works.
- **Verdict:** **MAJOR BOTH** — the documented command fails verbatim because addressing is by display name, which the doc's own `--display-name "Ana copy"` made diverge from `ana-copy`.

### `delete "Ana copy" --yes` (active profile)
- **Actual:** `status tombstoned / active_profile <none>` + Spanish notice that the active pointer was cleared. exit=0.
- **Verdict:** OK — the "clears the active pointer" promise holds.

### `export ana-real --to $BASE/ana-real-profile.json`
- **Expect:** Portable JSON file written.
- **Actual:** File written (6789 bytes) + strong `WARNING` that the bundle is UNENCRYPTED with raw tax id, ledger, etc. exit=0.
- **Verdict:** OK — app exceeds the doc here (doc's sensitivity note is softer than the app's blunt warning).

### `import ./ana-real-profile.json --label ana-restored`
- **Expect:** Imported under a fresh label.
- **Actual:** `display_name ana-restored` + INFO (Spanish) that the imported profile is now ACTIVE. exit=0.
- **Verdict:** OK — though, like duplicate, it silently makes the import active (doc doesn't mention).

### `logout`
- **Actual:** `logged_out_profile <id>` + Spanish notice that later verbs will be refused until you switch. exit=0.
- **Verdict:** OK.

### `history ana-real` — run after `logout` (doc order)
- **Expect:** Append-only event log.
- **Actual:** `Integrity. El runtime de almacenamiento no está listo ... No hay una sesion de bucket activa. Ejecuta aeat config switch NAME ...` — no events.
- **Verdict:** DOC/APP (MINOR) — `history` takes a profile NAME yet still needs an active bucket session; the doc orders `logout` before `history`, so a literal top-to-bottom reader hits this.

### `history ana-real` (after switching back, active session)
- **Actual:** 8 events including `profile.renamed` AND `bucket.renamed` — confirming the page's "rename appears as two events" claim. exit=0.
- **Verdict:** OK — positive, the two-event claim verifies.

### `history ana-real --event-type profile.renamed`
- **Actual:** `event_count 1`. exit=0. **Verdict:** OK.

### `history ana-real --since 2026-01-01 --until 2026-03-31` (verbatim doc command)
- **Expect:** Date-windowed events.
- **Actual:** Unhandled crash:
  ```
  File ".../_config/_bucket_history.py", line 178, in _bucket_history_event_matches
    if since_dt is not None and event.occurred_at < since_dt:
  TypeError: can't compare offset-naive and offset-aware datetimes
  Internal. The command failed due to an unexpected internal error.
    -> Run `aeat config repair integrity --help`
  ```
  `--since` alone crashes identically.
- **Verdict:** **BLOCKER APP** — a documented command emits a raw Python traceback and misleadingly points to `repair integrity`.

### `history ana-real --actor operator`
- **Actual:** `event_count 3` (activations + export). exit=0. **Verdict:** OK.

### `history ana-real --event-type ""` (discover vocabulary)
- **Actual:** `Invalid value: Unknown event type: . Valid event types: modelo.calculation.created, ... profile.renamed, profile.exported, profile.imported, ...` exit=2.
- **Verdict:** OK — the "empty value lists the vocabulary" claim holds.

### Interactive wizard `create my-profile` (no `--quiet`, non-interactive shell)
- **Actual:** `Refused. El asistente guiado necesita una terminal interactiva ...` with two clear recovery options. exit handled gracefully.
- **Verdict:** OK — graceful (Spanish).

### Passphrase dependency (`create ... ` with `AEAT_SECRET_PASSPHRASE` unset)
- **Actual:** `Failed. AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive; re-run the command from an interactive terminal ... or provide AEAT_SECRET_PASSPHRASE ...`
- **Verdict:** DOC-ISSUE (MINOR) — the page never mentions a master-key passphrase is required at all; a naive user in a non-interactive shell is blocked. Refusal itself is graceful.

---

## Findings

1. **[BLOCKER][APP]** `aeat config profile history NAME --since DATE [--until DATE]` crashes with `TypeError: can't compare offset-naive and offset-aware datetimes` (`_bucket_history.py:178`) and surfaces a raw traceback + a misleading `repair integrity` hint. This exact command is printed in the doc ("Narrow a long history with filters, which combine"). **Repro:** `history ana-real --since 2026-01-01 --until 2026-03-31`. **Fix:** make `--since`/`--until` timezone-aware (or normalise `event.occurred_at`) before comparison; until fixed, the doc should not advertise the filter.

2. **[MAJOR][BOTH]** The doc's `delete ana-copy --yes` fails verbatim. The preceding `duplicate ana-real ana-copy --display-name "Ana copy"` registers the profile under the **display name** `Ana copy`; `list`/`delete`/`switch` address profiles by display name, so `delete ana-copy` → `Refused. Unknown profile: ana-copy`. **Fix:** either make the positional `name` token addressable, or change the doc so the duplicate's `--display-name` matches the token it later deletes (e.g. drop `--display-name`, or `delete "Ana copy"`).

3. **[MAJOR][DOC]** The doc renders two refusal messages (the `--quiet` missing-flag block, line ~100; the foral-CCAA block, line ~180) as English ` ```text ` blocks, but the app emits them in **Spanish**. An English-only reader can't recognise the message as a match. **Fix:** show the actual Spanish output, or add a note that runtime messages render in Spanish.

4. **[MINOR][DOC]** The page never warns that a master-key passphrase is required (interactive prompt, or `AEAT_SECRET_PASSPHRASE`). A naive user in a non-interactive shell is blocked with `Failed. AEAT_SECRET_PASSPHRASE is not set ...`. **Fix:** one sentence near "Create your profile" noting the passphrase prompt (or link the quickstart section that covers it).

5. **[MINOR][DOC]** `duplicate` and `import` both silently switch the active profile to the new one; the doc states neither. **Fix:** add "becomes the active profile" to both paragraphs.

6. **[MINOR][BOTH]** `history` is documented after `logout` in the page flow, but it requires an active bucket session even when given an explicit profile name — so a literal top-to-bottom reader hits `No hay una sesion de bucket activa`. **Fix:** note that `history` needs an active session (switch first), or reorder.

7. **[NIT][APP]** Refusal localisation is inconsistent: `switch` unknown-profile is Spanish (`Perfil desconocido`), `delete` unknown-profile is English (`Unknown profile`). Output keys are English while several notices/messages are Spanish.

---

## Testimonial

Setup itself felt solid: the flagship freelancer example created, showed, and
validated a profile exactly as promised, the foral refusal was genuinely
educational, and the export warning was franker than the doc. But the page tripped
me twice for real — `delete ana-copy` from its own worked flow was rejected because
the tool addresses profiles by display name, and the documented `--since/--until`
history filter dropped a raw Python traceback in my lap. I also never knew a
passphrase was needed until a fresh shell refused me. The app mostly delivers what
the page promises, but a careful reader following it verbatim cannot get clean to
the end.

## Scorecard
- **Doc clarity:** 3 / 5
- **App capability:** 3 / 5
- **Findings:** BLOCKER 1 · MAJOR 2 · MINOR 3 · NIT 1
