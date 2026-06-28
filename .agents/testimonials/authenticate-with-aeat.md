# Testimonial — Authenticate with AEAT

- **Doc path:** `docs/how-to/authenticate-with-aeat.md`
- **Persona:** A first-time user setting up AEAT authentication (Cl@ve / certificate / browser), naive about the CLI.
- **Date:** 2026-06-18
- **Base dir:** `/tmp/persona-auth-fg`

Anti-hang note: `login` / `login --fresh` / `login --reset-lock` start a live AEAT
authentication flow and would hang headless. They were **not executed**; I inspected
`login --help` instead and judged the documented flags against it.

---

## Walkthrough

### 1. `aeat config auth providers`
- **Expect (doc):** A list of providers; the page presents 5 (`certificate`, `clave_pin`,
  `clave_permanente`, `clave_movil`, `dnie_pkcs`) under "Available providers include".
- **Actual:**
  ```
  certificate       disponible                       Certificado digital
  clave_movil       disponible                       Cl@ve Móvil
  clave_pin         reservado (no disponible aún)    Cl@ve PIN
  clave_permanente  reservado (no disponible aún)    Cl@ve Permanente
  dnie_pkcs         reservado (no disponible aún)    DNI-e PKCS
  ```
- **Verdict:** DOC-ISSUE, MAJOR. Only `certificate` and `clave_movil` are actually usable;
  3 of the 5 documented providers are `reservado (no disponible aún)` (reserved / not yet
  available). The page sets the wrong expectation that all five can be configured.

### 2. `aeat config auth configure --provider certificate --file ./certificate.p12`
- **Expect (doc):** Configures the provider; "Use `--file` for providers that need a file."
- **Actual (no profile yet):**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
  After `aeat config profile create persona --quiet --tax-id 00000000T`, retry succeeded:
  ```
  provider     certificate
  file         .../certificate.p12
  status       configured
  next_action  aeat config auth test --provider certificate
  ```
- **Verdict:** DOC-ISSUE, MAJOR. The first executable mutation on the page fails for a
  brand-new user: configure requires an **active profile** that the page never mentions
  and never links before this step. The refusal is graceful and instructive (in Spanish)
  and names the fix, so the app behaves well — the doc is the gap.

### 3. `aeat config auth status`
- **Expect (doc):** "Check what is configured."
- **Actual (before configure):** Ran cleanly with no profile/provider; `configured False`,
  plus a `active_profile_next_action` hint. After configure: `configured True`, and a
  surprise `health_summary: AEAT_CERTIFICATE_PASSWORD_SECRET not set`.
- **Verdict:** OK (command), DOC-ISSUE MINOR — see Finding 5 (undocumented certificate
  password secret).

### 4. `aeat config auth test`
- **Expect (doc):** Same as status, "inspect a specific provider" with `--provider`.
- **Actual:** Goes further than status — actually validated my (dummy) p12 and reported:
  ```
  probe_summary  El archivo de certificado no es un PKCS#12 válido o falta la contraseña; no se puede analizar.
  probe_result   corrupt
  ```
- **Verdict:** OK. Good, instructive probing. (The "corrupt" result is expected for my
  synthetic file.)

### 5. `aeat config auth login` (+ `--fresh`, `--reset-lock`)
- **Expect (doc):** Acquire/verify a live session; `--fresh` forces re-auth; `--reset-lock`
  clears a stuck lock.
- **Actual:** NOT run (live, would hang headless). `login --help` confirms `--provider`,
  `--fresh`, `--reset-lock` exactly as documented, plus an undocumented global
  `--output-language [es|en|ca|hu]`.
- **Verdict:** OK (flags match). The page does not explicitly warn this is the
  online/interactive step (browser/credential prompt) vs the local setup above — see
  Finding 4.

### 6. `aeat config auth clear --sessions | --locks | --provider certificate | --all`
- **Expect (doc):** Clear sessions/locks/one provider/all.
- **Actual:** All four ran cleanly, e.g. `removed_sessions 0  cleared_workflow_state True
  cleared_locks 0`.
- **Verdict:** OK.

### 7. `aeat config auth apoderado scopes list`
- **Expect (doc):** 9 scope codes (`RENT`, `IVA`, `PAGOSF`, `RETEN`, `GENERALNT`, `CENSO`,
  `INFORM`, `NOTIFIC`, `EXPED`).
- **Actual:** Exactly those 9, with friendly modelo bindings. Matches the page.
- **Verdict:** OK.

### 8. `aeat config auth apoderado configure --represented-nif <nif> --scope IVA --scope PAGOSF`
- **Expect (doc):** Records the represented party + scopes; NIF stored encrypted;
  comma-list rejected; unknown codes refused with accepted set.
- **Actual:**
  ```
  represented_nif  sha256:22b94d56     granted_scopes  IVA,PAGOSF
  ```
  Unknown scope → `Refused. scope code 'BOGUS' is not in catalogue ...  -> Run ... --scope ALL`.
  Comma → `Refused. scope token 'IVA,PAGOSF' contains a comma; pass --scope repeatedly instead`.
