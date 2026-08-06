# Testimonial — `docs/how-to/modelo-036.md`

- **Doc path:** `docs/how-to/modelo-036.md`
- **Persona:** A first-time user who filed a Modelo 036 census declaration at the AEAT sede and wants to record that fact in the local audit trail.
- **Date:** 2026-06-18

---

## Walkthrough

### 1. `aeat app modelo m036 list` (first attempt, before profile)
- **Command:** `uv run --no-sync aeat app modelo m036 list`
- **Expected:** The "Before you start" section says I need an active profile; an empty list otherwise.
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** OK (refusal is graceful and names the exact remediation command). The page links to profile-setup but does not print any command itself, so I had to leave the page. MINOR/DOC — see Finding 1.

### 2. Create the prerequisite profile (off-page, from the linked instruction)
- **Command:** `uv run --no-sync aeat config profile create persona036 --tax-id 12345678Z`
- **Expected:** A profile (the page only says "see set up your taxpayer profile").
- **Actual:** Refused — guided wizard needs an interactive terminal, but it printed a clean non-interactive recovery path:
  ```
  Refused. El asistente guiado necesita una terminal interactiva, y esta ejecución no la tiene.
  ...
  2. O créalo en un solo paso indicando los datos obligatorios como flags:
       aeat config profile create NAME --quiet --tax-id NIF/CIF/DNI/NIE
  ```
  Re-ran with `--quiet`; profile created: `estado=creado`, `active_profile=persona036`.
- **Verdict:** OK (refusal is graceful and self-correcting). Not a fault of this page — it correctly delegates profile creation to a linked page.

### 3. `aeat app modelo m036 list` (empty)
- **Command:** `uv run --no-sync aeat app modelo m036 list`
- **Expected:** "An empty list means you have recorded no declarations yet."
- **Actual:**
  ```
  operation	modelo.m036.list
  bucket_id	<bucket-id>
  declaration_count	0
  Aún no hay declaraciones M036 registradas.
  ```
- **Verdict:** OK. Matches the documented empty-state behaviour.

### 4. Record an alta
- **Command:** `uv run --no-sync aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante ACUSE-ALTA-001`
- **Expected ("What success looks like"):** declaration_id, event kind, declared-on date, when saved, justificante.
- **Actual:**
  ```
  declaration_id	29f7ff67e5ea5e509ade6de417bf52ae1f4b58e7dfacba2cbd4792243366057e
  event_kind	alta
  declared_on	2026-01-10
  recorded_at	2026-06-18T19:50:40.103982+00:00
  sede_justificante	ACUSE-ALTA-001
  ```
- **Verdict:** OK. Every promised field is present (`recorded_at` = "when the record was saved").

### 5. Record a modificacion
- **Command:** `uv run --no-sync aeat app modelo m036 modificacion --declared-on 2026-03-15 --sede-justificante ACUSE-MOD-002`
- **Expected:** A saved record with `event_kind=modificacion`.
- **Actual:** `declaration_id 9fa081f2...`, `event_kind modificacion`, `declared_on 2026-03-15`, `sede_justificante ACUSE-MOD-002`.
- **Verdict:** OK.

### 6. Record a baja
- **Command:** `uv run --no-sync aeat app modelo m036 baja --declared-on 2026-12-31 --sede-justificante ACUSE-BAJA-003`
- **Expected:** A saved record with `event_kind=baja`.
- **Actual:** `declaration_id cb062983...`, `event_kind baja`, `declared_on 2026-12-31`, `sede_justificante ACUSE-BAJA-003`.
- **Verdict:** OK.

### 7. `aeat app modelo m036 list` (populated)
- **Command:** `uv run --no-sync aeat app modelo m036 list`
- **Expected:** "each declaration's id, event kind, declared-on date, recorded-at timestamp, and whether you gave a justificante."
- **Actual:** A 3-row table with columns `declaration_id event_kind declared_on recorded_at justificante_present` and `justificante_present=yes` on each.
- **Verdict:** OK. The doc says "whether you gave a justificante"; the column header is `justificante_present` (yes/no), which matches the prose.

### 8. `view` by full id
- **Command:** `uv run --no-sync aeat app modelo m036 view 29f7ff67e5ea5e509ade6de417bf52ae1f4b58e7dfacba2cbd4792243366057e`
- **Expected:** "the full record, including the justificante and your note if you gave them."
- **Actual:** Full record printed (operation, declaration_id, event_kind, declared_on, recorded_at, sede_justificante). No `note` row at this point because I had not yet added one.
- **Verdict:** OK.

### 9. `view` by prefix
- **Command:** `uv run --no-sync aeat app modelo m036 view 9fa081`
- **Expected:** "an unambiguous prefix of it" resolves the record.
- **Actual:** Resolved the modificacion record correctly.
- **Verdict:** OK. Prefix matching works exactly as documented.

### 10. `view` of a non-matching id
- **Command:** `uv run --no-sync aeat app modelo m036 view deadbeefdeadbeef`
- **Expected:** "An id that matches no recorded declaration is refused."
- **Actual:**
  ```
  Invalid value: Ninguna declaración M036 coincide con 'deadbeefdeadbeef'.
  Ejecuta 'aeat app modelo m036 list' para ver las declaraciones registradas.
  ```
- **Verdict:** OK. Graceful, instructive refusal.

