---
tags:
  - '#plan'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-eliminate-shims-audit]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
  - "[[2026-05-13-testing-framework-tautology-audit]]"
  - "[[2026-05-10-eliminate-user-cli-shim-adr]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-12-schema-driven-wizard-research]]"
  - "[[2026-04-17-pytest-only-testing-research]]"
---

# audits resolution plan

Closure plan landing every HIGH and MEDIUM finding from three audits
landed on 2026-05-13: the eliminate-shims state audit, the schema-
driven wizard UX audit, and the testing-framework tautology audit.

## Proposed Changes

The three audits surfaced a coherent inventory of debt the current
branch carries. Severity-ranked, the actionable set is:

- Pydantic strictness leaks across persisted records and the sede
  cluster
- Two locale-discovery bypass classes (Unicode-stripped regex,
  f-string-built keys) plus one programmatic emission leak
- ~20 monkeypatch real-component patches that violate the no-mocks
  mandate
- One broad `pytest.raises(Exception)` clause
- Two `del path` ignored-parameter shims
- 12 transient-meta phrase violations
- A `__all__` private-name leak and a double-registration
- The wizard's git-bash TTY blocker on Windows
- The empty-profile ValidationError traceback leak from `aeat config
  status`
- Silent NIF acceptance in `--quiet` setup and `config set`
- The `wizard.errors.select_unknown` raw-key leak
- ca/hu locales falling back to English without an honest marker
- A pile of MEDIUM-severity wizard UX polish: flag-truncation,
  silent quiet-mode success, missing next-step hints, no progress
  indicator, misleading Quickstart, engineering jargon in prompts,
  bloated `--version` output

Plan ordering groups by audit origin so the executor can resume
cleanly if context limits hit mid-pass. The branch is
`chore/eliminate-shims`, which carries the theme.

## Tasks

The X-prefixed step numbers (Anumber, Bnumber, etc.) belong to this
plan and commit messages only; they never appear in source code.

### Group A — code audit HIGH/MEDIUM findings

- A1 — Add `strict=True` to four application-layer pydantic records
  - Files owned: `src/aeat/application/auth/_models.py`,
    `src/aeat/application/workflow/_models.py`,
    `src/aeat/application/review/_models.py`,
    `src/aeat/application/profile/_models.py`
  - For each `BaseModel` subclass that crosses the persistence
    boundary (`AuthState`, `WorkflowState`, `LedgerReviewRecord`,
    `ProfileRecord`), set `model_config = ConfigDict(strict=True,
    frozen=True, extra="forbid")`. If existing tests bind on lax
    coercion (e.g., int passed where str expected), update the test
    to use the strictly-typed value
  - Acceptance gates:
    - `pytest src/aeat/application/auth/ src/aeat/application/workflow/ src/aeat/application/review/ src/aeat/application/profile/ -q` green
    - `grep -n 'ConfigDict' src/aeat/application/{auth,workflow,review,profile}/_models.py` shows `strict=True` on every cited record
  - Does NOT: touch unrelated records

- A2 — Tighten `PersistedAuthSession` and `PersistedBrowserSession`
  - Files owned: `src/aeat/application/auth/_sessions.py`
  - Change `extra="ignore"` at line 63 to `extra="forbid"`. Add
    `strict=True` to both records' `ConfigDict`. If a current call
    site passes an unknown field, fix the call site, not the model
  - Acceptance gates:
    - `pytest src/aeat/application/auth/test_sessions.py -q` green
    - `grep -n 'extra="ignore"' src/aeat/application/auth/_sessions.py` returns nothing
  - Does NOT: touch other `extra="ignore"` sites in unrelated modules

