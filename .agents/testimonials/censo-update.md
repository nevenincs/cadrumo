# Testimonial — docs/how-to/censo-update.md

- **Doc path:** `docs/how-to/censo-update.md` (page title: "Link Modelo 036 census information")
- **Persona:** A first-time user trying to sync/review AEAT census (censo) facts into a profile (pull / show / compare / apply), expecting live pull to refuse without auth but local show/compare/apply to behave.
- **Date:** 2026-06-18
- **Base:** `/tmp/persona-censo-fg`

## Walkthrough

### 1. `aeat config profile status` (Before you start)
- **Expect:** A way to confirm the active profile.
- **Actual (no profile yet):**
  ```
  Sin perfil configurado. Ejecuta `aeat config profile create NAME` para empezar.
  next_action	aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>
  ```
- **Verdict:** OK (the command works and the refusal is instructive) — but see Finding 1: the page never tells a naive user how to create a profile; it only links out, and the page assumes a profile already exists.

### 1b. (Out-of-page prerequisite) `aeat config profile create personatest --quiet --accept-defaults --tax-id 12345678Z --activity "Consultoria"`
- **Expect:** Not on the page; I had to synthesize this to proceed.
- **Actual:**
  ```
  profile	personatest
  estado	creado
  active_profile	personatest
  ```
- **Verdict:** DOC-ISSUE MINOR — necessary setup the page leans entirely on a link for.

### 2. `aeat config profile status` (re-run with a profile)
- **Expect:** Confirms active profile.
- **Actual:**
  ```
  profile	personatest
  identity.tax_id	sha256:1c9f9632
  activities.description	Consultoria
  iva.regime	GENERAL
  Próximo paso: `aeat app overview status`
  ```
- **Verdict:** OK.

### 3. `aeat config profile censo pull`
- **Expect:** A live read requiring an active AEAT auth session; the page says it "requires an active AEAT authentication session" and may stop with a no-facts error.
- **Actual (refused in <2s, no hang):**
  ```
  auth_configured=False
  auth_identity_alignment=mismatch
  auth_identity_kind=NIE
  ...
  Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida o actualiza el perfil antes de la autenticación AEAT en directo.
    -> Run `aeat config switch NAME`
  ```
- **Verdict:** APP=OK (graceful, fast refusal with a suggestion) / DOC partial — the refusal is about an **identity mismatch (Cl@ve Móvil identity vs profile fiscal id)**, NOT the "no auth session" reason the page leads with. A naive user gets a different rejection than the page predicts (Finding 2). No browser/login was triggered; no hang.

### 4. `aeat config profile censo show`
- **Expect:** Show the latest snapshot; page says it refuses if no snapshot exists.
- **Actual:**
  ```
  Refused. No se ha capturado ninguna instantánea del censo para el perfil <profile-id>.
  ```
- **Verdict:** OK — refusal matches the page's promise ("they refuse instead of inventing censo values").

### 5. `aeat config profile censo show --snapshot-id bogus123`
- **Expect:** Show a specific earlier snapshot by reference number.
- **Actual:**
  ```
  Refused. censo snapshot 'bogus123' not found in bucket '<profile-id>'
    -> Run `aeat config profile censo pull`
  ```
- **Verdict:** OK functionally, but note this message is **in English** while the bare `show` refusal (step 4) is **in Spanish** — inconsistent language within the same subcommand (Finding 3). Also "reference number" in the doc vs `snapshot-id` flag naming is a slight mismatch.

### 6. `aeat config profile censo compare`
- **Expect:** Reports matching / diverging / censo-only / profile-only fields; refuses without a snapshot.
- **Actual:**
  ```
  Refused. No se ha capturado ninguna instantánea del censo para el perfil <profile-id>.
  ```
- **Verdict:** OK — refuses cleanly. Could not exercise the actual diff output because no snapshot can be obtained offline (expected in this environment).

### 7. `aeat config profile censo apply`
- **Expect:** Writes AEAT censo facts into the local profile; refuses without a snapshot.
- **Actual:**
  ```
  Refused. No se ha capturado ninguna instantánea del censo para el perfil <profile-id>.
  ```
- **Verdict:** OK — refuses cleanly, preserving the page's "only after review" guarantee.

