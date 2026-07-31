---
tags:
  - '#plan'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:aa42e746fac180a06703aba2fa1e1a43f2ae4a60783b7a2caa0f7f7226e266b9'
tier: L3
related:
  - '[[2026-07-13-docs-cli-sequences-adr]]'
  - '[[2026-07-13-docs-cli-sequences-research]]'
---

# `docs-cli-sequences` plan

## Wave `W01` - static conformance floor

Repair the rename-swept documented-command conformance gate so it scans real aeat invocations again, and burn down the latent doc defects the vacuous gate has been missing. Independent of every later wave; the honest static tier is the floor the executed tier stands on. Backed by ADR ruling D7 prerequisite zero.

### Phase `W01.P01` - repair the conformance token regex and burn down surfaced defects

Re-anchor the invocation-token regex on the aeat executable, re-run the gate to surface latent defects, fix them, and verify a green static tier.

- [x] `W01.P01.S01` - Re-anchor the invocation-token regex on the real aeat executable so documented aeat invocations are scanned again, fixing the rename-sweep vacuity; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [x] `W01.P01.S02` - Re-run the repaired conformance gate and capture the full inventory of latent verb-path and option-name defects it now surfaces; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [x] `W01.P01.S03` - Triage and fix every documented-command defect the repaired gate surfaces across the how-to, tutorial, explanation, and runbook doc pages; `docs/how-to`.
- [x] `W01.P01.S04` - Verify the full documented-command conformance gate passes green and pytest collect-only is clean; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Wave `W02` - execution engine under dev/docs/sequences

The one hermetic execution engine: frame-grammar parser, per-sequence sandbox runner, golden store and comparison, and the refresh/check CLI plus anti-tautology gate. Foundation for both downstream build gates. Depends on W01 landing the honest static floor. Backed by ADR rulings D1, D2, D3, D4, D6.

### Phase `W02.P02` - directive-body frame grammar parser

Parse the cli-sequence body into ordered frames with capture, expect, setup, result, and placeholder semantics, enforce the one-terminal-result contract, and inline seed recipes.

- [x] `W02.P02.S05` - Implement the frame-line parser for the cli-sequence grammar (visible aeat frames, @setup, @result, @capture, @expect, and {name} interpolation); `dev/docs/sequences/_parser.py`.
- [x] `W02.P02.S06` - Enforce the sequence-result contract at parse time, refusing a sequence with zero, multiple, or non-terminal @result frames; `dev/docs/sequences/_parser.py`.
- [x] `W02.P02.S07` - Implement :seed: recipe inlining that prepends a shared @setup fragment from the named seed file before the sequence's own frames; `dev/docs/sequences/_seeds.py`.
- [x] `W02.P02.S08` - Write parser unit tests covering grammar acceptance, every refusal case, capture and expect binding, and seed inlining; `dev/docs/sequences/tests/test_parser.py`.

### Phase `W02.P03` - per-sequence hermetic sandbox runner

Execute each frame in a fresh isolated storage root under frozen clock and injected profile id through the cached in-process Click tree, threading captured values into later frames.

- [x] `W02.P03.S09` - Implement the per-sequence sandbox runner (fresh isolated_profile_storage_root, frozen_clock, injected profile_id, English output, live tests off, invoke_cached_cli per frame); `dev/docs/sequences/_runner.py`.
- [x] `W02.P03.S10` - Implement @capture value threading that parses a frame's JSON envelope, binds the json-path, and interpolates {name} into later frames; `dev/docs/sequences/_runner.py`.
- [x] `W02.P03.S11` - Write runner tests driving a real create-calculate-verify chain hermetically and asserting captured values thread through subsequent frames; `dev/docs/sequences/tests/test_runner.py`.

### Phase `W02.P04` - golden store and comparison

Read and write committed light per-sequence goldens, compare JSON frames via the central-mask observability primitives and text frames by declared narrow normalisation, and assert exit codes and semantic expectations.

