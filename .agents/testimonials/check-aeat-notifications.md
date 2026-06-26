# Testimonial — Check AEAT notifications and live observations

- **Doc path:** `docs/how-to/check-aeat-notifications.md`
- **Persona:** A first-time user wanting to check AEAT notifications (DEHu / buzón), with no live AEAT auth configured.
- **Date:** 2026-06-18

---

## Walkthrough

### Starting state
- **Command:** `aeat config profile list`
- **Expected:** Doc's "Before you start" says I need an active profile; I check what I have.
- **Actual:** `active_profile	<none>` / `profiles	<none>` — no profile exists. Naive starting state.
- **Verdict:** OK (baseline).

### 1. Notifications

**`aeat app live notifications pull`** (no profile)
- **Expected:** Download DEHu notifications and save locally.
- **Actual:**
  `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.` (exit 2)
- **Verdict:** OK — graceful, instructive refusal (in Spanish). No hang, no browser.

**`aeat app live notifications list`** (no profile)
- **Expected:** "Download your current DEHu notifications" (the doc's wording for `list` is misleading — see Findings).
- **Actual:** `Invalid value: No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.` (exit 2)
- **Verdict:** OK (refusal) / DOC-ISSUE (wording).

**`aeat app live notifications latest`** / **`view <id>`** (no profile)
- **Actual:** Same active-profile refusal, exit 2.
- **Verdict:** OK refusal.

### Setup to test offline views (synthesized minimal prerequisite)
- **Command:** `aeat config profile create tester --tax-id 12345678Z`
- **Actual:** `Refused. El asistente guiado necesita una terminal interactiva...` then a 2-option recovery telling me to add `--quiet`. (exit 2)
- **Retry:** `aeat config profile create tester --quiet --tax-id 12345678Z` → `estado	creado`, `active_profile	tester`. (exit 0)
- **Verdict:** OK — excellent non-interactive recovery guidance (but this prerequisite path is NOT explained on this page).

### 1. Notifications — with a profile
**`aeat app live notifications list`** → `bucket <profile-id>` / `count 0` (exit 0). Works fully offline.
**`aeat app live notifications latest`** → `snapshot_id -` (exit 0). Works offline.
**`aeat app live notifications view nope123`** → `Refused. No hay ninguna instantánea... -> Run 'aeat app live notifications list'` (exit 2). Graceful.
**`aeat app live notifications pull`** (profile, no auth) →
emits a large `auth_preflight` diagnostic block (~30 lines: `auth_configured=False`, `auth_identity_alignment=mismatch`, `auth_probe_result=ok`, ...) then
`Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida... -> Run 'aeat config switch NAME'` (exit 2).
- **Verdict:** OK — refused in <2s, no browser launched, no hang.

### 2. Declaration history (expedientes)
**`aeat app live expedientes list`** → `count 0` (exit 0). Offline OK.

### 3. Filed declaration detail
**`aeat app live filed list --modelo 303 --from-year 2020 --to-year 2026`** →
auth preflight + `Refused. La identidad de Cl@ve Móvil no coincide...` (exit 2).
- **Expected (from doc):** "List filed returns **without downloading their full contents**" — reads as a local/cheap operation.
- **Actual:** It performs a LIVE AEAT read and refuses on auth. Surprising vs. the doc's framing.
- **Verdict:** DOC-ISSUE.

### 4. NIF / EU VAT verification
**`aeat app live verify list --surface tgvi`** → `count 0` (exit 0). Offline OK.
**`aeat app live verify nif-iva ESB12345678`** → `Error. IXVI form requires AEAT auth tier above cl@ve-movil; landed on AEAT 4033 page (failure_mode=auth_gate_detected)` (exit 1).
- **Verdict:** OK refusal (note: English error, exit 1 not 2 — inconsistent with other live refusals).

### 5. Official AEAT portal catalogue
**`aeat app live portals list --category sede_modelo --modelo 303`** (exact doc command) →
`Invalid value for '--category': 'sede_modelo' is not one of 'auth', 'filing', 'censo', 'consultation', 'borrador', 'payment', 'calendar_reference'.` (exit 2)
- **Retry with valid category:** `aeat app live portals list --category filing --modelo 303` →
`Invalid value: --category y --modelo son mutuamente excluyentes.` (exit 2)
- **Verdict:** DOC-ISSUE (BLOCKER) — the documented command is doubly wrong; it can never succeed.

### 6. Borrador (draft Modelo 100)
**`aeat app live borrador 100 list --state active`** → `count 0` (exit 0). Offline OK.

### 7. IVA compensation balance
**`aeat app live iva-wallet history --as-of-year 2026`** → `row_count=0` ... (exit 0). Offline OK.

---

## Findings

1. **[BLOCKER] [DOC]** — Section 5 documented command is invalid two ways.
   `aeat app live portals list --category sede_modelo --modelo 303` fails because (a) `sede_modelo` is not an accepted `--category` (accepted: `auth, filing, censo, consultation, borrador, payment, calendar_reference`), and (b) `--category` and `--modelo` are **mutually exclusive**. The exact documented invocation can never run.
   **Fix:** Replace with a valid single-axis example, e.g. `aeat app live portals list --modelo 303` OR `aeat app live portals list --category filing`.

2. **[MAJOR] [DOC]** — No mention of the master-key passphrase requirement.
   Every command needs the profile's encrypted store to open. In a non-interactive shell with no `AEAT_SECRET_PASSPHRASE`, a naive user is blocked before any of these commands. The page never warns of this.
   **Fix:** Add a one-line note in "Before you start" pointing to where the passphrase is set/prompted.

3. **[MAJOR] [DOC]** — Profile-creation prerequisite is under-served for the assumed reader.
   The page assumes an active profile but the only link goes to `profile-setup.md`. The refusal text correctly hints `aeat config profile create NAME --tax-id ...`, but that interactive form itself refuses non-interactively and needs `--quiet`. A naive user following the hint verbatim hits a second refusal.
   **Fix:** Ensure `profile-setup.md` documents the `--quiet --tax-id` non-interactive one-step form prominently; consider mentioning it here.

4. **[MINOR] [DOC]** — Misleading `list` descriptions for live-read verbs.
   For notifications, the doc labels `list` as "Download your current DEHu notifications" — but `pull` downloads and `list` shows local snapshots. Worse, `filed list` is described as listing "without downloading", yet it performs a **live** AEAT read and refused on auth. The local-vs-live distinction is blurred.
   **Fix:** State clearly which verbs are local (`list`, `latest`, `view`, `history`) and which hit AEAT (`pull`, `pull-*`, `filed list`, `verify nif-iva/tgvi`).

5. **[MINOR] [APP]** — Inconsistent refusal exit codes / language for live-auth failures.
   `notifications pull` and `filed list` refuse with exit 2 in Spanish; `verify nif-iva` errors with exit 1 in English. A user scripting these gets inconsistent signals.
   **Fix:** Normalize exit code and language for auth-gate refusals across the `live` surface.

6. **[NIT] [APP]** — `pull` dumps a ~30-line `auth_preflight` diagnostic before the one-line refusal.
   Useful for debugging but noisy for a first-timer; the actionable line is buried at the bottom.
   **Fix:** Consider summarizing or gating the verbose preflight behind a `--verbose`/`--debug` flag.

7. **[NIT] [DOC]** — Spanish CLI output vs. English docs.
   All refusals/help render in Spanish while the page is English; an English-only reader can't match the doc to the error. (Brief-noted expected friction.)

---

## Testimonial

Checking notifications without auth behaved well: every live `pull` refused fast, in plain language, with a concrete next command, and nothing ever tried to open a browser or hang. The local views (`list`, `latest`, `view`, `history`) genuinely work offline once a profile exists — that part delivered exactly what the page implied. But the page tripped me twice: the portals example in Section 5 is simply broken (the documented `--category sede_modelo --modelo 303` is rejected as an invalid category *and* as mutually-exclusive flags), and nothing warned me that a profile + passphrase must exist first, so a literal first-timer is blocked before command one. The app is robust; the page over-promises "no setup" and ships one un-runnable command.

---

## Scorecard
- **Doc clarity:** 2.5 / 5
- **App capability (graceful refusal + offline local views):** 4 / 5
- **Findings:** BLOCKER 1, MAJOR 2, MINOR 2, NIT 2
