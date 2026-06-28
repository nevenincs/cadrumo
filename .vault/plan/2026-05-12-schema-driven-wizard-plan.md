---
tags:
  - '#plan'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-adr]]"
  - "[[2026-05-12-schema-driven-wizard-reference]]"
  - "[[2026-05-12-schema-driven-wizard-research]]"
---



# `schema-driven-wizard` plan

This plan sequences the implementation of the `accepted — execution-ready`
schema-driven wizard ADR into auditable, single-commit slices. The ADR and the
reference audit are the authoritative inputs; this document does not redesign
any of those decisions, it only orders the work and pins the per-slice gates.

## Proposed Changes

The change lands one new application subpackage at `src/aeat/application/wizard/`
that carries the descriptor models, the prompter abstraction, the
`compile_profile_keys` derivation, the runtime, the verifier, the CLI command
factory, and the seed `WIZARD_FLOWS` catalogue. The existing
`src/aeat/application/setup/` subpackage is deleted outright (no shims, no
parallel modules), the `aeat init` root command is deleted, the `aeat setup`
command group is deleted, and `aeat config` becomes the single operator-facing
on-ramp (`config setup`, `config set`, `config get`, `config unset`,
`config list`, `config status`, `config reset`, `config auth`). Locale
catalogues lose every `setup.wizard.*`, `cli.setup.*`, `cli.init.*` key and
gain a `wizard.*` namespace that resolves in all four locales. The legacy
`PROFILE_KEYS` tuple flips from being hand-authored to being the import-time
output of `compile_profile_keys(WIZARD_FLOWS)`. The hand-rolled
`_bool_value` / `_iva_regime_value` helpers in `deadlines/_profiles.py`
collapse into `project_answers(flow, values)`. The asymmetric
`_normalise_key` gap is closed by a `ProfileKey.from_key(raw)` chokepoint.
`tax_residence_ccaa` becomes a descriptor-bound profile key for the first
time. The two never-prompted `SetupAnswers` fields become descriptor
questions in the setup flow.

The plan executes on the `chore/eliminate-shims` branch. Frequent commits
land directly on the branch; no PR is opened; no intermediate review is
requested by the executor. The plan is sliced so every commit is
independently auditable, prek-clean, and reversible.

## Standing mandates honoured

- No backwards compat, no deprecation, no partial implementations. Removed
  modules go in the same commit that replaces them.
- No transient meta / process state in source code. Docstrings describe what
  the code IS, never dates, vault paths, "previously hand-rolled",
  "phase 2 deferred", or historical commits.
- No wave / phase numbering in source code or docstrings. The Step W1..Wn
  identifiers in this plan and in the matching commit subjects are
  plan-and-commit-message-only; they never appear in code.
- CLI root is exactly `config` + `app`. The plan introduces no third root;
  every operator surface that survives lives under `aeat config`.
- Pydantic v2 strict + frozen + extra="forbid" applies to every descriptor
  and answer model.
- No tautological calculation tests. Every wizard test asserts external
  authority (`questionary` call shape, descriptor-to-`ProfileKey` snapshot
  via the compile function, scripted-prompter round-trip) or structural
  wiring; no test re-implements a widget validator or the derivation.

## Off-limits worktree state

The `chore/eliminate-shims` branch carries concurrent agent work on two
unrelated surfaces. The wizard plan MUST NOT stage or touch any of the
following files during its commits:

- Every `.vault/` document already shown as modified or untracked in
  `git status` that is not the wizard plan itself or the wizard exec
  records this plan generates.
- `src/aeat/application/aggregation/_renta_ledger.py` and its sibling
  `test_renta_ledger.py` (renta-pipeline agent).
- `src/aeat/application/filing/test_complementaria.py`,
  `test_import.py`, `test_modelo_303_390.py` (renta-pipeline agent dirty
  state).
- `src/aeat/entrypoints/cli/_common.py`,
  `src/aeat/entrypoints/cli/test_user_cli_surface.py` (restructure agent
  dirty state).
- `src/aeat/entrypoints/cli/test_error_boundary_integration.py`
  (untracked, restructure agent).
- `src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py`
  (untracked, renta-pipeline agent).

The executor stages files explicitly by path on every commit
(`git add <path1> <path2> ...`); never `git add -A` or `git add .`.

## Tasks

The implementation is one phase split into thirteen ordered Steps. Each Step
is one commit. Every Step declares the files it owns, the acceptance gates
that must hold when it is staged, and the things it explicitly defers to
later Steps.