### 11. Idempotency — re-run identical alta
- **Command:** `uv run --no-sync aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante ACUSE-ALTA-001`
- **Expected ("If you typed something wrong"):** "records no additional declaration, and you get the same declaration ID back."
- **Actual:** Same `declaration_id 29f7ff67...` returned; list count stayed at 3.
- **Verdict:** OK. (Note: `recorded_at` updated to the new run time on the returned record; the doc does not claim the timestamp is frozen, so this is acceptable, but see Finding 3.)

### 12. `--note`-only on an existing record
- **Command:** `uv run --no-sync aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante ACUSE-ALTA-001 --note "explaining the correction"`
- **Expected:** "Changing only `--note` does not create a new record."
- **Actual:** Same id `29f7ff67...`; list count still 3. A subsequent `view 29f7ff67` then showed `note explaining the correction`.
- **Verdict:** OK. The note is stored and surfaces in `view`, confirming the "including ... your note if you gave them" promise.

### 13. Corrected value creates an additional record
- **Command:** `uv run --no-sync aeat app modelo m036 alta --declared-on 2026-01-11 --sede-justificante ACUSE-ALTA-001 --note "corrected the date"`
- **Expected:** "Running the command with a corrected kind, date, or justificante records an additional declaration."
- **Actual:** New id `f0614346...`; list count rose to 4.
- **Verdict:** OK.

### 14. Passphrase requirement (off-page probe)
- **Command:** `unset AEAT_SECRET_PASSPHRASE; uv run --no-sync aeat app modelo m036 list`
- **Expected:** The page never mentions a master-key passphrase, so a naive user might assume none is needed.
- **Actual:**
  ```
  Failed. AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive; re-run the command from an interactive terminal (the CLI prompts for the passphrase) or provide AEAT_SECRET_PASSPHRASE through the Settings environment.
  ```
- **Verdict:** OK at the app layer (graceful, instructive). DOC gap — see Finding 2.

---

## Findings

### Finding 1 — Page does not print the profile-create command it depends on
- **Tag:** `[MINOR] [DOC]`
- **Repro:** Run any `m036` command before a profile exists. You are refused and must leave the page to `profile-setup.md` to learn how to create one.
- **Impact:** A first-time user following this page top-to-bottom hits a wall immediately; the "Before you start" bullet only links out. The CLI refusal happens to print the exact command (`aeat config profile create NAME --tax-id ...`), which rescues the user, but the page itself does not.
- **Suggested fix:** Either inline a one-line example (`aeat config profile create NAME --quiet --tax-id <NIF>`) in "Before you start", or note that the linked page's wizard needs an interactive terminal and that `--quiet` is the non-interactive form.

### Finding 2 — No mention of the master-key passphrase requirement
- **Tag:** `[MINOR] [DOC]`
- **Repro:** With `AEAT_SECRET_PASSPHRASE` unset and a non-interactive shell, every documented command fails with `Failed. AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive...`.
- **Impact:** The page promises commands that "record that fact in your local audit trail" but never says the local store is encrypted and requires a passphrase. An interactive user is prompted (fine); a scripting/non-interactive user is blocked with no warning from the page.
- **Suggested fix:** Add a one-line note (or a link) that recording writes to the encrypted profile store and the CLI will prompt for the master-key passphrase (or honour `AEAT_SECRET_PASSPHRASE`). The app's own error is excellent; the page just doesn't set the expectation.

### Finding 3 — Idempotent re-run silently updates `recorded_at`
- **Tag:** `[NIT] [BOTH]`
- **Repro:** Run an identical alta twice. Same `declaration_id`, but the second response's `recorded_at` reflects the later run time.
- **Impact:** The doc says re-running identical values "records no additional declaration" (true — count and id unchanged), but the returned `recorded_at` moves. A careful user comparing the two confirmations might think a new save occurred.
- **Suggested fix:** Either clarify in "If you typed something wrong" that the returned `recorded_at` is the most-recent touch (not a new record), or have the idempotent path echo the original save timestamp. Low priority — behaviour is harmless.

### Finding 4 — `<acuse>` placeholder is undefined inline
- **Tag:** `[NIT] [DOC]`
- **Repro:** The code blocks use `--sede-justificante <acuse>`. The word "acuse" (acuse de recibo) is Spanish and is only loosely defined later as "the receipt number the sede shows after you file."
- **Impact:** An English-only naive user sees `<acuse>` in the command before the prose explains it. Minor; the "Before you start" bullet does define justificante.
- **Suggested fix:** Use `<receipt-number>` or `<justificante>` as the placeholder to match the English prose, or gloss `acuse` on first use.

---

## Testimonial

Following this page felt smooth and honest: it never over-promised, and the one-sentence framing ("these commands only record that fact... they never file anything at AEAT") set my expectations perfectly. I tripped at the very first command because I had no profile and the page only links out to create one — but the CLI's own refusal printed the exact fix, so I recovered in seconds. Every promised behaviour delivered exactly: alta/modificacion/baja all saved, the success fields matched the doc word-for-word, prefix-view worked, no-match was refused gracefully, idempotency held, and `--note`-only correctly did not create a new record. The only thing the page never warned me about was the encrypted-store passphrase — the app handles it gracefully, but a naive non-interactive user would be momentarily blocked without a heads-up from the page.

## Scorecard
- **Doc clarity:** 4/5
- **App capability:** 5/5
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 2 · NIT 2
