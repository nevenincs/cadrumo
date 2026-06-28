---
tags:
  - '#reference'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related: []
---


# aeat config + setup wizard reference

This reference audits the **current** state of the AEAT setup wizard,
the profile/config schemas it duplicates, and every operator-facing
prompt or setter that touches operator-entered configuration. The
ADR for the schema-driven mini-API consumes this document as input.

NOTE: every file:line citation below is against the
`chore/eliminate-shims` worktree at HEAD; line numbers may drift
by a few lines if the surface is touched before the ADR lands.

---

## 1. Schema inventory

Every Pydantic model in the codebase that holds operator-entered
configuration, grouped by where it lives.

### 1.1 `aeat.application.setup` — the "first-run wizard" schema island

This subpackage is an **isolated, unwired** ten-step wizard with its
own answers/result records. **No CLI command imports `SetupWizard`
or `TyperPrompter`.** Only `_env_writer.load_profile_envelope` and a
couple of constants are imported by callers; the orchestrator itself
is dead code as of HEAD (see "Friction points" below).

- **`SetupStep`** (`src/aeat/application/setup/_models.py:23`) —
  `StrEnum` of `WELCOME | PROFILE | CERTIFICATE | LANGUAGE |
  OUTPUT_DIRS | LIVE_TESTS_OPT_IN | VERIFY | FIRST_RUN | DONE`.
  Closed catalogue of linear steps. Not used by any CLI.

- **`SetupOutcome`** (`_models.py:43`) — `StrEnum`
  `COMPLETED | SKIPPED | ABORTED_BY_USER | ABORTED_VERIFY_FAILED`.

- **`VerifySeverity`** (`_models.py:60`) — `StrEnum` `OK | WARNING | ERROR`.

- **`VerifyFinding`** (`_models.py:68`) — strict/frozen/extra=forbid;
  fields `name: str`, `severity: VerifySeverity`, `message: str`,
  `remediation: str | None`.

- **`SetupAnswers`** (`_models.py:86`) — strict/frozen/extra=forbid.
  **The most important model in this audit.** 22 fields:
  - Profile fields (lines 97-108): `tax_id`, `iva_regime` (`IVARegime`),
    `has_employees`, `pays_professionals_with_retencion`,
    `professional_income_withholding_ge_70pct`,
    `pays_rent_with_retencion`, `pays_capital_income_with_retencion`,
    `uses_objective_estimation_irpf`, `does_intracomunitario`,
    `third_party_transactions_above_347_threshold`,
    `bienes_extranjero_above_threshold`, `tax_residence_ccaa` (`CCAA`).
  - Certificate (lines 111-115): `certificate_path: Path`,
    `certificate_password_secret_var_name: str`,
    `certificate_friendly_name: str | None`,
    `certificate_backend: CertificateBackend`,
    `certificate_verify_url: str`.
  - Language (lines 118-119): `default_language: str = "en"`,
    `output_language: str = "es"`.
  - Output dirs (lines 122-124): `aeat_drafts_dir`,
    `aeat_submissions_dir`, `aeat_manuals_root` (all `Path`).
  - Profile JSON target (line 127): `default_profile_path: Path`.
  - Opt-in (line 130): `aeat_live_tests_enabled: bool`.
  - Control (lines 133-134): `steps_to_skip: frozenset[SetupStep]`,
    `notes: str`.

- **`SetupResult`** (`_models.py:137`) — strict/frozen/extra=forbid;
  outcome envelope of one `SetupWizard.run` call.

### 1.2 `aeat.application.profile` — the **live** profile schema island

This subpackage **is wired** to every operator CLI surface
(`aeat setup`, `aeat config`, `aeat init`). Both `_setup.py` and
`_config.py` import from here.

- **`ProfileRecord`** (`src/aeat/application/profile/_models.py:12`) —
  frozen/extra=forbid. Fields: `name: str`,
  `values: dict[str, str]`, `updated_at: datetime`. The `values`
  dict is the operator-entered key/value store; every entry is
  normalised by `_normalise_key` (`workflow/_utils.py:14`:
  strip + lowercase + dashes converted to dots).

- **`ProfileValidationResult`**
  (`src/aeat/application/profile/__init__.py:39`).
  strict/frozen/extra=forbid. Fields: `valid`, `missing_required`,
  `present_required`, `present_optional`, `unknown_keys`,
  `present_keys`, `total_keys`.

- **`ProfileValueRow`** (`__init__.py:71`) — strict/frozen/extra=forbid.
  One schema-backed row: `key`, `value`, `is_set`, `requirement`,
  `description`.

- **Service functions in `_actions.py`**:
  - `set_active_profile(state, name)` (`_actions.py:10`)
  - `set_profile_values(state, profile_name, values)` (`_actions.py:22`)
  - `clear_profile_values(state, profile_name, keys)` (`_actions.py:35`)

- **`validate_profile(values)`** (`__init__.py:97`) — pure
  projection of the domain `PROFILE_KEYS` registry over the
  operator's stored values.

- **`list_profile_value_rows(values, *, include_unset)`**
  (`__init__.py:153`) — schema-backed rows for display.

### 1.3 `aeat.domain.profile` — the schema **registry**

The authoritative catalogue both editor surfaces ultimately read.

- **`ProfileKeyRequirement`** (`src/aeat/domain/profile/_keys.py:31`)
  — `StrEnum` `REQUIRED | OPTIONAL`.

- **`ProfileKey`** (`_keys.py:38`) — strict/frozen/extra=forbid.
  Fields: `key: str` (max 128, dot-separated path),
  `requirement: ProfileKeyRequirement`,
  `description: Translatable` (translation key, must start with
  `profile.keys.`), `required_when_key: str | None`,
  `required_when_value: str | None`. Two validators enforce key
  shape (`_keys.py:49`) and conditional-requirement pairing
  (`_keys.py:78`).

