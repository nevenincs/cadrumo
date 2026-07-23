---
tags:
  - '#research'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `tui-wizard-substrate` research: `paged TUI wizard substrate`

The operator wants the interactive profile-setup experience replaced by a rich,
paged TUI in which every question is a full page (prompt, grounding help,
accepted values, format hints, failure modes, live validation, current-answer
echo) with forward/back/jump navigation, a review/summary surface, per-question
reset, whole-flow restart, and checkpoint/resume. None of these capabilities
exist today. This research grounds two questions for the substrate stream: what
does the canonical wizard already provide that a substrate must preserve or
absorb, and what is the option space for the paged-interaction architecture and
its rendering layer. The evidence favors a renderer-agnostic flow engine in the
application layer with a full-screen frontend; the rendering-library choice
needs an external survey (in flight) before the ADR can finalise it.

## Findings

### The canonical wizard is a forward-only, single-pass walk

The runtime `run_flow` (`src/cadrumo/application/wizard/_runner.py:122`)
iterates sections and questions strictly in declaration order, asking each
visible question exactly once: it evaluates `visible_when` incrementally,
calls `prompter.ask(question, default=...)`, validates, accumulates a
canonical-token dict, and returns the typed answers model. There is no cursor,
no history, no way to return to an earlier question, no summary view, and no
mid-flow persistence: an operator who mistypes question 3 of 12 and notices at
question 10 can only abort and start over, losing every answer. Checkpoint or
resume state does not exist anywhere in the package
(`src/cadrumo/application/wizard/_persistence.py` persists only *completed*
answer sets into the profile).

### The prompter contract is one-shot and line-oriented

`Prompter.ask` (`src/cadrumo/application/wizard/_prompter.py:82`) is a
one-question-in, one-canonical-token-out protocol. The module docstring pins
the shipping implementations to exactly two — `CanonicalAnswerPrompter`
(scripted, non-interactive) and `QuestionaryPrompter` (live, one `questionary`
primitive per widget) — a deliberate single-authority stance after a third
drifted prompter copy shipped in the CLI and was retired (see
`aeat-rag-discovery-mandatory` rule narrative). The one-shot shape is the
structural ceiling: `questionary` renders a prompt, blocks, returns, and the
screen scrolls on. Back-navigation, a persistent page layout, jump-to-question,
and a review screen cannot be expressed through a sequence of independent
one-shot prompts; they require an application-style event loop owning the
screen.

### What the current stack does well and must be preserved

Several disciplines in the existing package are load-bearing and should carry
into any substrate rather than be reinvented:

- **Declarative, frozen flow descriptors.** `WizardFlow` / `WizardSection` /
  `WizardQuestion` / `WizardChoice` / `WizardCondition`
  (`src/cadrumo/application/wizard/_models.py`) are strict frozen pydantic v2
  records; the descriptor is the single source of truth read by the runtime,
  the Typer command factory, and the profile-key projection. Build-time
  model validators enforce unique question ids, forward-only `visible_when`
  references, and the `wizard.<flow-id>.` translation-key prefix.
- **Canonical-token answer plane.** All answers travel as canonical strings
  (`"true"`/`"false"`, comma-joined checkbox sets, decimal-normalised
  integers), with typed parsing at the boundary
  (`_persistence.py:_parse_canonical`), including a deliberate three-state
  treatment of optional CONFIRMs (blank ≠ declared-false).
- **Widget-level validators with i18n message keys.**
  `validate_widget_answer` (`src/cadrumo/application/wizard/_widgets.py:241`)
  dispatches a closed `WizardWidget` StrEnum onto pure validators that raise
  `WizardValidationError` carrying translation keys and *redacted* context
  (raw operator answers are never carried into diagnostics — significant for
  tax-id and secret answers).
- **IO-injection and headless drive.** `QuestionaryPrompter` binds to
  `prompt_toolkit`'s app-session IO contract
  (`_prompter.py:from_ambient_app_session`), which is how the headless test
  harness drives the live flow through a pipe. The non-TTY / Windows
  `NoConsoleScreenBufferError` refusal is translated, not a traceback.