- A3 — Fix the sede `_STRICT_FROZEN` alias to actually carry `strict=True`
  - Files owned: `src/aeat/adapters/outbound/aeat/sede/_schema.py`,
    `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
  - The alias's name promised `strict=True`; verify its
    `ConfigDict` value and add `strict=True` if missing. Every
    record using `_STRICT_FROZEN` inherits the fix automatically
  - Acceptance gates:
    - `pytest src/aeat/adapters/outbound/aeat/sede/ -q` green
    - `grep -n 'strict=True' src/aeat/adapters/outbound/aeat/sede/_schema.py` returns at least the alias's line
  - Does NOT: re-export the alias

- A4 — Tighten the `pytest.raises(Exception)` at sql constraints test
  - Files owned: `src/aeat/adapters/persistence/storage/sql/_test_constraints.py`
  - Replace `pytest.raises(Exception)` at line 81 with the specific
    class the constraint violation raises (likely
    `IntegrityError` or a `RepositoryError` subclass). Add
    `match=` so the exact message is asserted
  - Acceptance gates:
    - `pytest src/aeat/adapters/persistence/storage/sql/_test_constraints.py -q` green
    - `grep -n 'pytest.raises(Exception)' src/aeat/adapters/persistence/storage/sql/_test_constraints.py` returns nothing
  - Does NOT: tighten unrelated broad raises

- A5 — Remove the two `del path` ignored-parameter shims
  - Files owned: `src/aeat/domain/usage_ratios/_service.py`,
    `src/aeat/application/filing/_review.py`, plus every caller
  - Remove the `path` argument from the helpers at
    `_service.py:34,84` and `_review.py:448,467`. The argument was
    ignored already; update every caller to drop the now-removed
    positional/keyword
  - Acceptance gates:
    - `grep -rn 'del path\b' src/aeat/` returns nothing
    - All test surfaces touching these helpers green
  - Does NOT: alter the helpers' logic

- A6 — Excise the 12 transient-meta phrase violations
  - Files owned: `src/aeat/domain/calculations/registry/test_text.py`
    (line 14), `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py`
    (line 57), `src/aeat/adapters/inbound/justificante/_extract.py`
    (line 124), `src/aeat/core/observability/_replay.py` (line 28),
    plus every UX-NNN issue-tracker reference and "previously"/"legacy
    flags removed" string the audit cited
  - Rewrite each docstring or comment to describe what the code IS
    structurally, with no process-history / issue-tracker / "what it
    was" framing
  - Acceptance gates:
    - `grep -rn 'historically\|previously\|formerly\|replaces\|legacy\|excised\|rebuild pending\|UX-[0-9]' src/aeat/` returns only legitimate domain references (legal text, registry-citation strings); the executor's commit body lists every site that survived for orchestrator review
    - prek + ruff + ty green
  - Does NOT: touch the legitimate AEAT/BOE legal references the
    audit explicitly allowlisted

- A7 — Fix `__all__` private leak and the double-registration
  - Files owned: `src/aeat/adapters/outbound/llm/_providers/__init__.py`,
    `src/aeat/entrypoints/cli/data/ledgers/inventory.py`
  - Remove `_DeterministicAdapter` and `_ProviderAdapter` from
    `__all__` at `_providers/__init__.py:10`. Diagnose the
    `InventoryValuationJson` double-registration at `inventory.py:103`
    and patch the import side-effect (likely a module imported in
    two paths)
  - Acceptance gates:
    - `python -c "from aeat.adapters.outbound.llm._providers import __all__; assert all(not n.startswith('_') for n in __all__)"`
    - Runtime walk of CLI ledger inventory commands shows
      `InventoryValuationJson` registered exactly once
  - Does NOT: refactor the LLM provider hierarchy

### Group B — UX audit HIGH findings

- B1 — Add NIF format validator to the descriptor's `tax-id` widget
  - Files owned: `src/aeat/application/wizard/_widgets.py`,
    `src/aeat/application/wizard/_catalogue.py`,
    `src/aeat/core/identity/_documents.py` (if a canonical NIF
    validator already exists, surface it; otherwise extend)
  - The `tax-id` TEXT widget gains a regex+checksum validator that
    rejects malformed NIFs. The validator fires on both
    interactive (`--prompt`) and quiet-mode (`--tax-id` flag) and
    on every `config set tax.id <value>` write. Use the existing
    `validate_spanish_tax_id` from `aeat.core.identity` if present
  - Acceptance gates:
    - `aeat config setup --quiet --tax-id INVALID --activity design`
      exits non-zero with a translated Spanish error
    - `aeat config set tax.id NOT_A_NIF` exits non-zero with the
      same envelope
    - `pytest src/aeat/application/wizard/ -q` green
  - Does NOT: extend validation to other identity fields

- B2 — Catch empty-profile in `aeat config status` and post-reset
  - Files owned: `src/aeat/entrypoints/cli/_config.py`,
    `src/aeat/application/wizard/_status.py`,
    locale files for the new key text
  - Detect the `SetupAnswers` ValidationError that fires when
    required answers are missing. Emit a clean translated
    "Sin perfil configurado. Ejecuta `aeat config setup`
    para empezar." in the operator's locale. Same path catches the
    after-state of `aeat config reset --scope PROFILE --yes`
  - Acceptance gates:
    - `aeat config status` against an empty sandbox exits 0 with
      the translated message and zero traceback
    - `aeat config reset --scope PROFILE --yes` followed by
      `aeat config status` reproduces the same clean message
    - `pytest src/aeat/entrypoints/cli/test_config_setter.py src/aeat/application/wizard/test_status.py -q` green
  - Does NOT: change reset semantics

- B3 — Add the `wizard.errors.select_unknown` catalogue entry
  - Files owned: `src/aeat/locales/{ca,en,es,hu}.yml`
  - The descriptor validator emits `wizard.errors.select_unknown`
    as a raw key on SELECT typo. Add a real translated value in
    every locale ("Valor no reconocido para %{question}: %{value}"
    or the equivalent). Confirm via runtime that operators see
    translated text on SELECT validation failure
  - Acceptance gates:
    - `validate_widget_answer(<SELECT question>, 'BOGUS')` raises
      with the translated text, not the raw key
    - All locale catalogues parse cleanly
  - Does NOT: change the validator's emission semantics

- B4 — Widen the locale-discovery regex to Unicode and add AST coverage
  - Files owned: `src/aeat/locales/manager.py` (the codebase-key
    scanner), `src/aeat/application/wizard/_translations.py` (the
    audit broadener)
  - Replace the regex `[a-zA-Z0-9_]+` with `\w+` so non-ASCII
    keys (e.g., `cli.filing.import.año_help`) are discovered.
    Add an AST-based scanner that finds:
    - String constants matching the dot-notation pattern passed
      to classes named `*Error` or `*Exception` with a
      `message_key=` kwarg (catches programmatic emissions like
      `WizardValidationError("wizard.errors.select_unknown")`)
    - f-string nodes whose JoinedStr starts with a literal
      dot-notation prefix — emits a `<prefix>.*` namespace
      finding (catches `cli.registry.metrics.{...}` family)
  - Acceptance gates:
    - `manager.get_codebase_keys()` returns `cli.filing.import.año_help`
    - The AST scanner returns `wizard.errors.select_unknown` and
      `cli.registry.metrics.*` namespace markers
    - The locale parity tests `test_codebase_to_locale_parity`
      and `test_inter_locale_parity` still pass after the
      catalogues are filled in B5
  - Does NOT: implement the locale-management CLI (deferred to a
    separate slice)

- B5 — Fill the discovered missing locale namespaces
  - Files owned: `src/aeat/locales/{ca,en,es,hu}.yml`
  - Add real translated values for `cli.filing.import.año_help`,
    every `cli.registry.metrics.*` key the entrypoint module
    references, and any other key the B4 scanner now discovers.
    Run `manager.scaffold()` once to align the YAML skeleton across
    every locale
  - Acceptance gates:
    - `manager.get_codebase_keys() - get_yaml_keys(locale)` is
      empty for every locale
    - The audit functions return `()`
  - Does NOT: re-translate existing keys

- B6 — Add an honesty assertion for ca/hu fallback values
  - Files owned: `src/aeat/locales/test_parity.py` (or a sibling
    `test_locale_translation_honesty.py`)
  - Implement `test_ca_hu_values_differ_from_en_unless_allowlisted`.
    For every key, the value in `ca` and `hu` must differ from
    the corresponding `en` value, OR appear in an explicit
    allowlist (a sibling YAML / JSON file mapping keys to an
    "intentionally-identical" justification). Walk every key
    where `ca[key] == en[key]` and either translate it or add the
    allowlist entry. For this slice, transfer every offending key
    into the allowlist with a single justification ("untranslated:
    ca/hu coverage pending"); the next slice translates them for
    real
  - Acceptance gates:
    - The new test runs green
    - The allowlist captures the current ca/hu English-equivalent
      values explicitly (no silent acceptance)
  - Does NOT: translate ca/hu content (deferred)

- B7 — Detect git-bash / unsupported Windows console; emit clean fallback
  - Files owned: `src/aeat/application/wizard/_prompter.py`,
    `src/aeat/entrypoints/cli/_config.py`,
    locale files for the new operator-facing message
  - Wrap the `QuestionaryPrompter`'s first prompt invocation in a
    try/except that catches
    `prompt_toolkit.output.win32.NoConsoleScreenBufferError`. On
    catch, surface a translated operator message: "El asistente
    interactivo necesita cmd.exe o Windows Terminal. Usa
    `aeat config setup --quiet --tax-id NIF --activity ACTIVIDAD
    ...` o cambia de terminal." Exit code 78 (the project's
    refused/unsupported-environment code) or similar
  - Acceptance gates:
    - Invoking `aeat config setup` under git-bash on Windows
      surfaces the translated message and exits non-zero without
      a traceback
    - `pytest src/aeat/application/wizard/ -q` green (the
      detection is tested with a forced fake `Output` implementation
      that raises the same exception)
  - Does NOT: implement a pure-Python prompter fallback (a
    larger build, deferred)

### Group C — UX audit MEDIUM findings

- C1 — Group `aeat config setup --help` flags via rich_help_panel
  - Files owned: `src/aeat/application/wizard/_commands.py`
  - When building the closure's signature, assign each Typer
    parameter a `rich_help_panel` matching its `WizardSection`
    title ("Identidad del perfil", "Cónyuge", "IVA",
    "Obligaciones", etc.). This both groups the help output and
    keeps the column wrapping from ellipsising long flag names
  - Acceptance gates:
    - `aeat config setup --help` shows each section as a separate
      panel; long flag names render without ellipsis under an
      80-column terminal
    - `pytest src/aeat/application/wizard/test_wizard_cli.py -q` green
  - Does NOT: change the flag derivation

- C2 — Emit a success message after `--quiet` setup
  - Files owned: `src/aeat/entrypoints/cli/_config.py`,
    locale files
  - On quiet-mode success, print a translated two-line message:
    "Perfil '%{profile_name}' guardado." plus a next-step pointer
    ("Ejecuta `aeat app overview` para revisar tu próxima
    obligación.")
  - Acceptance gates:
    - `aeat config setup --quiet --tax-id 00000000T --activity design`
      emits the translated message on stdout, exit 0
  - Does NOT: change the success path's side effects

- C3 — Add next-step hint to `aeat config status`
  - Files owned: `src/aeat/entrypoints/cli/_config.py`,
    `src/aeat/application/wizard/_status.py`, locale files
  - After the existing TSV output, append a translated single-line
    hint: "Próximo paso: `aeat app overview`" when an active profile
    is present
  - Acceptance gates:
    - `aeat config status` after a successful setup shows the
      hint; empty-profile branch (handled by B2) suppresses it
  - Does NOT: change the TSV format

- C4 — Rewrite the Quickstart line under `aeat --help`
  - Files owned: locale files
  - Replace the current "Quickstart: aeat config setup --profile-name
    NAME --tax-id NIF" with a correct minimal invocation:
    "Quickstart: aeat config setup --tax-id NIF --activity ACTIVIDAD".
    Drop the optional `--profile-name` flag; include the required
    `--activity` flag
  - Acceptance gates:
    - `aeat --help` renders the corrected Quickstart in every
      locale
  - Does NOT: change the root callback's signature

- C5 — Rewrite prompt strings that leak engineering vocabulary
  - Files owned: locale files
  - Three specific edits:
    - "Notas del operador (no consumidas por el motor)" →
      "Notas para tu propio recuerdo (opcional)"
    - "Ejecutar el asistente de configuración basado en esquema de
      forma interactiva o usando banderas" → "Configuración inicial
      guiada del perfil tributario"
    - "Clave de discapacidad del cónyuge" → "Grado de discapacidad
      del cónyuge (si aplica)"
  - Acceptance gates:
    - `aeat config setup --help` and the interactive prompts render
      the rewritten strings
  - Does NOT: touch unrelated locale strings

- C6 — Trim `aeat --version` output
  - Files owned: `src/aeat/entrypoints/cli/__init__.py`
  - Move the registry-summary metadata behind a `--detail` flag.
    Default `aeat --version` emits just "aeat %{version}". With
    `--detail`, emit the existing comprehensive summary
  - Acceptance gates:
    - `aeat --version` emits one line
    - `aeat --version --detail` emits the existing summary
    - `pytest src/aeat/entrypoints/cli/test_cli_surface.py -q` green
  - Does NOT: change the version string itself

- C7 — Add a progress indicator to the interactive wizard
  - Files owned: `src/aeat/application/wizard/_runner.py`
  - Before each section's first question, emit a translated header:
    "Sección %{section_n}/%{section_total}: %{title}". For each
    question within the section, the prompter prepends
    "(pregunta %{q_n}/%{q_total}) " to the prompt text. The
    descriptor knows the counts; the runner threads them
  - Acceptance gates:
    - The pipe-driven interactive transcript shows the new
      section-and-question position markers
    - `pytest src/aeat/application/wizard/test_wizard_runtime.py -q` green
  - Does NOT: redesign the prompter abstraction

### Group D — test hygiene closure

- D1 — Investigate and resolve the 7 derived chain-behaviour asserts
  - Files owned: `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py` (or wherever the seven asserts live per the test-hygiene audit)
  - For each of the seven asserts the static detector could not
    classify, read the surrounding test context, apply the rule's
    "if I changed the formula's declaration to be wrong, would this
    test fail?" predicate, and either:
    - Convert to a structural / graph-wiring assertion (operand
      set, op kind) and route arithmetic verification through the
      live Renta WEB Open replay parity tests
    - Mark the assertion as legitimately resolved-by-binding (the
      bindings are independently verified) with a brief inline
      structural docstring
  - Acceptance gates:
    - Every previously-derived assert now either is structural or
      carries an inline justification of its non-tautological
      grounding
    - `pytest src/aeat/domain/calculations/registry/test_tautology_gate.py -q` green
    - `pytest src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py -q` green
  - Does NOT: touch the escalated tautology candidate in
    `test_ledger_renta_expense_binding.py:105` (concurrent
    renta-pipeline territory)

- D2 — Resolve the three borderline tautological assertions from the code audit
  - Files owned: `src/aeat/domain/invoices/test_iva_classification.py`
    (lines 239-241),
    `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
    (line 256)
  - Apply the same predicate. For each: convert to a
    graph-wiring assertion or move arithmetic verification under a
    live oracle. The
    `test_ledger_renta_expense_binding.py:103-106` instance stays
    flagged for the concurrent workstream
  - Acceptance gates:
    - Each touched test now passes the tautology gate or
      structurally asserts the wiring
    - `pytest src/aeat/domain/invoices/ src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` green
  - Does NOT: cross into ledger-renta-pipeline files

