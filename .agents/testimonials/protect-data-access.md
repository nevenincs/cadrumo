# Testimonial — Protect access to your data

- **Doc path:** `docs/how-to/protect-data-access.md`
- **Persona:** A privacy-conscious first-time user securing local data — passphrase, recovery key, capability/session locking, encryption posture.
- **Date:** 2026-06-18

---

## Walkthrough

### 0. (Implicit prerequisite) — no profile yet

- **Command:** `aeat config show-recovery` (the page's very first command, run on a fresh install)
- **Expected:** The doc opens "Do this once, right after setup" and immediately gives `aeat config show-recovery`. As a naive user I ran it first.
- **Actual:**
  ```
  Refused. No se pudo determinar ningún bucket activo. Selecciona un perfil y vuelve a intentarlo.
    -> Run `aeat config profile list`
  ```
- **Verdict:** DOC-ISSUE, MAJOR. The page never says a profile must exist (and be active) before any of these commands work. The whole guide is dead-on-arrival for someone who literally "just set up."

### 0b. Scaffolding to continue (not on the page)

- **Command:** `aeat config profile create persona-test --quiet --accept-defaults --tax-id 12345678Z`
- **Note:** Needed to create a profile to test the rest. `--quiet` first refused with `--tax-id` missing; adding it worked. (Profile creation is a different page; recorded only as the unstated prerequisite.)

### 1. Create the recovery key

- **Command:** `aeat config show-recovery`
- **Expected:** If no recovery key exists, create one and print recovery words once.
- **Actual:**
  ```
  recovery_enrolled	yes
  rotated	no
  recovery_path	...\secrets\master.recovery.key
  recovery_key	giggle glass song again lawsuit limb bullet two minimum escape okay verify bachelor rally forward reflect talent ghost garlic hen grit muscle offer live
  Anota ahora esta clave de recuperacion. AEAT no almacena la clave de recuperacion en claro y no puede mostrarla otra vez.
  ```
- **Verdict:** OK. 24 words printed once, as promised. (Doc says "a list of recovery words"; it's exactly 24 — the count is only stated later under `recover`.)

### 2. Re-run to confirm enrollment

- **Command:** `aeat config show-recovery` (second time)
- **Expected:** Reports status, does not print words again.
- **Actual:** `recovery_enrolled yes`, `rotated no`, plus `La clave de recuperacion en claro no se almacena y no puede volver a mostrarse. Usa --rotate ...`
- **Verdict:** OK. Matches the doc exactly.

### 3. Verify the recovery key (correct words)

- **Command:** `aeat config verify-recovery --recovery-key "giggle glass ... offer live"`
- **Expected:** `verified yes`, nothing modified.
- **Actual:** `verified	yes` (exit 0).
- **Verdict:** OK.

### 4. Verify the recovery key (wrong words) — negative path

- **Command:** `aeat config verify-recovery --recovery-key "wrong words that do not open the wrapper at all nope nope"`
- **Expected:** `verified no` and a failure exit code.
- **Actual:** `verified	no`; true exit code **2** (good key returns 0).
- **Verdict:** OK. The "exits with a failure code" promise holds.

### 5. Rotate the recovery key

- **Command:** `aeat config show-recovery --rotate`
- **Expected:** New words printed once; previous words stop working immediately.
- **Actual:** `rotated yes` and a fresh 24-word key. Re-verifying: OLD words → `verified no`, NEW words → `verified yes`.
- **Verdict:** OK. Exactly as documented.

### 6. Change the passphrase (rekey, non-interactive)

- **Command:** `aeat config rekey --new-passphrase "new-pass-456" --confirm-new-passphrase "new-pass-456"`
- **Expected:** Replaces the passphrase; master key unchanged; all data stays readable. Doc points to `--new-passphrase`/`--confirm-new-passphrase` for non-interactive use.
- **Actual:** `rekeyed yes`. Setting the env passphrase to `new-pass-456`, `aeat config profile list` still listed `persona-test` → data readable. Rekeyed back to the original harness passphrase; `rekeyed yes`; original passphrase opens the store again.
- **Verdict:** OK. The documented non-interactive flags exist and work; data integrity confirmed across the rekey.

### 7. Recover after a forgotten passphrase

- **Command:** `aeat config recover --recovery-key "<current 24 words>" --new-passphrase "recovered-pass-789" --confirm-new-passphrase "recovered-pass-789"`
- **Expected:** Unlock the master key from the recovery wrapper, rewrap under a new passphrase, all data intact, nothing deleted.
- **Actual:** `recovered yes`. Under the new passphrase, `profile list` still showed `persona-test` → data intact. Rekeyed back to the harness passphrase afterward.
- **Verdict:** OK on behavior, but **DOC-ISSUE (MINOR):** the page's `recover` snippet says it "prompts twice (hidden) for a new passphrase" and never mentions the `--new-passphrase`/`--confirm-new-passphrase` flags — yet they exist and are the only non-interactive route. A non-interactive user following the page verbatim would hit a hidden prompt and block. (It mentions these flags for `rekey` but not for `recover`.)

### 8. Lock the session

- **Command:** `aeat config lock`
- **Expected:** Clears the active-profile pointer; nothing deleted; re-select with `aeat config switch <name>`.
- **Actual:**
  ```
  locked_profile	<profile-id>
  El cierre de sesion limpio el puntero del perfil activo. Los verbos posteriores ... seran rechazados con NoActiveBucketSessionError hasta que ejecutes aeat config switch NAME ...
  ```
  `profile list` afterward → `active_profile <none>`, profile still present.
- **Verdict:** OK on behavior. **APP-ISSUE (MINOR):** the output prints a literal placeholder `locked_profile	<profile-id>` instead of the actual profile name/id.

### 9. Re-select after lock

- **Command:** `aeat config switch persona-test`
- **Expected:** Active profile restored (the doc names this command in the lock section).
- **Actual:** `active_profile persona-test`; subsequent `profile list` shows `* persona-test`.
- **Verdict:** OK.

### 10. Reset guards

- **Command:** `aeat config reset --scope auth` (no `--yes`)
- **Actual:** `Refused. El reinicio es destructivo. Vuelve a ejecutar con --yes para confirmar.` (exit 2)
- **Command:** `aeat config reset --yes` (no `--scope`)
- **Actual:** `Refused. config reset requires an explicit --scope; accepted scopes: profile, auth, data, all. ...`
- **Verdict:** OK. Both guards exactly match the doc's "refuses without `--yes`" and "no default scope" claims.

### 11. Reset — auth scope (safe, executed)

- **Command:** `aeat config reset --scope auth --yes`
- **Expected:** Clears AEAT session/provider settings; stored profiles and records untouched.
- **Actual:** `scope AUTH`, `removed_profiles 0`, `removed_auth True`; `profile list` still shows `* persona-test`.
- **Verdict:** OK. (Did not execute `--scope profile/data/all` — destructive, and the page's purpose is preserving data.)

### 12. Cross-reference links

- `profile-setup.md`, `troubleshooting.md`, `../cli/index.rst` all EXIST.
- `aeat config profile export` is a real verb.
- **Verdict:** OK. All "Next steps" links and the referenced export command resolve.

---

## Findings

1. **[MAJOR] [DOC]** — The page's first command (`aeat config show-recovery`) refuses on a fresh install with `No se pudo determinar ningún bucket activo. Selecciona un perfil`. The guide never states that an **active profile is a prerequisite** for every command on the page. *Repro:* on a clean store, run `aeat config show-recovery` → refusal. *Fix:* add a one-line prerequisite at the top ("These commands require an active profile — see Set up your taxpayer profile") and link `profile-setup.md` from the intro, not just the footer.

2. **[MAJOR] [DOC]** — No mention that a **master-key passphrase is required** and how it is supplied. Every command here opens the encrypted store, which needs the passphrase; in a non-interactive shell without `AEAT_SECRET_PASSPHRASE` set, a naive user is blocked with no guidance. The page is literally about the passphrase yet never says where it comes from at command time (interactive prompt vs. `AEAT_SECRET_PASSPHRASE` env var). *Fix:* state that commands prompt for the current passphrase (or read `AEAT_SECRET_PASSPHRASE` non-interactively) before doing anything.

3. **[MINOR] [DOC]** — `config recover` documents only an interactive hidden prompt for the new passphrase and omits the `--new-passphrase`/`--confirm-new-passphrase` flags, which DO exist and are the only non-interactive route. *Repro:* `aeat config recover --help` lists both flags. *Fix:* mirror the `rekey` wording ("For non-interactive use, pass `--new-passphrase` together with `--confirm-new-passphrase`").

4. **[MINOR] [APP]** — `aeat config lock` prints a literal placeholder: `locked_profile	<profile-id>` instead of the real profile name/id. *Repro:* `aeat config lock` on an active profile. *Fix:* substitute the actual profile identifier in the output.

5. **[NIT] [DOC]** — The recovery-word count ("24") is only stated in the `recover` section ("veinticuatro palabras" in help). The create/verify/rotate sections say "a list of recovery words" / "word1 word2 word3 ...". *Fix:* state "24 words" where the key is first created so the user knows how many to write down.

6. **[NIT] [BOTH]** — CLI output is Spanish, docs are English. A privacy-conscious English reader sees `Refused. ...` lines and field labels (`recovery_enrolled`, `rotated`) mixed with Spanish prose. Behavior is correct but the language mismatch adds friction. (Most field keys are English; the sentences are Spanish.)

---

## Testimonial

As a privacy-first user this page actually delivered: the recovery-key lifecycle (create → verify → rotate → recover) and the rekey-without-re-encrypting promise all behaved *exactly* as written, and the reset guards (`--yes`, explicit `--scope`) gave me real confidence I wouldn't nuke my data by accident. Notably this is the one page that takes the master-key passphrase seriously as a concept — but it still never tells me a passphrase is required *at command time* or that I need an active profile first, so my very first documented command refused. I tripped immediately on that missing prerequisite, and again (briefly) on the `recover` section hiding its non-interactive flags. Once past those, every encryption-posture claim held up under test — data stayed readable through a passphrase change and a full recovery, and locking only cleared the pointer without deleting anything.

## Scorecard

- **Doc clarity:** 3/5 (strong, accurate prose; loses points for the unstated profile + passphrase prerequisites and the recover non-interactive omission)
- **App capability:** 5/5 (every documented behavior verified correct, including failure exit codes and guards)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2
