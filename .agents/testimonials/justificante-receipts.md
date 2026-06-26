# Testimonial — Pull and keep your filing receipts

- **Doc path:** `docs/how-to/justificante-receipts.md`
- **Persona:** A first-time user trying to pull a filing receipt (justificante) from the AEAT sede, store it, and find it again — also expecting a "parse a local file" path.
- **Date:** 2026-06-18

---

## Walkthrough

### 1. `aeat app live justificante --help` (orientation, not on page)
- **Expected:** A group exposing the pull/list/view verbs the page describes.
- **Actual:** Group help in Spanish: "Capturas de justificantes AEAT (solo lectura)..." with commands `pull`, `list`, `view`. Matches the page's three sections exactly.
- **Verdict:** OK.

### 2. `aeat app live justificante pull --modelo 130 --year 2026 --period 1T` (first attempt, no profile)
- **Expected:** Per the page, fetch the receipt and report the stored capture (snapshot id, expediente, CSV code, fingerprint, capture time).
- **Actual:** Refused, graceful:
  ```
  Invalid value: No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** DOC-ISSUE, MINOR. The refusal is excellent (names the exact fix), but the page lists "an active profile" as a prerequisite with **no command and no link** to create one. A naive reader is stranded until they trigger the error.

### 3. `aeat config profile create persona --tax-id 12345678Z` (following the error's instruction verbatim)
- **Expected:** Profile created (the error message implied this single command).
- **Actual:** Refused:
  ```
  Refused. El asistente guiado necesita una terminal interactiva, y esta ejecución no la tiene.
  Todavía no se ha guardado nada.
  ...
  2. O créalo en un solo paso indicando los datos obligatorios como flags:
       aeat config profile create NAME --quiet --tax-id NIF/CIF/DNI/NIE
  ```
- **Verdict:** OK (graceful, instructive) — but note the on-page prerequisite gap compounds here: the error message AEAT itself printed in step 2 (`profile create NAME --tax-id ...`) is **missing `--quiet`** and hangs/refuses non-interactively. Scaffolding friction, not strictly my page.

### 4. `aeat config profile create persona --quiet --tax-id 12345678Z`
- **Expected:** Profile created and active.
- **Actual:** `profile persona / estado creado / active_profile persona`.
- **Verdict:** OK.

### 5. `aeat app live justificante pull --modelo 130 --year 2026 --period 1T` (with active profile)
- **Expected:** Fetch + store the receipt; report snapshot id, expediente, CSV code, fingerprint, capture time. The page says nothing about needing prior authentication setup (only links it).
- **Actual:** No browser launch, no hang — a long `auth_preflight` diagnostic dump, then:
  ```
  auth_identity_alignment=mismatch
  ...
  Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida o actualiza el perfil antes de la autenticación AEAT en directo.
    -> Run `aeat config switch NAME`
  ```
- **Verdict:** APP/DOC-ISSUE, MINOR. The refusal is graceful (no hang — good), but for a naive user the diagnostic surface (~30 lines of `auth_*=...`) is overwhelming, and the refusal blames an *identity mismatch* rather than the actual blocker a reader would expect ("no AEAT session — authenticate first"). The page links [Authenticate with AEAT] but never warns that a configured, identity-matching live session is mandatory before `pull` does anything — so the page under-sets expectations.

### 6. `aeat app live justificante pull --help` (probe for a local-file path)
- **Expected (from persona brief):** Possibly a local-file parse option, since the brief mentions "parse a local file."
- **Actual:** Only `--modelo`, `--year`, `--period` (all required). **No `--file` / local-file option exists on `justificante pull`.**
- **Verdict:** OK (the page never promises a local-file path here). The local-file parse lives elsewhere — `aeat app modelo reconcile file --file` — which the page only gestures at via the "Use a receipt" section. The page is internally honest, but a reader expecting to ingest a downloaded PDF receipt directly into the justificante store finds no such path.

### 7. `aeat app live justificante list`
- **Expected:** Rows of stored captures (snapshot id, modelo, year, period, capture time).
- **Actual:** `bucket <profile-id> / count 0` — clean (no captures, because the pull was refused).
- **Verdict:** OK. Empty state is graceful; though it would be friendlier to hint "no captures yet — run `... pull` first."

### 8. `aeat app live justificante view` (no id) and `... view deadbeef`
- **Expected:** Show full provenance of one capture; an unambiguous prefix suffices.
- **Actual:** No id → `Missing argument 'SNAPSHOT_ID'`. Bogus id →
  ```
  Refused. justificante capture snapshot 'deadbeef' not found in bucket '<profile-id>'
    -> Run `aeat app live justificante list`
  ```
- **Verdict:** OK. Positional id as documented; both refusals instructive. Could not exercise `view` against a real capture (no successful pull possible without live AEAT auth) — an environment limitation the page's "Before you start" correctly anticipates.

---

## Findings

1. **[MINOR][DOC]** Prerequisite "an active profile" has no command or link. The page lists it under "Before you start" but never tells the reader how to create/activate one; they only discover the fix by triggering the refusal. *Fix:* link to the profile-setup how-to (e.g. workstation-setup / quickstart) or inline `aeat config profile create NAME --quiet --tax-id <NIF/CIF/DNI/NIE>` alongside the prerequisite.

2. **[MINOR][DOC]** No passphrase warning. The page never states that a master-key passphrase is required; a naive user in a non-interactive shell (or any first run) would be blocked at the prompt. The harness pre-set `AEAT_SECRET_PASSPHRASE`, masking this, but the omission is real. *Fix:* add a one-line note that the first command will prompt for the profile passphrase.

3. **[MINOR][BOTH]** `pull` refusal is verbose and mis-framed for a newcomer. It emits ~30 `auth_*=...` diagnostic lines and refuses with "identidad de Cl@ve Móvil no coincide" rather than a plain "no active AEAT session — run [Authenticate with AEAT] first." The page should warn that `pull` needs a *configured, identity-matching* live session, not merely "working AEAT authentication." *Fix:* strengthen the prerequisite wording; consider gating the diagnostic dump behind a verbose flag.

4. **[NIT][DOC]** Spanish/English split. Every CLI message (help, refusals) is Spanish; the doc is English. An English-only reader cannot map "No hay un perfil activo" / "solo lectura" to the page's prose without guessing. *Fix:* note that CLI output is Spanish, or show expected Spanish snippets.

5. **[NIT][DOC]** No "parse a local receipt PDF" path is offered or disclaimed. A user who already downloaded their justificante PDF from the portal has no documented way to store it as a capture (`pull` is live-only; the local-file path is `modelo reconcile file --file`, only hinted). *Fix:* add a sentence clarifying that storing a receipt is live-pull only, and point to reconcile-from-file for local artefacts.

6. **[NIT][APP]** Empty `list` could hint next step. `count 0` is correct but a "no captures yet — run `... pull`" next-action would aid first-timers.

---

## Testimonial

Following the page literally, I hit a wall immediately: it told me I needed "an active profile" but not how to make one, so my first real command bounced. Every step after that *refused gracefully* — no hangs, no crashes, and each refusal pointed at the exact next command — which felt reassuring even when blocked. The live `pull` did exactly what a safe read-only command should (it refused instead of hanging on a browser), but it dumped a wall of `auth_*` diagnostics and blamed an "identity mismatch" rather than the plain truth that I have no AEAT session yet, and the page never warned me how much auth setup `pull` truly demands. I could verify the *shape* of the app (pull/list/view all exist and behave as described) but never the *payoff* — I couldn't store or view a real receipt without live AEAT credentials, which the page's "Before you start" did at least flag.

---

## Scorecard

- **Doc clarity:** 3.5 / 5
- **App capability:** 4 / 5 (graceful, instructive refusals; no hangs; payoff unverifiable without live auth)
- **Findings by severity:** BLOCKER 0, MAJOR 0, MINOR 3, NIT 3
