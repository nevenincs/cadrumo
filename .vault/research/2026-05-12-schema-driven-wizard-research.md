---
tags:
  - "#research"
  - "#schema-driven-wizard"
date: "2026-05-12"
modified: '2026-05-12'
related:
  - "[[2026-04-12-setup-wizard-research]]"
---

# schema-driven-wizard research: schema-driven wizard research

Survey of prior art for schema-driven CLI configuration wizards in
Python. The motivating problem: the current aeat setup wizard
hand-rolls every typer.prompt() call, duplicating the structure of
a Pydantic v2 Profile/SetupAnswers schema that already declares
field types, defaults, and validation. The goal is to lay out the
landscape so that a follow-on ADR can pick a target topology;
no design recommendation is made here.

## Findings

### 1. taxonomy of approaches

The ecosystem clusters into six families, sorted by how the schema is
married to the prompt loop. Each family is named after one or two
exemplars; the comparison table in the next section enumerates them
exhaustively.

(a) Pydantic-as-CLI adapters (no prompts).
Tools like pydantic-settings (CliApp.run), clipstick, tyro, cyclopts,
and pydantic-cli read a Pydantic / dataclass / attrs model and emit
an argparse-style flag surface. Field types map to flag types,
nested models map to dotted-flag namespaces, Literal becomes a
choices group, docstrings become help text. None of them prompt the
user; they are typed argparse replacements. They establish the
discipline that the schema IS the surface but do not solve the
interactive wizard problem.

(b) Prompt libraries with a list-of-dict batch API.
questionary.prompt(questions_list) accepts a Python list of dicts
where each dict carries type, name, message, default, choices, when,
validate, filter. The when key is a lambda receiving the answers
collected so far - this is the canonical conditional-question
mechanism in Python. The list-of-dicts shape is itself a schema; the
natural move is to compile a Pydantic model into that list.
questionary ships no Pydantic adapter - that bridge has to be written.

(c) Per-question prompt primitives (no batch shape).
rich.prompt (Prompt, IntPrompt, FloatPrompt, Confirm with choices=,
default=, password=), typer.prompt/typer.confirm, plain input().
Each call is a single question; multi-step wizards must be
orchestrated externally. This is what the current TyperPrompter in
aeat does. Strength: trivially composable. Weakness: every question
is hand-wired.

(d) Full-screen TUI form frameworks.
prompt_toolkit widgets (TextArea, RadioList, CheckboxList, Button,
Frame, ScrollablePane), urwid, Textual (the Rich-derived modern TUI
framework). These give a true form-with-tabs UX but require the
wizard to leave the Typer read-a-line model behind, and they tend
to be heavy for a first-run CLI on-ramp.

(e) Templating-engine wizards.
copier (YAML schema, Jinja-templated defaults and when conditions,
secret/multiline flags, dynamic choices via Jinja) and cookiecutter
(JSON schema, conditionals via Jinja2 in template bodies, no native
when field). These are the most mature schema-driven wizards in the
Python ecosystem. They prove the YAML/JSON-with-Jinja pattern works
at scale (every modern project template uses one of them) but their
output is a templated repo, not a Pydantic-validated config object.

(f) Reference CLIs (non-Python) for design lessons.
gh auth login, aws configure sso, gcloud init, npm init, cargo init,
poetry init. The Go CLIs ride on charmbracelet/huh or the (now-
archived) AlecAivazis/survey. huh exposes a Form -> Group -> Field
hierarchy with WithHide(predicate), Validate(func), TitleFunc(binding),
OptionsFunc(binding) for dynamic state - this is the most polished
schema-driven wizard model in any modern language and is worth
borrowing as a vocabulary even if the implementation stays
Python-side. poetry init uses clikit prompts in a hand-rolled state
machine; npm init delegates to promzard, a prompting-JSON module
that defines questions as a module export, mirroring the questionary
shape.

### 2. comparison table