- D3 — Replace the master-key keychain monkeypatch with an injection seam
  - Files owned: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`,
    `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py`
  - The current ~20 `monkeypatch.setattr(keyring, ...)` and
    `monkeypatch.setattr(KeyringMasterKeyProvider, "_probe_backend", ...)`
    calls patch real components. Introduce a `KeyringClient`
    protocol (or equivalent injection seam) and rewrite the tests
    to pass a `_FakeKeyringClient` implementation that is a real
    type, not a mock. The tests verify the protocol's contract,
    not the patched method's identity
  - Acceptance gates:
    - `grep -n 'monkeypatch.setattr' src/aeat/adapters/persistence/storage/master_key/_test_master_key.py` returns nothing
    - `pytest src/aeat/adapters/persistence/storage/master_key/ -q` green
  - Does NOT: change keyring backend behavior in production code

- D4 — Replace the certificate-health monkeypatch with an injection seam
  - Files owned: `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`,
    `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`
  - Same pattern as D3 applied to the
    `monkeypatch.setattr(authenticator_module, 'certificate_health', ...)`
    call at `test_authenticator.py:844`. Introduce a `CertificateHealthCheck`
    protocol and pass a `_FakeCertificateHealth` real-type implementation
  - Acceptance gates:
    - `grep -n 'monkeypatch.setattr' src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` returns nothing
    - `pytest src/aeat/adapters/outbound/aeat/auth/ -q` green
  - Does NOT: change certificate validation in production code

### Group E — final verification

- E1 — Re-run the UX transcripts for the regression scenarios
  - Files owned: none (verification only — write a step record
    under `.vault/exec/2026-05-13-audits-resolution/`)
  - Re-execute the UX transcripts scenarios B1 (empty-profile
    status), D1 (quiet-mode NIF rejection), D3 (post-setup NIF
    rejection), D8d (SELECT validation), F5 (post-reset status),
    and the Quickstart line check. Confirm every previously-broken
    behaviour now renders cleanly in es and en. Note ca/hu state
    against the new honesty allowlist
  - Acceptance gate: every scenario's new transcript matches the
    expected post-fix shape

- E2 — Final repo-wide verification sweep
  - Files owned: none (verification record only)
  - Run:
    - `vault check all` shows zero new findings attributed to
      audits-resolution
    - `prek run --all-files` green
    - `pytest src/aeat/ -q` green for every surface this plan
      touched (concurrent-agent pre-existing failures flagged but
      not fixed)
    - `audit_cli_translations()` and `audit_wizard_translations()`
      both return `()`
    - `manager.get_codebase_keys()` returns the Unicode key
      `cli.filing.import.año_help` plus the
      `cli.registry.metrics.*` family plus
      `wizard.errors.select_unknown`
    - `inspect.signature(build_wizard_command(SETUP_FLOW))`
      still derives 42 parameters per ADR §D
    - `aeat --version` emits one line; `aeat --version --detail`
      emits the existing summary
    - `aeat --help` lists exactly `config` and `app`
  - Acceptance gate: every check above passes

### Group F — type-safety closure (`ty` + suppression strip)

This group was added 2026-05-15 after `uv run ty check src/` was wired
into prek and immediately surfaced a backlog of legitimate type defects
plus a residue of `# type: ignore` suppressions that mask real bugs.
The calculation engines are type-sensitive (Decimal vs. float vs. bool,
binding-source Literals, frozen Pydantic schemas) and every silenced
type error is a latent calculation defect. Closure of this group is
non-negotiable for any merge from this branch.

