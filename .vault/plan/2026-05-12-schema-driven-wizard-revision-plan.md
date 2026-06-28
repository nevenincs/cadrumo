---
tags:
  - '#plan'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-reference]]"
  - "[[2026-05-12-schema-driven-wizard-research]]"
  - "[[2026-04-12-setup-wizard-research]]"
---

# schema-driven wizard revision plan

Revision plan landing the fifteen follow-ups surfaced by the code review of
the initial wizard slice. The originating ADR is unchanged; this plan does
not redesign, it closes the partial-implementation, deprecation-shim, and
locale-regression debt the executor deferred.

## Proposed Changes

The first wizard slice landed thirteen commits but the reviewer flagged
that three classes of standing-mandate violations remain on disk:

- Partial-implementation shims in `setup/`, `setup_status.py`, and
  `deadlines/_profiles.py`
- The ADR §D headline (descriptor-driven Typer flag derivation) was not
  implemented; `aeat config setup` hand-codes only two of thirty-nine
  question flags
- A locale regression — every new `cli.config.*` translation key the
  wizard CLI introduced is absent from the four locale catalogues, so
  `aeat config --help` leaks raw translation keys
- Self-inflicted regressions in four downstream CLI test surfaces and one
  project-wide boundary test
- The pre-existing standing-mandate debt on the CLI root (`config` + `app`
  only) was surfaced but not closed

This revision plan turns the reviewer's fifteen-point follow-up list into
ordered single-commit steps. Each step's acceptance gate is the specific
test or assertion the reviewer's report cites; nothing is deferred to a
future slice.

## Tasks

The R-prefixed step numbers belong to this plan and commit messages only;
they never appear in source code.

- R1 — Strip transient-process-state markers from the new test surface
  - Files owned: `src/aeat/entrypoints/cli/test_config_setter.py`
  - Remove the `xfail` block and the `W12` comment at line 6-7 (the
    case-insensitive lookup landed; the test is now a plain pass)
  - Acceptance gates:
    - `pytest src/aeat/entrypoints/cli/test_config_setter.py` green
    - `pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language` green
    - `grep -n 'W[0-9]\|xfail\|previously\|legacy' src/aeat/entrypoints/cli/test_config_setter.py` returns nothing
  - Does NOT: touch any other test file

- R2 — Excise historical phrasing from production source
  - Files owned: `src/aeat/application/wizard/_verifier.py`,
    `src/aeat/application/filing/runtime.py`
  - Rewrite the `_verifier.py:9` docstring to describe the check shape
    structurally, not as a replacement of a "legacy `Verifier`"
  - Drop the "Retained for source-compatibility with the historical
    signature" sentence from `runtime.py:191` (the function will be
    rewritten in R7 anyway, but the docstring update is independent)
  - Acceptance gates:
    - `grep -rn 'legacy\|historical\|previously\|formerly\|replaces' src/aeat/application/wizard/` returns nothing
    - prek + ruff + ty green
  - Does NOT: change behavior

- R3 — Convert raw `assert` to typed guard in the compiler
  - Files owned: `src/aeat/application/wizard/_compiler.py`
  - Replace `assert question.profile_key is not None` at line 74 with an
    explicit `if … is None: raise WizardCompileError(...)` and bind a
    proper error class to the registry. Add an `ERROR_REGISTRY` entry
    if one does not already exist for this failure mode
  - Acceptance gates:
    - `pytest src/aeat/application/wizard/test_compile.py` green
    - `grep -n '^\s*assert ' src/aeat/application/wizard/_compiler.py` returns nothing
  - Does NOT: convert asserts elsewhere

- R4 — Replace the `monkeypatch.setattr(Path.read_text)` purity test with a structural assertion
  - Files owned: `src/aeat/application/wizard/test_compile.py`
  - Rewrite `test_compile_is_pure_no_env_or_file_io` to walk
    `WIZARD_FLOWS` and assert every captured value is a frozen pydantic
    record, a `Translatable` key, or a primitive — no filesystem patch
  - Acceptance gates:
    - `grep -n 'monkeypatch\|MonkeyPatch\|setattr' src/aeat/application/wizard/test_compile.py` returns nothing
    - test still passes
  - Does NOT: rewrite other tests

