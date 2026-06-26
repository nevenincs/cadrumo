# Testimonial — Review calculations with Google Sheets

- **Doc path:** `docs/how-to/review-with-google-sheets.md`
- **Persona:** A first-time user who calculated a modelo 303 draft and now wants to export it to Google Sheets for review — but has no Google OAuth credentials configured in this environment.
- **Date:** 2026-06-18

## Walkthrough

### Prerequisites (not on the page, but required to reach it)

The page's "Before you start" needs an active profile, classified transactions, and a calculable modelo. I built the minimum:

- `aeat config profile create persona --entity-type natural_person --tax-id 12345678Z --irpf-income-categories actividad_economica --quiet --accept-defaults` → profile created (`active_profile persona`). The page links profile setup to `profile-setup.md` (exists). It does NOT mention that profile creation advertises a `--google-export` capability flag (`--google-export / --no-google-export` "Activar la exportación a Google Sheets").
- `aeat app modelo work create --modelo 303 --year 2026 --period 1T` → work unit created (`revision_id 2023-y-siguientes`, state `borrador`).
- `aeat app modelo work calculate --modelo 303 --year 2026 --period 1T` → draft calculation revision persisted (`81bf54aa…`). All casillas 0.00 (empty ledger), which is fine for the export refusal test.

### 1. `aeat config google register --client-json ./client_secret.json`
- **Expect (doc):** Register the Desktop OAuth client for the active profile.
- **Actual:** With no file present: `Invalid value for '--client-json': File './client_secret.json' does not exist.` With a synthetic minimal JSON it refused with a precise pydantic schema error naming the missing fields (`project_id`, `auth_provider_x509_cert_url`). With a well-formed `installed` client JSON it succeeded: `operation config.google.register / client_id … / project_id persona-proj`.
- **Verdict:** OK (app). DOC-ISSUE MINOR — the page says "a Desktop OAuth client JSON from the Google Cloud Console" but never says the file's expected name (`client_secret.json` is shown only in the command), nor what required fields it must contain. A naive user with a wrong-shape JSON gets a raw pydantic dump (no plain-language "this is not a Desktop OAuth client" hint).

### 2. `aeat config google login`
- **Expect (doc):** "Run the Google consent flow."
- **Actual:** **Hung with no output for >20s** in a non-interactive shell, even with stdin redirected from `/dev/null`. No prompt text, no "open this URL", no timeout — it just blocks. I had to kill it.
- **Verdict:** APP-ISSUE / BOTH, MAJOR. The command blocks silently waiting on the browser/consent loopback with zero on-screen guidance. The page gives no warning that this step opens a browser and requires interactive consent.

### 3. `aeat config google status`
- **Expect (doc):** Show Google session status.
- **Actual:** `operation config.google.status / client_registered True / session_present False / client_id …`. Clear and instant.
- **Verdict:** OK.