- `Phase 1 — schema-driven wizard landing`
  1. `W1` — Add `questionary` dependency and smoke-import test.
  1. `W2` — Land descriptor models (`WizardFlow`, `WizardSection`,
     `WizardQuestion`, `WizardChoice`, `WizardCondition`).
  1. `W3` — Land `WizardWidget` enum and per-widget validators.
  1. `W4` — Land `Prompter` Protocol and `ScriptedPrompter`.
  1. `W5` — Land `QuestionaryPrompter` plus headless integration smoke
     test.
  1. `W6` — Land `compile_profile_keys(flows)` derivation.
  1. `W7` — Land `WIZARD_FLOWS` catalogue and rewire `PROFILE_KEYS` to
     the compiled output.
  1. `W8` — Land `_runner.py`, `_verifier.py`, and `build_wizard_command(flow)`.
  1. `W9` — Wire generated typer commands into `aeat config` and route
     `aeat config set` through the descriptor's per-widget validator.
  1. `W10` — Land `wizard.*` translation keys in `en` / `es` / `ca` / `hu`
     and add the locale-parity gate test.
  1. `W11` — Delete the dead `setup` subpackage, the `aeat init` root
     command, the `aeat setup` command group, and every `setup.wizard.*` /
     `cli.setup.*` / `cli.init.*` locale key.
  1. `W12` — Reconcile `WorkflowState.profiles` typing,
     `ProfileRecord.values` typed projection, and the `_normalise_key`
     asymmetry via `ProfileKey.from_key(raw)`.
  1. `W13` — Run the full verification gate suite.

### Step W1 — add `questionary` dependency

- Files owned:
  - `pyproject.toml` — add `"questionary>=2.1.1"` to the `dependencies` table.
  - `uv.lock` — regenerated by `uv lock`.
  - `src/aeat/application/wizard/__init__.py` — new file, empty module
    docstring only (description of what the subpackage IS, no dates or
    history).
  - `src/aeat/application/wizard/test_dependency_import.py` — new file,
    one test asserting `import questionary` succeeds and the installed
    version satisfies `>= 2.1.1`.

- Acceptance gates:
  - `uv lock` succeeds.
  - `uv sync` succeeds.
  - `uv run pytest src/aeat/application/wizard/test_dependency_import.py`
    passes.
  - `uv run prek run --files pyproject.toml uv.lock src/aeat/application/wizard/__init__.py src/aeat/application/wizard/test_dependency_import.py`
    passes (ruff check, ruff format, ty type check).

- Does NOT:
  - introduce any descriptor model code.
  - touch `questionary` import sites yet (the prompter lands in W5).
  - modify any CLI entrypoint.

### Step W2 — descriptor models

- Files owned:
  - `src/aeat/application/wizard/_models.py` — new file. Declares the five
    pydantic v2 strict + frozen + extra="forbid" models exactly as the ADR
    section A skeletons specify: `WizardFlow`, `WizardSection`,
    `WizardQuestion`, `WizardChoice`, `WizardCondition`. The `WizardWidget`
    StrEnum is imported from `_widgets.py` (forward-declared as
    `from ._widgets import WizardWidget`); the import site is added in W3
    but the type stub for `WizardQuestion.widget: WizardWidget` is
    annotated against the eventual import. To avoid a load-order
    circular dep, `WizardWidget` is declared in this same `_models.py`
    file and `_widgets.py` (added in W3) imports it back. The ADR's
    canonical class skeletons are copied verbatim.
  - `src/aeat/application/wizard/test_models.py` — new file. Structural
    assertions only: every model is `frozen=True`, `extra="forbid"`,
    `strict=True`; constructing a `WizardFlow` with a non-tuple
    `sections=` raises; constructing a `WizardSection` with an empty
    `questions` tuple raises; constructing a `WizardCondition` with
    `equals=` non-string raises. No assertions that re-implement the
    pydantic primitive layer.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_models.py` is green.
  - The five model class names are importable from
    `aeat.application.wizard._models`.
  - `WizardQuestion.answer_type` annotation accepts exactly
    `type[str | bool | int | Path]`; constructing with any other type
    raises at validation time.
  - `WizardQuestion.profile_key` accepts `None` (transient questions are
    legal at the schema level).
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - introduce widget enum dispatch or per-widget validators (W3).
  - introduce the `Translatable`-prefix validator that ties prompt keys
    to `wizard.<flow-id>.` (deferred to W7 when the catalogue lands and
    the prefix is enforced as the flow is constructed; the model layer
    accepts any `Translatable`).
  - introduce a `Prompter` protocol (W4).

### Step W3 — widget enum and per-widget validators

- Files owned:
  - `src/aeat/application/wizard/_widgets.py` — new file. Declares (a)
    the `WizardWidget` `StrEnum` re-export from `_models.py` (so external
    callers import the symbol from `_widgets`), (b) seven pure validator
    functions: `validate_text(raw: str, question: WizardQuestion) -> str`,
    `validate_secret(...)`, `validate_confirm(...)` (canonical-token
    parser for `"true"`/`"false"`), `validate_select(...)` (membership
    against `question.choices`), `validate_checkbox(...)` (membership for
    each token in a comma-separated list), `validate_path(...)`
    (existence check when the descriptor flags it), `validate_integer(...)`
    (raises on non-integer), (c) a single dispatch function
    `validate_widget_answer(question, raw)` that selects the validator
    by `question.widget`.
  - `src/aeat/application/wizard/test_widgets.py` — new file. Tests
    feed both valid and invalid canonical tokens through
    `validate_widget_answer` and assert the validation outcome (pass for
    valid, raise for invalid). Tests do not re-implement the validator's
    decision rules; they assert the contract via observable behaviour.
    For `validate_select` the test constructs a `WizardQuestion` with a
    closed set of `WizardChoice` tokens and verifies that an out-of-set
    token raises and an in-set token passes.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_widgets.py` is green.
  - `validate_widget_answer` raises a translated error for every invalid
    canonical token; the error references the question's prompt key, not
    raw English.
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - dispatch to questionary (W5).
  - touch CLI flag derivation (W8).
  - persist anything (W8 / W12).