- [x] `W02.P04.S12` - Implement the golden reader and writer for committed light per-sequence JSON (resolved argv, exit code, verbatim captured envelope or text, capture bindings); `dev/docs/sequences/_golden_store.py`.
- [x] `W02.P04.S13` - Implement JSON-frame comparison delegating to the observability primitives with exactly the central GOLDEN_MASK_FIELDS, refusing any per-sequence mask extension; `dev/docs/sequences/_compare.py`.
- [x] `W02.P04.S14` - Implement text-frame exact comparison with declared narrow normalisation, per-frame exit-code assertion, and @expect semantic evaluation against live output; `dev/docs/sequences/_compare.py`.
- [x] `W02.P04.S15` - Write comparison tests covering JSON match and mismatch diagnostics, text match, exit-code failure, and @expect pass and fail; `dev/docs/sequences/tests/test_compare.py`.

### Phase `W02.P05` - refresh/check CLI and anti-tautology gate

Ship the CLI-owned refresh and check modes and the executor-level mask-honesty proof, then verify the whole engine suite green.

- [x] `W02.P05.S16` - Implement the refresh CLI mode that re-executes sequences in the sandbox and rewrites the golden files, scoped by --page or --sequence; `dev/docs/sequences/__main__.py`.
- [x] `W02.P05.S17` - Implement the check CLI mode that fails with the page, sequence id, frame index, argv, differing_paths or unified diff, and the exact refresh invocation; `dev/docs/sequences/__main__.py`.
- [x] `W02.P05.S18` - Implement the executor-level anti-tautology proof that executes one representative sequence twice and asserts the pre-mask differing paths equal the central mask set exactly; `dev/docs/tests/test_sequence_goldens.py`.
- [x] `W02.P05.S19` - Verify the whole engine test suite (parser, runner, comparison, CLI, anti-tautology) passes green with no mocks or skips; `dev/docs/sequences/tests`.

## Wave `W03` - cli-tree projection, MyST directive, and two build gates

The cli-tree.json help projection, the Python tokeniser and cli-sequence MyST directive rendering server-side static frames plus inline payload, the conformance-gate grammar extension, and the two-surfaces-one-engine build hook and pytest gate. Depends on W02 engine. Backed by ADR rulings D1, D5, D6.

### Phase `W03.P06` - cli-tree.json help projection

Project the live Click tree to a gitignored cli-tree.json help catalogue reusing the existing English-pinned reference machinery, failing the build on a documented path absent from the projection.

- [x] `W03.P06.S20` - Implement the cli-tree.json projection generator reusing the English-pinned reference environment, lazy-import forcing, and per-option param extraction; `dev/docs/cli_tree.py`.
- [x] `W03.P06.S21` - Write projection tests and make a documented command path absent from the projection a hard build failure; `dev/docs/tests/test_cli_tree.py`.

### Phase `W03.P07` - Python tokeniser and cli-sequence MyST directive

Tokenise command lines against the materialised Click tree, register the backtick-fenced directive rendering server-side static frames plus inline JSON payload, and teach the conformance gate the sequence grammar and enrolled-page fence tier.

- [x] `W03.P07.S22` - Implement the Python tokeniser against the materialised Click tree, classifying executable, verb path, option, option value, positional value, and interpolated placeholder tokens with a command-path key on each verb token; `dev/docs/sequences/_tokeniser.py`.
- [x] `W03.P07.S23` - Register the backtick-fenced cli-sequence MyST directive rendering server-side static frames in document order plus one inline application/json payload per sequence; `docs/conf.py`.
- [x] `W03.P07.S24` - Teach the conformance gate the sequence grammar (strip @setup and @result sigils, treat {name} as a positional placeholder) and add the enrolled-page no-plain-executable-fence tier; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [x] `W03.P07.S25` - Write directive and tokeniser tests asserting the payload shape, token classification, and no-JS static frame HTML; `dev/docs/tests/test_sequence_directive.py`.

### Phase `W03.P08` - build-hook and pytest gate surfaces

Wire the builder-inited Sphinx check hook and the dev/docs pytest gate to the same engine functions so a divergence reds both surfaces without re-implementing execution.

- [x] `W03.P08.S26` - Add the builder-inited hook in docs conf setup running the engine check mode and emitting cli-tree.json into the static output, scoped for the incremental changed-page build; `docs/conf.py`.
- [x] `W03.P08.S27` - Wire the pytest gate calling the same engine check functions so CI catches golden drift without a full docs build; `dev/docs/tests/test_sequence_goldens.py`.
- [x] `W03.P08.S28` - Verify the docs build check surface and the pytest gate both red on an injected golden divergence and both pass green on clean goldens; `dev/docs/tests/test_sequence_goldens.py`.