### 8. `aeat app modelo m036 alta --declared-on 2026-01-10 --sede-justificante ACUSE123`
- **Expect:** Record a Modelo 036 alta filed outside aeat; does not file with AEAT.
- **Actual:**
  ```
  declaration_id	6122ab1e...fd6b
  event_kind	alta
  declared_on	2026-01-10
  sede_justificante	ACUSE123
  ```
- **Verdict:** OK — recorded locally as promised. (Doc uses placeholder `<acuse>`; help calls it "Identificador opcional del acuse de recibo" — clear enough.)

### 9. `aeat config profile validate`
- **Actual:** `readiness	ready	issues=0` ... `valid	True`
- **Verdict:** OK.

### 10. `aeat config profile edit personatest --quiet --activity "Consultoria IT"`
- **Actual:** `profile	personatest` / `estado	actualizado`
- **Verdict:** OK. Note: the doc shows `edit <profile-name> --quiet --activity <value>` — the `--quiet` flag is needed for non-interactive use and the page does include it; good.

### 11. `aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T`
- **Actual:** `readiness	ready	missing=0` / `modelo 303` / `revision_id 2023-y-siguientes`
- **Verdict:** OK.

## Findings

1. **[MAJOR] [DOC]** The page assumes an active profile already exists but never gives the create command inline; "Before you start" only links to `profile-setup.md`. A naive user on this page alone, with no profile, cannot start. The CLI's own `next_action` (`aeat config profile create NAME --tax-id ... --activity ...`) is more helpful than the page. *Fix:* add a one-line create example or a clearer "run this first" callout, not just a bare link.

2. **[MAJOR] [BOTH]** The page frames the only `pull` failure mode as "requires an active AEAT authentication session" + "no-facts error", but the real refusal I hit was an **identity mismatch** ("La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo"). A naive user is told to expect "log in first" and instead gets "switch profiles / fix your profile", which is confusing. *Fix:* document that `pull` also refuses on identity mismatch between the configured auth identity and the profile fiscal ID, and that auth must be configured (link to authenticate-with-aeat.md is present, good).

3. **[MINOR] [APP]** Language inconsistency inside the censo family: `censo show` (no snapshot) refuses in **Spanish**, but `censo show --snapshot-id bogus123` refuses in **English** ("censo snapshot 'bogus123' not found"). Same subcommand, two languages. *Fix:* localize the snapshot-not-found message consistently.

4. **[MINOR] [DOC]** No passphrase warning. The page never mentions that a master-key passphrase is required; in a non-interactive shell every command would block on the prompt without `AEAT_SECRET_PASSPHRASE`. The harness supplied it, but a real naive user would be stuck. *Fix:* note that profile/censo commands require the master-key passphrase (interactively prompted).

5. **[NIT] [DOC]** Terminology drift: the page says "Show a specific earlier snapshot by its **reference number**" but the flag is `--snapshot-id` and the error calls it a "snapshot". Align the prose to "snapshot id".

6. **[NIT] [DOC]** Filename vs title: the file is `censo-update.md` but the H1 is "Link Modelo 036 census information" — fine, but the slug and title diverge; cross-links elsewhere may expect a "censo update" name.

7. **[NIT] [BOTH]** English docs, Spanish CLI: all help text and most refusals render in Spanish while the page is English. Expected per environment, but worth a one-line note on the page that the CLI surfaces Spanish.

## Testimonial

Following only this page, I hit a wall immediately: I had no profile and the page just pointed me at another doc instead of showing me the create command — the CLI's own hint rescued me. Once I had a profile, the censo flow behaved well and honestly: `pull` refused fast and clearly (no hang, no browser), and `show`/`compare`/`apply` all refused cleanly with "no snapshot captured" exactly as the page promised, never inventing data. The biggest friction was that `pull` failed for a reason the page never mentions (an identity mismatch, not "log in first"), and that the refusal messages flip between Spanish and English. The local recording path (`m036 alta`) and the closing profile checks (`validate`, `edit`, `preflight`) all worked exactly as documented.

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 4 / 5 (graceful refusals everywhere; couldn't exercise real compare/apply output without auth, as expected)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 3