### Step W4 — `Prompter` protocol and `ScriptedPrompter`

- Files owned:
  - `src/aeat/application/wizard/_prompter.py` — new file. Declares the
    `Prompter` Protocol with one method
    `ask(self, question: WizardQuestion, *, default: str | None) -> str`,
    plus the `ScriptedPrompter` test-only implementation. The
    `ScriptedPrompter` accepts a `deque[str]` of canonical-token answers,
    pops the leftmost on every call, and raises `WizardScriptUnderflowError`
    on empty deque. A companion `WizardScriptOverflowError` is raised by
    a `close()` method the runtime calls at flow end (asserts all
    scripted answers consumed).
  - `src/aeat/application/wizard/_errors.py` — new file. Declares the
    error hierarchy: `WizardError` (base), `WizardScriptUnderflowError`,
    `WizardScriptOverflowError`, `WizardValidationError`,
    `WizardMissingFlagError`. The folded contents of the deleted
    `setup/_errors.py` are inlined here (only the error classes that
    survive in the new shape; legacy errors that no longer apply do
    not get a replacement).
  - `src/aeat/application/wizard/test_prompter.py` — new file. Asserts:
    - `ScriptedPrompter` pops in FIFO order;
    - underflow raises `WizardScriptUnderflowError`;
    - `close()` raises `WizardScriptOverflowError` when the deque is
      non-empty.
    - calling `ask` on a `Prompter` that does not implement the protocol
      surface fails at type-check time (verified via a `ty` annotation
      run rather than runtime).

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_prompter.py` is green.
  - `uv run prek run --files <touched paths>` passes including `ty`
    type-check.

- Does NOT:
  - implement `QuestionaryPrompter` (W5).
  - declare the runtime that consumes the prompter (W8).

### Step W5 — `QuestionaryPrompter` plus headless integration smoke

- Files owned:
  - `src/aeat/application/wizard/_prompter.py` — modified. Adds
    `QuestionaryPrompter` which dispatches `question.widget` onto the
    matching `questionary` primitive
    (`questionary.text`, `.password`, `.confirm`, `.select`, `.checkbox`,
    `.path`, plus a `.text` with a numeric validator for `INTEGER`).
    The class accepts an optional `input` parameter to support the
    `create_pipe_input` test path.
  - `src/aeat/application/wizard/test_questionary_smoke.py` — new file.
    One integration test per widget kind that uses
    `prompt_toolkit.input.create_pipe_input` plus
    `prompt_toolkit.output.DummyOutput` to drive a real
    `QuestionaryPrompter.ask()` call and asserts the returned
    canonical-token answer matches the piped input. Per ADR I, this is
    the single TTY-emulation smoke; per-flow integration coverage
    follows in W7.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_questionary_smoke.py`
    is green.
  - `QuestionaryPrompter.ask` never returns a Python value not
    expressible as a canonical token (str / `"true"` / `"false"` / int
    string / path string).
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - touch any flow's catalogue entry (W7).
  - register any typer command (W9).

### Step W6 — `compile_profile_keys(flows)` derivation

