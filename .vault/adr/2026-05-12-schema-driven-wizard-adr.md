---
tags:
  - '#adr'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-research]]"
  - "[[2026-05-12-schema-driven-wizard-reference]]"
---



# `schema-driven-wizard` adr: `schema-driven-wizard-adr` | (**status:** `accepted — execution-ready`)

## Context

The operator-facing configuration surface is fragmented across four
entry points (`aeat init`, `aeat setup init`, `aeat setup profile set`,
`aeat config set`) and one ten-step orchestrator (`SetupWizard`) that
has no live caller. The orchestrator hand-rolls every `typer.prompt`
call, duplicates fields the live registry already declares, and renders
raw translation keys when the unwired path is exercised. The directive
for this ADR is non-negotiable: the wizard becomes the source of truth,
the descriptor schema generates the `PROFILE_KEYS` registry rather than
the other way around, the Typer command surface is derived from the
descriptor, and the wizard exposes a mini-API that backend callers and
tests invoke directly without going through Typer. The codebase
already carries the seeds — `PROFILE_KEYS` with conditional-requirement
encoding, `AUTH_PROVIDER_CATALOGUE` as a closed descriptor tuple,
`autonomo_profile_from_mapping` as a typed-projection precedent, and
the `Prompter` Protocol as an interaction-source decoupling. This ADR
commits to a specific shape for assembling those seeds into one
schema-driven wizard subsystem and removes every artifact the new
shape obsoletes in the same change.

## Decision

### A. Descriptor schema shape

The wizard descriptor lives under `aeat.application.wizard` as a
new subpackage. Five strict frozen pydantic v2 models compose the
descriptor: `WizardFlow`, `WizardSection`, `WizardQuestion`,
`WizardChoice`, and `WizardCondition`. A flow is a closed tuple of
sections; a section is a closed tuple of questions; a question has
exactly one widget kind and zero-or-one persistence binding. The
canonical class skeletons:

```python
class WizardWidget(StrEnum):
    TEXT = "text"
    SECRET = "secret"
    CONFIRM = "confirm"
    SELECT = "select"
    CHECKBOX = "checkbox"
    PATH = "path"
    INTEGER = "integer"

class WizardCondition(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    question_id: str
    equals: str  # canonical-token comparison; bool answers serialise to "true"/"false"

class WizardChoice(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    value: str                  # canonical token stored in the profile
    label: Translatable         # rendered via tr() at prompt time
    description: Translatable | None = None

class WizardQuestion(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    id: str                      # stable identifier, kebab-case, scope=flow
    profile_key: str | None      # binds the answer to a PROFILE_KEYS row; None means
                                 # the answer is consumed by a flow-local sink
    widget: WizardWidget
    prompt: Translatable         # tr key shown to the operator
    help: Translatable | None = None
    choices: tuple[WizardChoice, ...] = ()
    default: str | None = None   # canonical token; None means "no default"
    required: bool = True        # baseline requirement; conditional overrides via visible_when
    visible_when: WizardCondition | None = None
    answer_type: type[str | bool | int | Path]  # canonical typed projection
    # (see G; one of the four exact types above)

class WizardSection(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    id: str
    title: Translatable
    questions: tuple[WizardQuestion, ...] = Field(min_length=1)

class WizardFlow(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    id: str                      # stable, kebab-case, becomes the Typer command name
    title: Translatable
    description: Translatable
    sections: tuple[WizardSection, ...] = Field(min_length=1)
    answers_model: type[BaseModel]  # the per-flow typed answers projection (see G)
```

Relationship between `WizardQuestion` and `ProfileKey`: structural, not
inheritance. A question MAY bind to a profile key via `profile_key`,
and the `compile_profile_keys` derivation (see B) walks every flow and
emits one `ProfileKey` per distinct `profile_key` value seen, with
`requirement` derived from the `required` flag and any `visible_when`
condition becoming `required_when_key`/`required_when_value`. A
question with `profile_key=None` exists for transient input that the
flow consumes itself (e.g. a flow-controlling toggle that gates other
questions but is not persisted as a profile key). One profile key MAY
NOT be bound by more than one question across the flow registry — the
derivation rejects duplicates.

