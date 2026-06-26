# Testimonial — Read live AEAT data

- **Doc path:** `docs/how-to/read-live-aeat-data.md`
- **Persona:** A first-time user trying to pull live data from AEAT (expedientes, notifications, filed declarations) on a machine with no AEAT auth and no browser.
- **Date:** 2026-06-18

---

## Walkthrough

### 1. `aeat config profile censo pull` (no profile yet)
- **Command:** `uv run --no-sync aeat config profile censo pull`
- **Expected (from page):** The page's "How a live read works" section prints this verbatim as the first concrete example and says it "reads your censo from AEAT and saves a snapshot."
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
  Exit 2.
- **Verdict:** OK (graceful, names the fix) — but the message is Spanish while the doc is English. MINOR/DOC: the page's example assumes a profile exists; the "Before you start" prerequisite is correct, but the example itself never restates it.

### 2. Create a profile to satisfy the prerequisite
- **Command:** `aeat config profile create persona1 --tax-id 12345678Z` → refused (needs interactive terminal), then `aeat config profile create persona1 --quiet --tax-id 12345678Z`
- **Expected:** Page links to `profile-setup.md`; I synthesized a minimal profile.
- **Actual:** First form refused with a clear two-option recovery message naming `--quiet`. Second form succeeded: `estado=creado`, `active_profile=persona1`. Exit 0.
- **Verdict:** OK (not a command on this page; setup only). The refusal-with-recovery is excellent.

### 3. `aeat config profile censo pull` (active profile, no auth)
- **Command:** `uv run --no-sync aeat config profile censo pull`
- **Expected (from page):** Reads censo from AEAT and saves a snapshot.
- **Actual:** A full `auth_*` preflight dump (`auth_configured=False`, `auth_persisted_session=no_session`, `auth_identity_alignment=mismatch`) then:
  ```
  Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida o actualiza el perfil antes de la autenticación AEAT en directo.
    -> Run `aeat config switch NAME`
  ```
  Exit 2. Returned in well under 30s. No hang.
- **Verdict:** OK (APP) on gracefulness/speed; DOC-ISSUE — the page never warns auth is unconfigured by default, and the refusal blames an "identity mismatch" rather than "you have not authenticated," which is confusing given `auth_configured=False`.

### 4. `aeat app live --help`
- **Command:** `uv run --no-sync aeat app live --help`
- **Expected (from page):** "Run `aeat app live --help` to see them."
- **Actual:** Lists `filed`, `iva-wallet`, `notifications`, `portals`, `expedientes`, `justificante`, `verify`, `borrador`. All Spanish descriptions. Exit 0.
- **Verdict:** OK. The page's three named verbs (`justificante`, `notifications`, `filed`) all exist; `expedientes` (which the page does NOT name in the live group) also exists.

### 5. `aeat app live notifications pull`
- **Command:** `uv run --no-sync aeat app live notifications pull`
- **Expected (from page):** A read-only pull saving a snapshot.
- **Actual:** Same `auth_*` preflight + identity-mismatch refusal as step 3. Exit 2. Fast.
- **Verdict:** OK (graceful, fast refusal — exactly what the persona hoped for). Same DOC gap on auth expectation.

### 6. `aeat app live filed pull` (verbatim, as printed on the page)
- **Command:** `uv run --no-sync aeat app live filed pull`
- **Expected (from page):** The page prints `aeat app live filed pull` as an example of the read-only verbs.
- **Actual:**
  ```
  Invalid value: either --year or both --from-year and --to-year are required
  ```
  Exit 2. The arg-validation error fires BEFORE any auth check.
- **Verdict:** DOC-ISSUE (MAJOR-leaning-MINOR) — copying the page's literal command does not produce the documented "live read"; it produces an unrelated argument error. With `--year 2024` added it then reached the graceful identity-mismatch auth refusal (confirmed).

### 7. `aeat app live expedientes pull`
- **Command:** `uv run --no-sync aeat app live expedientes pull` then `... --year 2024`
- **Expected (from page):** The persona expected an expedientes pull; the page mentions expedientes only via a linked guide, not in the live-group examples.
- **Actual:** Bare form → same `--year`/`--from-year` required error (exit 2). With `--year 2024` → graceful identity-mismatch refusal (exit 2). Fast.
- **Verdict:** OK on the app; DOC-NIT — expedientes is not named in this page's live-group example list even though it is a core "read live AEAT data" surface and the persona expected it here.