- **`PROFILE_KEYS`** (`_keys.py:106-425`) — **the closed registry**.
  35 entries spanning `tax.id`, `name`, `surnames`, `activity`,
  `address.postcode`, `declaration.type`, `taxpayer.*`, `spouse.*`,
  `family.*`, `iva.*`, `enrollment.*`, `has_employees`,
  `pays_professionals_with_retencion`,
  `professional_income_withholding_ge_70pct`,
  `pays_rent_with_retencion`, `pays_capital_income_with_retencion`,
  `uses_objective_estimation_irpf`, `does_intracomunitario`,
  `third_party_transactions_above_347_threshold`,
  `bienes_extranjero_above_threshold`, `notes`. Required keys:
  `tax.id`, `activity`. Conditional requirements: `spouse.*`
  cascades from `declaration.type=2`; `spouse.eu_eea_country`
  cascades from `spouse.eu_eea_resident=true`.

- **`get_profile_key(key)`** (`_keys.py:432`) — registry lookup,
  raises `KeyError`.

- **`required_profile_keys()`** / **`optional_profile_keys()`**
  (`_keys.py:444`, `:449`) — registry slicing.

### 1.4 `aeat.domain.profile.family` — Modelo 100 family rows

Used downstream of the wizard for IRPF; **not currently prompted
by the wizard**.

- **`RentaDescendantProfile`** (`family.py:19`),
  **`RentaAscendantProfile`** (`family.py:48`),
  **`RentaFamilyProfile`** (`family.py:78`) — all strict/frozen/
  extra=forbid. No CLI prompt or `config set` path exposes these.

### 1.5 `aeat.domain.profile` (top) — tax-residence profile

- **`CCAA`** (`src/aeat/domain/profile/__init__.py:28`) —
  `StrEnum` of 15 common-regime CCAAs. Foral regimes
  (`pais-vasco`, `navarra`, ...) raise `ForalRegimeError`
  via `parse_tax_region`.

- **`ResidenceChange`** (`__init__.py:60`) — frozen/strict.
  Fields: `from_ccaa`, `to_ccaa`, `effective_from`, `reason`.

- **`TaxResidenceProfile`** (`__init__.py:85`) — frozen/strict.
  Fields: `schema_version: str = "1"`, `ccaa: CCAA`,
  `tax_residence_since: date | None`,
  `tax_residence_change_history: tuple[ResidenceChange, ...]`.
  Persisted separately via `adapters.persistence.profile.save_tax_residence`.

### 1.6 `aeat.domain.deadlines` — `AutonomoProfile` (downstream consumer)

- **`AutonomoProfile`** (`src/aeat/domain/deadlines/_models.py:92`)
  — strict/frozen/extra=forbid. 13 fields mirroring most of
  `SetupAnswers`'s profile section plus nested `FilingIVAProfile`
  / `FilingEnrollment`. **Constructed from a flat
  `Mapping[str, object]` via `autonomo_profile_from_mapping`**
  (`src/aeat/domain/deadlines/_profiles.py:14`). The mapping
  function (lines 81-118) handles boolean coercion and key-alias
  fallback (`has_employees`/`has.employees`, etc.). Two boolean
  token sets are hand-rolled at lines 10-11 (`_TRUE_TOKENS`,
  `_FALSE_TOKENS`) — the **canonical "string to typed field"
  resolver** for the live profile.

- **`IVARegime`** (`_models.py:23`) — `StrEnum`
  `GENERAL | SIMPLIFICADO | RECARGO_EQUIVALENCIA | EXENTO`.

- **`FilingIVAProfile`** (`_models.py:82`),
  **`FilingEnrollment`** (`_models.py:73`) — nested into
  `AutonomoProfile`. Each carries booleans operator-entered as
  flat `iva.*` / `enrollment.*` keys.

### 1.7 `aeat.application.auth` — auth state

- **`AuthState`** (`src/aeat/application/auth/_models.py:10`) —
  frozen/extra=forbid. Fields: `provider`, `certificate_path`,
  `configured_at`, `authenticated_at`, `subject`. Mutated by
  `update_auth` (`_actions.py:14`).

- **`AuthProviderListing`** (`_catalogue.py:13`) — strict/frozen.
  `id`, `label: Translatable`, `description: Translatable`.

- **`AUTH_PROVIDER_CATALOGUE`** (`_catalogue.py:33`) — closed tuple
  of `certificate` and `clave_movil` listings, with `tr()`
  translation keys for label/description. **This is the closest
  thing the codebase has to a descriptor-driven listing of
  configurable surfaces.**

- **`AuthProviderKind`** (`auth/__init__.py:21`) — `StrEnum`
  `CERTIFICATE | CLAVE_MOVIL`.

### 1.8 `aeat.application.workflow._models` — operator state

- **`WorkflowState`** (`workflow/_models.py:95`) — frozen/extra=forbid.
  Fields: `auth: AuthState`, **`profiles: dict[str, Any]`** keyed
  by profile name (typed loosely so legacy dict shapes can be
  round-tripped via `model_validate` in `active_profile_record`),
  `active_profile: str | None`, `declarations`, `invoice_reviews`,
  `ledger_reviews`, `updated_at`. **The container that every CLI
  setter mutates via `workflow_state_repository().update(...)`.**

- **`active_profile_record(self)`** (`_models.py:123`) — returns the
  active `ProfileRecord` or `None`, defending against legacy dict
  payloads.

### 1.9 `aeat.application.setup_reset` — scoped reset