Question-type taxonomy: the seven `WizardWidget` enum values listed
above. The taxonomy mirrors the closed react-jsonschema-form widget
list documented in the research artifact and matches the questionary
primitive API 1:1 (`text`, `password`, `confirm`, `select`, `checkbox`,
`path`, plus an `integer` variant of `text` with a numeric validator).
No widget for free-form multi-line — multi-line input is out of scope
for this surface.

Conditional questions are encoded **declaratively** via the
`WizardCondition` pydantic model on `visible_when`. The condition
references another question by id and compares the canonical-token
answer against a literal string. Imperative `Callable[[Answers], bool]`
predicates are rejected: callables cannot be serialised, cannot be
walked by `compile_profile_keys` to derive `required_when_key`/
`required_when_value`, and cannot be diffed in a snapshot test. The
declarative shape is intentionally less expressive than the questionary
`when` lambda; if a future flow needs a multi-clause predicate, the
descriptor MAY be extended with a `WizardAllOf`/`WizardAnyOf` algebra,
but the initial commitment is single-clause equality only.

Validation is encoded in two layers: per-widget validators are
built-in to the runtime (path-exists for `PATH`, choice-membership for
`SELECT`/`CHECKBOX`, boolean-token parse for `CONFIRM`, integer parse
for `INTEGER`), and end-of-flow validation is delegated to the
`answers_model` pydantic class via `model_validate({...})`. The
descriptor does NOT carry per-question validator callables. The
two-layer split has a clean contract: widget validators ensure the
answer is well-typed before storage; the answers model ensures cross-
field invariants (e.g. spouse fields populated when declaration type
is joint).

### B. Source-of-truth direction

The descriptor is a **registry**, not a discovered surface. A single
module — `aeat.application.wizard._catalogue` — exports
`WIZARD_FLOWS: tuple[WizardFlow, ...]` as a frozen tuple, mirroring
how `AUTH_PROVIDER_CATALOGUE` is exported today. No entry-point walk,
no plugin protocol, no decorator-based registration. Adding a new
flow means appending a `WizardFlow` literal to the tuple.

The descriptor-to-`PROFILE_KEYS` derivation is a pure function:

```python
def compile_profile_keys(flows: Sequence[WizardFlow]) -> tuple[ProfileKey, ...]:
    """Project the wizard catalogue into the legacy registry shape."""
```

The function runs at module import time inside
`aeat.domain.profile._keys`, so `PROFILE_KEYS` becomes
`compile_profile_keys(WIZARD_FLOWS)`. The derivation:

- emits one `ProfileKey` per distinct `WizardQuestion.profile_key`
  value across all flows (None-bound questions are skipped);
- sets `requirement = REQUIRED` when `WizardQuestion.required is True`
  AND `visible_when is None`, else `OPTIONAL`;
- sets `required_when_key`/`required_when_value` from
  `visible_when.question_id`/`visible_when.equals` when the
  parent question is itself bound to a profile key, else leaves them
  None;
- carries `description = Translatable("profile.keys.<key>")` exactly
  as today, since the per-key catalogue copy is locale-owned and
  orthogonal to the per-question prompt copy.

Codegen at build time is rejected: it would require a separate
toolchain step and a generated `.py` file checked into the repo,
duplicating the registry into two locations. The import-time pure
function keeps the source-of-truth direction one-way and the audit
trail trivial — `PROFILE_KEYS` is always whatever `WIZARD_FLOWS`
projects, full stop.

`AUTH_PROVIDER_CATALOGUE` is **not** folded into the wizard
descriptor. Auth provider listings serve the
`aeat setup auth configure --provider <id>` action surface, which is
a distinct concern (provider selection plus credential file binding,
mediated by `update_auth`), not a profile-value setter. A wizard
question MAY reference auth providers as `WizardChoice`s via a
helper that reads `AUTH_PROVIDER_CATALOGUE` and emits a tuple of
`WizardChoice(value=p.id, label=p.label, description=p.description)`,
but the two registries stay independent. The wizard owns operator
profile values; the auth catalogue owns provider selection.