Concurrent activity caveat: a prior session lost ~4h of work to a
`git reset --hard` race. Every Step in Group F commits the moment its
acceptance gates pass; no Step parks more than one file's worth of
work in the unstaged tree.

- F1 — Close the four `ty` diagnostics in `_binding_prefill.py`
  - Files owned: `src/aeat/application/calculations/_binding_prefill.py`
  - The diagnostics at lines 86, 92, 154, 161 are all
    `invalid-argument-type` against `int.__new__` and `tuple` — values
    typed `object` reaching `int(value)` and `tuple(value)` without
    runtime narrowing. Add `isinstance` guards that raise
    `RegistryValidationError` (or the closest contextual error) on
    unexpected types; do not widen the consumer-side signature.
  - Acceptance gates:
    - `uv run --no-sync ty check src/aeat/application/calculations/_binding_prefill.py 2>&1 | tail -3` shows `All checks passed!`
    - `uv run --no-sync pytest src/aeat/application/calculations/ -q` green
    - `uv run --no-sync ty check src/ 2>&1 | tail -3` reports zero diagnostics
  - Does NOT: refactor the prefill engine or change its public API

- F2 — Finalise the half-implemented features from commit `6b78f880`
  - Files owned:
    - `src/aeat/domain/calculations/registry/_schema.py`
    - `src/aeat/domain/calculations/registry/__init__.py`
    - `src/aeat/domain/calculations/registry/_bindings.py`
    - `registry/aeat/modelos/100/revisions/2025.toml`
  - Three sub-features were partially shipped and crashed mid-session.
    Each must be completed end-to-end:
    1. `DataBindingDefinition.aeat_prefilled: bool = False` field on
       the schema, with `aeat_prefilled = true` declared on the two
       binding rows the borrador-prefilled test pins
       (`renta-2025-profile-tax-residence-ccaa` and
       `renta-2025-modelo-111-retenciones-periodicas`).
    2. Re-export the seventeen `_census_modelos` public names from
       `registry/__init__.py` (`CENSUS_MODELO_*`,
       `CensusModeloFoundation*`, `census_modelo_ownership*`,
       `resolve_census_modelo_*`, etc.). The implementations exist;
       only the package surface gap remains.
    3. Implement the registry-side counterpart binding API in
       `_bindings.py`: `CounterpartAggregationObservation`,
       `CounterpartObservationRequirement`,
       `counterpart_binding_requirements`,
       `resolve_counterpart_binding_values`,
       `resolve_counterpart_binding_row_values`, plus extending
       `DataBindingDefinition.source` Literal with
       `payable_invoice`, `collectible_invoice`, `ledger_transaction`,
       `purchase_invoice_evidence`. Pattern: parallel of the existing
       `InvoiceObservation` / `resolve_invoice_binding_*` machinery.
       The full test contract lives in
       `src/aeat/domain/calculations/registry/test_counterpart_bindings.py`.
  - Acceptance gates:
    - `pytest src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_counterpart_bindings.py -q` green
    - `uv run --no-sync ty check src/aeat/domain/calculations/registry/ 2>&1 | tail -3` zero diagnostics
    - Every name listed above resolves from `aeat.domain.calculations.registry` via `from aeat.domain.calculations.registry import <name>` in a one-shot import smoke test
  - Does NOT: extend the in-flight features beyond the test contract; no new modelos, no new TOML rows beyond the two prefilled markers

