# Testimonial — `docs/workstation-setup.md`

- **Doc path:** `docs/workstation-setup.md`
- **Persona:** A user setting up `aeat` on a fresh workstation for the first time.
- **Date:** 2026-06-18
- **Note:** Repo is shared, so mutating setup commands (`just bootstrap`, `just provision`,
  `pip install`, `ollama serve/pull`) were INSPECTED (via `--help` / source / justfile),
  not executed. Only read-only diagnostics were run.

## Walkthrough

### 1. `just bootstrap` (INSPECTED, not run)
- **Command:** `just bootstrap`
- **Expected:** Installs the Python environment, syncs every dependency group, runs the
  readiness check at the end.
- **Actual:** Recipe exists in the justfile (`just --list` shows `bootstrap`). Not executed
  per shared-repo rule. Description is plausible and matches the recipe's documented intent.
- **Verdict:** OK (inspection only).

### 2. `just doctor`
- **Command:** `just doctor`
- **Expected:** Lists each external dependency, whether it is available, the exact fix
  command for any gap, the profile capability posture; exits with an error when an enabled
  capability has a missing dependency.
- **Actual:** Delivered exactly that. Real output (head):
  ```
  uv run --no-sync aeat config check
  capability	cloud_evidence_upload	desactivado	global_setting
  capability	llm_vision	activado	default
  capability	google_export	activado	default
  dependency	ollama-vision	ausente	start Ollama (ollama serve) and ensure it listens on aeat_llm_ollama_chat_url
  dependency	llm-provider:claude	disponible
  ...
  dependency	extra:google	disponible
  dependency	extra:browser	disponible
  dependency	extra:anthropic	disponible
  problema	llm_vision is on but Ollama is not reachable at http://127.0.0.1 start Ollama (ollama serve) and ensure it listens on aeat_llm_ollama_chat_url
  error: Recipe `doctor` failed on line 25 with exit code 1
  ```
  Each dependency row carries an availability state and a fix hint; the non-zero exit on an
  enabled-but-unmet capability (`llm_vision` on, Ollama absent) matches the page's promise.
- **Verdict:** OK. (Spanish/English mix in the report — `desactivado`/`activado`/`ausente`/
  `problema` — would mildly confuse an English-only reader, see Finding 5.)

### 3. `aeat config check --format json`
- **Command:** `uv run --no-sync aeat config check --format json`
- **Expected (per page):** "Run the check directly for machine-readable output."
- **Actual:** It fails. Real output:
  ```
  {"command":null,"error":{"category":"REFUSED","code":"REFUSED_CLI_BOUNDARY","context":null,
  "message":"No such option: --format","retryable":false,...},"status":"error"}
  ```
  `aeat config check --help` confirms the command has **no options at all** (only `--help`).
  There is no `--format` flag, no `--json` flag on `config check`, and no global `--json`
  flag on `aeat` or `aeat config`. The documented machine-readable path does not exist.
- **Verdict:** DOC-ISSUE, **MAJOR** (Finding 1).

### 4. `aeat config profile capabilities show`
- **Command:** `uv run --no-sync aeat config profile capabilities show`
- **Expected:** Show the resolved capability posture for the three services.
- **Actual:** Worked (no active profile present, fell back to defaults). Real output:
  ```
  cloud_evidence_upload	desactivado	global_setting	cloud evidence upload is off by default (no profile opt-in, global flag unset)
  llm_vision	activado	default	llm_vision is on by default (no profile opt-in)
  google_export	activado	default	google_export is on by default (no profile opt-in)
  ```
  Matches the page's three-capability description and default postures
  (cloud off, vision on, google on) precisely.
- **Verdict:** OK.

### 5. `aeat config profile capabilities set llm_vision off`
- **Command:** `uv run --no-sync aeat config profile capabilities set llm_vision off`
- **Expected:** Turn the capability off for the active profile.
- **Actual:** Refused because there is no active profile (a fresh workstation has none yet):
  ```
  Invalid value: No hay perfil activo; selecciona uno con 'aeat config
  profile use <nombre>' antes de configurar una capacidad.
  ```
  The refusal is graceful (not a crash) — good. BUT the suggested fix command
  `aeat config profile use <nombre>` does not exist: `aeat config profile use` returns
  `No such command 'use'`. The real verb is `aeat config switch NAME`.
  The `set` command syntax itself (`CAPABILITY STATE`, enum-validated `{on|off}`) exactly
  matches the page.
- **Verdict:** APP-ISSUE, **MAJOR** for the dead suggestion (Finding 2); the page itself is
  fine here, but the page also never tells a fresh-workstation reader they must create/switch
  to a profile before the `set` examples will work (Finding 3).

