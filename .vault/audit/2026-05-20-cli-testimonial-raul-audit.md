---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# CLI testimonial - Raul, auth setup

## What I was trying to do

I am a sole trader (autónomo) with a digital certificate and some familiarity with Cl@ve. I heard this tool can connect to AEAT so I can eventually check my filed declarations. My goal was to:

1. Create a profile for myself.
2. See which authentication providers the tool supports.
3. Configure one — ideally the digital certificate, since I already have it.
4. Check the status and run the built-in test.
5. Understand exactly what the tool would need from me to actually connect to AEAT.

I do not have my real credentials available right now, so I stopped before any live network call.

---

## My session

### Step 1 — Get oriented

**Command:** `uv run --no-sync aeat --help`

**Expectation:** Understand what the tool does and where authentication lives.

**Output (relevant excerpt):**
```
aeat - local-first Spanish tax workflow

The CLI has exactly two roots: config and app.
Use config for local state and app for tax work.

Section setup
  aeat config profile create NAME  Setup create profile
  aeat config auth                 Setup configure auth
```

**Feeling:** Clean. Two-root design is clear. "config" for setup and "app" for work makes sense. I immediately saw `aeat config auth` listed. Good start.

---

### Step 2 — Create my profile

**Command:** `uv run --no-sync aeat config profile create raul --tax-id "12345678A" ...`

**Expectation:** Create a profile with my name and a placeholder NIF.

**Output:**
```
Refused. NIF/NIE/CIF no válido para wizard.setup.profile.tax-id.prompt: 12345678A.
NIF check letter mismatch: expected 'Z', got 'A'.
```

**Feeling:** Good validation — it caught a wrong NIF check letter. The error message is clear enough, though it exposes internal key names (`wizard.setup.profile.tax-id.prompt`, `question_id: tax-id`) that look like implementation internals. A real user might not know what `question_id` means.

**Fix:** Used `12345678Z` (correct check letter). Profile created silently (no confirmation output at all).

**Feeling after fix:** Profile created with zero feedback. I had to run `aeat config profile list` separately to confirm it worked. A brief "Profile 'raul' created and activated." would be reassuring.

---

### Step 3 — List auth providers

**Command:** `uv run --no-sync aeat config auth providers`

**Expectation:** See a list of supported authentication methods.

**Output:**
```
certificate     implemented   Certificado digital
clave_movil     implemented   Cl@ve Móvil
clave_pin       reserved      Cl@ve PIN
clave_permanente reserved     Cl@ve Permanente
dnie_pkcs       reserved      DNI-e PKCS
```

**Feeling:** Excellent. Clean three-column table. I can immediately see that `certificate` and `clave_movil` are "implemented" and the others are "reserved" (not yet available). As someone with a digital certificate and Cl@ve experience, I know which ones I can use. No description of *what* each provider means for a less-technical user (e.g. "use this if you have a .p12 file from FNMT"), but the labels are recognisable.

---

### Step 4 — Explore configure help

**Command:** `uv run --no-sync aeat config auth configure --help`

**Output:**
```
--provider  [certificate|clave_movil|...]   Identificador del proveedor [required]
--file      PATH                            Ruta al archivo de credenciales
                                            (certificado o clave)
```

**Feeling:** Minimal. `--file` description says "ruta al archivo de credenciales (certificado o clave)" — which is reasonable, but tells me nothing about:
- What file format is expected (.p12? .pfx? PEM?)
- Whether a password will be prompted
- What happens with Cl@ve Móvil (does `--file` even apply?)

---

### Step 5 — Configure certificate provider (no file)

**Command:** `uv run --no-sync aeat config auth configure --provider certificate`

**Expectation:** It would prompt me for the file path interactively.

**Output:**
```
provider    certificate
file        
active_profile  raul
next_action aeat config auth test --provider certificate
```

**Feeling:** Confusing. It accepted the command with an empty `file` field and told me the "next action" is to run the test. But if the file is empty, how can the test work? There was no prompt for the file path, no warning that the configuration is incomplete. It felt like I had done something successfully when I had not.

---

### Step 6 — Check auth status

**Command:** `uv run --no-sync aeat config auth status`