- F3 — Strip every `# type: ignore` suppression, fix each underlying issue
  - Files owned: every `.py` under `src/aeat/` carrying a `# type: ignore` comment (current count `91`; reconfirm with `grep -rn "# type: ignore" src/ --include="*.py" | wc -l`)
  - Each suppression must be removed and the underlying type defect resolved per the project's mandate: "Any type checking suppression should be treated as a critical failure in a type-sensitive application like this where calculation engines require very specific input/output types." Permitted patterns for legitimate misuse-tests:
    - `typing.cast(T, value)` only at boundaries where the runtime contract is documented and the cast is provably safe.
    - `Model.model_validate({...})` for tests that intentionally pass forbidden inputs through Pydantic runtime validation.
    - `setattr(obj, "field", value)  # noqa: B010` for tests that verify frozen-Pydantic rejection (B010 is a ruff style rule, not a type-checker suppression).
  - Acceptance gates:
    - `grep -rn "# type: ignore" src/ --include="*.py" | wc -l` returns `0`
    - `uv run --no-sync ty check src/ 2>&1 | tail -3` shows `All checks passed!`
    - `pytest src/aeat/ -q` green for every test surface a suppression was removed from
  - Does NOT: introduce new `# pyright: ignore`, `# pylint: disable`, or other type-checker bypasses