- **Patch-vs-create persistence split.** `persist_answers` distinguishes the
  `create` full-set registration from the `edit` patch scoped to explicitly
  supplied question ids (`_persistence.py:94`), so editing one field never
  reverts others to defaults.

### The gap between operator requirements and the current shape

Mapping the operator's requirement list onto the code: understanding aids
exist only as an optional one-line `help` key rarely rendered
(`WizardQuestion.help`); accepted-value surfacing exists only implicitly
through `questionary.select` choice lists; format/structure hints and
failure-mode descriptions have no descriptor slot at all; invalid input is
surfaced only *after* submit as a raised error that (in the current CLI
wiring) aborts rather than re-prompts; answer review, modification,
backward navigation, jump, reset, restart, and checkpoint have no mechanism.
The conclusion is structural, not incremental: the missing capabilities all
require a stateful flow engine with a navigable cursor and a screen-owning
frontend, which the one-shot prompt architecture cannot grow into.

### Option space: where the paging/navigation logic lives

Two architectures were weighed:

1. **Frontend-owned flow (wizard logic inside a TUI app).** The TUI framework
   drives; questions become framework screens directly. Rejected on evidence:
   it welds domain-agnostic flow semantics to one rendering library, leaves
   the non-interactive (`--quiet`/flags) path and the headless tests to
   re-implement branching and validation (the disconnected-surface drift class
   the codebase repeatedly pays for, cf. the pull-vs-calculate parity rule),
   and violates the hexagonal split (application logic in an adapter).
2. **Renderer-agnostic flow engine + thin frontends.** A pure state machine in
   the application layer owns the flow state (answer map, cursor, visit
   history, per-question validation results) and exposes typed transitions
   (`answer`, `next`, `back`, `jump`, `reset`, `restart`, `checkpoint`);
   frontends — full-screen TUI, plain line fallback, scripted/non-interactive
   driver — project the state and dispatch intents. This is the shape the
   existing code is already half-way to (declarative descriptor + swappable
   prompter), generalised from "answer source" to "interaction frontend". It
   keeps exactly one authority for flow semantics, which is the durable answer
   to the third-prompter incident class.

The evidence strongly favors option 2; the ADR must settle its exact contract.

### Option space: rendering layer for the full-screen frontend

Candidates: Textual (full application framework: screens, focus, reactive
widgets, CSS-like styling, headless `Pilot` test driver; new direct
dependency), prompt_toolkit full-screen `Application` (already a transitive
dependency via `questionary`; low-level — layout, widgets, and focus handling
largely hand-built), urwid (mature but aging API, weaker Windows story), and
Rich alone (rendering only, no input/event loop — insufficient by itself).
Windows behaviour is a first-class constraint: the codebase already carries
translated refusals for `NoConsoleScreenBufferError` under git-bash
(`_prompter.py:29`), and any candidate must degrade to the line-mode frontend
on such hosts. A scoped external survey (paging/back-jump support, keystroke
validation, headless testing, Windows Terminal/conhost/git-bash behaviour,
dependency weight and health, i18n/wide-char rendering, coexistence with the
existing prompt_toolkit pin) has been requested from the coordinator's
research track; its outcome resolves the rendering decision without changing
the engine architecture, which is deliberately insulated from it.

### Dependency verdict for the rendering candidates

