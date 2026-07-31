---
tags:
  - '#research'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:931fa7cdb1f5693a4c10a4b9e7cf817025eff27c77a92b815db06816c8b823a3'
related: []
---

# `docs-cli-sequences` research: `interactive executed CLI sequence docs`

Research toward replacing the static CLI code blocks in the user docs with
dynamic, interactive, build-time-executed "sequence" demonstrators: Jupyter-style
step-through playback of command→output frames, rich token-level syntax
highlighting, hover `--help` on verbs, and a build engine that executes every
documented command against the live CLI so a wrong writeup fails the build.
Two research passes were run: an external landscape survey (2026 state of the
art) and an internal infrastructure grounding pass over the docs build, the
conformance gates, the CLI-surface introspection tooling, the execution
sandbox substrates, and the frontend constraints.

## Operator requirements (MUST criteria)

- Rich syntax highlighting of CLI commands, tokenized against the real CLI
  grammar (verb, subcommand, option, argument, value) — not generic bash
  highlighting.
- Custom hover states: hovering a verb/subcommand token displays that command
  path's `--help` directly, sourced from the live CLI surface.
- Every CLI box carries playback controls, an output display, and
  next/previous navigation stepping command → output → next command → output
  → final result.
- Internal terminology: a series of CLI commands is a "sequence" (not
  user-facing). Every sequence MUST be capped by a "sequence result" — an
  abstract closing frame that demonstrates or verifies the sequence worked.
  User-facing framing is verification guidance ("to verify the calculation is
  correct…"), teaching the user how to check their own results.
- Every CLI block is testable: the docs source is parsed directly, every
  command executes as part of its sequence, and the declared verification
  result must be the real output. A wrong writeup is a build failure — the
  docs are a correctness gate.
- Authoring stays in md/rst (possibly ordinary bash code blocks) with a build
  engine that parses commands against the live CLI and captures output, help,
  and args at build time.

## Findings

### The gap is real and precisely bounded

The ~35 how-to guides under `docs/how-to/` show commands in plain ` ```bash `
fences (no prompt prefixes; `highlight_language="console"`; copybutton strips
prompts) and describe output in prose only. There are zero captured
command→output transcript frames and zero rendered JSON envelopes anywhere in
the docs. `docs/tutorials/` holds only an index page — the step-by-step
instructional surface is thin. The existing conformance gate
(`src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`)
is regex-based: it validates that documented verb paths resolve in the live
in-process Click tree and that cited `--option` tokens are real params, but it
never executes commands, never checks output, and never checks option values.
Nothing today asserts documented output equals real output.

### Naming context

The Python package was renamed `aeat` → `cadrumo`; the human CLI executable
remains exactly `aeat`; env vars are `CADRUMO_*`; the docs brand is "Cadrumo".
New tooling imports `cadrumo`, invokes `aeat`, uses `CADRUMO_*`.

### External landscape (2026)

No existing tool covers the whole requirement; the combination of discrete
step navigation plus token-level hover-help is a genuine gap. The problem
decomposes into three layers:

Terminal playback/rendering components: asciinema-player is a raw ANSI byte
replayer with time-scrubbing only and is GPL-3.0 — excluded. termynal (MIT,
~unmaintained) is the closest render skeleton: line-by-line scripted playback
in plain HTML/CSS/tiny JS, zero dependencies, degrades without JS. Shiki (MIT)
is the strongest build-time tokenizer producing styled spans; Expressive Code
(MIT) has the best terminal-framed visual language. Astro
Starlight/Docusaurus/Fern/Mintlify components are wrong-stack (React/MDX)
design references only. None provide hover-help or discrete step navigation.

Executable/tested documentation engines: tesh (MIT) executes ` ```console `
blocks as real shell sessions and fails the build on output mismatch; its
session command/output-pair model matches the step-frame model. Sybil (MIT)
parses fenced blocks in md/MyST/reST inside pytest with fixtures; one custom
parser can both verify and emit capture JSON in a single pass. Sphinx doctest
and sphinx-exec-code are Python-centric; byexample supports shell but its
licence was not verified — excluded pending verification; runme.dev is a
runnable-markdown VS Code product, not a strict gate; MyST-NB/Jupyter Book
execute bash cells and store structured per-cell outputs but require a
different build system — highest switching cost, rejected.

CLI-help-as-data: Click 8+ `Context.to_info_dict()` walks the entire command
tree (commands, subcommands, options, arguments, help strings) as structured
data, explicitly intended for documentation generators. Typer is Click
underneath (`typer.main.get_command(app)`).

Sphinx integration: a custom directive plus `builder-inited`/`build-finished`
hooks plus inlined JS/CSS/JSON (raw HTML nodes / data attributes) is a small,
well-trodden path; no existing extension provides a stepped hover-help
terminal, so that layer is bespoke regardless.

### Internal infrastructure (decisive: most of the stack already exists)

Docs build: Sphinx + Furo + MyST, orchestrated by `dev/docs/build.py`
(changed-page-aware incremental builds; strict `-n -W` nitpicky gate;
`CADRUMO_DOCS_OFFLINE=1` hermetic with vendored inventories). Generated
surfaces (`docs/cli/*.rst`, glossary, api stubs, Pagefind index) are built at
build time, gitignored, never committed, wired via `docs/conf.py` `setup()`
`builder-inited` hooks. The build already imports the app and sandboxes
storage via `ensure_isolated_storage_root()`.

Execution sandbox (strongly feasible, harness exists):
`src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py` already runs the
full readiness→create→calculate→verify→export chain in-process with real
KEK/DEK encrypted SQLite, no mocks, no live AEAT. Reusable primitives:
`invoke_cached_cli(args)` in `src/cadrumo/tests/cli_runner.py` (cached Click
tree via `CliRunner`, accepts `env=` and `input=`) and
`isolated_profile_storage_root()` in `src/cadrumo/tests/secure_sql.py` (real
`bucket-dek-v1` bucket, `EphemeralMasterKeyProvider`, isolated storage root
under `override_settings`).

Determinism substrate (implemented, accepted ADR
`2026-06-30-deterministic-output-replay-substrate-adr`): clock seam
`cadrumo.core.time.frozen_clock`; caller-injectable `profile_id`;
`cadrumo.core.observability` capture/compare primitives (`capture_envelopes`,
`replay_run`, `assert_golden_match`, `canonicalise`, `mask_document`,
`GOLDEN_MASK_FIELDS`, `differing_paths`). This is exactly the "execute and
fail on output mismatch" machinery. Known honesty hazard: the mask set must
equal exactly the residual nondeterministic field set, with an anti-tautology
proof.

CLI-surface-as-data (already solved in-house): `dev/docs/cli_reference.py`
pins `CADRUMO_OUTPUT_LANGUAGE=en`, materialises lazy subtrees
(`_force_lazy_imports`), collects `{path_tuple: click.Command}` for every
group and leaf (`_collect_commands`), and extracts per-option
help/required/kind (`_render_param_table`). Help text originates from `tr()`
locale keys in `src/cadrumo/locales/{en,es,ca,hu}.yml`. Emitting a
`cli-tree.json` projection from this gives tokenization and hover-help
correct-by-construction, plus a free gate: a documented command path that no
longer resolves fails the build.

Frontend constraints: fully self-contained/offline — everything vendored
under `docs/_static/` (mermaid, d3, woff2 fonts, `cadrumo-docs.css`, and the
framework-free 23 KB `cadrumo-docs.js` which already ships a Ctrl/Cmd-K
command palette). The new widget must be vendored, framework-free, no
external requests. Search is post-build Pagefind (gitignored, regenerated)
with a `SearchRecord` injection seam in `dev/docs/pagefind_inject.py`.

Prior vault decisions that constrain or enable this feature:
`2026-06-01-docs-cli-buildtime-adr` (CLI reference is a build-time projection
of the live tree — direct philosophical precedent),
`2026-06-01-docs-educational-surface-adr` (single-source conformance;
redeclaration is the central risk — generated output, never hand-authored),
`2026-05-30-docs-architecture-adr` (three-surface taxonomy; instructional
surface deferred), the docs-terminology-search ADRs (Pagefind licence-clean
shipping and commit boundary), `2026-06-14-docs-tooling-separation-adr`
(tooling lives under `dev/docs/`), and the user-docs-hardening rules
(imperative single-step voice). No prior ADR proposes executed or interactive
transcripts — this feature is greenfield on mature substrates.

## Candidate architectures

Option 1 (recommended by both passes, adjusted by the internal findings):
bespoke-but-thin build executor over the in-house substrates
(`invoke_cached_cli` + `isolated_profile_storage_root` + `frozen_clock` +
`cadrumo.core.observability` golden-match) instead of adopting tesh/Sybil;
`cli-tree.json` projected from `dev/docs/cli_reference.py` for
tokenization/hover-help; a bespoke Sphinx/MyST directive binding executed
frames + CLI tree into an inlined, self-contained, framework-free stepped web
component extending `docs/_static/cadrumo-docs.js` (termynal/Expressive Code
as MIT design references). Rationale: envelope-level (not string-level)
comparison, anti-tautology discipline preserved, no new third-party execution
dependency, and the in-house substrates were purpose-built for this.

Option 2: Sybil-based parsing/verification inside pytest with a custom parser
that emits the capture JSON in the same pass; same help layer and frontend.
Choose only if directive-driven build-time execution proves awkward — costs a
dependency and a second comparison model.

Option 3: MyST-NB notebook capture — rejected (different build system,
Jupyter kernel dependency, weaker gate semantics, highest switching cost).

## Hard constraints for the ADR

- Never contact live AEAT; `CADRUMO_LIVE_TESTS_ENABLED` stays off; sequences
  build/verify/export only, never submit.
- Golden fixtures carry synthetic data only; sensitive financial data never
  leaves secure storage.
- Heavy generated artifacts are gitignored and regenerated at build; commit
  only light golden frames (Pagefind commit-boundary pattern).
- Output is generated, never hand-authored (single-source conformance).
- Mask-set honesty: masked fields must equal exactly the residual
  nondeterministic set, with an anti-tautology proof.
- Frontend is vendored, framework-free, self-contained; the nitpicky `-n -W`
  offline gate stays green.
- The new sequence fence/directive syntax must stay compatible with the
  existing documented-command conformance regex, or that gate must be taught
  the new format in the same change.
- Licence hygiene: asciinema-player (GPL-3.0) and byexample (unverified) are
  excluded; termynal, Shiki, Expressive Code, tesh, Sybil are
  MIT/BSD/Apache-clean as references or dependencies.

## Open decisions for the ADR

- Authoring syntax: bespoke MyST directive vs annotated ` ```bash ` fences,
  and how sequence boundaries, setup/fixture frames, and the sequence-result
  frame are declared.
- Golden-frame storage format and commit boundary (committed light frames vs
  fully regenerated at build; drift-refresh workflow).
- Comparison policy: JSON envelope golden-match vs rendered-text match, per
  frame kind; treatment of human-readable (non-JSON) CLI output.
- Sequence-result contract: what qualifies as a verification frame and how it
  is narrated user-facing.
- Frontend component contract: data payload shape inlined per sequence, hover
  help keying, step/playback semantics, degradation without JS.
- Sandbox seeding: how each sequence declares its fixture ledger/profile
  state, and whether sequences share or isolate sandboxes per page.
