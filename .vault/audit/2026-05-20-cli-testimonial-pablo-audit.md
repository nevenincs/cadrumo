---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
---

# CLI testimonial - Pablo, profile lifecycle and repair

## What I was trying to do

I manage taxes for myself and my spouse Maria. I wanted to create two separate profiles — one for me, one for her — switch between them, make a backup copy of mine, rename it, and understand how to recover if something goes wrong. I had seen the tool mentions `repair`, `diagnostics`, and `quarantine` commands and wanted to understand them before trusting the tool with real tax data.

## My session

### Step 1 — Discover the CLI surface

**Command:** `aeat --help`

**Expectation:** See what commands are available.

**Output (excerpt):**
```
aeat - local-first Spanish tax workflow
The CLI has exactly two roots: config and app.
Section profile lifecycle
  aeat config profile switch NAME
  aeat config profile delete NAME
  aeat config profile duplicate SRC DST
  aeat config profile rename SRC DST
Section diagnostics
  aeat config repair
  aeat config repair logs
  aeat config repair quarantine
  aeat config repair reset-state
```

**Feeling:** Clear, well-structured. Two-root design is easy to understand.

---

### Step 2 — Create my profile (pablo)

**Command:** `aeat config profile create pablo --quiet --tax-id 12345678A ...`

**Output (first attempt):**
```
Exit code 2
Refused. NIF/NIE/CIF no válido: 12345678A. NIF check letter mismatch: expected 'Z', got 'A'.
```

**Feeling:** Good that it validates. But as a non-expert I do not know the NIF check-letter algorithm. No hint of what a valid NIF looks like. Also discovered `--tax-residence-community` does not exist — the help table truncates `--tax-residence-ccaa` to `--tax-residence-…`, hiding the real flag name.

**Second attempt** with `12345678Z` and `--tax-residence-ccaa madrid`: succeeded **silently** (no output, exit 0).

**Feeling:** Silent success with no confirmation. I cannot tell if the profile was created or if the command hung.

---

### Step 3 — Verify profile was created

**Command:** `aeat config profile list`

**Output:**
```
active_profile	pablo
*	pablo
```

**Feeling:** Fine. The `*` marker is clear.

---

### Step 4 — Show profile details

**Command:** `aeat config profile show`

**Output:** Full flat table with 30+ fields. Tax ID, name, IVA regime, CCAA, dates present.

**Feeling:** Good. However, the spouse fields I supplied (`--spouse-tax-id`, `--spouse-name`, etc.) do not appear. I cannot verify spouse data was saved.

---

### Step 5 — Profile status

**Command:** `aeat config profile status`

**Output:**
```
profile	pablo
identity.tax_id	12345678Z
activities.description	Desarrollo de software
iva.regime	GENERAL
tax_residence.ccaa	madrid
Próximo paso: `aeat app overview status`
```

**Feeling:** Compact and useful. The next-step hint is good.

---

### Step 6 — Create spouse profile (maria)

**Command:** `aeat config profile create maria --quiet --tax-id 87654321B ...`

**Output:** NIF rejected. Had to try `87654321X`. Succeeded silently.

**Observation:** Creating the second profile silently switched the active profile to maria.

**Command:** `aeat config profile list`

**Output:**
```
active_profile	maria
*	maria
 	pablo
```

**Feeling:** Creating a second profile while working on pablo silently changed the active context without any warning. This is unexpected.

---

### Step 7 — Switch back to pablo, verify app context

**Command:** `aeat config profile switch pablo` — output: `active_profile  pablo`

**Command:** `aeat app overview status`

**Output:** `Estas trabajando en el perfil pablo.`

**Feeling:** Switch works correctly and app confirms the right profile.

---

### Step 8 — Duplicate profile

**Command:** `aeat config profile duplicate pablo pablo-backup --display-name "Pablo backup"`

**Output:**
```
source_profile_id	pablo
target_profile_id	pablo-backup
display_name	Pablo backup
```

**Command:** `aeat config profile show pablo-backup` — shows identical data to pablo with new `profile_id`.

**Feeling:** Works well.

---

### Step 9 — Rename the backup

**Command:** `aeat config profile rename pablo-backup pablo-2024-snapshot --display-name "Pablo snapshot 2024"`