- Files owned:
  - `src/aeat/application/wizard/_compiler.py` — new file. Implements
    the pure function
    `compile_profile_keys(flows: Sequence[WizardFlow]) -> tuple[ProfileKey, ...]`
    exactly as ADR section B specifies:
    - one `ProfileKey` per distinct `WizardQuestion.profile_key`;
    - `None`-bound questions skipped;
    - `requirement = REQUIRED` when `required is True and visible_when is None`,
      else `OPTIONAL`;
    - `required_when_key` / `required_when_value` derived from
      `visible_when` when the parent question is itself profile-bound;
    - `description = Translatable("profile.keys.<key>")`;
    - duplicate `profile_key` bindings raise `WizardCompileError`.
  - `src/aeat/application/wizard/test_compile.py` — new file. Structural
    assertions:
    - every `WizardQuestion` with a non-None `profile_key` in a tiny
      fixture catalogue produces exactly one `ProfileKey` entry;
    - duplicate `profile_key` across two flows raises
      `WizardCompileError`;
    - `required_when_key` and `required_when_value` resolve when the
      `visible_when` references a profile-bound parent;
    - `visible_when` pointing at a transient (`profile_key=None`)
      parent yields a `ProfileKey` with both `required_when_*` left
      `None` (the parent does not surface in the legacy registry);
    - the function is import-time pure (no file I/O, no env lookups);
      asserted by patching `os.environ` to empty and `pathlib.Path.read_text`
      to raise, then invoking the compiler.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_compile.py` is green.
  - The function is callable with a tuple literal at module import time
    without side effects.
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - mutate `aeat.domain.profile._keys` yet (W7).
  - assume any specific flow shape (the test uses a tiny synthetic
    fixture, not `WIZARD_FLOWS`).

### Step W7 — `WIZARD_FLOWS` catalogue and `PROFILE_KEYS` rewire

- Files owned:
  - `src/aeat/application/wizard/_catalogue.py` — new file. Exports
    `WIZARD_FLOWS: tuple[WizardFlow, ...]` containing exactly one
    `setup` flow whose questions cover:
    - every current `PROFILE_KEYS` entry from `domain/profile/_keys.py`
      (35 entries: `tax.id`, `name`, `surnames`, `activity`,
      `address.postcode`, `declaration.type`, `taxpayer.*`,
      `spouse.*`, `family.*`, `iva.*`, `enrollment.*`, `has_employees`,
      the eight retencion/objective/intracomunitario/threshold booleans,
      `notes`);
    - the two never-prompted booleans `pays_capital_income_with_retencion`
      and `uses_objective_estimation_irpf` (gap from ADR section G);
    - `tax.residence.ccaa` bound via a `SELECT` widget with choices
      projected from `domain.profile.CCAA` (the ADR's `tax_residence_ccaa`
      lift);
    - `iva.regime` is `SELECT` with choices `{general, simplificado,
      recargo-equivalencia, exento}` (closes the legacy "stores arbitrary
      string" gap);
    - the conditional `spouse.*` / `family.*` requirements are encoded
      via `WizardCondition(question_id="declaration-type", equals="2")`
      and `WizardCondition(question_id="spouse-eu-eea-resident", equals="true")`
      mirroring the existing `required_when_key` / `required_when_value`
      pairs.
    The catalogue construction enforces the `wizard.setup.<section-id>.<question-id>.prompt`
    prefix for every `Translatable` value via a model_validator on
    `WizardQuestion` added in this Step (the validator was deferred from
    W2 to here).
  - `src/aeat/application/wizard/_models.py` — modified. The
    `Translatable`-prefix model_validator is added now that the
    convention is anchored by a real catalogue.
  - `src/aeat/application/wizard/_setup_answers.py` — new file. The
    per-flow typed `SetupAnswers` pydantic v2 model that the
    `setup` flow's `answers_model` references. Cross-field invariants
    live here as `model_validator`s (spouse fields required when
    declaration type is joint, EU/EEA country required when spouse is
    EU/EEA resident).
  - `src/aeat/domain/profile/_keys.py` — modified. The hand-authored
    `PROFILE_KEYS` tuple is replaced by an import-time call
    `PROFILE_KEYS = compile_profile_keys(WIZARD_FLOWS)`. The
    `ProfileKey` class itself stays in place. `get_profile_key`,
    `required_profile_keys`, `optional_profile_keys` continue to work
    unchanged because they read off `PROFILE_KEYS`.
  - `src/aeat/application/wizard/test_setup_compiles.py` — new file.
    Structural / wiring assertions on the `setup` flow per ADR I:
    - every question id is unique inside the flow;
    - every `WizardCondition.question_id` resolves to an earlier
      question in the same flow;
    - every `Translatable` resolves in every locale (the locale parity
      gate is exercised here in addition to W10's translation-test);
    - every `profile_key` (when set) appears in the compiled
      `PROFILE_KEYS`;
    - every `WizardChoice` value passes
      `validate_widget_answer(question, choice.value)`.

- Acceptance gates:
  - `from aeat.domain.profile import PROFILE_KEYS` succeeds; the result
    is a non-empty tuple; its length is `>=` the previous hand-authored
    tuple's length (37 = 35 prior entries + 2 newly-prompted booleans +
    `tax.residence.ccaa` minus any prior key that the descriptor split
    differently); the executor verifies the exact count against the
    catalogue.
  - `uv run pytest src/aeat/application/wizard/test_setup_compiles.py`
    is green.
  - `uv run pytest src/aeat/domain/profile/` is green (existing tests
    against `PROFILE_KEYS` still pass — `tax.id` / `activity` are still
    REQUIRED, conditional `spouse.*` requirements still cascade).
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - register any typer command (W9).
  - delete the dead `setup` subpackage yet (W11).
  - migrate the locales (W10).

### Step W8 — runtime, verifier, and `build_wizard_command(flow)`

- Files owned:
  - `src/aeat/application/wizard/_runner.py` — new file. Declares
    `run_flow(flow: WizardFlow, prompter: Prompter, *, defaults: Mapping[str, str] | None) -> BaseModel`
    which iterates the flow's sections, evaluates `visible_when` against
    the answer collected so far, calls
    `prompter.ask(question, default=...)`, runs
    `validate_widget_answer(question, raw)`, builds the canonical-token
    dict, parses each value into its `answer_type`, and returns
    `flow.answers_model.model_validate(dict)`. Calls `prompter.close()`
    at the end if the prompter exposes one.
  - `src/aeat/application/wizard/_persistence.py` — new file. Declares
    `persist_answers(flow, answers, *, state, profile_name) -> WorkflowState`
    and `project_answers(flow, values) -> BaseModel` exactly as ADR
    section G specifies. The bool / int / Path / str canonical-token
    serialiser lives here and is the only place the conversion exists.
    `persist_answers` also invokes the side-effect
    `adapters.persistence.profile.save_tax_residence` when the flow
    writes a `tax.residence.ccaa` answer.
  - `src/aeat/application/wizard/_verifier.py` — new file. The
    seven legacy verifier checks from the dead `setup/_verifier.py`
    refactored into per-flow `WizardCheck` records that run after
    `persist_answers` succeeds. Severity enum becomes
    `WizardCheckSeverity` and finding record becomes `WizardCheckFinding`
    per ADR section H.
  - `src/aeat/application/wizard/_commands.py` — new file. Declares
    `build_wizard_command(flow: WizardFlow) -> Callable[..., None]`
    exactly as ADR section D specifies. The returned closure has a
    signature composed from the flow's questions plus the fixed
    `--quiet` / `--profile-name` / `--accept-defaults` mode flags;
    when `--quiet` is set, the closure raises
    `WizardMissingFlagError` (translated via
    `wizard.setup.errors.missing_required_flags`) if any
    required-and-not-conditional question lacks a flag value or
    descriptor default.
  - `src/aeat/application/wizard/test_setup_runtime.py` — new file.
    Per ADR I `test_<flow-id>_runtime.py`:
    - feed a canonical-token answer set through `ScriptedPrompter`;
    - assert the runtime calls `ask` in the expected sequence
      (recording prompter calls in a witness list);
    - assert conditional branches skip the right questions (e.g.
      `spouse.*` skipped when `declaration.type` is not `"2"`);
    - assert the resulting `answers_model` validates;
    - assert `persist_answers` writes a canonical-token dict
      that `project_answers` round-trips back to the same typed
      model.
  - `src/aeat/application/wizard/test_verifier.py` — new file.
    Asserts each of the seven `WizardCheck` records produces an
    expected severity for a given `project_answers` result. Only
    severity + finding-name structure is asserted; no reproduction
    of the check's decision rule.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_setup_runtime.py`
    is green.
  - `uv run pytest src/aeat/application/wizard/test_verifier.py` is
    green.
  - `build_wizard_command(WIZARD_FLOWS[0])` returns a callable whose
    signature includes one Typer parameter per question plus the three
    mode flags.
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - register the closure against any typer app (W9).
  - delete any legacy CLI surface (W11).