## Wave `W04` - progressive-enhancement frontend widget

The vendored framework-free stepped-player enhancement over server-rendered frames: visibility toggling, prev/next/play controls, keyboard operability, hover help keyed into cli-tree.json, reduced-motion and no-JS content-identical degradation. Consumes the W03 payload contract; may begin once the payload shape lands. Backed by ADR ruling D5.

### Phase `W04.P09` - stepped-player enhancement layer

Extend the vendored framework-free widget with playback controls, hover help, keyboard and reduced-motion support, and content-identical no-JS degradation.

- [x] `W04.P09.S29` - Extend the vendored widget to parse the inline JSON payload and add frame visibility toggling, prev/next/play controls, a position indicator, and full keyboard operability; `docs/_static/cadrumo-docs.js`.
- [x] `W04.P09.S30` - Extend the vendored stylesheet with the terminal-framed visual language, the collapsed setup disclosure, and prefers-reduced-motion handling; `docs/_static/cadrumo-docs.css`.
- [x] `W04.P09.S31` - Implement the hover and focus help popover keyed into cli-tree.json via one same-origin per-page fetch, opening a verb token's live help by its command-path key; `docs/_static/cadrumo-docs.js`.
- [x] `W04.P09.S32` - Verify no-JS content-identical degradation, keyboard and reduced-motion accessibility, and the nitpicky offline -n -W gate green on a rendered sequence page; `dev/docs/tests/test_docs_build.py`.

## Wave `W05` - first enrolled tutorial content

Greenfield tutorial pages authored with real cli-sequence directives from birth, plus their synthetic fixtures and seed recipes and committed goldens, proving the pipeline end to end. Depends on W02 engine and W03 directive/gates. Backed by ADR ruling D7.

### Phase `W05.P10` - author greenfield tutorials with real sequences

Author synthetic fixtures, seed recipes, and the first tutorial pages with real cli-sequence directives and committed goldens.

- [x] `W05.P10.S33` - Author the synthetic input fixtures and shared seed recipes for the first tutorials; `docs/_sequences/fixtures`.
- [x] `W05.P10.S34` - Author the first greenfield tutorial page with real cli-sequence directives and generate its committed goldens via the refresh CLI; `docs/tutorials`.
- [x] `W05.P10.S35` - Verify the tutorial sequences execute and match their goldens, the @result @expect asserts success, and the page renders stepped with content-identical no-JS output; `docs/tutorials`.

## Wave `W06` - rollout, docs gates green, and codification candidates

Confirm the two-tier enrollment gate, bring the full docs gate suite green, and record the codification candidates for post-cycle promotion. Depends on all prior waves. Backed by ADR ruling D7 and the Codification candidates section.

### Phase `W06.P11` - green gates and codification

Confirm the two-tier enrollment gate, bring the full docs gate suite green, and record codification candidates for post-cycle promotion.

- [x] `W06.P11.S36` - Confirm the two-tier enrollment gate refuses a plain executable fence on an enrolled page while non-enrolled pages keep the verb-path and option-name checks; `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`.
- [x] `W06.P11.S37` - Run the full docs gate suite (nitpicky -n -W build, Pagefind, documented-command conformance, sequence goldens) and bring it green; `dev/docs/tests`.
- [x] `W06.P11.S38` - Record the three codification candidates from the ADR as post-cycle rule-promotion notes in the feature close audit; `.vault/audit`.

## Description