Settled from this worktree's `pyproject.toml` + `uv.lock` and PyPI metadata
(coordinator-grounded, 2026-07-23) after the delegated external survey
stalled without a deliverable. The repo already ships
`prompt_toolkit@3.0.52` (pinned `>=3.0,<4`), `questionary@2.1.1`
(`>=2.1.1,<3`), and `rich@15.0.0` (`>=14.2.0,<16`); neither Textual nor
urwid is present. `textual@8.2.8` is MIT-licensed, requires Python
`>=3.9,<4`, and depends on `rich>=14.2.0` (uncapped — satisfied by the
repo's 15.0.0), `markdown-it-py`, `platformdirs`, and `typing-extensions`;
it does not depend on prompt_toolkit. Textual therefore adds cleanly with
no version conflict against the existing rich/questionary/prompt_toolkit
set — the rich-pin-collision risk is empirically absent. The
prompt_toolkit full-screen alternative costs zero new dependencies and is
the stack the existing translated no-console refusal already lives on, but
its full-screen mode supplies only a low-level layout/widget layer that a
paged wizard would have to hand-build. urwid adds a dependency with no
coexistence benefit; Rich alone has no input layer and is not viable. The
decision axis thus reduces to Textual's application/widget/testing model
(one clean MIT dependency) versus prompt_toolkit's zero-new-dependency,
hand-built-widget path.

### Checkpoint state is sensitive data

Profile-setup answers include NIF/NIE identifiers, addresses, family facts,
and regime declarations. A checkpoint file on disk is therefore not a
neutral cache: under `sensitive-financial-data-secure-storage-only`, any
persisted in-progress answer set belongs in the encrypted secure-object
substrate (`SecureObjectRepository` via the bucket-scoped wrappers), never a
plaintext scratch file. A checkpoint written before a profile bucket exists
(the `create` flow's cold start) needs an owning storage location decided in
the ADR. Resume-across-definition-change also needs a stance: flows evolve,
and a stale checkpoint must re-validate rather than blindly rehydrate.

### Reconciliation against the profile-integration grounding map

A 96-agent discovery swarm (`rg`/direct-read, RAG unavailable) produced a
profile-integration shape map (coordinator scratchpad artifact
`profile_shape_map.md`, 2026-07-23) whose §3–§6 bear directly on this
stream. Verdicts relevant to the substrate:

- **Single wizard authority CONFIRMED.** Exactly one catalogue
  (`SETUP_FLOW`/`WIZARD_FLOWS`) and one key-uniqueness registry
  (`compile_profile_keys` → `register_profile_keys`/`ProfileKey`,
  `domain/contribuyente/_keys.py`, duplicate keys rejected at compile,
  `_compiler.py:54`); no second prompter/catalogue exists. The compiler
  also projects conditional requirements (`required_when_*`) from
  `visible_when` gates — a substrate engine must keep feeding this
  projection.
- **No checkpoint object exists today.** The closest analogue is
  `persist_patch`/`set_active_fields` writing partial edits directly into
  the live encrypted `UserProfileRecord`; there is no separate
  draft/staging store. Critically, `TaxpayerProfile`'s cross-field legal
  validators (impatriado start date, non-resident country, representante
  fiscal) fire at full-model construction via
  `taxpayer_profile_from_mapping` — partial fact sets must never be
  promoted through that constructor, and readiness gates
  (`build_wizard_status`, `require_profile_ready_for_modelo_work`) are
  what keep an incomplete profile non-usable downstream.
- **Copy-assembly corpus leg unsupported.** The schema↔locale leg is real
  and gate-enforced (`schema.toml` field definitions with
  `legal_refs`/`export_headers`; `wizard.setup.profile.<profile_key>.*`
  keys across all four catalogues under the parity/honesty gates; the
  wizard's own `audit_wizard_translations` sweep in `_translations.py`).
  No site assembles wizard question copy from the BOE/AEAT legal corpus
  (`_data/corpus/normatives/html/`) — that corpus grounds registry
  *calculation* `legal_refs`, not question text.
- **Binding write-path constraints.** `ProfileLifecycleService` is the
  sole mutation writer (event co-emission pinned by
  `test_event_emission_contract.py`); the persisted shape is
  effective-dated `UserProfileFact` rows under the `schema.toml`
  authority; apoderamiento is a separate encrypted namespace
  (`ApoderadoService`), not a profile fact; the active-profile pointer
  has a single transacted writer.
- **Raw per-domain maps add four substrate-relevant contract facts**
  (from the full per-domain synthesis `profile_domain_maps.md` and its
  underlying raw site lists, reviewed directly): (1) the wizard feeds two
  *core registration slots* so lower layers never import the application
  package upward — `register_wizard_catalogue` receives the flow
  descriptors (`_catalogue.py:1050`) and `register_project_answers`
  receives the reverse projection (`_persistence.py:250`), consumed by
  `taxpayer_profile_from_mapping` and calc binding resolution; any
  substrate definition model must keep feeding both slots. (2)
  `verify_setup_answers` (`_verifier.py`) is a separate cross-field
  consistency gate (spouse/joint-taxation/monoparental checks, LIRPF
  Art. 82 grounded) distinct from the ProfileKey requirement registry —
  a consolidating redesign can silently drop one class while keeping the
  other. (3) `ProfileValidationService` validates every fact against
  `ProfileSchemaDefinition` before persistence, and the pointer file has
  a single reentrant transacted writer
  (`active_profile_pointer_transaction`); delete is soft-tombstone,
  never hard-delete. (4) The `TaxpayerProfile` derivation surface is one
  layered coercion path, not two parallel ones:
  `load_active_taxpayer_profile` (`_status.py`) delegates through
  `projection_for_taxpayer` into `taxpayer_profile_from_mapping`. One
  genuine bypass did exist — `application/state_projection.py` built the
  model from a selector-keyed mapping while the authority feeds path
  keys, and `taxpayer_profile_from_mapping` reads a mix of both key
  spaces (the fiscal-address family via its `model_selectors` alias) —
  silently blanking the aliased family on one path and dropping
  path-keyed facts on the other. Fixed under the profile-setup-flow
  plan (commit `bc794c9699`): the authority's record branch now merges
  both key spaces disjoint-by-construction and the state projection
  delegates to it, locked by real-behavior regressions. The substrate
  must not add a derivation path of its own. The locale map also confirms
  the `profile` root is allowlisted in `_DYNAMIC_TRANSLATION_ROOTS`
  (dynamic keys invisible to static scanning — scaffold/audit must run
  explicitly on any question set change) and that `tema-profile.toml` is
  a `draft`, uncurated concept: no taxpayer-facing profile glossary
  entry ships today.
- **Wizard internals now fully read.** The map flagged the wizard package
  as its least-traced surface; this stream has since read every module in
  full (`_catalogue.py` end-to-end — 11 sections, ~70 profile-bound
  questions, no descendant collection in the flow (descendants ride a
  separate CLI verb and dedicated fact serializers) — plus `_status.py`,
  `_compiler.py`, `_verifier.py`, `_translations.py`, and the previously
  read core). One map detail did not verify: no
  `save_answers_to_profile` symbol exists in `_persistence.py`; the real
  writers are `persist_answers`/`persist_patch`.

### Not investigated

An exhaustive feature-level framework comparison (per-keystroke validation
ergonomics, wide-char/i18n rendering fidelity, terminal-emulator matrix)
was not produced — the delegated survey stalled and the decision proceeded
on the dependency verdict above plus the frameworks' documented
capability models; the modelo work wizard
(`entrypoints/cli/_modelo_work_wizard_cli.py`) beyond confirming it consumes
the same prompter surface; terminal-capability detection specifics per
platform; accessibility/screen-reader behaviour of candidate frameworks.
vaultspec-rag semantic sweeps were attempted but the service returned
persistent HTTP 500s during this pass (server up, search failing); grounding
here is from full-file reads of the canonical wizard package, which the
dispatch brief named as the authoritative surface.

## Sources

- `src/cadrumo/application/wizard/_runner.py:122` — forward-only walk.
- `src/cadrumo/application/wizard/_prompter.py:82` — one-shot `Prompter`
  protocol; module docstring pinning exactly two implementations;
  `from_ambient_app_session` IO-injection; `NoConsoleScreenBufferError`
  handling at `:29` and `:51`.
- `src/cadrumo/application/wizard/_models.py` — frozen descriptor records and
  build-time validators.
- `src/cadrumo/application/wizard/_widgets.py:241` — validator dispatch;
  redacted diagnostics at `:69`.
- `src/cadrumo/application/wizard/_persistence.py:94` — create-vs-edit
  persistence split; `:226` three-state CONFIRM parsing.
- `src/cadrumo/application/wizard/_catalogue.py` — import-time-pure flow
  catalogue; `src/cadrumo/application/wizard/_commands.py` — Typer command
  factory deriving flags from the descriptor.
- General-knowledge claims about Textual, prompt_toolkit full-screen, urwid,
  and Rich capabilities are unverified pending the delegated external survey.