### Step W9 — wire the typer commands into `aeat config`

- Files owned:
  - `src/aeat/entrypoints/cli/_config.py` — modified. (a) Adds a
    module-import-time loop that walks `WIZARD_FLOWS` and registers
    `app.command(name=flow.id)(build_wizard_command(flow))` against the
    existing `aeat config` Typer sub-app; (b) rewrites the existing
    `aeat config set <key> <value>` body to look up the
    `WizardQuestion` whose `profile_key == key`, call
    `validate_widget_answer(question, raw)`, and then persist via
    `set_profile_values` — so `aeat config set iva.regime XYZ` is
    rejected at the CLI boundary; (c) renames the existing
    `aeat setup reset` to `aeat config reset` and the existing
    `aeat setup auth configure` to `aeat config auth` per ADR section
    E; (d) folds `aeat setup status` to `aeat config status` and
    rewrites the status body to read `project_answers(setup_flow, profile_values)`
    instead of the raw `dict[str, str]`.
  - `src/aeat/entrypoints/cli/_setup.py` — modified. The `aeat setup`
    sub-app and every command body remaining in it
    (`setup_init`, `setup_profile_set`, `setup_profile_unset`,
    `setup_auth_configure`, `setup_reset`, the setup status body) is
    moved out: every surface that survives moves to `_config.py`, the
    rest is deleted (full module deletion happens in W11; this Step
    only relocates the survivors).
  - `src/aeat/entrypoints/cli/_common.py` — left untouched in this
    Step (it is in the concurrent-restructure agent's dirty surface;
    if `_config.py` newly needs a helper that lives there, the helper
    is duplicated locally inside `_config.py` and deduplicated by the
    restructure agent later).
  - `src/aeat/entrypoints/cli/test_config_setter.py` — new file. Per
    ADR I `test_<flow-id>_cli.py`:
    - build the `setup` command via `build_wizard_command`;
    - invoke through Typer's `CliRunner` with `--quiet` + flag values;
    - assert exit code zero;
    - assert the `WorkflowState` mutation matches the scripted-runtime
      result;
    - invoke `aeat config set iva.regime XYZ` and assert non-zero exit
      plus a translated error referencing the valid choices.
    - invoke `aeat config set TAX.ID 12345678Z` and
      `aeat config set tax.id 12345678Z`; assert both succeed and
      produce the same `ProfileRecord` state (the case-insensitivity
      gate is asserted here; the implementation lands in W12).

- Acceptance gates:
  - `uv run pytest src/aeat/entrypoints/cli/test_config_setter.py` is
    green for the parts that do not depend on W12 (the case-insensitivity
    assertion is allowed to xfail on this Step's commit; W12 flips it
    to green).
  - `aeat config --help` lists the setup flow plus
    `set`, `get`, `unset`, `list`, `status`, `reset`, `auth` exactly.
  - `aeat init --help` still exists (deletion in W11).
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - delete `init_cmd` or the `aeat setup` group module (W11).
  - touch locale catalogues (W10).
  - close the case-insensitive lookup gap (W12).

### Step W10 — locale catalogues