**Output:**
```
provider        certificate
configured      True
authenticated   False
available       False
...
certificate_path  
health_severity   
health_summary    certificate path not configured
```

**Feeling:** Contradictory. `configured: True` but `health_summary: certificate path not configured`. If the path is not configured, is it really "configured: True"? This is confusing. I would expect `configured: False` when the critical field (the certificate file) is missing.

---

### Step 7 — Configure with a dummy non-existent file path

**Command:** `uv run --no-sync aeat config auth configure --provider certificate --file "/nonexistent/my-certificate.p12"`

**Output (note: path was rewritten by the shell):**
```
provider    certificate
file        C:\Program Files\Git\nonexistent\my-certificate.p12
active_profile  raul
next_action aeat config auth test --provider certificate
```

**Feeling:** The tool accepted a path that does not exist without any warning. The path was also silently mangled from a Unix-style path (`/nonexistent/...`) to a Windows absolute path (`C:\Program Files\Git\nonexistent\...`) by the shell, which is a shell behaviour rather than the tool's fault. However, the tool should validate that the file exists at `configure` time, not silently persist an invalid path.

---

### Step 8 — Run auth test (certificate, non-existent file)

**Command:** `uv run --no-sync aeat config auth test --provider certificate`

**Output:**
```
provider        certificate
configured      False
authenticated   False
available       False
active_profile  
active_profile_status  
active_profile_registered  False
active_profile_record_present  False
active_profile_next_action  
...
health_summary  certificate path not configured
```

**Feeling:** Broken. `status` said `configured: True`, but `test` says `configured: False`. The active profile fields (`active_profile`, `active_profile_status`, `active_profile_registered`) are all empty — as if the test command cannot see the profile. This looks like a bug where `test` does not read the active profile from storage. The inconsistency between `status` and `test` is the most disorienting moment of the session.

---

### Step 9 — Configure certificate with an existing (but fake) file

I created a dummy file at a real path. Then:

**Command:** `uv run --no-sync aeat config auth configure --provider certificate --file "<real path to dummy .p12>"`

**Status output:**
```
certificate_path  Y:\...\mi-certificado.p12
health_summary    certificate path not configured
```

**Feeling:** The health summary still says "certificate path not configured" even though the path is clearly shown in the output above it. The file exists on disk. This is another contradictory state — path is present, file exists, but the summary denies it.

---

### Step 10 — Try Cl@ve Móvil

**Command:** `uv run --no-sync aeat config auth configure --provider clave_movil`

**Output:**
```
provider        clave_movil
file            
active_profile  raul
profile_tax_id  present
clave_identity  present
identity_alignment  mismatch
next_action     aeat config auth test --provider clave_movil
```

**Feeling:** Interesting — there is an `identity_alignment: mismatch` field. I do not know what this means. Does "mismatch" mean my profile NIF does not match what Cl@ve knows? Is this a warning or a fatal error? No explanation is offered. `status` after this shows `health_summary: Preparado; requiere finalización de Cl@ve mediada por el operador.` — which is a Spanish message in an otherwise English session (my profile is set to `output-language: en`). Also, `backend_available: True` for Cl@ve but `False` for certificate — this distinction is never explained anywhere.

---

### Step 11 — Auth test for Cl@ve Móvil

**Command:** `uv run --no-sync aeat config auth test --provider clave_movil`

**Output:**
```
provider        clave_movil
configured      True
available       True
active_profile  
active_profile_registered  False
...
```

**Feeling:** Same bug as certificate: `test` shows empty `active_profile` even though the profile "raul" is clearly active (confirmed by `status`). The test reports `configured: True` and `available: True` (progress over certificate), but cannot see the profile.

---

### Step 12 — Clear and verify

**Command:** `uv run --no-sync aeat config auth clear --provider certificate`

**Output:**
```
removed_sessions    0
cleared_workflow_state  True
cleared_locks       0
```

**Command:** `uv run --no-sync aeat config auth status`

**Output:**
```
provider     
configured   False
...
```

**Feeling:** Clear worked correctly and cleanly. Status reflects the reset state.

---

## Did it work?

Partially. I was able to:
- Create a profile.
- Discover the two implemented providers (`certificate` and `clave_movil`).
- Configure each provider (with caveats about empty/invalid file acceptance).
- Read a status that is mostly meaningful.
- Clear configuration cleanly.