### 8. `aeat app live justificante pull` (verbatim, as printed on the page)
- **Command:** `uv run --no-sync aeat app live justificante pull`
- **Expected (from page):** A read-only justificante pull.
- **Actual:**
  ```
  Missing option '--modelo'.
  ```
  Exit 2. `--help` shows `--modelo`, `--year`, `--period` are all `[required]`. With all three supplied (`--modelo 303 --year 2024 --period 1T`) it reached the graceful identity-mismatch auth refusal (exit 2).
- **Verdict:** DOC-ISSUE — same as step 6: the page's literal `justificante pull` example cannot run as printed; it needs three required options the page never mentions.

### 9. `aeat config profile censo apply`
- **Command:** `uv run --no-sync aeat config profile censo apply`
- **Expected (from page):** "writes the reviewed censo facts into your local profile."
- **Actual:**
  ```
  Refused. No se ha capturado ninguna instantánea del censo para el perfil <profile-id>.
  ```
  Exit 2.
- **Verdict:** OK — sensible refusal (nothing pulled yet to apply).

---

## Findings

1. **[MINOR] [DOC]** No passphrase warning. The page never mentions that a master-key passphrase is required for any profile/local-store operation. A naive user in a non-interactive shell would be blocked (the harness pre-set `AEAT_SECRET_PASSPHRASE` for me). **Fix:** add a one-line note in "Before you start" that a master-key passphrase is required and link to where it is set.

2. **[MAJOR] [DOC]** The literal `pull` examples are not runnable as printed. `aeat app live filed pull` errors with `either --year or both --from-year and --to-year are required`, and `aeat app live justificante pull` errors with `Missing option '--modelo'` (also requires `--year`, `--period`). The page presents both as complete read-only commands. A naive user copying them hits an argument error, not the documented read. **Fix:** show the required options inline (e.g. `aeat app live filed pull --year 2024`, `aeat app live justificante pull --modelo 303 --year 2024 --period 1T`) or explicitly defer to the per-surface guides for the full invocation.

3. **[MINOR] [DOC]** The page sets no expectation that authentication is unconfigured by default. The persona's whole task is "no auth → should refuse." It does refuse gracefully, but the page's "If a live read fails" section frames failure as "authentication is missing or the session expired" while the actual refusal is an **identity mismatch** (`La identidad de Cl@ve Móvil no coincide con la identidad fiscal`). **Fix:** mention the identity-alignment requirement (the Cl@ve identity must match the profile's fiscal identity) as a distinct failure mode in "If a live read fails."

4. **[MINOR] [BOTH]** Refusal message is confusing vs. the preflight. The preflight reports `auth_configured=False` (auth not set up at all) yet the headline refusal blames an identity *mismatch*. For a user who has configured nothing, "mismatch" is misleading — the more accurate refusal would be "authentication not configured." **Fix (app):** when `auth_configured=False`, refuse with an "auth not configured" message and point to `authenticate-with-aeat.md`, reserving the mismatch message for the case where auth IS configured but identities differ.

5. **[NIT] [DOC]** Expedientes is a core live-read surface the persona expected on this page, but it is not listed among the `aeat app live` examples (only `justificante`, `notifications`, `filed` are named). **Fix:** add `aeat app live expedientes pull` to the example list in "How a live read works."

6. **[NIT] [DOC]** Spanish CLI vs. English docs. Every refusal and help screen renders in Spanish (`Refused. No hay un perfil activo...`). The page is English and never warns the CLI output is Spanish. **Fix:** a one-line note that CLI messages render in Spanish.

---

## Testimonial

As a first-timer with no AEAT login and no browser, I was relieved that every `pull` refused fast — no hangs, no browser ever launched, each command back in well under 30 seconds with a clear exit code 2. The app's safety boundary felt solid and the refusals were genuinely instructive (they even printed a `-> Run` next step). But the page tripped me twice: the two commands it prints verbatim — `filed pull` and `justificante pull` — don't actually run as written, because they need required `--year`/`--modelo`/`--period` flags the page never mentions, so I got argument errors instead of the promised "live read." And once I did get to a real refusal, it blamed an "identity mismatch" even though I'd configured no authentication at all, which would leave a naive user hunting for a problem that isn't really the problem. The page sets the read-only/safety expectation well; it sets the auth-and-arguments expectation poorly.

## Scorecard

- **Doc clarity:** 3 / 5 (good safety framing and prerequisites; but two unrunnable verbatim examples and no auth/passphrase expectation)
- **App capability:** 4 / 5 (fast, graceful, exit-coded refusals with next-step hints; the `auth_configured=False` → "mismatch" message is the one rough edge)
- **Findings by severity:** BLOCKER 0 · MAJOR 1 · MINOR 3 · NIT 2