- **`SetupResetScope`** (`src/aeat/application/setup_reset.py:33`)
  — `StrEnum` `PROFILE | AUTH | DATA | ALL`.

- **`SetupResetReport`** (`setup_reset.py:46`) — strict/frozen/
  extra=forbid. `scope`, `removed_profile_names`,
  `removed_auth_session`, `quarantined_namespace_count`.

- **`reset_setup(scope, *, confirmed)`** (`setup_reset.py:68`).

### 1.10 `aeat.core.config.Settings` — env-var driven settings

`src/aeat/core/config.py:82` — pydantic-settings `BaseSettings`.
**70+ fields**, all `aeat_*`-prefixed (1:1 with env vars). The
fields the wizard currently mirrors:

| Field (env var) | line |
|---|---|
| `aeat_token_dir` | 96 |
| `aeat_base_url` | 102 |
| `aeat_output_language` | 149 |
| `aeat_certificate_path` | 292 |
| `aeat_certificate_password_secret` (SecretStr) | 296 |
| `aeat_certificate_friendly_name` | 300 |
| `aeat_certificate_backend` | 304 |
| `aeat_certificate_verify_url` | 308 |
| `aeat_auth_provider` | 340 |
| `aeat_default_profile_path` | 452 |
| `aeat_drafts_dir` | 507 |
| `aeat_submissions_dir` | 467 |
| `aeat_manuals_root` | 222 |
| `aeat_live_tests_enabled` | 216 |
| `aeat_secret_store_backend` | 179 |
| `aeat_allow_unencrypted` | 190 |
| `aeat_clave_movil_dni_nie` | 350 |
| `aeat_clave_movil_dni_fecha` | 360 |
| `aeat_clave_movil_nie_soporte` | 368 |

Auxiliary `StrEnum`s defined for `Settings` consumption:
`SecretStoreBackend` (`config.py:24`), `LLMProviderSetting` (`:53`),
`CertificateBackendSetting` (`:62`), `AuthProviderKindSetting` (`:69`),
`JustificanteParserBackendSetting` (`:76`).

`Settings.env_var_names()` (`config.py:673`) — returns the set of
uppercase env var names; useful seed for a config-set surface.

---

## 2. Current wizard flow — step-by-step trace

The **unwired** `aeat.application.setup.SetupWizard` flow first
(authoritative for any "what the legacy wizard does"). Then the
**live** wizard surface: `aeat init`, `aeat setup init`, `aeat setup
profile set`, `aeat config set`.

### 2.1 Unwired ten-step `SetupWizard`

Entry point: `SetupWizard.run` (`_wizard.py:66`).

Argument routing: non-interactive uses `defaults: SetupAnswers`
directly (`_wizard.py:105-108`); interactive calls
`_collect_interactive` (`_wizard.py:112`).

`_collect_interactive` (`_wizard.py:181-338`) walks every field
sequentially. **One Python-level call per field; no branching, no
re-prompt loop except inside `TyperPrompter.prompt_choice`
(`_prompter.py:151`).**

Per-prompt trace (prompt site, type coercion, default):

| Step | Field | Prompt site | Type coercion | Default |
|---|---|---|---|---|
| WELCOME | (informational) | `_wizard.py:194-197` (`prompter.announce`) | — | — |
| PROFILE | `tax_id` | `_wizard.py:199-203` (`prompt_text`) | raw `str` | from defaults or none |
|  | `iva_regime` | `_wizard.py:204-209` (`prompt_choice`) | `IVARegime(raw)` line 316 | `GENERAL` |
|  | `has_employees` | `_wizard.py:210-214` (`prompt_bool`) | `bool` | `False` |
|  | `pays_professionals_with_retencion` | `_wizard.py:215-219` | `bool` | `False` |
|  | `professional_income_withholding_ge_70pct` | `_wizard.py:220-224` | `bool` | `False` |
|  | `pays_rent_with_retencion` | `_wizard.py:225-229` | `bool` | `False` |
|  | `does_intracomunitario` | `_wizard.py:230-234` | `bool` | `False` |
|  | `third_party_transactions_above_347_threshold` | `_wizard.py:235-239` | `bool` | `False` |
|  | `bienes_extranjero_above_threshold` | `_wizard.py:240-244` | `bool` | `False` |
|  | `tax_residence_ccaa` | `_wizard.py:245-250` (`prompt_choice`) | `CCAA(raw)` line 324 | `MADRID` |
| CERTIFICATE | `certificate_path` | `_wizard.py:252-256` (`prompt_path`) | `Path` | none |
|  | `certificate_password_secret_var_name` | `_wizard.py:257-261` | `str` | `AEAT_CERTIFICATE_PASSWORD_SECRET` |
|  | `certificate_friendly_name` | `_wizard.py:262-266` | `str` (empty becomes `None` line 327) | `""` |
|  | `certificate_backend` | `_wizard.py:267-272` (`prompt_choice`) | `CertificateBackend(raw)` line 328 | `PLAYWRIGHT_CONTEXT` |
| LANGUAGE | `default_language` | `_wizard.py:274-279` | `str` (choice) | `"en"` |
|  | `output_language` | `_wizard.py:280-285` | `str` (choice) | `"es"` |
| OUTPUT_DIRS | `aeat_drafts_dir` | `_wizard.py:287-291` (`prompt_path`) | `Path` | `var/drafts` |
|  | `aeat_submissions_dir` | `_wizard.py:292-296` | `Path` | `var/submissions` |
|  | `aeat_manuals_root` | `_wizard.py:297-301` | `Path` | `corpus/manuals` |
|  | `default_profile_path` | `_wizard.py:302-306` | `Path` | `env/profile.json` |
| LIVE_TESTS_OPT_IN | `aeat_live_tests_enabled` | `_wizard.py:308-312` (`prompt_bool`) | `bool` | `False` |