- F4 — Final type-safety verification + prek closure
  - Files owned: none (verification record only)
  - Run:
    - `uv run --no-sync ty check src/` — `All checks passed!`
    - `grep -rn "# type: ignore\|# pyright: ignore" src/ --include="*.py" | wc -l` returns `0`
    - `uv run --no-sync prek run --all-files` green
    - `pytest src/aeat/ -q` overall green (concurrent-agent pre-existing failures flagged but not fixed)
  - Acceptance gate: every check above passes; record the closure in `.vault/exec/2026-05-13-audits-resolution/`

### Group G — ruff lint backlog closure (restore prek gate)

Group F left `prek run --all-files` failing on ~85 pre-existing
ruff diagnostics. Until they close, every commit needs
`--no-verify`, which defeats the gate's purpose. Group G closes
the lint backlog by partitioning the diagnostics into two
buckets: structural patterns that warrant per-file-ignore
declarations (false positives, idiomatic deferred imports, test-
fixture synthetic secrets) and legitimate defects that need
real fixes.

Baseline at amendment time: 85 diagnostics under
`uv run --no-sync ruff check src/`. Breakdown:

- E402 (26): module-level imports placed mid-file as
  circular-import workarounds inside package `__init__.py`s and
  the registry error-registry merge points.
- S603 (11): subprocess-without-shell-equals-true on legitimate
  AEAT-CLI / subprocess invocations.