- Files owned:
  - `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`,
    `src/aeat/locales/ca.yml`, `src/aeat/locales/hu.yml` — each gains a
    `wizard.setup.<section-id>.<question-id>.{prompt,help,label,description}`
    block covering every `Translatable` referenced by `WIZARD_FLOWS`,
    plus `wizard.setup.errors.missing_required_flags`. Existing
    `setup.wizard.*`, `cli.setup.*`, `cli.init.*` keys are NOT
    deleted yet (deletion is W11 to keep this Step's commit purely
    additive).
  - `src/aeat/application/wizard/_translations.py` — new file. Declares
    `audit_wizard_translations() -> tuple[str, ...]` per ADR section F:
    walks every `Translatable` referenced by `WIZARD_FLOWS` and returns
    the tuple of keys that fail to resolve in any of the four locales.
  - `src/aeat/application/wizard/test_wizard_translations_resolve.py`
    — new file. One test asserts `audit_wizard_translations()` returns
    the empty tuple; the test is the locale-parity gate per ADR I.

- Acceptance gates:
  - `uv run pytest src/aeat/application/wizard/test_wizard_translations_resolve.py`
    is green.
  - Every key referenced by `WIZARD_FLOWS` resolves in every locale
    (no raw key shown to the operator on any locale).
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - delete any legacy locale key (W11).
  - register any new locale (the four supported locales stay fixed).

### Step W11 — delete dead artifacts (ADR section H)

- Files deleted:
  - `src/aeat/application/setup/_wizard.py`
  - `src/aeat/application/setup/_models.py`
  - `src/aeat/application/setup/_prompter.py`
  - `src/aeat/application/setup/_verifier.py`
  - `src/aeat/application/setup/_env_writer.py`
  - `src/aeat/application/setup/_protocols.py`
  - `src/aeat/application/setup/_errors.py`
  - `src/aeat/application/setup/__init__.py`
  - `src/aeat/application/setup/test_verifier.py`
  - `src/aeat/application/setup/test_env_writer.py`
  - `src/aeat/application/setup/test_wizard.py`
  - `src/aeat/application/setup/test_models.py`
  - `src/aeat/application/setup_status.py` (the body is now in
    `aeat config status`; the `build_setup_status` function is
    rewritten and relocated to `aeat.application.wizard._status`
    in this Step — file owned in this Step).