**Note**: `pays_capital_income_with_retencion`,
`uses_objective_estimation_irpf` — declared on `SetupAnswers`
(`_models.py:103`, `:105`) but **never prompted** in
`_collect_interactive`. They default to `False` and are written
into `AutonomoProfile` in `write_profile_file` with that default.
This is a latent inconsistency.

**Validation**: each prompt-level value is coerced inside the
`SetupAnswers(...)` constructor at `_wizard.py:314-338`. Pydantic
v2 validation runs on construction; failures raise
`ValidationError` and bubble out of `run`.

**Commit**: side-effect order in `run`:
1. `write_profile_file(answers, answers.default_profile_path)`
   (`_wizard.py:138`) — builds `AutonomoProfile`, secures it via
   `SecureObjectRepository` (`_env_writer.py:196-203`), and writes
   `TaxResidenceProfile` (`_env_writer.py:204`).
2. `write_env_file(answers, target_env)` (`_wizard.py:139`) — fixed
   set of 10 env vars listed by `owned_env_keys` (`_env_writer.py:39`)
   plus an idempotent comment line for the password env var name
   (`_env_writer.py:82-114`).
3. `Verifier().run(answers)` (`_wizard.py:147`) — 7 checks (see
   `_verifier.py:154-170`): self-consistency, cert path, password
   env var, three directory mkdirs, profile envelope round-trip.

**Error handling / re-prompt**: only `TyperPrompter.prompt_choice`
loops on invalid choices (`_prompter.py:151-155`). Every other
prompt is single-shot; pydantic raises and the wizard aborts. No
"back" navigation, no skip-this-field option except via
`steps_to_skip` populated upfront.

**Reset/re-run semantics**: `SetupWizard.run` always re-prompts
every field. If `defaults` is supplied, prompter defaults are
populated from it but **every prompt is still issued**. There is
no idempotent diff-only path; re-running produces a byte-equal env
file when answers match (`write_env_vars` preserves unrelated keys
— `_env_writer.py` lines 117-138 plus `core/env_io.py` behaviour) but
the wizard's UX always asks every question.

### 2.2 Live wizard surfaces (what operators actually run)

`aeat init` — root command (`src/aeat/entrypoints/cli/__init__.py:119`),
`init_cmd` body at lines 120-179. Prompt sites:

| Field | Prompt site | Commit |
|---|---|---|
| `name` | `__init__.py:147` (`typer.prompt`) | `set_profile_values(state, resolved_name, seeded)` line 164 |
| `tax.id` | `__init__.py:148` | same line 164 |
| `activity` | `__init__.py:149` | same line 164 |
| `iva.regime` | `__init__.py:150` (default `"general"`) | same line 164 |

`init_cmd` quiet-mode validation: lines 138-141 (`--name`,
`--tax-id`, `--activity` all required when `--quiet`).

`aeat setup init` (`src/aeat/entrypoints/cli/_setup.py:65`,
`setup_init` body at lines 66-95) — **flag-only**, no prompts.
Required: `--name`. Optional: `--tax-id`, `--activity`. Commits
via `set_profile_values` (`_setup.py:79`) or `set_active_profile`
(`_setup.py:81`).

`aeat setup profile set <key> <value>` (`_setup.py:537-551`) —
schema-validated through `get_profile_key(key)` (line 544;
`KeyError` triggers `_bad`). Commits via `set_profile_values`
(`_setup.py:548`).

`aeat setup profile unset <key>` (`_setup.py:554-564`) — same
schema check, commits via `clear_profile_values` (line 563).

`aeat config set <key> <value>` (`src/aeat/entrypoints/cli/_config.py:161-190`)
— **NEW** alias surface added by this branch. Schema-validates
via `get_profile_key` (line 173); rejects when no active profile
(line 180). Commits via `set_profile_values` (line 181).

`aeat config get <key>` (`_config.py:136-158`) and `aeat config
unset <key>` (`_config.py:193-213`) — symmetric reads/clears.

`aeat config list` (`_config.py:103-133`) — renders every
`PROFILE_KEYS` entry with its current value (`<unset>` when blank).

`aeat setup auth configure --provider <id> [--file PATH]`
(`_setup.py:208-238`) — provider lookup via `get_auth_provider`
(`_setup.py:216`); commits via `update_auth` (`_setup.py:224-229`).

`aeat setup reset --profile|--auth|--data|--all --yes`
(`_setup.py:130-182`) — scope flag becomes `SetupResetScope`
(lines 154-161); `--yes` required (line 163). Commits via
`reset_setup` (`_setup.py:166`).

---

## 3. Duplication matrix

For every operator-entered field, every place that field is
prompted, set, or validated. **Read top-to-bottom: the same
field cuts across the dead `SetupWizard`, the live `aeat init`,
the live `aeat setup init`, and the live `aeat setup profile set`
/ `aeat config set` surfaces.**