### 4. `aeat config google folder set <id>` / `folder get`
- **Expect (doc):** Set/read the Drive folder where spreadsheets are created.
- **Actual:** Both succeeded WITHOUT a live session: `folder set` → `root_folder_id 1AbCdEfGhIjKlMnOpQrStUvWxYz`; `folder get` → `configured True / root_folder_id …`. The folder id is accepted as an opaque string (no Drive validation, expected offline).
- **Verdict:** OK. (Minor: they don't verify the folder exists, but the page says to copy the id from the folder URL, so acceptable.)

### 5. `aeat config google sync probe`
- **Expect (doc):** Diagnostic probe.
- **Actual:** `Refused. La autenticación con Google falló: No hay ningun token OAuth de Google persistido para el perfil activo. Ejecuta 'aeat config google login' primero.` (exit 0)
- **Verdict:** OK — graceful refusal that names the exact fix.

### 6. `aeat config google sync calc export --modelo 303 --year 2026 --period 1T`  ← the page's main promise
- **Expect (doc):** Create a Google Sheets workbook inside `aeat-vault/` in Drive.
- **Actual:** `Refused. La autenticación con Google falló: No hay ningun token OAuth de Google persistido para el perfil activo. Ejecuta 'aeat config google login' primero.` (exit 0)
- **Verdict:** OK (app) — refusal is graceful and names the exact fix. DOC-ISSUE MINOR — the page never warns that, without a completed `login`, every sync/export verb refuses; a reader who skips/can't-complete login hits this on the main command.

### 7. `aeat config google sync calc pull … --spreadsheet-id <id>`
- **Expect (doc):** Pull typed edits back from the Sheet.
- **Actual:** Same auth refusal as export (exit 0).
- **Verdict:** OK.

### 8. `aeat config google sync calc verify --modelo 303 --year 2026 --period 1T`
- **Expect (doc):** "Verification compares the calculation surfaces implemented by the app. It does not submit a filing to AEAT." — reads like a LOCAL comparison.
- **Actual:** Same Google-auth refusal as export (exit 0): `…No hay ningun token OAuth… Ejecuta 'aeat config google login' primero.`
- **Verdict:** DOC-ISSUE MINOR — the prose frames verify as a local-app comparison, but it requires a live Google session (it lives under `config google sync`). A reader could reasonably expect to verify offline; the page should state verify needs Google auth too.

### 9. `aeat config google sync push --dry-run` / `push`
- **Expect (doc):** "Preview with `--dry-run` first; it reports what would upload per storage area without changing anything."
- **Actual:** BOTH refused on auth (exit 0), same message — `--dry-run` did NOT produce a per-area preview; it refused before reporting anything.
- **Verdict:** DOC-ISSUE MINOR — the page implies `--dry-run` is a safe offline preview; in practice it still requires a live Google session and refuses with no report when unauthenticated.

### 10. `aeat config google logout`
- **Expect (doc):** Clear the session, keep the registered OAuth client.
- **Actual:** `operation config.google.logout / token_removed False / metadata_removed False / client_preserved True`. Matches the page exactly (nothing to remove since login never completed; client preserved).
- **Verdict:** OK.

### 11. "Where this fits": `aeat app ledger preflight` / `aeat app ledger status`
- **Actual:** `preflight` → `ready true, issues 0`; `status` → all counts 0, `Preparado True`. Both clean and instant.
- **Verdict:** OK.

## Findings

1. **[MAJOR] [BOTH]** `aeat config google login` hangs silently in a non-interactive shell. With `</dev/null` and >20s wait it produced NO output, no URL, no prompt, no timeout — it just blocks until killed. Repro: register a well-formed client JSON, then `aeat config google login </dev/null`. **Fix (app):** detect non-interactive/headless and fail fast with an instructive message (e.g. "consent requires an interactive browser session"); print the consent URL up front. **Fix (doc):** warn that this step opens a browser and requires interactive consent, and that it cannot complete in a headless/CI shell.

2. **[MINOR] [DOC]** The page references "a Desktop OAuth client JSON from the Google Cloud Console" but never explains the file's expected shape/required fields, and never names the `--google-export` profile capability flag surfaced at profile creation. A naive user feeding a wrong-shape JSON gets a raw pydantic schema dump. **Fix:** add a one-line note on what a valid Desktop OAuth client JSON contains and link the Cloud Console "Create OAuth client (Desktop app)" step; mention whether `--google-export` must be enabled on the profile.

3. **[MINOR] [DOC]** Every `config google sync …` verb (export, pull, **verify**, push, even `push --dry-run`) refuses without a completed `login`, but the page sets no expectation that login is a hard gate for all of them. **Fix:** add a sentence up top: "All export/pull/verify/push commands require a completed `aeat config google login`; run `aeat config google status` to confirm `session_present`."

4. **[MINOR] [DOC]** `calc verify` is framed as a local app-vs-app comparison ("does not submit a filing"), yet it requires a live Google session. **Fix:** state explicitly that verify runs through the Google sync surface and needs auth, or move/duplicate a local verification path that works offline.

5. **[MINOR] [DOC]** `sync push --dry-run` is described as a safe offline preview ("without changing anything"), but it refuses on auth before producing any report. **Fix:** clarify that `--dry-run` still requires a live Google session, or make `--dry-run` enumerate storage areas offline.

6. **[NIT] [DOC]** No passphrase/master-key warning. The harness pre-set `AEAT_SECRET_PASSPHRASE`; a real non-interactive user would be blocked at the master-key prompt before any Google command. Worth a one-line note (consistent with the brief's expectation).

## Testimonial

Once I had a calculated draft, the page read like a clean, linear flow — register, login, set folder, export. The refusals I hit were genuinely the *good* kind: every sync command stopped politely and told me the exact next command (`Ejecuta 'aeat config google login' primero`), and `logout` behaved precisely as documented. What tripped me hard was `login` itself: it hung in silence with no prompt or URL, and as an English reader I had no signal it was even waiting on a browser. The page also let me believe `verify` and `push --dry-run` were offline/local operations, so their auth refusals felt like contradictions of what I'd just read. The app delivered the export promise's *guardrails* well, but the page undersells that Google auth is a hard, interactive gate for the whole workflow.

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 4 / 5 (graceful, fix-naming refusals everywhere except the silent `login` hang)
- **Findings by severity:** BLOCKER 0 · MAJOR 1 · MINOR 4 · NIT 1