Replace the ~35 static ` ```bash ` how-to fences with build-time-executed CLI sequences: an author writes a backtick-fenced `cli-sequence` MyST directive whose frame lines run hermetically at build time, are compared against committed light per-sequence goldens, and render as a server-side static transcript that a vendored framework-free widget progressively enhances into a stepped player with real-grammar token highlighting and hover help. A wrong writeup, a renamed verb, a changed output shape, or a CLI regression then reds the docs build with a named sequence, frame, and diff. This plan implements exactly the seven accepted rulings D1 through D7 of the `docs-cli-sequences` ADR, grounded in the `docs-cli-sequences` research, and reuses the already-shipped substrate: `invoke_cached_cli` and `isolated_profile_storage_root` for hermetic execution, `frozen_clock` and the `cadrumo.core.observability` golden primitives with the central `GOLDEN_MASK_FIELDS` for deterministic comparison, `dev/docs/cli_reference.py` for the CLI-surface projection, and the existing `builder-inited` docs-build hooks.

Prerequisite zero (ADR D7) is a dedicated first wave: the documented-command conformance gate's invocation-token regex was swept by the package rename to match the token `cadrumo` while the docs cite the real executable `aeat` (roughly 547 times), so the gate is currently near-vacuous and scans almost no invocation. That repair lands before the executed tier stands on it, and is dispatchable independently of the rest of the plan. The engine, its two build gates (a `builder-inited` Sphinx check hook and a `dev/docs/tests` pytest gate over one execution path), the frontend widget, and the first greenfield tutorials then land wave by wave. All work is additive under `dev/docs/`, `docs/`, `docs/_sequences/`, `docs/_static/`, and the two gate test modules; the sandbox never sets `CADRUMO_LIVE_TESTS_ENABLED`, fixtures are synthetic, and the nitpicky offline `-n -W` gate stays green.

## Steps

The plan's Waves, Phases, and Steps are authored above under their headings via the vaultspec-core vault plan CLI; this heading is the canonical anchor and the rows live in their Phase blocks.

## Parallelization

Waves are sequenced by default; the hard ordering and the intra-wave parallelism are:

- Wave `W01` (static conformance floor) is fully independent and is the intended first dispatch. It shares no file with the engine work and can run in parallel with `W02` if capacity allows, though it should land before any enrolled page relies on the gate.
- Wave `W02` (execution engine) is the foundation for everything downstream. Within it the phases carry hard ordering: the parser (`W02.P02`) precedes the runner (`W02.P03`), which precedes the golden store and comparison (`W02.P04`), which precedes the refresh/check CLI and anti-tautology gate (`W02.P05`). Steps within a phase are largely sequential because they build one module; the test steps (`S08`, `S11`, `S15`, `S19`) gate their phase.
- Wave `W03` depends on the `W02` engine. Its three phases can run partly in parallel once the engine lands: the cli-tree projection (`W03.P06`) is independent of the directive and tokeniser (`W03.P07`); the build-hook and pytest surfaces (`W03.P08`) depend on both `W03.P06` and `W03.P07`.
- Wave `W04` (frontend widget) consumes the `W03.P07` payload contract and the `W03.P06` cli-tree projection; it may begin once that payload shape is fixed, in parallel with the remaining `W03` and `W05` work.
- Wave `W05` (first tutorials) depends on the `W02` engine and the `W03` directive and gates being usable end to end; it produces the first committed goldens.
- Wave `W06` (rollout and gates) depends on all prior waves and is the closing sequence.

## Verification

Every Step carries its own verification gate in its row; the plan is complete when all 38 Steps are closed (`- [x]`). Mission-level success criteria, each a real gate with no mocks, skips, or tautological assertions:

- The repaired documented-command conformance gate scans `aeat` invocations, passes green, and pytest collect-only is clean across the touched doc pages (`W01`).
- The engine test suite (parser, runner, comparison, refresh/check CLI, and the executor-level anti-tautology proof that pre-mask differing paths equal exactly the central `GOLDEN_MASK_FIELDS`) passes green with real crypto and no mocks (`W02`).
- A documented command path absent from the generated `cli-tree.json` projection is a hard build failure, and the `cli-sequence` directive renders server-side static frames plus one inline JSON payload per sequence (`W03`).
- The `builder-inited` docs check hook and the `dev/docs/tests` pytest gate both red on an injected golden divergence and both pass green on clean goldens, over one shared execution path (`W03.P08`).
- Without JavaScript the enhanced widget page shows a content-identical linear transcript, keyboard operation and `prefers-reduced-motion` are honoured, hover help resolves against `cli-tree.json`, and the nitpicky offline `-n -W` gate stays green on a rendered sequence page (`W04`).
- At least one greenfield tutorial page executes its real sequences against committed goldens with a terminal `@result` frame whose `@expect` asserts success (`W05`).
- The two-tier enrollment gate refuses a plain executable fence on an enrolled page while non-enrolled pages keep the verb-path and option-name checks, and the full docs gate suite (nitpicky `-n -W`, Pagefind, conformance, sequence goldens) is green (`W06`).