- S105 (8): hardcoded-password-string on env-var NAME literals.
- S108 (8): hardcoded-temp-file inside test fixtures.
- SIM115 (6): open-file-with-context-handler real defects.
- N811 (5): constant-imported-as-non-constant alias renames.
- RUF001 / RUF003 (5): ambiguous-unicode in Spanish content.
- N806 / N801 / N814 / N818 (7): naming convention strays.
- RUF043 (3): pytest.raises without a `match=`.
- E501 (2): line-too-long.
- SIM117 (1): nested-with-statements.
- S106 (2): hardcoded-password-func-arg in test fixtures.
- S311 (1): non-cryptographic-random in PDF scrubbing.

- G1 — Codify per-file-ignores for the structural / domain-
  justified buckets in `pyproject.toml`
  - Files owned: `pyproject.toml`
  - For each of the following clusters, add a `[tool.ruff.lint.per-file-ignores]`
    entry that excludes the rule against the precise file pattern.
    Do NOT add a project-wide `ignore` entry unless the rule is
    universally inappropriate.
    - `E402` on `src/aeat/application/auth/__init__.py`,
      `src/aeat/application/workflow/_models.py`,
      `src/aeat/core/errors/__init__.py`,
      `src/aeat/core/errors/_registry.py`,
      `src/aeat/entrypoints/cli/__init__.py`,
      `src/aeat/entrypoints/cli/_config/__init__.py`,
      `src/aeat/domain/calculations/registry/_bindings.py`,
      `src/aeat/domain/currency/test_service.py`,
      `src/aeat/adapters/outbound/aeat/sede/test_groi_check.py` —
      the deferred-import positions are deliberate; document via
      the per-file-ignore comment.
    - `S603` / `S105` / `S106` / `S108` test-fixture clusters —
      extend existing patterns under `[tool.ruff.lint.per-file-ignores]`
      to cover any new files surfaced post-restructure.
    - `RUF001` / `RUF003` on locale source files
      (`src/aeat/locales/*.yml`-driven Python carrying Spanish
      strings) and on legal-text label parsing in
      `src/aeat/adapters/inbound/pdf/_label_regex.py` — these are
      Spanish-language string-content patterns, not bugs.
    - `S311` on `src/aeat/adapters/inbound/pdf/_scrub.py` —
      synthetic-replacement random is non-cryptographic by
      design (scrubber is local-only, never used for keying).
  - Acceptance gates:
    - `uv run --no-sync ruff check src/ 2>&1 | grep -E "^E402|^S603|^S10[568]|^S311|^RUF00[13]"` returns nothing
    - `uv run --no-sync ty check src/ 2>&1 | tail -3` still clean
  - Does NOT: add a project-wide `ignore` entry; relax any
    boundary-crossing security check