### 6. Optional integrations / provisioning (INSPECTED)
- **`pip install "aeat[google|browser|anthropic|all]"`:** all four extras exist in
  `pyproject.toml [project.optional-dependencies]`; `config check` reports
  `extra:google/browser/anthropic` as `disponible`. Accurate.
- **`just provision`:** recipe exists; described as the Playwright browser install. Plausible.
- **`ollama pull qwen2.5vl:7b`:** the page hardcodes `qwen2.5vl:7b`, but the actual config
  default is `qwen2.5vl:3b` (`aeat_llm_ollama_vision_model` default `"qwen2.5vl:3b"`; 7b is
  documented in source as the optional 8GB+ GPU upgrade). Also, `just doctor`'s remediation
  row does NOT name a model — it says only "start Ollama (ollama serve)". So the page's
  instruction "pull the model named in the report" contradicts both the report (names none)
  and the real default (3b, not 7b).
- **Verdict:** DOC-ISSUE, **MINOR** (Finding 4).

### 7. Links
- All "Next steps" / inline links resolve: `how-to/profile-setup.md`, `how-to/quickstart.md`,
  `how-to/setup-llm-classification.md`, `how-to/troubleshooting.md` all exist.
- **Verdict:** OK.

## Findings

1. **[MAJOR] [DOC]** `aeat config check --format json` is documented ("Run the check directly
   for machine-readable output") but the flag does not exist. Repro:
   `uv run --no-sync aeat config check --format json` →
   `"message":"No such option: --format"`. `aeat config check --help` shows only `--help`;
   no JSON output mode exists on this command or as a global flag.
   **Fix:** Remove the JSON snippet, or implement a `--format json` / `--json` option on
   `config check` and document the real flag. (Note: the command's plain output is already
   tab-separated and machine-parseable, so the "machine-readable" claim is half-true — the
   doc just names a nonexistent flag.)

2. **[MAJOR] [APP]** The capability-set refusal recommends a command that does not exist:
   `aeat config profile use <nombre>` → `No such command 'use'`. The actual verb is
   `aeat config switch NAME`. Repro: `aeat config profile capabilities set llm_vision off`
   with no active profile. **Fix:** Update the error message's suggestion to
   `aeat config switch <nombre>`.

3. **[MINOR] [DOC]** On a genuinely fresh workstation there is no profile, so the page's
   `capabilities set` examples refuse immediately. The page never tells the reader to create
   or switch to a profile first (the "Set up a profile" link is only mentioned afterward, as
   an aside about the wizard). **Fix:** Add a one-line prerequisite before the `set` examples:
   create/switch a profile first (link `how-to/profile-setup.md`), since the active-profile
   posture is what `set` mutates.

4. **[MINOR] [DOC]** The page hardcodes `ollama pull qwen2.5vl:7b`, but the app default is
   `qwen2.5vl:3b` (7b is the optional GPU upgrade), and `just doctor`'s Ollama remediation row
   names no model at all. The page's "pull the model named in the report" is therefore
   self-contradicting. **Fix:** Either pull the actual default (`qwen2.5vl:3b`) or have the
   doctor report print the model name so "the model named in the report" is true.

5. **[NIT] [DOC]** The `just doctor` / `config check` report is partly Spanish
   (`desactivado`, `activado`, `ausente`, `problema`, `disponible`) while the page is English.
   An English-only reader on a fresh box meets unexplained Spanish status tokens. **Fix:** A
   short legend on the page, or localise the report status tokens.

6. **[NIT] [DOC]** The page never mentions that a master-key passphrase
   (`AEAT_SECRET_PASSPHRASE`, or an interactive prompt) is needed for profile-bearing
   operations. The page's own commands (doctor, check, capabilities show) don't need it, so
   it is not a blocker for THIS page — but the moment a fresh user follows the "Set up a
   profile" link they will hit it unwarned. Worth a one-line forward-pointer.

## Testimonial

As a fresh-workstation user this page felt mostly trustworthy: `just doctor` did exactly
what it promised — a clean dependency table with fix hints and a correct non-zero exit when
an enabled capability was unmet — and `capabilities show` mirrored the documented defaults
to the letter. But the very next line burned me: the documented JSON command
(`config check --format json`) simply doesn't exist and errors out, which undermines my
confidence that the rest was tested. The capability toggle then refused (correctly, no
profile yet) but pointed me at `aeat config profile use`, a command that doesn't exist — so
the tool's own escape hatch was a dead end. The app delivers the core promise (works with
no optional services, capabilities are real and enum-validated), but two documented/suggested
commands are flat wrong, and the hardcoded `qwen2.5vl:7b` doesn't match the actual 3b default.

## Scorecard

- **Doc clarity:** 3 / 5 (strong narrative, but a nonexistent flag and a model-name mismatch)
- **App capability:** 4 / 5 (diagnostics and capability surface work; one stale error-message
  suggestion)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2