- R5 — Delete the trivially-OK verifier checks
  - Files owned: `src/aeat/application/wizard/_verifier.py`,
    `src/aeat/application/wizard/test_verifier.py`
  - Delete `_check_residence_ccaa` and `_check_iva_regime`; remove the
    matching assertions in `test_verifier.py`. The descriptor's per-
    widget validators already reject the same inputs at prompt time;
    duplicating them in the verifier yields no signal
  - Acceptance gates:
    - `pytest src/aeat/application/wizard/test_verifier.py` green
    - Verifier still produces structured findings for the cases that
      actually verify something
  - Does NOT: rewrite the verifier orchestration

- R6 — Deduplicate `_normalise_key`
  - Files owned: `src/aeat/application/workflow/_utils.py`,
    `src/aeat/domain/profile/_keys.py`
  - Move `_normalise_key` to `domain/profile/_normalise.py` (or inline
    on `ProfileKey`) and re-export from `application/workflow/_utils.py`
    so there is exactly one definition
  - Acceptance gates:
    - `grep -rn 'def _normalise_key' src/aeat/` returns one hit
    - Existing tests green
  - Does NOT: change normalization semantics

- R7 — Excise the ignored-path-arg deprecation shims
  - Files owned: `src/aeat/application/filing/runtime.py`,
    `src/aeat/entrypoints/cli/deadlines/_helpers.py`, and every caller
  - Remove the `path: Path | None = None` parameter from
    `load_default_filing_profile` and `load_profile` (it is ignored).
    Update every caller and every fixture. The new signature reads
    profile state from `WorkflowState` and takes no `path` argument
  - Acceptance gates:
    - `grep -rn 'del path\b\|Ignored\. Retained' src/aeat/` returns nothing
    - All deadlines and filing CLI tests green (see R12 for the four
      currently-broken ones that this Step's fixture updates will fix)
  - Does NOT: touch the wizard models

- R8 — Implement the ADR §D descriptor-driven Typer flag derivation
  - Files owned: `src/aeat/application/wizard/_commands.py`,
    `src/aeat/entrypoints/cli/_config.py`
  - Make `build_wizard_command(flow)` return a closure whose signature
    composes from `flow`'s questions: TEXT/SECRET/PATH/INTEGER →
    optional `--<question-id>` flag with the matching type;
    CONFIRM → `--<question-id>/--no-<question-id>` boolean pair;
    SELECT → `click.Choice([c.value for c in choices])`; CHECKBOX →
    repeated flag. Plus the three mode flags (`profile_name`, `quiet`,
    `accept_defaults`)
  - Replace the hand-coded `config_setup` body in `_config.py` with
    `for flow in WIZARD_FLOWS: app.command(name=flow.id)(build_wizard_command(flow))`
  - Wire `flag_signature` if it remains useful; delete it if the new
    code path supersedes it
  - Acceptance gates:
    - `inspect.signature(build_wizard_command(SETUP_FLOW))` parameters
      include one per question plus the three mode flags
    - `aeat config setup --help` shows every per-question flag with its
      translated help text
    - `pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/` green
  - Does NOT: change the prompter abstraction

- R9 — Land the `cli.config.*` translation keys and broaden the locale-parity gate
  - Files owned: `src/aeat/locales/{ca,en,es,hu}.yml`,
    `src/aeat/application/wizard/_translations.py` (or wherever the
    audit function lives)
  - Add every `cli.config.*` key the wizard CLI references (full
    inventory listed in the reviewer's follow-up #5; minimum set
    covers `cli.config.setup.*`, `cli.config.status.*`,
    `cli.config.reset.*`, `cli.config.auth.*`, `cli.config.set.*`,
    `cli.config.get.*`, `cli.config.unset.*`, `cli.config.list.*`, and
    `cli.config.errors.*`) in all four locales
  - Broaden the locale-parity audit to walk every translation key
    referenced by `entrypoints/cli/_config.py` (regex over the source
    or a runtime catalogue extraction); fail the test if any key is
    absent from any locale
  - Acceptance gates:
    - `aeat config --help` renders translated text in every locale
    - `pytest src/aeat/application/wizard/test_translations.py` (or
      sibling) green; the audit's scope now includes the CLI surface
  - Does NOT: add wizard-flow keys (those landed in W10)

- R10 — Sweep dead next-action guidance pointing at deleted commands
  - Files owned: `src/aeat/locales/{ca,en,es,hu}.yml`,
    `src/aeat/application/diagnostics.py`,
    `src/aeat/core/errors/registry/` for the suggestion strings that
    parse-as-valid-cli-command checks
  - Replace every `aeat setup init` / `aeat setup ...` next-action
    string with the descriptor-derived `aeat config setup` invocation.
    The error-registry suggestion strings must parse as valid CLI
    commands per the existing boundary test
  - Acceptance gates:
    - `grep -rn 'aeat setup' src/aeat/locales/ src/aeat/application/diagnostics.py src/aeat/core/errors/registry/` returns nothing
    - `pytest src/aeat/entrypoints/cli/test_error_registry_contract.py::test_suggestions_parse_as_valid_cli_commands` green
  - Does NOT: touch `_common.py` (off-limits)

- R11 — Replace `setup_status.py` with the wizard-owned `build_wizard_status`
  - Files owned: `src/aeat/application/setup_status.py` (deletion),
    `src/aeat/application/test_setup_status.py` (deletion if no
    surviving non-redundant assertions; otherwise port to a
    `wizard/test_status.py`),
    `src/aeat/application/diagnostics.py`,
    `src/aeat/application/wizard/_status.py`,
    `src/aeat/application/wizard/test_status.py` (new)
  - Delete `application/setup_status.py`. Rewrite the importer at
    `diagnostics.py:20` to consume `wizard._status.build_wizard_status`.
    Add `wizard/test_status.py` with structural / wiring assertions on
    the report shape (the plan W11 acceptance gate the executor missed)
  - Acceptance gates:
    - No file at `src/aeat/application/setup_status.py`
    - `grep -rn 'build_setup_status\|SetupStatusReport' src/aeat/` returns nothing
    - `pytest src/aeat/application/wizard/test_status.py src/aeat/application/test_diagnostics.py` green
  - Does NOT: change the report's semantic surface (only the home)

- R12 — Excise the legacy autonomo helpers and fix the four wizard-introduced regressions
  - Files owned: `src/aeat/domain/deadlines/_profiles.py`,
    every test fixture that previously seeded an on-disk profile envelope
    for the deadlines + filing CLI commands
  - Delete `_bool_value`, `_iva_regime_value`, `_text_value`,
    `_TRUE_TOKENS`, `_FALSE_TOKENS`, and the alias-fallback chain.
    Rewrite `autonomo_profile_from_mapping` to consume
    `project_answers(SETUP_FLOW, profile_values)` and read
    `AutonomoProfile` fields off the typed projection (or delete the
    helper outright if every caller can route through
    `load_active_autonomo_profile` directly)
  - Update the deadlines list/next/explain CLI test fixtures and the
    `test_build_uses_configured_profile_file` filing test fixture to
    seed `WorkflowState` instead of writing on-disk envelopes
  - Acceptance gates:
    - `grep -n '_bool_value\|_iva_regime_value\|_TRUE_TOKENS\|_FALSE_TOKENS' src/aeat/domain/deadlines/_profiles.py` returns nothing
    - All four previously-regressed CLI tests green
    - `load_active_autonomo_profile` raises `WizardError`-rooted errors
      with registered codes (not raw `ValueError`)
  - Does NOT: touch unrelated profile-mapping consumers outside the
    wizard's typed-bridge surface

- R13 — Relocate the namespace constants and delete `application/setup/`
  - Files owned: `src/aeat/application/setup/` (full deletion),
    `src/aeat/adapters/persistence/storage/_rotation.py`,
    `src/aeat/application/archive/_registry.py`, plus the new home for
    the namespace constants (target: `src/aeat/application/profile/_storage_namespaces.py`)
  - Move `_PROFILE_NAMESPACE`, `_PROFILE_VERSION`, and `_profile_object_key`
    out of `setup/_env_writer.py` into a non-setup home. The HKDF
    context byte string `b"aeat.application.setup.profile.v1"` itself
    is a stable identifier and stays as a literal at the new location;
    only the Python module path moves. Update both consumers
  - Delete `src/aeat/application/setup/` (including `__init__.py` and
    `_env_writer.py`)
  - Acceptance gates:
    - No directory at `src/aeat/application/setup/`
    - `grep -rn 'application.setup' src/aeat/` returns only test
      assertions about its absence (or returns nothing)
    - Persisted-profile crypto round-trip tests green (HKDF context
      byte string unchanged)
  - Does NOT: re-key persisted profiles

- R14 — Fold the CLI root surfaces to `config` + `app` only
  - Files owned: `src/aeat/entrypoints/cli/__init__.py`,
    `src/aeat/entrypoints/cli/_topic.py` (likely deletion),
    `src/aeat/entrypoints/cli/_archive.py` (likely relocation under
    `aeat config archive` or `aeat app archive`)
  - Decide per-command: archive (operator-facing backup/restore) →
    fold into `aeat app archive`; topic (help-text catalogue) → fold
    into `aeat app topic` or delete entirely and replace with
    `aeat --help` topic links. The standing rule requires exactly two
    root groups; the wizard plan acknowledged but did not close the gap
  - Acceptance gates:
    - `aeat --help` lists exactly two subgroups: `config` and `app`
    - `aeat app archive` / `aeat app topic` (or the chosen home) works
    - No stale references to `aeat archive` or `aeat topic` survive
      in locales, diagnostics, or error suggestions
  - Does NOT: redesign archive or topic semantics

- R15 — Final verification sweep
  - Files owned: none (verification only — write a step record under
    `.vault/exec/2026-05-12-schema-driven-wizard/` documenting gate
    results)
  - Run every gate the reviewer cited:
    - `vault check all` shows zero new findings attributed to this
      revision
    - `prek run --all-files` green
    - `pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/` green
    - `aeat --help` shows exactly two subgroups
    - `aeat config --help` renders translated text in every locale
    - `inspect.signature(build_wizard_command(SETUP_FLOW))` matches
      ADR §D
    - `grep -rn 'application.setup\b' src/aeat/` returns nothing
    - `grep -rn 'build_setup_status\|SetupStatusReport' src/aeat/` returns nothing
    - `grep -rn '_bool_value\|_iva_regime_value' src/aeat/domain/deadlines/` returns nothing
  - Acceptance gate: every check above passes
  - Does NOT: introduce new code

## Off-limits worktree state

Concurrent agents are working on the renta-pipeline and restructure
streams. Files staged by those agents (per `git status --short`) must
not be touched by this revision:

- Every file under `.vault/adr/`, `.vault/research/`, `.vault/exec/`
  belonging to the renta-pipeline and CLI-workflow-redesign features
- Every dirty source file already in the worktree before R1 begins
  (rerun `git status --short` at the start of each Step to refresh the
  exclusion list)

The executor must stage every file by explicit path, never recursively
or by glob.

## Commit discipline

- One R-step → one commit (no bundled multi-step commits)
- Commit subject style: imperative, no dates, no R<n> markers in the
  subject line, no phase language. The R<n> identifier may appear in
  the commit body for traceability but never in the subject or in any
  `.py` file
- Never bypass pre-commit hooks. If prek auto-fixes a file the Step
  owns, re-stage and re-commit
- Branch is `chore/eliminate-shims`. Do not switch. Do not push

## Parallelization

No intra-revision parallelism — every Step builds on earlier Steps' file
state or test fixtures. R-step ordering is the hard sequence.

## Verification

Mission success when every gate in R15 passes plus the reviewer's
fifteen-point follow-up list is closed end-to-end. The reviewer's
report is the authoritative checklist; this plan is the work order.

Final outcome: a wizard slice that satisfies every standing project
mandate (no shims, no partial implementations, no transient meta in
source, CLI root is exactly `config` + `app`, every test grounded in
external authority or structural wiring), and the four wizard-introduced
CLI regressions are fixed at their fixture root.