- G2 — Mechanically fix the legitimate-defect bucket
  - Files owned: every file flagged by SIM115, SIM117, RUF043,
    N801, N806, N811, N814, N818, E501
  - For each rule:
    - `SIM115` → wrap `open(...)` calls in `with open(...) as f:`
    - `SIM117` → collapse nested `with` into a single multi-context `with`
    - `RUF043` → add a `match=` regex to `pytest.raises(...)`
    - `N81x` / `N806` → rename aliases to match the constant /
      function-naming convention; if the alias is a domain pattern
      (e.g. `Translatable as tr`) use the existing project-wide
      ignore in `pyproject.toml`
    - `E501` → run `ruff format` on the offending file
  - Acceptance gates:
    - `uv run --no-sync ruff check src/ 2>&1 | tail -3` shows zero diagnostics
    - `uv run --no-sync ty check src/ 2>&1 | tail -3` still clean
    - `pytest src/aeat/ -q --collect-only 2>&1 | tail -3` collects without import errors
  - Does NOT: introduce new `# noqa: <rule>` comments; per-line
    noqa is only acceptable when documented in a 2-line code
    comment explaining the domain reason

- G3 — Restore prek gate; confirm green commit possible
  - Files owned: none (verification only)
  - Run:
    - `uv run --no-sync ruff check src/` — zero diagnostics
    - `uv run --no-sync prek run --all-files` — every hook passes
    - A trivial test commit (touch a comment, commit, revert) lands
      without `--no-verify`
  - Acceptance gate: prek gate green; document closure in
    `.vault/exec/2026-05-13-audits-resolution/`

## Off-limits worktree state

Concurrent agents are working on the renta-pipeline and CLI-
workflow-redesign streams plus an active error-registry hardening
stream. Files staged by those agents must not be touched. Re-run
`git status --short` at the start of each Step.

Specifically off-limits:
- The `test_ledger_renta_expense_binding.py:103-106` tautology
  candidate (concurrent ledger-renta-pipeline territory)
- Every dirty file under `.vault/adr/`, `.vault/exec/`, `.vault/research/`
  outside the audits-resolution feature
- Every source file already dirty in the worktree before A1 begins

The executor must stage every file by explicit path, never
recursively or by glob.

## Commit discipline

- One step → one commit (no bundled multi-step commits)
- Commit subject: imperative, no dates, no step IDs in the subject.
  The step ID (`A1` / `B4` / etc.) may appear in the commit body
  for traceability but never in `.py` files
- Never bypass pre-commit hooks. If prek auto-fixes a file the Step
  owns, re-stage and re-commit
- Branch is `chore/eliminate-shims`. Do not switch. Do not push

## Parallelization

No intra-resolution parallelism — B5 depends on B4 (the regex
broadening must land before the missing-keys can be discovered);
B6 depends on B5 (the allowlist captures values that exist post-fill);
C-group depends on existing wizard/locale infrastructure; D-group
depends on the audit's classification. Sequential.

## Verification

Mission success when every gate in E1 + E2 passes plus every
HIGH/MEDIUM finding from the three audits is closed end-to-end.
LOW findings (the `__all__` private leak, the double-registration,
the four LOW UX wizard polish items) are folded into the relevant
groups above where adjacent; pure-LOW items deferred to a sibling
slice are explicitly enumerated in the closure verification record.

Final outcome: the branch passes a third-loop review with zero
HIGH or MEDIUM findings surviving. The CI tautology gate landed
in commit `f98ae451` continues to enforce that no new tautological
calculation tests can re-introduce the antipattern.