**Output (first attempt):**
```
Exit code 2
Refused. Failed to rename bucket directory: [WinError 32] The process cannot access the file
because it is being used by another process: ...pablo-backup\db\aeat.db
```

**Second attempt (immediately after):**
```
Exit code 2
Refused. El perfil pablo-2024-snapshot ya existe. Elige otro identificador de destino.
```

**Observation:** The first attempt partially succeeded — the target bucket was created and registered — but failed to remove the source. Now both `pablo-backup` and `pablo-2024-snapshot` appear in `profile list` but `profile show` on either returns:

```
readiness	missing_profile_record
profile_id	pablo-backup
registered_bucket	present
profile_record	missing
next_action	aeat config repair profile --profile pablo-backup
```

---

### Step 10 — Attempt to repair broken profiles

**Command:** `aeat config repair profile --profile pablo-backup --yes`

**Output (repeated identically regardless of flags):**
```
readiness	missing_profile_record
next_action	aeat config repair profile --profile pablo-backup
```

**Feeling:** The repair command loops. It diagnoses correctly but does nothing and keeps suggesting itself.

**Command:** `aeat config profile delete pablo-backup --yes`

**Output:**
```
Refused. Perfil desconocido: pablo-backup.
```

**Feeling:** The profile appears in `profile list` but delete refuses it as unknown. Incoherent.

---

### Step 11 — Delete a healthy profile (maria)

**Command:** `aeat config profile delete maria --yes`

**Output:** `profile_id  maria  status  tombstoned`

**Command:** `aeat config profile list` — maria still appears.

**Command:** `aeat config profile show maria` — shows full data with `status  tombstoned`.

**Command:** `aeat config profile switch maria` — succeeds.

**Command:** `aeat app overview status` — runs normally against the tombstoned profile.

**Feeling:** "Delete" does not remove the profile — it tombstones it. The profile stays in the list, is switchable, and is fully operational. This behaviour is not explained in `--help`. The word "delete" is misleading.

---

### Step 12 — Rename active profile causes cascade failure

**Command:** `aeat config profile rename pablo pablo-renamed`

**Output:** Same WinError 32 failure. A new ghost `pablo-renamed` appears in the list.

**Command:** `aeat config profile show pablo`

**Output:**
```
readiness	missing_profile_record
next_action	aeat config repair profile --clear-active --yes
```

The active pablo profile is now broken.

---

### Step 13 — Follow repair suggestion

**Command:** `aeat config repair profile --clear-active --yes`

**Output:**
```
cleared_pointer	True
active_profile	(empty)
next_action	aeat config profile create NAME --tax-id <TAX_ID> ...
```

**Command:** `aeat config profile switch pablo`

**Output:**
```
readiness	missing_profile_record
next_action	aeat config repair profile --profile pablo
```

Pablo is still broken. The repair loop continues. Recovery requires manual filesystem intervention not described anywhere in the CLI.

---

### Step 14 — Repair diagnostic commands

**Command:** `aeat config repair reset-state --dry-run`

**Output:** Full SQLAlchemy traceback, `NoActiveBucketSessionError`, exit code 6.

**Feeling:** The `--dry-run` flag is supposed to be safe but crashes with an uncaught internal error. This destroys trust in the repair surface.

**Command:** `aeat config repair reset-state` (no flags)

**Output:** `Refused. Esta operación es destructiva. Vuelve a ejecutar con --yes para confirmar o pasa --dry-run para inspeccionar la huella.`

**Feeling:** The gate is correct but `--dry-run` is broken so there is no safe inspection path.

**Command:** `aeat config repair integrity`

**Output:**
```
readable	3
unreadable	0
status	ok
summary	3 row(s) decryptable across 3 namespace(s)
```

**Feeling:** Best diagnostic command — clear, safe, actionable.

**Command:** `aeat config repair connectivity`

**Output:** `State label  ok`

**Feeling:** Good. Simple and clear.

**Command:** `aeat config repair logs`

**Output:** Shows log path and recent lines including raw SQLAlchemy debug output and pytest temp paths.

**Feeling:** Useful for a developer; not helpful to a non-expert.

---

## Did it work?