- **Verdict:** OK. Every claim on the page (encrypted NIF, comma rejected, unknown refused
  with the accepted set) is true and the refusals are excellent.

### 9. `aeat config auth apoderado status` / `check` / `clear`
- **Actual:** `status` reads offline config fine. `check` → `Refused. La comprobación en
  vivo de apoderamientos no está disponible...` (exactly the documented "live verification
  unavailable, use status" behaviour). `clear` → `cleared True`.
- **Verdict:** OK. The page's description of the sealed live path is accurate.

### Extra checks
- `configure --provider clave_movil` (no `--file`): configured, but surfaced an
  undocumented `identity_alignment: mismatch` warning ("El DNI/NIE de la identidad Cl@ve …
  no coincide con el identificador fiscal del perfil activo …"). See Finding 6.
- `configure --provider clave_pin`: `Refused. Proveedor de autenticación reservado pero no
  disponible: clave_pin.` (graceful; confirms Finding 1).
- `configure` with `AEAT_SECRET_PASSPHRASE` unset: `Failed. AEAT_SECRET_PASSPHRASE is not
  set and stdin is not interactive...` (graceful; confirms Finding 3).

---

## Findings

1. **[MAJOR][DOC]** Three of five documented providers are not usable. `aeat config auth
   providers` marks `clave_pin`, `clave_permanente`, and `dnie_pkcs` as `reservado (no
   disponible aún)`, and `configure --provider clave_pin` refuses with "reservado pero no
   disponible". The page lists all five as "Available providers" with no note that only
   `certificate` and `clave_movil` work today.
   *Fix:* Mark the reserved providers clearly (e.g. "planned / not yet available") and lead
   with the two that work.

2. **[MAJOR][DOC]** The first mutating command on the page (`configure`) requires an active
   profile that the page never establishes. A literal first-time reader hits
   `Refused. No hay un perfil activo...` on step 2.
   *Fix:* Add a one-line prerequisite at the top — "First create a profile (see
   [Set up your taxpayer profile](profile-setup.md))" — before "Configure a provider".

3. **[MAJOR][DOC]** No mention of the master-key passphrase. `configure` (and any encrypted
   write) needs `AEAT_SECRET_PASSPHRASE` or an interactive prompt; in a non-interactive
   shell it fails with "AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive". A
   naive user scripting this is blocked with no warning from the page.
   *Fix:* Note that configuring/clearing prompts for (or requires) the profile passphrase.

4. **[MINOR][DOC]** The online/interactive boundary is implied but not stated. Steps 1–4 and
   `clear`/`apoderado` are local/offline; only `login` (and live apoderado `check`) go
   online and are interactive (browser/credential prompt). The page's intro says auth "is
   local setup" but never flags that `login` itself is the interactive online step.
   *Fix:* Add a sentence under "Acquire or verify a live session" that `login` opens a live
   AEAT flow and is interactive (certificate password / Cl@ve prompt / browser).

5. **[MINOR][DOC]** Undocumented `AEAT_CERTIFICATE_PASSWORD_SECRET`. After configuring a
   certificate, `status`/`test` report `health_severity: warning`,
   `health_summary: AEAT_CERTIFICATE_PASSWORD_SECRET not set`. The page never explains how a
   certificate's password is supplied, so the warning is mysterious.
   *Fix:* Mention how the .p12 password is provided (env var / prompt) for certificate auth.

6. **[MINOR][APP/DOC]** `clave_movil` configure can warn `identity_alignment: mismatch` when
   the Cl@ve DNI/NIE differs from the active profile's tax-id. The behaviour is good and the
   message is clear, but the page presents `clave_movil` as a plain option with no hint that
   Cl@ve identity must match the profile.
   *Fix:* One line noting the Cl@ve identity must match the active profile's tax id.

7. **[NIT][DOC]** Undocumented sibling command `aeat config auth diagnostics` exists in the
   tree but is not mentioned (troubleshooting may belong on the linked troubleshooting page,
   so low priority).

8. **[NIT][APP]** Refusals exit with code 0 (e.g. unknown scope, reserved provider, missing
   passphrase all returned `EXIT=0`). A scripting user can't detect failure by exit status.
   Out of doc scope, but worth flagging.

---

## Testimonial

The page reads cleanly and the apoderado section in particular is a model of accuracy —
every refusal it promised (comma rejected, unknown scope named, sealed live `check`) fired
exactly as written, and the encrypted-NIF claim held up. But as a true first-timer I tripped
immediately: step 2's `configure` bounced me because I had no profile, and the page never
told me to make one or to set a passphrase, so my "local setup" stalled twice before I got
going. I was also misled into thinking I could pick Cl@ve PIN or my DNI-e — three of the five
listed providers are reserved and refuse. The app itself was excellent throughout: every
refusal was graceful, localized, and told me the next command. The friction was the doc
under-stating its prerequisites and over-stating which providers actually work today.

---

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 4.5 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 3 · MINOR 3 · NIT 2