| tool | schema source | prompt library | branching | validation | conditional fields | escape hatches | license | maturity | fit (1-5) |
|------|---------------|----------------|-----------|------------|--------------------|----------------|---------|----------|-----------|
| pydantic-settings CliApp | Pydantic v2 BaseSettings | none (argparse) | subcommands via CliSubCommand | pydantic | none | mix env / CLI / init kwargs | MIT | stable, official | 3 |
| clipstick | Pydantic v2 BaseModel | none (argparse) | none documented | pydantic | none | falls back to standard typing | MIT | small, active | 2 |
| tyro | dataclass / pydantic / attrs | none (argparse) | subcommands, hierarchical | type-driven | none | tyro.conf.* markers | MIT | mature, large user base | 2 |
| cyclopts | type hints | none (argparse) | subcommands, mutually-exclusive groups | type + custom | none | Annotated parameter metadata | MIT | active, gaining traction | 2 |
| pydantic-cli | Pydantic v1/v2 | none (argparse) | subcommands | pydantic | none | custom validators | MIT | stable | 2 |
| questionary.prompt(list) | list of dicts | prompt_toolkit-backed | when lambda per question | validate callable | yes, lambda over prior answers | drop to per-question API | MIT | mature, widely used | 5 |
| rich.prompt | none - single Q | rich | external | callable retry loop | external | trivial - it is a primitive | MIT | very mature | 4 |
| typer.prompt | none - single Q | click | external | external | external | trivial - it is a primitive | MIT | very mature | 4 |
| prompt_toolkit widgets | manual layout | self | full TUI navigation | per-widget | yes, via state binding | full re-layout | BSD | very mature | 2 |
| Textual | manual TUI | self | screens / modal stack | per-widget reactive | yes, reactive | full app model | MIT | active, modern | 1 |
| copier | YAML (copier.yml) | questionary | sequential, no back-nav | Jinja validator | yes, when Jinja | post-gen Python hooks | MIT | very mature | 4 |
| cookiecutter | JSON (cookiecutter.json) | click | sequential | Jinja in template | only via Jinja in templated files | pre/post-gen hooks | BSD | very mature | 3 |
| python-statemachine | declarative class | none | full FSM + statecharts | guards (cond=, unless=) | yes, transitions | callbacks | MIT | stable | 4 |
| transitions | dict / class | none | FSM | callbacks | yes, transitions | callbacks | MIT | mature | 3 |
| charmbracelet/huh (Go) | code-as-schema | bubbletea | WithHide, group sequencing | Validate | yes, *Func bindings | accessible mode | MIT | very active | n/a (Go) |
| react-jsonschema-form (JS) | JSON Schema | React widgets | none built-in | JSON Schema | via ui:options + JSON Schema if/then/else | custom widgets | Apache-2.0 | very mature | n/a (browser) |

Fit-for-our-use-case scale: 5 = directly applicable, 1 = inspiration only.

### 3. candidate design patterns

#### pattern A: questionary-compiled-from-pydantic

- Use the existing Profile / SetupAnswers Pydantic v2 models as the
  authoritative schema; the wizard never declares fields a second
  time.
- Walk model.model_fields and emit a list of dicts in questionary
  format: str -> text, bool -> confirm, Literal/Enum -> select,
  Path -> text with path-existence validator, etc.
- Use Field(json_schema_extra={...}) (or a small custom annotation,
  e.g. Annotated[str, Prompt(when=lambda a: a["regime"] == "iva")])
  to carry the questionary when lambda, custom message, and override
  the auto-derived widget.
- Validation goes through a single validate= thunk that does a
  partial model_validate({**answers, key: value}) - every keystroke
  trip is checked by pydantic, not by ad-hoc helpers.
- Leans on: questionary.prompt, pydantic v2 model_fields
  introspection, Annotated metadata convention (mirrors how
  tyro.conf.* and pydantic-settings CliSubCommand attach CLI-only
  metadata).

#### pattern B: FSM + per-question prompter, schema as field registry

- Keep the existing Prompter Protocol (the TyperPrompter /
  QueuedPrompter split is already correct).
- Add a FieldDescriptor model (pydantic, of course) listing name,
  widget, prompt, default_from, validate_from, visible_when,
  generated by walking the source Pydantic schema.
- Drive the descriptor list through python-statemachine: each
  FieldDescriptor is a state, when predicates become cond= guards
  on transitions, the FSM gives back-navigation, retry-on-validate,
  and a single canonical event loop testable without any TUI library.
- Render via any prompt backend (rich.prompt, typer.prompt,
  questionary per-question, even pure input()) - the FSM is
  rendering-agnostic.
- Leans on: python-statemachine guard semantics, the huh
  Form -> Group -> Field mental model (groups become FSM
  macrostates), the existing Prompter Protocol that already proves
  rendering can be inverted.

#### pattern C: YAML wizard schema, Pydantic answers

- Borrow copier.yml shape outright: a YAML file (or an embedded
  Python WizardSpec model) lists questions with type, default, when,
  validate, secret, multiline. The wizard runtime consumes the
  spec; the Pydantic profile is reconstructed from the collected
  answers at the end.
- Separates wizard-flow concerns (order, conditionality, prompt
  text, i18n) from data-model concerns (validation, persistence,
  domain invariants). The setup-wizard team edits a YAML file when
  questions change; the schema team edits the Pydantic model when
  fields change; they meet at the answer-collection boundary.
- The schema source is the YAML spec, but the validation source
  remains pydantic - so the wizard can never accept an answer set
  the Profile model would reject.
- Leans on: copier decade-deep evidence that YAML-driven wizards
  scale, react-jsonschema-form field-type -> widget taxonomy (table
  above) as the closed list of allowed widgets, pydantic-settings
  for env-fallback so the YAML spec can declare env_fallback:
  AEAT_FOO per question.

### 4. cross-cutting observations

- No mainstream Python tool does what we want end-to-end. Every
  candidate either skips the prompt loop (pydantic-settings, tyro,
  clipstick, cyclopts) or skips the Pydantic-as-source-of-truth half
  (questionary, rich, copier). The win is in the adapter layer -
  whichever pattern we pick, we are writing a small bridge.