I was **not** able to:
- Get the auth `test` command to acknowledge my active profile — it always shows empty profile fields.
- Understand what `identity_alignment: mismatch` means for Cl@ve Móvil.
- Get a consistent picture from `status` vs `test` (they disagree on `configured`).
- Understand what file format the certificate provider expects, or whether a password will be prompted.

The tool would need from me, to actually connect:
- **Certificate provider:** A real `.p12` or `.pfx` FNMT certificate file (the password would presumably be prompted at login time). The exact supported format is not stated.
- **Cl@ve Móvil:** It seems to detect Cl@ve identity automatically from profile data. The "mediada por el operador" message suggests a browser-based or app-based OAuth flow would be triggered at `aeat config auth login`.

I did not run `aeat config auth login` because that would initiate a live network connection to AEAT.

---

## Bugs and gaps

1. **`auth test` does not load the active profile**
   - Command: `aeat config auth test`
   - Expected: `active_profile: raul`, `active_profile_registered: True`, matching what `aeat config auth status` shows.
   - Actual: All active-profile fields are empty (`active_profile: `, `active_profile_registered: False`).
   - Severity: **Blocker** — `test` is the operator's primary readiness check. Returning empty profile data makes it useless; a user cannot tell if auth is ready for their profile.

2. **`status` reports `configured: True` when the certificate path is empty**
   - Command: `aeat config auth configure --provider certificate` (no `--file`), then `aeat config auth status`
   - Expected: `configured: False` or a warning that the required file is not set.
   - Actual: `configured: True`, `health_summary: certificate path not configured`.
   - Severity: **Major** — contradictory output actively misleads the user into thinking setup is complete.

3. **`health_summary` says "certificate path not configured" even when path is present**
   - Command: `aeat config auth configure --provider certificate --file <existing file>`, then `aeat config auth status`
   - Expected: The summary reflects that the path is set (even if the file is not a valid certificate).
   - Actual: `certificate_path` shows the path; `health_summary` says "certificate path not configured".
   - Severity: **Major** — contradictory. Either the field name in the summary is wrong, or the "configured" check uses a different condition that is not surfaced to the user.

4. **`configure --file` accepts non-existent paths without warning**
   - Command: `aeat config auth configure --provider certificate --file /nonexistent/cert.p12`
   - Expected: Warning or error that the file does not exist, or at minimum a note that the path will be validated at login time.
   - Actual: Silently persists the invalid path with no feedback.
   - Severity: **Minor** — a user who mistypes their certificate path will only discover the error much later.

5. **`identity_alignment: mismatch` in Cl@ve Móvil output is unexplained**
   - Command: `aeat config auth configure --provider clave_movil`
   - Expected: If there is an identity mismatch, the output should explain what mismatches and what the user should do.
   - Actual: `identity_alignment: mismatch` with no further context, no remediation hint.
   - Severity: **Major** — a real user with a properly registered Cl@ve account seeing "mismatch" would be alarmed and would not know if configuration succeeded or failed.

6. **`profile create` produces no confirmation output on success**
   - Command: `aeat config profile create raul ...`
   - Expected: At least one line confirming the profile name and that it is now active.
   - Actual: Exits silently (exit code 0, zero output).
   - Severity: **Minor** — unsettling but not blocking; `aeat config profile list` confirms state.

7. **Language mixing: Spanish `health_summary` in English-language profile**
   - Command: `aeat config auth status` (profile set to `output-language: en`, provider `clave_movil`)
   - Expected: All output in English per the profile's `output-language` setting.
   - Actual: `health_summary: Preparado; requiere finalización de Cl@ve mediada por el operador.` (Spanish).
   - Severity: **Minor** — inconsistent locale handling; other fields in the same output are in English.

8. **`configure --file` help does not state expected file format**
   - Help text: "Ruta al archivo de credenciales (certificado o clave)"
   - Expected: States whether .p12, .pfx, PEM, or other formats are accepted; whether a password will be prompted.
   - Actual: Generic description only.
   - Severity: **Minor** — friction for first-time users who may not know whether their FNMT certificate export format is compatible.