### C. Prompt library choice

`questionary` is adopted as the prompt backend. Fit-score 5 in the
research comparison table, MIT-licensed, current release 2.1.1
(verified against PyPI on the ADR date), prompt_toolkit-backed which
gives a documented headless test pattern via `create_pipe_input`. The
questionary primitive API (`questionary.text`, `.confirm`, `.select`,
`.checkbox`, `.path`, `.password`) maps directly onto the seven
`WizardWidget` values. Rejected alternatives: `rich.prompt` (no
select/checkbox primitive, would require hand-rolled choice loops
exactly as `TyperPrompter.prompt_choice` does today), `typer.prompt`
(same gap — the current dead wizard demonstrates the cost),
`prompt_toolkit` widgets directly (full-screen TUI, leaves the
read-a-line model), `Textual` (fit-score 1, framework-level
commitment).

Testability is preserved by wrapping questionary behind an internal
`Prompter` interface — pydantic-validated protocol, two
implementations:

```python
class Prompter(Protocol):
    def ask(self, question: WizardQuestion, *, default: str | None) -> str: ...

class QuestionaryPrompter:  # production
    """Renders one WizardQuestion via the matching questionary primitive."""

class ScriptedPrompter:  # tests
    """Pops canonical-token answers from a deque; raises on under/overflow."""
```

The wizard runtime accepts the prompter as a constructor argument.
Tests use `ScriptedPrompter(answers=deque(["12345678Z", "general"]))`
and assert that the runtime feeds each question to the prompter in
the expected order, that conditional branches skip the right
questions, and that the final answers project into a valid
`answers_model`. No `create_pipe_input`-style integration test against
real questionary is required at the unit-test boundary; one
integration smoke test per flow exercises the questionary path
end-to-end.

### D. CLI generation

The descriptor generates a **single callable** per flow, not a full
codegen module. A pure function:

```python
def build_wizard_command(flow: WizardFlow) -> Callable[..., None]:
    """Return a Typer-compatible callable that runs `flow` end-to-end."""
```

returns a closure whose signature is composed at call time from the
flow's questions plus a fixed set of mode flags (`--quiet`,
`--profile-name`, `--accept-defaults`). The closure is registered
against the appropriate Typer sub-app via
`app.command(name=flow.id)(callable)` inside the CLI entrypoint
module. Typer's `app.command()` is a decorator factory that returns
the function unmodified — there is no semantic difference between
decorator application at import time and programmatic application at
import time. The entrypoint module walks `WIZARD_FLOWS` once and
registers every flow's command in one loop.

Flag derivation per question: every `WizardQuestion` whose `widget` is
in `{TEXT, SECRET, PATH, INTEGER}` becomes an optional Typer
`--<question-id>` flag with the matching type; `CONFIRM` becomes a
`--<question-id>/--no-<question-id>` boolean pair; `SELECT` becomes a
flag with `click_type=click.Choice([c.value for c in choices])`;
`CHECKBOX` becomes a repeated flag. When `--quiet` is set, every
required-and-not-conditional question MUST have a flag value (or a
descriptor default); the runtime raises a translated error
referencing the missing flags. The mode flags `--quiet`,
`--profile-name`, `--accept-defaults` interleave at the closure
signature level and are validated before any question is dispatched.

The callable path (single closure per flow) is preferred over
full codegen at import time because it keeps Typer's introspection
intact for `--help` rendering, avoids `exec()` of generated source,
and allows the same closure to be invoked from tests via
`build_wizard_command(flow)(ScriptedPrompter(...), **answer_kwargs)`
without any Typer infrastructure.

### E. Surface convergence

The four current surfaces collapse to exactly two CLI invocation
shapes against the same descriptor:

- `aeat config <flow-id>` — full-flow run. Walks every visible
  question in the flow, persists the answers via `set_profile_values`,
  optionally activates the profile if the flow declares
  `profile_name` as the binding for the first question.