| Field (semantic) | Dead `SetupWizard` prompt | `aeat init` prompt | `aeat setup init` flag | `aeat setup profile set` / `aeat config set` | Backend setter | Validator | Notes |
|---|---|---|---|---|---|---|---|
| `tax_id` / `tax.id` | `_wizard.py:199` | `__init__.py:148` | `_setup.py:70` (`--tax-id`) | accepts `tax.id` | `set_profile_values` | `PROFILE_KEYS["tax.id"]` REQUIRED | **4 paths** |
| `activity` | (not prompted) | `__init__.py:149` | `_setup.py:69` (`--activity`) | accepts `activity` | `set_profile_values` | `PROFILE_KEYS["activity"]` REQUIRED | **3 paths**; legacy wizard never asked |
| `iva_regime` / `iva.regime` | `_wizard.py:204` (`IVARegime` choice) | `__init__.py:150` (free text) | not prompted | accepts `iva.regime` (string only) | `set_profile_values` | none on the live path; legacy uses `IVARegime(raw)` | **type drift**: legacy enforces enum, live `aeat init` stores raw string |
| `has_employees` | `_wizard.py:210` (`bool`) | none | none | accepts `has_employees` (string token) | `set_profile_values` | `_bool_value` (`deadlines/_profiles.py:92`) at read time | **2 paths**; live stores `"true"`/`"false"`/etc strings |
| `pays_professionals_with_retencion` | `_wizard.py:215` (`bool`) | none | none | accepts | `set_profile_values` | same | "string-bool" mismatch |
| `professional_income_withholding_ge_70pct` | `_wizard.py:220` | none | none | accepts | `set_profile_values` | same | same |
| `pays_rent_with_retencion` | `_wizard.py:225` | none | none | accepts | `set_profile_values` | same | same |
| `pays_capital_income_with_retencion` | **not prompted** but declared on `SetupAnswers` line 103 | none | none | accepts | `set_profile_values` | same | latent: legacy wizard writes `False` to env / profile envelope unconditionally |
| `uses_objective_estimation_irpf` | **not prompted** line 105 | none | none | accepts | `set_profile_values` | same | latent (as above) |
| `does_intracomunitario` | `_wizard.py:230` (`bool`) | none | none | accepts | `set_profile_values` | `_bool_value` | string-bool drift |
| `third_party_transactions_above_347_threshold` | `_wizard.py:235` | none | none | accepts | `set_profile_values` | `_bool_value` | drift |
| `bienes_extranjero_above_threshold` | `_wizard.py:240` | none | none | accepts | `set_profile_values` | `_bool_value` | drift |
| `tax_residence_ccaa` | `_wizard.py:245` (`CCAA` choice) | none | none | not exposed (NOT in `PROFILE_KEYS`) | `save_tax_residence(TaxResidenceProfile(...))` (`_env_writer.py:204`) | `parse_tax_region` raises `ForalRegimeError` | **completely separate surface**: legacy wizard persists this OUTSIDE the workflow state, in `adapters.persistence.profile`; live CLI cannot set it |
| `certificate_path` | `_wizard.py:252` (`Path`) | none | none | not exposed (NOT in `PROFILE_KEYS`) | `_env_writer.write_env_file` writes env file | filesystem existence check in `Verifier._check_certificate_path` (`_verifier.py:39`) | live path is `aeat setup auth configure --file PATH` (`_setup.py:212`) which writes to `AuthState`, **not** profile values |
| `certificate_password_secret_var_name` | `_wizard.py:257` | none | none | not exposed | `_env_writer._ensure_password_comment` (env-file comment only) | `Verifier._check_password_env_var` (`_verifier.py:61`) | only the legacy wizard records the env-var **name**; live setup has no equivalent — the password is read from `Settings.aeat_certificate_password_secret` (env-only `SecretStr`) at use time |
| `certificate_friendly_name` | `_wizard.py:262` | none | none | not exposed | env file | none | drift |
| `certificate_backend` | `_wizard.py:267` (`CertificateBackend` choice) | none | none | not exposed | env file | none | live equivalent is `Settings.aeat_certificate_backend` (line 304) sourced from env |
| `default_language` | `_wizard.py:274` | none | none | not exposed | env file | choice loop in prompter | live equivalent is `Settings.aeat_output_language` (line 149) sourced from env |
| `output_language` | `_wizard.py:280` | none | none | not exposed | env file | choice loop | same |
| `aeat_drafts_dir` | `_wizard.py:287` (`Path`) | none | none | not exposed | env file plus `Verifier._check_directory` mkdir | `Verifier._check_directory` (`_verifier.py:77`) | live equivalent is `Settings.aeat_drafts_dir` (line 507) |
| `aeat_submissions_dir` | `_wizard.py:292` | none | none | not exposed | env file + mkdir | same | live: `Settings.aeat_submissions_dir` (line 467) |
| `aeat_manuals_root` | `_wizard.py:297` | none | none | not exposed | env file + mkdir | same | live: `Settings.aeat_manuals_root` (line 222) |
| `default_profile_path` | `_wizard.py:302` | none | none | not exposed | env file | `Verifier._check_profile_file` (`_verifier.py:94`) | live: `Settings.aeat_default_profile_path` (line 452) |
| `aeat_live_tests_enabled` | `_wizard.py:308` (`bool`) | none | none | not exposed | env file | none | live: `Settings.aeat_live_tests_enabled` (line 216) |
| `name` (profile label) | not a field on `SetupAnswers` | `__init__.py:147` | `_setup.py:68` (`--name`, required) | not a settable key | `set_active_profile`/`set_profile_values` | profile name trim validator (`profile/_models.py:21`) | live-only concept; `SetupAnswers` has no profile-label field |
| `auth provider` | implied by `certificate_backend` | not exposed | not exposed | `aeat setup auth configure --provider <id>` (`_setup.py:211`) | `update_auth` | `get_auth_provider` (`_catalogue.py:57`) | dedicated surface, separate from the profile editor |
| **Cl@ve fields** (`dni_nie`, `dni_fecha`, `nie_soporte`) | not exposed | not exposed | not exposed | not exposed | `Settings` env-only | none | env-only; no CLI prompt or config surface |
| **Usage ratios** (per `SpendingCategory`) | not exposed | not exposed | not exposed | not exposed (separate surface) | `aeat financial profile set-ratio` (`financial/profile.py:81`) | `_parse_ratio` (`financial/profile.py:263`) | parallel "profile editor" with its own validator/error UX |