Partially. The happy path works: creating profiles, switching between them, duplicating, and using `app` commands against the right profile all work correctly. The `repair integrity` and `repair connectivity` commands are clear and safe.

The lifecycle breaks on `rename` on Windows. A single failed rename leaves multiple ghost profiles that cannot be deleted, repaired, or cleaned up through any available CLI command. A second rename attempt on the active profile left the main working profile in a broken unrecoverable state. After all attempts, I had 4 ghost profiles, my main pablo profile broken, and no CLI path to restore it.

I would not trust this tool with real tax data until `rename` is atomic or the ghost-profile cleanup path exists.

---

## Bugs and gaps

1. **Command:** `aeat config profile rename` on Windows  
   **Expected:** Atomic rename — either succeeds fully or rolls back the registry to original state on failure  
   **Actual:** On WinError 32 (SQLite file lock), the target bucket is already registered before the rename fails; the source registration is already removed. Both appear in `profile list` as `missing_profile_record` ghosts. No rollback occurs.  
   **Severity:** BLOCKER — rename is non-atomic on Windows and leaves the registry in an unrecoverable state without manual filesystem intervention.

2. **Command:** `aeat config profile delete <ghost-name>` after broken rename  
   **Expected:** Deletes the ghost entry or explains why it cannot  
   **Actual:** `Refused. Perfil desconocido: <name>` even though `profile list` shows the profile  
   **Severity:** BLOCKER — ghost profiles created by failed renames cannot be cleaned up through any CLI command.

3. **Command:** `aeat config repair profile --profile <broken> --yes`  
   **Expected:** Repairs or removes the broken profile record  
   **Actual:** Loops identically regardless of flags; no repair performed; the `next_action` suggestion points back to itself  
   **Severity:** BLOCKER — the repair command cannot repair the `missing_profile_record` state.

4. **Command:** `aeat config repair reset-state --dry-run`  
   **Expected:** Shows what would be deleted, exits cleanly  
   **Actual:** Crashes with full SQLAlchemy traceback, `NoActiveBucketSessionError`, exit code 6  
   **Severity:** MAJOR — a `--dry-run` option must not throw an uncaught exception; this destroys trust in the entire repair surface.

5. **Command:** `aeat config profile create NAME` (success case)  
   **Expected:** Confirmation line showing profile ID and active status  
   **Actual:** No output, exit 0  
   **Severity:** MAJOR — silent success is ambiguous; users cannot distinguish success from a hung process.

6. **Command:** `aeat config profile create NAME` (second profile creation)  
   **Expected:** Active profile stays on the current profile; or at minimum a warning is shown  
   **Actual:** Active profile silently switches to the newly created profile without any message  
   **Severity:** MAJOR — creating a second profile changes the operating context silently; any subsequent `app` commands run against the wrong profile.

7. **Command:** `aeat config profile show` (spouse field visibility)  
   **Expected:** Spouse tax ID, name, surnames, birth date visible in output  
   **Actual:** No spouse fields appear in `profile show` output  
   **Severity:** MAJOR — user cannot verify spouse data was saved; it is unclear whether the data round-trips correctly.

8. **Command:** `aeat config profile delete NAME --yes`  
   **Expected:** Profile removed from list and inaccessible  
   **Actual:** Profile tombstoned; remains in list, remains switchable, and `app` runs against it  
   **Severity:** MINOR — tombstone semantics are unexplained in `--help`; the word "delete" is misleading.

9. **Command:** `aeat config profile create ... --tax-residence-community`  
   **Expected:** Either works or shows the correct flag name  
   **Actual:** `No such option: --tax-residence-community Did you mean --tax-residence-ccaa?`; the `--help` table truncates the real flag name to `--tax-residence-…`  
   **Severity:** MINOR — truncated help text forces users to guess flag names.

10. **Command:** `aeat config repair quarantine --yes` (after `profile switch` in a broken state)  
    **Expected:** Scans the active bucket or explains clearly it requires a live session  
    **Actual:** `Refused. no active bucket session` even after `switch` reports `active_profile pablo` — the switch succeeded at the pointer level but did not establish a session, and the error message is identical to the pre-switch error giving no guidance  
    **Severity:** MINOR — switch and session establishment appear decoupled; error message provides no actionable next step beyond the switch already performed.