- `aeat config set <key> <value>` — single-field set. Looks up the
  `WizardQuestion` whose `profile_key == key`, applies the
  widget-level validator (so `aeat config set iva.regime XYZ` is
  rejected at the CLI boundary, not at deadline-compute time, closing
  the `iva.regime` drift gap), and persists via `set_profile_values`.

Both invocation shapes share the same descriptor, so single-field
set inherits widget validators, choice constraints, and defaults for
free. The "thin wrapper" mandate holds: each Typer command body is a
two-line closure that delegates to the wizard runtime.

The root `aeat init` command is removed. `aeat setup init` is
removed. `aeat setup profile set` / `aeat setup profile unset` are
removed. The complete CLI on-ramp lives under `aeat config` per the
"CLI root is exactly config + app" mandate. The first-run flow
becomes `aeat config setup` (the flow's `id` is `setup`), and the
single-field setter remains `aeat config set` / `aeat config unset` /
`aeat config get` / `aeat config list`, all reading from the same
compiled `PROFILE_KEYS`.

### F. i18n model

Prompt strings live in the descriptor as `Translatable` markers,
identical to how `ProfileKey.description` carries a `profile.keys.<key>`
key today. The convention
`wizard.<flow-id>.<section-id>.<question-id>.prompt` / `.help` /
`.label` / `.description` (for choices) is mandatory; the descriptor
constructor validates that every `Translatable` value starts with the
matching `wizard.<flow-id>.` prefix.

A build-time check enforces locale coverage: a new function
`audit_wizard_translations()` walks every `Translatable` referenced by
`WIZARD_FLOWS` and asserts that every key resolves in every locale
catalogue (`en`, `es`, `ca`, `hu`). The check runs as a pytest case
(`test_wizard_translations_resolve.py`); a CLI subcommand surface for
the same check is out of scope. The `cli.init.quiet_requires_all` gap
surfaced in the reference audit is closed by deleting the `init_cmd`
quiet branch entirely; the replacement message lives under
`wizard.setup.errors.missing_required_flags` and ships in all four
locales as part of the landing change.

### G. Answer model and persistence

Each `WizardFlow` declares an `answers_model: type[BaseModel]`. The
runtime collects canonical-token strings from the prompter, parses
them into the declared `answer_type` per question (`str` / `bool` /
`int` / `Path`), builds a dict keyed by `WizardQuestion.id`, and
calls `answers_model.model_validate(dict)`. Cross-field invariants
live exclusively on `answers_model` as pydantic `model_validator`s.

Persistence to `ProfileRecord.values` happens via a typed adapter:

```python
def persist_answers(
    flow: WizardFlow,
    answers: BaseModel,
    *,
    state: WorkflowState,
    profile_name: str,
) -> WorkflowState:
    """Serialise typed answers back to canonical tokens and call set_profile_values."""
```

`ProfileRecord.values` stays `dict[str, str]` — the canonical-token
serialisation (bool to `"true"`/`"false"`, int to `str(int)`, Path to
`str(path)`, str passthrough) is owned by `persist_answers`. The
reverse projection (`dict[str, str]` to typed answers) lives in a
new pure function `project_answers(flow, values) -> answers_model`,
which replaces the hand-rolled `_bool_value` / `_iva_regime_value`
helpers in `deadlines/_profiles.py`. Those helpers are deleted; the
deadline engine consumes `project_answers(setup_flow, profile_values)`
and reads `AutonomoProfile` fields off the typed projection.

The asymmetric `_normalise_key` gap (lowercase on write, exact on
read) is closed at the same boundary: `get_profile_key` runs the same
`_normalise_key` on its argument before the registry lookup, so
`aeat config set TAX.ID 12345678Z` and `aeat config set tax.id 12345678Z`
resolve to the same descriptor entry. The normalisation lives on
`ProfileKey` itself (a `from_key(raw: str)` classmethod) so every
consumer reads through one chokepoint.

`tax_residence_ccaa` becomes a `WizardQuestion` bound to
`profile_key = "tax.residence.ccaa"` with widget `SELECT` and choices
projected from `CCAA`. The separate `save_tax_residence` persistence
path is retained internally — `persist_answers` calls it as a
side-effect when the flow writes the `tax.residence.ccaa` key — but
the operator interacts through one descriptor entry, not two
surfaces. The `TaxResidenceProfile.tax_residence_since` /
`tax_residence_change_history` fields are not added to the wizard
descriptor; they remain managed by a separate domain action invoked
by future flows, out of scope for this ADR.

`SetupAnswers`'s two never-prompted fields
(`pays_capital_income_with_retencion`,
`uses_objective_estimation_irpf`) become descriptor questions in the
`setup` flow. They were latent inconsistencies in the dead wizard;
making them descriptor questions closes the gap.

### H. Dead-code removal scope

In the same change that lands the new wizard, the following artifacts
are deleted outright. No shims, no parallel modules, no deprecation
notices.

- `src/aeat/application/setup/_wizard.py` — delete (`SetupWizard`,
  `_collect_interactive`, the ten-step orchestration).
- `src/aeat/application/setup/_models.py` — delete (`SetupStep`,
  `SetupOutcome`, `SetupAnswers`, `SetupResult`). `VerifySeverity`
  and `VerifyFinding` fold into the new wizard verification surface
  as `WizardCheckSeverity` / `WizardCheckFinding`.
- `src/aeat/application/setup/_prompter.py` — delete (`TyperPrompter`,
  `QueuedPrompter`). The `Prompter` protocol moves to
  `aeat/application/wizard/_prompter.py` with the new
  `QuestionaryPrompter` / `ScriptedPrompter` pair.
- `src/aeat/application/setup/_verifier.py` — fold into
  `aeat/application/wizard/_verifier.py`. The seven checks (cert
  path, password env var, dir mkdirs, profile envelope load) become
  per-flow `WizardCheck` records on the descriptor; the orchestrator
  runs them after `persist_answers` succeeds.
- `src/aeat/application/setup/_env_writer.py` — delete
  `write_profile_file`, `write_env_file`. The env-var write path is
  excised; operator-entered values commit to `ProfileRecord` only.
  `load_profile_envelope` (consumed by `deadlines/_helpers.py:67`)
  is rewritten to read directly from the active `ProfileRecord`
  through `project_answers`; the deadline engine no longer reads
  the env file.
- `src/aeat/application/setup/_protocols.py` — delete; the
  `Prompter` protocol relocates to `application/wizard/`.
- `src/aeat/application/setup/_errors.py` — fold into
  `aeat/application/wizard/_errors.py`.
- `src/aeat/application/setup/__init__.py` — delete the subpackage.
- `src/aeat/entrypoints/cli/__init__.py` — `init_cmd` (the root
  `aeat init` command body) deleted. The root module retains only
  the app instance and sub-app registration.
- `src/aeat/entrypoints/cli/_setup.py` — `setup_init`,
  `setup_profile_set`, `setup_profile_unset` deleted. The
  `aeat setup` command group itself is removed; reset and
  auth-configure live under `aeat config` as `aeat config reset` and
  `aeat config auth`, preserving the "config + app" two-root mandate.
- `src/aeat/locales/{en,es,ca,hu}.yml` — every `setup.wizard.*` key,
  `cli.setup.*` key, and `cli.init.*` key deleted. Replacement keys
  under `wizard.*` ship in all four locales as part of the same
  change.
- `application/setup_status.build_setup_status` and `aeat setup
  status` — relocated to `aeat config status` and rewritten to
  consume `project_answers(setup_flow, profile_values)` instead of
  the raw `dict[str, str]`.

`AutonomoProfile`, `autonomo_profile_from_mapping`, `IVARegime`,
`FilingIVAProfile`, `FilingEnrollment`, `TaxResidenceProfile`,
`CCAA`, `ResidenceChange`, `WorkflowState`, `ProfileRecord`,
`set_profile_values`, `set_active_profile`, `clear_profile_values`,
`SetupResetScope`, `reset_setup`, `AuthState`, `update_auth`,
`AUTH_PROVIDER_CATALOGUE`, `Settings` (all 70+ env-only fields) —
kept as-is. The wizard runtime reads and writes through these
existing seams.

### I. Testing strategy

Every flow ships with three test files following one pattern.

- `test_<flow-id>_compiles.py` — structural / wiring assertions
  against the descriptor itself: every question id is unique inside
  the flow, every `WizardCondition.question_id` resolves to an
  earlier question in the same flow, every `Translatable` resolves
  in every locale, every `profile_key` (when set) appears in the
  compiled `PROFILE_KEYS`, every choice value passes the widget
  validator.
- `test_<flow-id>_runtime.py` — scripted-answer round-trip: feed a
  canonical-token answer set through `ScriptedPrompter`, assert the
  runtime calls the prompter in the expected sequence (including
  skipped questions when `visible_when` evaluates false), assert the
  resulting `answers_model` validates, assert `persist_answers`
  writes the canonical-token dict that `project_answers` round-trips
  back to the same typed model.
- `test_<flow-id>_cli.py` — Typer surface contract: build the
  command via `build_wizard_command`, invoke it through Typer's
  `CliRunner`, supply `--quiet` + flag values, assert exit code,
  assert the workflow state mutation matches the scripted-runtime
  result. No real questionary path is exercised here; the prompter
  injection is overridden via a fixture.

One additional integration test per flow exercises the questionary
path against `prompt_toolkit.input.create_pipe_input`, asserting that
the production prompter wires correctly. This is the single smoke
test that costs the questionary TTY-emulation dependency.

The descriptor-to-`PROFILE_KEYS` derivation is tested via
`test_compile_profile_keys.py`: structural assertions that every
descriptor question with a `profile_key` produces one and only one
registry entry, that requirement flags are derived correctly, that
duplicate `profile_key` bindings raise at import time. No snapshot of
the compiled tuple is taken — the derivation function is short
enough that structural assertions are sufficient, and a snapshot
would couple unrelated tests to descriptor edits.

All tests obey the no-tautological-calculation-tests rule. None of
them assert that "the descriptor computes what the descriptor says it
computes"; they assert structural invariants, sequence contracts, and
typed-projection round-trips. Choice validators are exercised by
feeding both valid and invalid tokens and asserting validation
behaviour, not by re-implementing the validator.

## Consequences

### Simpler

- One source of truth for operator-entered configuration. The
  descriptor catalogue is the only place a new field lands; the
  legacy registry is derived. Future "add a wizard field" PRs
  touch one tuple literal plus four translation files.
- One CLI invocation shape per surface. `aeat config <flow-id>` for
  full flows, `aeat config set <key> <value>` for single-field
  set, both reading from the same descriptor. The four-way split
  collapses to two.
- One typed-projection function. `_bool_value`, `_iva_regime_value`,
  the alias fallback, the asymmetric normalisation — all replaced
  by `project_answers(flow, values)` reading the canonical widget
  taxonomy. The deadline engine consumes typed objects, not raw
  strings.
- The "dead wizard exists but is wrong" trap is gone. The unwired
  ten-step `SetupWizard`, the orphan `setup.wizard.*` translation
  keys, the never-prompted-but-defaulted-to-false fields, the
  raw-key-shown-to-operator i18n bug — all excised in one change.

### Harder

- Adding a new widget kind requires touching the `WizardWidget`
  enum, the questionary primitive dispatcher, the Typer flag
  derivation, and the canonical-token serialiser. Four-point edit
  for a closed-set addition; mitigated by keeping the widget
  taxonomy small and stable.
- Conditional-question expressiveness is narrower than questionary's
  raw `when` lambda. Multi-clause predicates (e.g. "spouse fields
  required iff declaration is joint AND spouse is resident") are not
  expressible until the descriptor grows a
  `WizardAllOf`/`WizardAnyOf` algebra. The current `setup` flow does
  not need it; the trap is that future flows might.
- The wizard descriptor MUST be import-time pure. Any side-effect
  in `WIZARD_FLOWS` construction (file reads, env lookups, etc.)
  breaks `compile_profile_keys` and the audit test. Reviewers must
  catch this; the descriptor models being frozen pydantic v2
  records helps but does not prevent constructor-time side effects.

### New failure modes

- A flow whose `answers_model` accepts a typed value the canonical-
  token serialiser cannot round-trip (e.g. an arbitrary union type)
  would land as a runtime error during `persist_answers`, not at
  descriptor-construction time. Mitigation: the per-flow
  `test_<flow-id>_runtime.py` round-trip catches this; the
  `WizardQuestion.answer_type` constraint to the four canonical
  types is enforced at descriptor construction.
- Questionary 3.x (not on the immediate horizon) MAY change the
  primitive API. The `QuestionaryPrompter` abstraction is the
  single point of impact; a major-version bump is contained to one
  module.
- The descriptor + Typer-closure dance leans on `app.command()`
  returning the wrapped function unmodified. A future Typer release
  that changes this contract would break the dynamic registration
  loop. Mitigation: the per-flow `test_<flow-id>_cli.py` uses
  Typer's own `CliRunner`, so a regression surfaces in CI.
- The wizard verifier (folded from the dead `Verifier`) now runs
  against the typed-projection result, not the raw `SetupAnswers`.
  Check ordering and check granularity may need to shift; the plan
  phase enumerates each of the seven legacy checks and assigns it
  to a descriptor `WizardCheck` record.

## Rejected alternatives

- **Pattern A from the research artifact (questionary compiled from
  pydantic via `model_fields` introspection)** — rejected because it
  makes the domain model the source of truth for prompt-level
  metadata (prompt strings, conditional logic, widget kind). The
  directive explicitly mandates the opposite direction: the wizard
  descriptor generates the profile registry. Reading the schema in
  the wrong direction is a hard mismatch with the brief.
- **Pattern C (YAML wizard spec, pydantic answers)** — rejected
  because YAML adds a second serialisation format, a Jinja templater
  for defaults, and an i18n path that diverges from the existing
  `Translatable` marker convention. The codebase already proves that
  pydantic-record catalogues (`PROFILE_KEYS`, `AUTH_PROVIDER_CATALOGUE`)
  scale; introducing YAML would fragment that pattern.
- **python-statemachine FSM (Pattern B)** — rejected because back-
  navigation and re-prompt-on-validate are not in the operator's
  current expectations and adding them as a primary feature
  pessimises the simple linear flows that dominate AEAT setup. The
  declarative `WizardCondition` plus end-of-flow `model_validator`
  covers every current and known-near-term use case without a state
  machine.
- **`rich.prompt` as the backend** — rejected because
  `Prompt.ask(choices=[...])` only returns the typed answer, not a
  validated selection from a discriminator-rich choice catalogue;
  emulating questionary's `select` requires hand-rolled retry loops
  duplicating exactly the code the new wizard exists to delete.
- **Full code generation of Typer command modules at build time** —
  rejected because it requires a separate toolchain step, generated
  files in the repo, and a snapshot diff in CI. The runtime-closure
  approach achieves the same surface with less ceremony.
- **Keeping `aeat init` as a root convenience** — rejected per the
  "CLI root is exactly config + app" mandate. A third root is
  forbidden.
- **Imperative `Callable[[Answers], bool]` for `visible_when`** —
  rejected because callables cannot be walked by
  `compile_profile_keys` to derive `required_when_*` and cannot be
  enumerated by the structural compile-test. The declarative
  `WizardCondition` is intentionally less expressive in exchange
  for full introspection.
- **Letting one `WizardQuestion` map to multiple `ProfileKey`s** —
  rejected because the inverse relationship (one ProfileKey, one
  source-of-truth question) is the property that makes the
  derivation deterministic. Composite questions (e.g. a name that
  splits into given/surname keys) MUST be decomposed at the
  descriptor level.
- **Keeping `SetupAnswers` as a typed shim during the transition** —
  rejected per the no-backwards-compat mandate. The dead module
  goes in the same change.

## Out of scope

- The wizard's interaction with the auth subsystem's credential-
  provisioning flow (PIN entry, browser handshake, Cl@ve Móvil OTP).
  The wizard captures provider identity and certificate path; the
  rest of the auth lifecycle is a separate domain.
- Env-var write-back. The legacy wizard wrote ten env vars to an
  `.env` file; the new wizard writes only to `ProfileRecord` and
  reads `Settings` from process env as today. The mapping of
  formerly-env-only operator inputs (drafts dir, submissions dir,
  manuals root, live-tests opt-in) onto the descriptor MAY happen
  in a follow-on flow but is not committed here.
- The `aeat financial profile set-ratio` surface and its parallel
  validator. That surface manages usage ratios per `SpendingCategory`
  and is structurally distinct from the profile-key registry; this
  ADR does not absorb it.
- Multi-clause `WizardCondition` algebra (`WizardAllOf`,
  `WizardAnyOf`). Single-clause equality is sufficient for the
  current `setup` flow; the algebra is deferred until a real
  multi-clause flow appears.
- Re-run / diff-only semantics. The new `aeat config setup` re-
  prompts every visible question on each invocation, mirroring the
  legacy behaviour. A `--only-unset` mode is a future enhancement.
- `RentaDescendantProfile` / `RentaAscendantProfile` /
  `RentaFamilyProfile` capture flows. These are downstream Modelo
  100 capture surfaces with their own domain models; they belong
  in a separate `family-capture` wizard flow that consumes this
  ADR's primitives but is not specified here.
- Wizard secret-store integration. `WizardWidget.SECRET` collects
  the value via `questionary.password`, but the persistence target
  for secrets (env var? secret-store backend?) is owned by the
  existing secret-management surface; this ADR commits only to
  collection, not to storage.

## Verification gates

The design is considered landed when every check below passes on
the merge commit.

- The directory `src/aeat/application/setup/` does not exist. All
  modules listed in section H are deleted.
- `src/aeat/application/wizard/` exists and exports `WIZARD_FLOWS`
  as a non-empty `tuple[WizardFlow, ...]`.
- `from aeat.domain.profile import PROFILE_KEYS` returns a tuple
  produced by `compile_profile_keys(WIZARD_FLOWS)`. The function is
  a pure import-time call with no side effects.
- `aeat config setup --help`, `aeat config set --help`,
  `aeat config get --help`, `aeat config unset --help`,
  `aeat config list --help`, `aeat config status --help`,
  `aeat config reset --help`, `aeat config auth --help` all return
  zero exit and render help text in the active locale.
- `aeat init --help`, `aeat setup --help`, `aeat setup init --help`,
  `aeat setup profile set --help`, `aeat setup profile unset --help`
  all return non-zero (the commands do not exist).
- `aeat config set tax.id 12345678Z` and
  `aeat config set TAX.ID 12345678Z` both succeed and produce the
  same `ProfileRecord` state. The case-insensitivity gap from the
  reference audit is closed.
- `aeat config set iva.regime XYZ` exits non-zero with a translated
  error referencing the valid choices. The legacy "stores arbitrary
  string, fails at deadline time" path is gone.
- `aeat config set tax.residence.ccaa madrid` succeeds and writes
  through to `TaxResidenceProfile`. The previously-unreachable field
  is now CLI-addressable.
- `test_compile_profile_keys.py`, `test_setup_compiles.py`,
  `test_setup_runtime.py`, `test_setup_cli.py`,
  `test_wizard_translations_resolve.py` all pass.
- No grep hit for `setup.wizard.`, `cli.init.`, or `cli.setup.` in
  any `src/aeat/locales/*.yml` file. No grep hit for `SetupWizard`,
  `SetupAnswers`, `TyperPrompter`, `QueuedPrompter`, or `Verifier`
  (the dead-wizard class) anywhere under `src/`.
- `uv run --no-sync vaultspec-core vault check all` passes with zero
  drift findings against this ADR.
- The reference document's "open questions for the ADR phase"
  section is fully addressed: each of the eight bullets has a
  resolution captured in sections A through I above.
