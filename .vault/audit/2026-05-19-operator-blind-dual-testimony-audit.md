---
tags:
  - "#audit"
  - "#operator-testimonial"
date: '2026-05-19'
modified: '2026-05-19'
related: []
---

# Operator persona

Freelance plumber (personal autónomo) and co-owner of a small property-rental SL. Two legal identities:

- **personal** — NIF `12345678Z`, activity: Fontanería, IVA régimen general
- **sl-alquileres** — CIF `B12345674`, activity: Alquiler de inmuebles, IVA régimen general

I switch between them several times a day. I need to be sure I never mix up invoices, ledgers, or modelos between the two. I am not a developer; I just want to type commands.

---

# What I tried to do

1. Set up a clean local environment with `AEAT_LOCAL_STORAGE_ROOT`, `AEAT_DATABASE_URL`, `AEAT_SECRET_STORE_BACKEND=unsecured`, `AEAT_ALLOW_UNENCRYPTED=1`.
2. Create profile `personal` (NIF `12345678Z`, Fontanería, IVA GENERAL).
3. Create profile `sl-alquileres` (CIF `B12345674`, Alquiler, IVA GENERAL).
4. List profiles. Check whether the active one is marked.
5. Switch to `personal`, run `aeat config profile show`.
6. Switch to `sl-alquileres`, run `aeat config profile show`.
7. Run `aeat app overview` for each profile.
8. Delete `sl-alquileres` while `personal` is active; verify `personal` survives.
9. Rename `personal` to `fontaneria-jg`.
10. Run `aeat config profile show personal` while `sl-alquileres` is active.
11. Try `aeat config profile export` / `import`.

---

# What worked

- `aeat config profile create NAME --quiet --tax-id ... --iva-regime ...` — exits 0 silently once a session is active.
- `aeat config profile switch NAME` — exits 0, emits `active_profile\t<name>`. Pointer is updated.
- `aeat config profile status` — exits 0, shows the last-created profile's key fields (tax_id, activity, iva.regime, tax_residence.ccaa) and a `Next step` hint. This is the clearest output in the entire surface.
- `aeat config profile list` — exits 0, shows profile key-value dump for one profile (see "What hurt").
- Creating a second profile after a first one was already created exits 0 without complaint.

---

# What hurt

### Pain 1 — Bootstrapping deadlock (severity: 5/5)

**Every single command fails on a fresh storage root** with `NoActiveBucketSessionError`:

```
Internal. The command failed due to an unexpected internal error.
  -> Run `aeat config repair`
  recovery: aeat config repair
```

The error message instructs: "run `aeat config profile switch NAME` to unlock a profile." But `switch NAME` itself raises the identical error. `repair`, `repair reset-state`, `status`, `list`, `create` — all fail the same way.

The only working path is a Python-level `get_master_key_provider()` context manager that is test-infrastructure, not user-facing. There is no operator bootstrap command. The CLI advertises `aeat config profile create NAME` as "Initialize a new active profile and config bucket" but it immediately attempts to decrypt an existing (non-existent) state object and crashes.

**Consequence**: The CLI is completely unusable from a cold start without developer knowledge.

### Pain 2 — `switch` succeeds but `show` refuses (severity: 4/5)

After `switch personal` exits 0 and emits `active_profile\tpersonal`, running `show` (or `show personal`) immediately returns:

```
Refused. Unknown profile: personal. Run 'aeat config profile list' to see registered profiles.
```

Exit code 2. The active pointer was updated but the profile data is not retrievable. `status` works and shows the correct fields. `show` is broken for any profile created via `create`.

**Consequence**: I switch profiles and then cannot verify what I switched to. The only verification path is `status`, which works but the help text says to use `show`.

### Pain 3 — `list` shows one profile only, no active marker (severity: 3/5)

`aeat config profile list` dumps the full key-value table for exactly one profile — the last one created. It does not enumerate all profiles. There is no `*` or `(active)` marker. After creating `personal` and `sl-alquileres` and switching to `personal`, `list` still only shows `sl-alquileres` (last created) with no indication that `personal` exists or is active.

**Consequence**: I cannot see at a glance how many profiles I have or which is live. I have no way to audit cross-contamination risk.

### Pain 4 — `delete` hangs indefinitely (severity: 4/5)

`aeat config profile delete sl-alquileres --yes` does not return. No output, no error, no timeout. The process must be killed manually.

**Consequence**: Cannot exercise the delete path at all. Cannot test that the other profile survives deletion.

### Pain 5 — No active-profile context cue anywhere (severity: 3/5)

After switching, no command output shows "you are operating as: `personal` (NIF: 12345678Z)". The `status` command shows the last-created profile's data without a label telling me which profile that is. If I forget which profile I last switched to, there is no quick command to answer "what am I operating as right now?" — `status` shows fields but not the profile name in its header line. `switch` emits `active_profile\t<name>` but that is a one-shot confirmation, not a persistent display.