- Annotated[T, ...] metadata is the canonical Python way to carry
  CLI/prompt extras without polluting the domain model. Both
  pydantic-settings (CliSubCommand, CliPositionalArg, CliImplicitFlag)
  and tyro (tyro.conf.* markers) ride on it. Whatever we build
  should follow that grain.
- questionary when lambda is the de-facto standard for conditional
  questions in Python CLIs. Even tools that do not use questionary
  directly (e.g. copier) re-implement the same predicate shape.
  Picking the same vocabulary for aeat future-proofs us.
- The widget taxonomy idea from react-jsonschema-form translates
  cleanly to CLI. A finite enum of widget kinds (text, password,
  confirm, select, checkbox, path, multiline) is small, closed,
  testable, and matches the questionary surface 1:1. We can declare
  the taxonomy as a StrEnum and pin every field descriptor to one.
- Escape hatches matter. Every mature schema-driven wizard (copier,
  cookiecutter, huh) added an imperative escape hatch after launch -
  Jinja templates, pre/post hooks, raw callbacks. Any pattern we
  adopt has to admit one explicit drop-to-imperative seam per wizard
  run, or the abstraction will fight the user the first time AEAT
  changes a question shape.

### 5. risks and unknowns

- Pydantic v2 introspection drift. model_fields, field_info.metadata,
  and json_schema_extra are stable but evolving - patterns A and B
  both depend on this surface. A v2 -> v3 jump (not on the immediate
  horizon) would require revisiting the adapter.
- Discriminated unions and recursive models. The current Profile is
  flat, but if it grows discriminated-union fields (e.g. Regime =
  IVAGeneral | IVARecargo | NoIVA), the wizard needs to branch on
  the discriminator. Questionary when handles it syntactically; the
  FSM pattern handles it as a guard; the YAML pattern needs a
  discriminator: regime directive. None of the candidates make this
  hard but each makes it differently.
- i18n at the prompt boundary. aeat runs trilingual. Embedding raw
  prompt strings in the Pydantic schema couples i18n to the domain
  model; embedding them in a YAML spec leaves the domain model
  clean. This is a real trade-off, not a tooling gap.
- Test ergonomics. The current QueuedPrompter is excellent because
  it is dumb. Any schema-driven layer must preserve the property
  that a unit test feeds a list of typed answers and asserts the
  final pydantic object - patterns A and B preserve this trivially,
  pattern C preserves it only if the YAML loader is hermetic.
- No prior art for Typer command surface generated from schema that
  also drives interactive prompts. Every tool in the table picks one
  half. The win is novel; the risk is that we land on a custom
  abstraction nobody else uses, which has long-term maintenance
  cost. Mitigation: the abstraction has to be small, in-tree, and
  obviously a thin wrapper over questionary / rich.prompt / pydantic
  - never a framework.
- Over-abstraction trap. Schema-driven wizards become harder to read
  than hand-rolled wizards once the schema expressive power outruns
  the domain actual irregularity. The current SetupAnswers is small
  enough that any of the three patterns is overkill if we only ever
  have ten or so fields. Pattern selection should be informed by the
  expected growth curve of profile fields over the forthcoming
  filing-engine work, not just the present cardinality.

### 6. external sources

- questionary docs - advanced concepts, prompt(), when, validators:
  https://questionary.readthedocs.io/en/stable/pages/advanced.html
- questionary repo: https://github.com/tmbo/questionary
- pydantic-settings CLI parsing, CliApp, CliSubCommand,
  cli_parse_args, nested models:
  https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
- clipstick (Pydantic v2 to CLI):
  https://github.com/sander76/clipstick
- pydantic-cli: https://github.com/mpkocher/pydantic-cli
- tyro (configs-as-dataclasses): https://brentyi.github.io/tyro/
- cyclopts vs typer comparison:
  https://cyclopts.readthedocs.io/en/latest/vs_typer/README.html
- copier configuring guide (YAML question schema, when, validators,
  Jinja defaults):
  https://copier.readthedocs.io/en/stable/configuring/
- cookiecutter choice variables and Jinja conditionals:
  https://cookiecutter.readthedocs.io/en/stable/advanced/choice_variables.html
- charmbracelet/huh (Go) - Form to Group to Field, WithHide,
  OptionsFunc: https://github.com/charmbracelet/huh
- react-jsonschema-form widget taxonomy:
  https://rjsf-team.github.io/react-jsonschema-form/docs/usage/widgets/
- prompt_toolkit full-screen apps / widgets:
  https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html
- rich.prompt: https://rich.readthedocs.io/en/stable/prompt.html
- python-statemachine (guards, statecharts, processing model):
  https://python-statemachine.readthedocs.io/
- pytransitions/transitions FSM:
  https://github.com/pytransitions/transitions
- AlecAivazis/survey (Go, archived - design lessons):
  https://github.com/AlecAivazis/survey
- npm/promzard (npm init prompt module):
  https://github.com/npm/promzard
- poetry init internals (DeepWiki summary):
  https://deepwiki.com/python-poetry/poetry/6.3-project-initialization
- AWS CLI aws configure sso wizard reference:
  https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html