- Files modified:
  - `src/aeat/entrypoints/cli/__init__.py` — `init_cmd` body and the
    root `aeat init` command registration are deleted. The module
    keeps the app instance and sub-app registration only.
  - `src/aeat/entrypoints/cli/_setup.py` — file deleted. The
    `aeat setup` Typer sub-app registration is removed from the CLI
    root.
  - `src/aeat/application/__init__.py` — drop any re-export of
    `setup.*` symbols.
  - `src/aeat/application/deadlines/_helpers.py` — the line that calls
    `load_profile_envelope` is rewritten to read directly from the
    active `ProfileRecord` through `project_answers(setup_flow,
    profile_values)` per ADR section H.
  - `src/aeat/application/deadlines/_profiles.py` — the
    `_bool_value` / `_iva_regime_value` / alias-fallback helpers
    and the `_TRUE_TOKENS` / `_FALSE_TOKENS` tables are deleted. The
    deadline engine consumes `project_answers(setup_flow, values)`
    and reads typed fields off `AutonomoProfile` directly.
  - `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — every
    `setup.wizard.*`, `cli.setup.*`, `cli.init.*` key deleted.
    `setup.verifier.t_*` keys: those that map to checks the new
    verifier reuses become `wizard.setup.verifier.<finding-name>`;
    those that don't are deleted.

- New files:
  - `src/aeat/application/wizard/_status.py` — new file. Declares
    `build_wizard_status(flow, state) -> WizardStatusReport` (the
    relocated `build_setup_status` rewritten against
    `project_answers`).
  - `src/aeat/application/wizard/test_status.py` — new file.
    Structural / wiring assertions on the report shape.

- Acceptance gates:
  - The directory `src/aeat/application/setup/` does not exist.
  - `grep -r "from aeat.application.setup" src/` returns no hits.
  - `grep -r "SetupWizard\|SetupAnswers\|TyperPrompter\|QueuedPrompter"
    src/` returns no hits.
  - `grep -r "setup\.wizard\.\|cli\.setup\.\|cli\.init\." src/aeat/locales/`
    returns no hits.
  - `aeat init --help` exits non-zero (the command does not exist).
  - `aeat setup --help` exits non-zero (the command group does not
    exist).
  - `aeat config --help` returns zero and lists exactly the surfaces
    enumerated in ADR section E verification gate.
  - `uv run pytest src/aeat/application/wizard/` is green.
  - `uv run pytest src/aeat/application/deadlines/` is green (the
    helpers rewrite is covered by existing deadline tests).
  - `uv run pytest src/aeat/entrypoints/cli/` is green for the touched
    commands.
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - touch `WorkflowState.profiles` typing (W12).
  - touch `_normalise_key` asymmetry (W12).

### Step W12 — reconcile typing and `_normalise_key` chokepoint

- Files owned:
  - `src/aeat/domain/profile/_keys.py` — modified. Adds
    `ProfileKey.from_key(raw: str) -> ProfileKey` classmethod that
    runs `_normalise_key` on its argument before the registry lookup.
    `get_profile_key(key)` is rewritten to delegate to
    `ProfileKey.from_key(key)`. This closes the asymmetric-normalisation
    gap so `aeat config set TAX.ID 12345678Z` resolves to the same
    descriptor entry as `aeat config set tax.id 12345678Z`.
  - `src/aeat/application/workflow/_utils.py` — modified. `_normalise_key`
    is re-exported from `domain.profile` rather than living here; the
    file becomes a thin re-export to keep import-cycle hygiene. (If a
    re-export creates a cycle, the function itself moves to
    `domain.profile` and the workflow module imports it.)
  - `src/aeat/application/workflow/_models.py` — modified.
    `WorkflowState.profiles` type stays `dict[str, Any]` per ADR
    section G (the typed projection happens via `project_answers`,
    not by re-typing the container). `active_profile_record` is
    rewritten to delegate to `project_answers` for shape coercion.
    This re-typing is intentionally conservative: the ADR rejects a
    full `dict[str, ProfileRecord]` lift to preserve legacy dict
    round-trip.
  - `src/aeat/application/profile/_models.py` — modified.
    `ProfileRecord.values` typing stays `dict[str, str]`; the typed
    projection is consumed via `project_answers`.
  - `src/aeat/entrypoints/cli/test_config_setter.py` — modified.
    Flips the case-insensitivity xfail assertion (introduced in W9)
    to a hard pass.

- Acceptance gates:
  - `aeat config set TAX.ID 12345678Z` and
    `aeat config set tax.id 12345678Z` both produce identical
    `ProfileRecord.values` content.
  - `uv run pytest src/aeat/entrypoints/cli/test_config_setter.py`
    is green with no xfail markers.
  - `uv run pytest src/aeat/domain/profile/` is green.
  - `uv run pytest src/aeat/application/workflow/` is green.
  - `uv run prek run --files <touched paths>` passes.

- Does NOT:
  - touch the wizard runtime (it already routes through the
    descriptor).
  - migrate any historical operator data (out of scope per ADR §G —
    `tax_residence_since` / change history are not lifted into the
    descriptor in this change).

### Step W13 — final verification gate sweep

- Files owned:
  - None new. This Step runs the global gates and lands a single
    follow-up commit only if a gate surfaces a fix.

- Acceptance gates (all must pass; this Step closes when every gate
  is green, with at most one follow-up commit allowed inside this
  Step to address a gate failure):
  - `uv run --no-sync vaultspec-core vault check all` returns zero new
    drift findings against the wizard plan / ADR / reference / research
    cluster (the pre-existing baseline of 254 unrelated errors is
    accepted as the floor; the Step asserts the wizard cluster
    contributes zero new errors).
  - `uv run prek run --all-files` is green.
  - `uv run pytest src/aeat/application/wizard/` is green.
  - `uv run pytest src/aeat/entrypoints/cli/` is green.
  - `uv run pytest src/aeat/domain/profile/` is green.
  - `uv run pytest src/aeat/application/deadlines/` is green.
  - The directory `src/aeat/application/setup/` does not exist.
  - No grep hit for `setup.wizard.`, `cli.init.`, or `cli.setup.` in
    any `src/aeat/locales/*.yml` file. No grep hit for `SetupWizard`,
    `SetupAnswers`, `TyperPrompter`, `QueuedPrompter`, or `Verifier`
    (the dead-wizard class) anywhere under `src/`.
  - `compile_profile_keys(WIZARD_FLOWS)` round-trips with a structural
    snapshot test (already covered by `test_compile.py` +
    `test_setup_compiles.py`; this Step re-runs them as the final
    sweep).
  - `aeat --help` lists exactly two subgroups (`config`, `app`).
  - `aeat config setup --help`, `aeat config set --help`,
    `aeat config get --help`, `aeat config unset --help`,
    `aeat config list --help`, `aeat config status --help`,
    `aeat config reset --help`, `aeat config auth --help` all return
    zero exit and render in the active locale.

- Does NOT:
  - introduce any new feature surface.
  - delete any artifact not already in scope.

## Commit discipline

- One Step is one commit. No bundled multi-Step commits; the executor
  runs each Step's gates and commits at the end of that Step before
  moving on.
- Commit subject style is imperative present tense, no dates, no
  vault paths, no `W<n>` markers in the source. Examples:
  - "Add questionary dependency for wizard prompter" (W1)
  - "Add WizardFlow descriptor pydantic models" (W2)
  - "Add WizardWidget enum and per-widget validators" (W3)
  - "Wire setup wizard into aeat config" (W9)
  - "Remove dead setup subpackage and aeat init root command" (W11)
  The `W<n>` ordinal lives in the plan and (optionally) in the
  commit body's first line as a parenthesised marker; it never
  appears in `src/` content.
- Stage files explicitly by path. Never `git add -A`, `git add .`,
  or `git add -u`. The off-limits list in the "Off-limits worktree
  state" section above is final.
- Never bypass pre-commit hooks. Never run `--no-verify`. Never
  skip ruff / ruff format / ty. If a hook fails, fix the underlying
  issue and stage a new commit; do not amend the failed commit.
- The branch is `chore/eliminate-shims`. Do not switch branches.
  Do not push. Do not open a PR.
- Each Step's commit body summarises the Step's intent and the
  acceptance gates it cleared; the body never references the
  ADR's section letters or the reference document's section
  numbers (those are vault metadata, not source-history metadata).

## Out of scope

The following items are explicitly NOT covered by this plan, per
ADR section "Out of scope" and per scope-discipline:

- The auth subsystem's credential-provisioning lifecycle (PIN entry,
  browser handshake, Cl@ve Móvil OTP). The wizard captures provider
  identity and certificate path; the rest of the auth dance is a
  separate domain. `aeat config auth` is moved in this plan, but
  not redesigned.
- Env-var write-back. The legacy wizard wrote ten env vars to an
  `.env` file via `_env_writer.write_env_file`; the new wizard writes
  only to `ProfileRecord`. The mapping of formerly-env-only operator
  inputs (drafts dir, submissions dir, manuals root, live-tests
  opt-in, default profile path, language pair, certificate backend /
  friendly name / verify URL) onto the descriptor MAY happen in a
  follow-on flow but is not committed here.
- The `aeat financial profile set-ratio` surface and its parallel
  validator. Out of scope per ADR.
- Multi-clause `WizardCondition` algebra (`WizardAllOf`,
  `WizardAnyOf`). Single-clause equality is sufficient for the
  current `setup` flow; the algebra is deferred.
- Re-run / diff-only semantics for `aeat config setup`. The flow
  re-prompts every visible question on each invocation.
- `RentaDescendantProfile` / `RentaAscendantProfile` /
  `RentaFamilyProfile` capture flows. These belong in a separate
  `family-capture` wizard flow.
- Wizard secret-store integration. `WizardWidget.SECRET` collects
  the value via `questionary.password`, but the persistence target
  for secrets is owned by the existing secret-management surface;
  this plan commits only to collection.
- Migration of historical operator data into the new descriptor
  shape. The `TaxResidenceProfile.tax_residence_since` /
  `tax_residence_change_history` fields are not lifted into the
  wizard. The plan adds `tax.residence.ccaa` as a descriptor key for
  the first time but does not back-fill old profiles.
- The concurrent renta-pipeline and restructure agent surfaces.
  Their dirty files are listed in "Off-limits worktree state" and
  must not be touched by this plan's commits.

## Parallelization

Within this plan the Steps are strictly sequential — each Step
depends on artifacts produced by an earlier Step, and the commits
land in W1..W13 order on the `chore/eliminate-shims` branch.
W1 unblocks W5, W2 unblocks W3..W8, W3 unblocks W7..W9, W4
unblocks W5..W8, W6 unblocks W7..W12, W7 unblocks W8..W13, W8
unblocks W9..W13, W9 unblocks W11..W13, W10 unblocks W11, W11
unblocks W12..W13, W12 unblocks W13. No two Steps can be
executed in parallel without merge conflict on the shared
descriptor / catalogue files. Parallelism is therefore zero
inside this plan.

Across plans, this work is parallel-safe with the renta-pipeline
agent and the restructure agent provided the off-limits list is
respected; the wizard plan's source surface intersects with the
restructure agent only at `src/aeat/entrypoints/cli/__init__.py`
(wizard W11 deletes `init_cmd`; the restructure agent owns other
helpers in `_common.py`). Conflicts on `__init__.py` resolve in
favour of the wizard's deletion edits.

## Verification

The plan is considered fully executed when every gate in Step W13
passes on the merge commit. The closing verification mirrors ADR
section "Verification gates" exactly and adds the plan-level
gates:

- `uv run --no-sync vaultspec-core vault check all` passes with
  zero new drift findings attributable to this plan.
- `uv run prek run --all-files` passes.
- `uv run pytest src/aeat/application/wizard/` is green.
- `uv run pytest src/aeat/entrypoints/cli/` is green for touched
  commands.
- The directory `src/aeat/application/setup/` does not exist.
- No file under `src/aeat/` contains `setup.wizard.`, `cli.init.`,
  `cli.setup.`, `SetupWizard`, `SetupAnswers`, `TyperPrompter`,
  `QueuedPrompter`, or the dead-wizard `Verifier` class.
- `compile_profile_keys(WIZARD_FLOWS)` is the one call that
  produces `PROFILE_KEYS` at import time; the function is pure
  and the assertion is covered by `test_compile.py` plus
  `test_setup_compiles.py`.
- `aeat --help` lists exactly two subgroups (`config`, `app`); no
  third root exists.
- `aeat config set tax.id 12345678Z` and
  `aeat config set TAX.ID 12345678Z` produce identical
  `ProfileRecord.values` content.
- `aeat config set iva.regime XYZ` exits non-zero with a
  translated error referencing the valid choices.
- `aeat config set tax.residence.ccaa madrid` succeeds and writes
  through to `TaxResidenceProfile`.

The plan is honest about what it cannot prove by automated test:
the questionary integration smoke covers one TTY-emulation path
per widget kind, not every operator's terminal. A live operator
walkthrough on each of the four locales remains a human-loop
verification that this plan does NOT cover.