---

# Cross-contamination check

**Could data from one profile leak into the other?**

The architecture encrypts profile state per bucket session. In the test harness (with `get_master_key_provider()` active), both profiles write to the same `secure_objects` SQLite table and are namespaced by `object_key`. The `list` command — when it works — appears to show only the last-created profile's data, not a merged view. However:

- There is no `--profile-name` flag on any command to explicitly scope a single operation to a named profile. The only scoping is via `switch` + the global active-pointer.
- After `switch`, commands like `overview`, `ledger list`, etc. should read from the active bucket. Whether the bucket partitioning is correct is untestable because `show` is broken.
- The most dangerous scenario — running `aeat app ledger import` right after a failed `switch` that left the pointer in an ambiguous state — cannot be verified because `switch` currently appears to update the pointer without unlocking the actual bucket session for subsequent commands.

**Verdict**: Cannot confirm isolation is working. The combination of `show` refusing after `switch` and `list` not enumerating all profiles means there is no operator-visible evidence of correct profile scoping.

---

# Verbatim commands and outputs

```
# Attempt 1: fresh environment (all commands fail the same way)
$ AEAT_LOCAL_STORAGE_ROOT=Y:/tmp/op-dual AEAT_DATABASE_URL=sqlite:///Y:/tmp/op-dual/aeat.db \
  AEAT_SECRET_STORE_BACKEND=unsecured AEAT_ALLOW_UNENCRYPTED=1 \
  uv run --no-sync aeat config profile create personal --quiet --tax-id 12345678Z \
    --name "Juan García" --activity "Fontanería" --iva-regime GENERAL

Exit code 5:
  Failed. aeat_database_url is empty; set AEAT_DATABASE_URL.

# After adding AEAT_DATABASE_URL:
Exit code 6:
  NoActiveBucketSessionError: no active bucket session; run `aeat config profile switch NAME`
  ...
  recovery: aeat config repair

# Same error from every command including:
#   aeat config profile switch personal       → exit 6, same error
#   aeat config profile list                  → exit 6, same error
#   aeat config profile status                → exit 6, same error
#   aeat config repair                        → prints registry warnings, ends with "warn runtime.dependency_sync Venv stale"
#   aeat config repair reset-state --yes      → exit 6, same error

# With get_master_key_provider() bootstrap (Python harness only):
$ profile list
profile	sl-alquileres       ← only last-created, no active marker
identity.tax_id	required	B12345674
...

$ profile switch personal
→ exit 0: active_profile	personal

$ profile show               ← after switch personal
→ exit 2: Refused. Unknown profile: personal.

$ profile show sl-alquileres ← explicit name
→ exit 2: Refused. Unknown profile: sl-alquileres.

$ profile status
→ exit 0:
profile	sl-alquileres       ← shows last-created, not active
identity.tax_id	B12345674
activities.description	Alquiler de inmuebles
iva.regime	GENERAL
tax_residence.ccaa	madrid
Next step: `aeat app overview status`

$ profile delete sl-alquileres --yes
→ hangs indefinitely

$ profile rename personal fontaneria-jg
→ not tested (blocked by delete hang in session)

$ profile export
→ not tested
```

---

# Brutal feedback to the developer

**The CLI is dead on arrival for any operator who has not read the source code.**

`create` is described as "Initialize a new active profile and config bucket." It does not do this. It crashes immediately because it tries to read from the encrypted state object before writing anything. There is no self-bootstrapping path. The operator is told to run `switch` to fix the error; `switch` gives the same error. This is not a minor UX issue — it is a complete blocking failure on the advertised primary use case.

`show` is broken: it refuses profiles that `switch` just confirmed as active. If the documentation says to use `show` to verify a switch, and `show` always fails, operators cannot build any mental model of the system working correctly.

`list` shows one profile, not all profiles. In a multi-profile setup, `list` is the only discovery surface. If it silently drops profiles, an operator cannot know they have two identities configured, which creates direct tax risk.

`delete` hangs without output. A destructive operation that never terminates and produces no output is a data-safety hazard.

The active-profile context is invisible. After `switch`, there is no way to run a single read-only command and see "active profile: personal (12345678Z)". Every tax task starts with uncertainty about which entity I am operating as. For a dual-identity operator, this is the same as having no profile system at all.

**Priority fix order**:
1. Bootstrapping: `create NAME` must not require a session when no profiles exist yet. The `UnsecuredMasterKeyProvider` must auto-activate when `AEAT_SECRET_STORE_BACKEND=unsecured` and `AEAT_ALLOW_UNENCRYPTED=1` are set.
2. `show` must work after `switch`. If `show` reads from a different registry than `switch` writes to, that is a split-brain bug.
3. `list` must enumerate ALL profiles and mark the active one.
4. `delete` must not hang.
5. Every command output must include an "active profile: NAME (NIF)" header line.