**Headline duplications**:
- Eight booleans (`has_employees`, `pays_*`, `*_threshold`, `does_intracomunitario`, ...) live in three orthogonal places: `SetupAnswers` (typed `bool`), `ProfileRecord.values` (string token), and `AutonomoProfile` (typed `bool` parsed from token by `_bool_value`).
- The IVA regime exists as an enum in multiple places (`IVARegime` typed; the workflow state holds it as a free string under `iva.regime`).
- The certificate has **two independent representations**: `SetupAnswers.certificate_path/_backend/_friendly_name/_verify_url` (dead) and `AuthState.certificate_path` plus `Settings.aeat_certificate_*` (live).
- `tax_residence_ccaa` is the lone field that traverses a third storage surface (`adapters.persistence.profile.save_tax_residence`) bypassing both `ProfileRecord.values` and `Settings`.

---

## 4. i18n entanglement

The translation system has two distinct primitives, easily confused:

- **`Translatable`** (`src/aeat/core/i18n/_translatable.py:11`) —
  pydantic-aware `str` subclass used as a **typed marker** on
  schema fields. Stores the translation **key**, not the rendered
  string. Aliased as `tr` in pydantic-record modules (`from
  ...core.i18n import Translatable as tr` — e.g. `_keys.py:27`,
  `setup/_wizard.py:20`).
- **`tr(key, **kwargs)`** (`src/aeat/core/i18n/_render.py:46`) —
  function that lazily initialises `python-i18n` (locale path from
  `importlib.resources.files("aeat").joinpath("locales")`) and
  renders the key. CLI imports this from `_i18n.py` (`cli/_i18n.py:10`).

The legacy wizard's `_collect_interactive` (`_wizard.py:181-338`)
passes `tr("setup.wizard.tax_id_prompt")` (the **Translatable
marker**) into the prompter as the `prompt=` argument. The
prompter receives it as a `str`. Whether it gets rendered depends
on the prompter:
- `TyperPrompter.prompt_text` (`_prompter.py:121-126`) passes
  `prompt` straight to `typer.prompt` — **the raw translation key
  is shown to the operator**, never rendered. This is a latent
  bug in the dead wizard.
- `QueuedPrompter` ignores `prompt` (line 64 `del prompt, default`).

Locale catalogues:
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`. Loaded
  by `_render.py:24`.
- `setup.wizard.*` keys: `en.yml:807-834` — 24 prompt strings,
  one per field, all hand-authored.
- `cli.setup.*` keys: `en.yml:598-691` — 60+ help / header /
  label / error strings for the live `aeat setup` group.
- `cli.init.*` keys: only present in `es.yml:391-402`; `en.yml` /
  `ca.yml` / `hu.yml` are **missing translations** for the new
  root `aeat init` command. Operators on `aeat_output_language=en`
  see raw keys (or python-i18n fallback) for those prompts.
- `profile.keys.<key>` keys (per-key description): consumed by
  `ProfileKey.description` (`_keys.py:103`) and rendered by
  `_description_for` in `cli/_common.py:103`.
- `setup.verifier.t_NNNNNN` keys: hand-numbered translation keys
  in `en.yml:792-806` for verifier findings.

What's coupled vs. liftable:
- **Coupled** — every help string in `cli/_setup.py` and
  `cli/_config.py` is wrapped in a `tr(...)` call at module import
  time (Typer evaluates the help string when constructing the
  command). The translations resolve once, at process start.
- **Coupled** — the dead wizard's prompt strings are not actually
  rendered (`TyperPrompter` passes them raw). The locale catalogue
  exists for the keys but the rendering path is broken.
- **Liftable** — the `profile.keys.*` translation pattern (one
  catalogue entry per registry key) is the **closest existing
  precedent for descriptor-driven copy**. Generating prompt strings
  from `f"profile.prompts.{key}"` keys per field would mirror the
  existing pattern exactly.
- **Liftable** — `Translatable` is already a pydantic v2 marker
  type (`__get_pydantic_core_schema__`), so a hypothetical
  descriptor record can carry `Translatable` fields for prompt /
  label / description and the schema layer validates the shape.

---

## 5. Existing abstractions to lean on

The codebase already has the seeds of a schema-driven wizard,
scattered across three locations.

### 5.1 `PROFILE_KEYS` + `validate_profile` — the **resolver / registry seed**

The `aeat config set <key> <value>` resolver flow is the closest
existing implementation of "schema-driven setter":

`_config.py:172` `get_profile_key(key)` (raises `KeyError`)
then `set_profile_values(state, profile_name, {key: value})`
(`profile/_actions.py:22`) then workflow state commit.

This is **already key-uniform**: any `PROFILE_KEYS` entry can be
written via `aeat config set <key> <value>` without the CLI knowing
which key is which. The schema-driven wizard is a strict superset
of this resolver — add prompt-text / input-type / default fields
to `ProfileKey` and the existing resolver feeds the prompt loop.

### 5.2 `ProfileKeyRequirement` plus `required_when_key`/`required_when_value`

`_keys.py:46-47, 78-82` — already encodes **conditional
requirements** (e.g. `spouse.*` becomes required when
`declaration.type = "2"`). A schema-driven wizard's
branching/skipping logic can read this directly. The `model_validator`
pairing rule (`_keys.py:78`) ensures both `when_key` and
`when_value` are set together.

### 5.3 `AUTH_PROVIDER_CATALOGUE` — descriptor-list precedent

`auth/_catalogue.py:33` is a tuple of `AuthProviderListing` records,
each with `id` + translation-keyed `label` + `description`. The CLI
iterates this tuple to render help text and `_setup.py:216` resolves
operator-supplied `--provider` ids against it. **This is the
existing pattern for "render a catalogue, then act on the
identifier"** — a wizard-descriptor list would mirror it directly.

### 5.4 `autonomo_profile_from_mapping` — typed-projection precedent

`deadlines/_profiles.py:14` — pure function from
`Mapping[str, object]` to a typed `AutonomoProfile`. Handles
boolean coercion (lines 92-105), aliases (e.g.
`has_employees`/`has.employees`), enum parsing
(`_iva_regime_value` lines 108-118). **Any new wizard-descriptor
type that emits typed records should re-use this resolver or
mimic its shape**, not invent a parallel coercion table.

### 5.5 `Prompter` Protocol — interaction-source decoupling

`setup/_protocols.py:20` — already abstracts "where do answers
come from" away from "what does the wizard ask for". The
`QueuedPrompter` / `TyperPrompter` split (`_prompter.py`) is the
existing test-vs-prod abstraction. A schema-driven wizard's
prompt-loop can re-use this Protocol verbatim and add a
descriptor-aware variant.

### 5.6 `SetupResetScope` / `reset_setup` — scoped-action precedent

`setup_reset.py:33-130` — closed enum of operator-driven scopes,
each with its own state-mutation path, gated by a single
`confirmed=True` parameter. **The "scope to mutation" pattern
generalises** to "wizard descriptor to mutation" with the same
confirmation contract.

### 5.7 `Settings.env_var_names()` — env-discovery seed

`config.py:673` returns the set of `aeat_*` env vars. If a future
descriptor encodes which fields are env-sourced vs.
profile-sourced, this is the right enumeration point.


---

## 6. Friction points

Empirical observations of where the current flow has accumulated
workarounds, dead code, or behaviour gaps.

- **The `SetupWizard` orchestrator is unwired**. No CLI command
  imports it. Its translations (`setup.wizard.*` in `en.yml:807-834`)
  exist but `TyperPrompter.prompt_text` passes the raw translation
  key to `typer.prompt` as the prompt string (`_prompter.py:125`)
  -- the operator would see literally `setup.wizard.tax_id_prompt`
  if any code path ever invoked it. The wizard exists primarily
  because `_env_writer.load_profile_envelope` is consumed by
  `deadlines/_helpers.py:67`. The orchestrators only real use
  is the `_env_writer.write_profile_file` call (referenced from
  `filing_cli` tests for namespace constants).

- **Two parallel first-run code paths**. `aeat init`
  (`__init__.py:119`) does a 4-field interactive prompt;
  `aeat setup init` (`_setup.py:65`) is flag-only. The two
  commands accept different flag shapes (`aeat init --iva-regime`
  vs. `aeat setup profile set iva.regime ...`) and serve overlapping
  audiences. The root `init` was added recently (UX-003) atop the
  existing `setup init`; no clear authority over who owns first-run.

- **`SetupAnswers` declares fields it never prompts for**:
  `pays_capital_income_with_retencion` (line 103),
  `uses_objective_estimation_irpf` (line 105). The wizard
  silently writes `False` to the resulting `AutonomoProfile`
  even though the operator was never asked. Latent correctness
  bug in the dead path; also a signal that schema and prompt
  list have already drifted apart.

- **String-typed booleans on the live path**. `aeat config set
  has_employees true` stores the **string** `"true"`; reads use
  `_bool_value` (`deadlines/_profiles.py:92`) with a hand-rolled
  token table (`_TRUE_TOKENS` line 10, `_FALSE_TOKENS` line 11).
  The dead wizard accepted typed booleans via `prompt_bool`. The
  type contract changes depending on which entry point the
  operator uses.

- **No `iva.regime` enum validation on the live path**. `aeat
  config set iva.regime XYZ` stores arbitrary strings; the read
  side (`_iva_regime_value` `deadlines/_profiles.py:108`) raises
  `ValueError` at deadline computation time, far from the setter.

- **`tax_residence_ccaa` is unreachable from the live CLI**. Only
  the dead `SetupWizard` writes it, via the side-effect path in
  `write_profile_file` (`_env_writer.py:204`). `aeat config set
  tax_residence_ccaa madrid` fails because the key is not in
  `PROFILE_KEYS`. There is no live CLI surface to set this without
  hand-editing JSON.

- **`certificate_path` is split across two stores**. Live CLI
  writes it into `AuthState.certificate_path` (`_actions.py:32-33`
  via `update_auth`). The dead wizard writes it into
  `AEAT_CERTIFICATE_PATH` env var (`_env_writer.py:69`).
  `Settings.aeat_certificate_path` (`config.py:292`) reads only
  from env. Two operator-input paths, one settings read.

- **`Settings` is `BaseSettings`-only**. Of 70+ fields in
  `core/config.py:82`, none are written by any CLI command;
  they are env-only. The wizard would either have to write env
  files (the dead path does this) or extend `Settings` to support
  a non-env source. Today nothing bridges operator-entered values
  to a `Settings` field.

- **`Verifier` lives inside the dead wizard subpackage**
  (`_verifier.py:142`). Its checks (cert path, password env var,
  dir mkdir, profile envelope load) are exactly the checks a
  live wizard would run, but they take a `SetupAnswers` (dead
  model) as input -- not the `WorkflowState` / `Settings` /
  `ProfileRecord` the live surfaces produce.

- **`init_cmd` quiet-mode error text** (`__init__.py:139-141`)
  uses `tr("cli.init.quiet_requires_all")`, but the key is only
  present in `es.yml:398` -- `en.yml` returns the raw key. UX
  regression on the default English path.

- **Profile-value normalisation is asymmetric**. `_normalise_key`
  (`workflow/_utils.py:14`) strips, lowercases, and converts
  dashes to dots. `ProfileRecord._normalise_values`
  (`profile/_models.py:31`) runs it on every set. But
  `get_profile_key` (`_keys.py:432`) does an exact-string lookup
  in `_BY_KEY` (`_keys.py:429`) without normalising the query --
  so the CLI rejects `aeat config set TAX.ID 12345678Z` ("unknown
  key") even though the post-normalisation form would be valid.
  The asymmetry is hidden by Typer-level argument trimming.

- **`aeat setup status` and `build_setup_status`
  (`application/setup_status.py:34`) consume the workflow-state-
  shaped profile** (`ProfileRecord.values: dict[str, str]`).
  Adding a typed descriptor model means either keeping the
  `dict[str, str]` projection forever (so `setup_status` still
  works) or rewriting the status report.

---

## 7. Open questions for the ADR phase

These are decisions the audit surfaces but cannot answer on its
own. The ADR will need to resolve each.

- **Does the descriptor model replace `ProfileKey`, or sit
  alongside it?** `ProfileKey` is consumed by `validate_profile`,
  the CLI list-keys command, and indirectly by the deadline
  engine via the `autonomo_profile_from_mapping` key set. A
  descriptor type with a superset shape (adding `prompt`,
  `input_kind`, `choices`, `default`, `bool_token_map`, ...) is
  one path; an adjacent registry that references `PROFILE_KEYS`
  by key is another.

- **Where do the dead wizards env-file fields live in the
  new model?** `aeat_drafts_dir`, `aeat_submissions_dir`,
  `aeat_manuals_root`, `aeat_live_tests_enabled`,
  `aeat_certificate_*`, `default_language`, `output_language`,
  `default_profile_path` are all `Settings` fields, not
  `PROFILE_KEYS` entries. The new wizard either has to
  (a) write to env files (re-using `core/env_io.py`),
  (b) extend `Settings` to accept an alternate source, or
  (c) treat them as out-of-scope for "operator profile".

- **Is `tax_residence_ccaa` a profile field or a separate
  surface?** Currently it lives in `TaxResidenceProfile` via
  `adapters.persistence.profile.save_tax_residence`. If the
  descriptor model owns it, that separate persistence path
  becomes a setter target like every other field.

- **Does the certificate-path collapse into the profile or
  remain an `AuthState` field?** `_setup.py:208-238` already
  treats `--file PATH` as auth configuration, not profile
  configuration. The dead wizard treats it as a profile field.
  Mixed model today.

- **What is the relationship between `aeat init`, `aeat setup
  init`, `aeat config set`, and the new wizard?** Three live
  surfaces accept the same fields with different flags. The ADR
  should pick exactly one canonical operator first-run path and
  demote (or remove) the others; the CLI mandate says the root
  has exactly two surfaces (`config` + `app`), so `setup` itself
  may be on the chopping block.

- **Does `Verifier` move into the new wizard descriptor (one
  check per descriptor) or stay as an orchestrator-level
  post-write check?** The current checks are field-scoped
  (cert path, dir mkdir, profile envelope) and would map
  cleanly to per-field validators on a descriptor.

- **What happens to the `SetupWizard.steps_to_skip` /
  `steps_completed` machinery?** No live surface uses it. If
  the new model is descriptor-driven, skip likely becomes a
  property of the descriptor (e.g. `optional: bool`,
  `conditional_on: ProfileKeySelector`) rather than a separate
  closed-enum skip list.

- **Re-run semantics**: should the new wizard re-prompt every
  field (current dead-wizard behaviour) or diff-only (only
  re-prompt unset/changed)? Currently nothing in the codebase
  models a diff-only iteration of the descriptor.

- **Is the `Translatable as tr` marker (`_keys.py:27`,
  `_wizard.py:20`) sustainable for the prompt strings**, or
  should the descriptor explicitly carry a rendered `str` plus
  a translation key for both prompt and help?

---

## Appendix: file map

Modules:
- `src/aeat/application/setup/` -- dead wizard (orchestrator,
  models, prompter, verifier, env-writer, errors, protocols).
- `src/aeat/application/profile/` -- live profile schema layer
  (models, actions, validation result/row).
- `src/aeat/application/workflow/` -- live state container
  (`WorkflowState`, persistence, utilities).
- `src/aeat/application/auth/` -- auth state + catalogue + actions.
- `src/aeat/application/setup_status.py` -- readiness projection.
- `src/aeat/application/setup_reset.py` -- scoped reset.
- `src/aeat/domain/profile/` -- registry (`PROFILE_KEYS`,
  `ProfileKey`, `ProfileKeyRequirement`), family rows, tax
  residence model, CCAA enum.
- `src/aeat/domain/deadlines/` -- `AutonomoProfile`,
  `autonomo_profile_from_mapping`, `IVARegime`,
  `FilingEnrollment`, `FilingIVAProfile`.
- `src/aeat/core/config.py` -- `Settings` (env-only).
- `src/aeat/core/i18n/` -- `Translatable` marker and `tr`
  renderer.
- `src/aeat/entrypoints/cli/__init__.py` -- root + `aeat init`.
- `src/aeat/entrypoints/cli/_setup.py` -- `aeat setup` group.
- `src/aeat/entrypoints/cli/_config.py` -- `aeat config` group.
- `src/aeat/entrypoints/cli/_common.py` -- shared helpers
  (`_emit`, `_state`, `_active_profile_or_exit`,
  `_profile_to_autonomo`).
- `src/aeat/entrypoints/cli/_i18n.py` -- re-export of `tr` for CLI.
- `src/aeat/entrypoints/cli/financial/profile.py` -- separate
  ratio-profile editor (parallel pattern, not part of the wizard).
- `src/aeat/locales/{en,es,ca,hu}.yml` -- translation catalogues.
