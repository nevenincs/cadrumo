---
tags:
  - '#adr'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-docs-cli-sequences-research]]"
---

# `docs-cli-sequences` adr: `interactive executed CLI sequence docs` | (**status:** `accepted`)

Operator approval recorded 2026-07-13 (session team-docs-branch1); the
conformance-gate repair is mandated as its own plan phase.

## Problem Statement

The ~35 how-to guides show `aeat` commands as static ` ```bash ` fences and
describe their output only in prose. Nothing today asserts that a documented
command actually runs, that its documented behaviour is real, or that its
output is what the page claims: the existing documented-command conformance
gate validates verb paths and option names against the live Click tree but
never executes anything. Worse, a grounding pass for this ADR found that gate
is currently largely vacuous — its invocation-token regex
(`_CADRUMO_TOKEN_RE` in `test_documented_command_conformance.py`) was swept by
the package rename to match the token `cadrumo`, while the docs cite the real
executable `aeat` 547 times, so almost no documented invocation is scanned at
all. The operator mandate is a step change: every documented CLI interaction
becomes a "sequence" — a build-time-executed series of command→output frames
rendered as an interactive stepped player with real-grammar token
highlighting and hover `--help`, capped by a mandatory verification frame —
so a wrong writeup is a build failure and the docs become a correctness gate.
This ADR rules on the seven open decisions the research left: authoring
syntax (D1), golden storage and commit boundary (D2), comparison policy (D3),
the sequence-result contract (D4), the frontend component contract (D5), the
sandbox and seeding model (D6), and rollout (D7).

## Considerations

Nearly the entire execution stack already exists in-house and was verified at
HEAD for this decision. `invoke_cached_cli` in `src/cadrumo/tests/cli_runner.py`
invokes the cached Click tree in-process with `env=`/`input=` support;
`isolated_profile_storage_root` in `src/cadrumo/tests/secure_sql.py` yields a
hermetic real-crypto storage root under `override_settings`;
`test_app_quickfile.py` already drives a full create→calculate→verify→export
chain on exactly those two primitives. The determinism substrate is accepted
and implemented: `frozen_clock` in `src/cadrumo/core/time/_clock.py`, and
`capture_envelopes`, `canonicalise`, `mask_document`, `differing_paths`,
`assert_golden_match`, and the narrow declared `GOLDEN_MASK_FIELDS`
(`snapshot_id`, `run_id`) in `src/cadrumo/core/observability/_golden.py`,
already defended by an anti-tautology proof in its own test module.
CLI-surface-as-data is solved by `dev/docs/cli_reference.py` (English-pinned
subprocess environment, lazy-subtree materialisation, per-command param
extraction). The docs build (`dev/docs/build.py`, `docs/conf.py` `setup()`)
already wires generated gitignored surfaces through `builder-inited` hooks and
sandboxes storage via `ensure_isolated_storage_root()`. The frontend is
strictly vendored and framework-free (`docs/_static/cadrumo-docs.js`,
`cadrumo-docs.css`); the nitpicky offline `-n -W` gate must stay green.

Binding prior decisions: the CLI reference is a build-time projection, never
committed (`2026-06-01-docs-cli-buildtime-adr`); educational docs reference
the live surface and never redeclare it (`2026-06-01-docs-educational-surface-adr`);
docs tooling lives under `dev/docs/` (`2026-06-14-docs-tooling-separation-adr`);
light curated data is committed while heavy generated indexes are regenerated
(the Pagefind commit boundary); capture-raw-mask-at-compare with a
provably-minimal mask set (`2026-06-30-deterministic-output-replay-substrate-adr`);
user docs speak in singular imperative steps (`aeat-user-docs-hardening`);
never live AEAT, synthetic data only, sensitive bytes never leave secure
storage. Naming: package `cadrumo`, executable `aeat`, env `CADRUMO_*`.

## Considered options

### D1 — Authoring syntax: a backtick-fenced MyST directive with a line-oriented frame grammar

**Chosen.** Authors write a `cli-sequence` MyST directive using the
*backtick* fence form (never the colon `:::` form), with a required unique
sequence id argument, directive options, and a body of plain frame lines —
no nested fences. The grammar:

- A line beginning `aeat ...` is a visible command frame.
- `@setup aeat ...` is an executed but visually collapsed setup frame
  (rendered inside a "Preparation" disclosure — executed truth, never
  invisible magic).
- `@result aeat ...` is the mandatory terminal verification frame; exactly
  one, and it must be the last frame (D4).
- `@capture <name> <json-path>` directly after a command frame binds a value
  from that frame's parsed JSON envelope; later frames interpolate it as
  `{name}` (this is how a real `work_unit_id` produced at build time threads
  into subsequent commands instead of a hand-faked placeholder).
- `@expect <json-path> == <literal>` lines attach semantic assertions to the
  frame above them (used on the result frame, D4).

Worked example, exactly as authored in a how-to page:

    ```{cli-sequence} modelo-303-first-quarter
    :seed: autonomo-basic-2026
    :verify: Verify the calculation before exporting.
    @setup aeat app ledger import --file fixtures/2026-1t-statement.csv
    aeat app modelo create 303 --year 2026 --period 1T
    @capture work_unit_id result.work_unit_id
    aeat app modelo calculate {work_unit_id}
    @result aeat app modelo verify {work_unit_id}
    @expect result.status == "verified_complete"
    ```

Conformance compatibility: the existing gate scans fenced blocks with a
generic ` ``` ` regex, so the directive body's frame lines are already inside
its scan surface. The same change that lands the directive MUST teach that
gate three small things, atomically: (a) re-anchor the invocation token regex
on the real executable `aeat` (fixing the rename-sweep vacuity defect above),
(b) strip a leading `@setup`/`@result` sigil before parsing, and (c) treat
`{name}` interpolations as positional placeholders (its existing placeholder
class). Frame lines then get the verb-path and option-name checks for free,
on top of full execution.

*Rejected:* annotated plain ` ```bash ` fences with magic comments (invisible
in rendered output, un-typed options surface, no place for the id/seed
contract); a colon-fenced directive (invisible to the conformance gate's
fence regex); nested code fences inside the directive (breaks the generic
fence scan and doubles the parsing grammar); reStructuredText-first authoring
(the narrative surface is MyST markdown).

### D2 — Golden storage and commit boundary: committed light per-sequence golden JSON, regenerated rendering, CLI-owned refresh

**Chosen.** Each sequence has one committed golden file at
`docs/_sequences/<page-path>/<sequence-id>.json` carrying, per frame: the
resolved argv, exit code, the verbatim captured `SchemaEnvelope` document for
JSON frames (post-redaction, pre-mask — capture raw, mask at compare), the
verbatim text for text frames, and the capture bindings. Shared synthetic
input artifacts live under `docs/_sequences/fixtures/`; named seed recipes
under `docs/_sequences/seeds/` (D6). These are light, review-diffable data —
the Pagefind commit-boundary pattern: commit the light data, regenerate the
heavy output. Everything rendered (the inlined frame payloads, the
`cli-tree.json` help projection, tokenised HTML) is generated at build time
and gitignored.

Goldens are CLI-owned, never hand-edited (the `aeat-docs-scaffolding-cli` /
locales-CLI discipline): `python -m dev.docs.sequences refresh
[--page PAGE | --sequence ID]` re-executes the sequence(s) in the sandbox and
rewrites the golden files; the author reviews the git diff — which IS the
behaviour-change review — and commits goldens together with the CLI change
that legitimately moved them. `python -m dev.docs.sequences check` is the
gate mode. A divergence fails the build with a message naming the page, the
sequence id, the frame index and argv, and either the post-mask
`differing_paths` list (JSON frames) or a unified diff (text frames), plus
the exact `refresh` invocation that updates the golden.

*Rejected:* fully regenerated goldens with no committed expectation (then the
build cannot fail on drift — there is nothing to compare against, and a CLI
behaviour regression ships silently re-documented as the new truth);
committing rendered HTML or the help projection (drift surface the
docs-cli-buildtime ADR exists to forbid); storing post-mask canonicalised
goldens (bakes the mask into the artifact; rejected for the same reason as
the substrate ADR's decision 3); one monolithic golden file per page (merge
conflicts across concurrent authors, no per-sequence refresh).

### D3 — Comparison policy: full-envelope golden match for JSON frames, exact match with declared narrow normalisation for text frames, exit code always

**Chosen.** Per frame kind:

- **JSON frames** (the frame's stdout parses as a registered
  `SchemaEnvelope`): compare via the substrate primitives — `canonicalise` +
  `mask_document` with exactly the central `GOLDEN_MASK_FIELDS`, asserting
  the full envelope (spine `schema_version`/`command`/`status`/`notices` plus
  `result`), reporting `differing_paths` on failure. The executor MUST NOT
  declare its own mask set and a sequence MUST NOT carry per-sequence mask
  extensions; a newly nondeterministic field is added to the one central set
  with the existing anti-tautology proof extended to cover it.
- **Text frames** (human-readable output): exact string equality after a
  declared, narrow token normalisation limited to values already masked or
  injected in the JSON policy — the sandbox storage root path (replaced by a
  stable token) and the central masked ids where they appear inline. No
  regex-wildcard goldens, no fuzzy matching, no "contains" assertions.
- **Exit code** asserted on every frame (a frame expecting failure must
  declare it explicitly via `@expect exit_code == <n>`; default expectation
  is 0).

Mask honesty is enforced at the executor level too: a dedicated gate executes
one representative committed sequence twice in fresh sandboxes (frozen clock,
injected profile id) and asserts the pre-mask differing paths equal exactly
the declared mask set — the sequence-level analogue of the substrate's
anti-tautology proof, so the docs gate cannot silently rot into tautology.

*Rejected:* string-level comparison of JSON output (loses the typed spine,
breaks on key ordering, and forfeits `differing_paths` diagnostics);
per-sequence mask overrides (the exact "widen the mask to silence a diff"
hazard the substrate ADR names as the central honesty risk); skipping text
output comparison (text frames are what the reader sees most; unverified
text is the current defect class restated).

### D4 — Sequence-result contract: exactly one terminal `@result` frame, semantically asserted, narrated as user verification

**Chosen.** Every sequence MUST end in exactly one `@result` frame; the
directive parser refuses a sequence with zero, multiple, or non-terminal
result frames. The result frame is a real executed command like any other
(golden-gated per D3) with two additional obligations. First, it MUST carry
at least one `@expect <json-path> == <literal>` semantic assertion evaluated
against the live output at build time — golden equality proves the output is
reproducible; the `@expect` proves it *means* success (e.g.
`result.status == "verified_complete"`), so a sequence cannot "verify" by
merely reproducing a failure. Second, the result frame SHOULD be an
inspection or verification verb (`verify`, `view`, `status`, `history`), not
a repetition of the last mutation; this is author discipline checked in
review, not machine-classified.

User-facing narration follows `aeat-user-docs-hardening` imperative voice:
the required `:verify:` directive option carries one singular imperative
sentence ("Verify the calculation before exporting."), rendered as the
result frame's caption, and each `@expect` renders as an imperative check
the reader can perform on their own real output ("Confirm `status` reads
`verified_complete`."). The word "sequence" never renders; user-facing
framing is verification guidance only.

*Rejected:* an abstract non-executed closing frame (hand-authored claims are
the defect class this feature removes); implicit last-frame-is-result (loses
the parser's ability to refuse an uncapped sequence); requiring
machine-classification of read-only verbs (no reliable mutating/read
taxonomy exists on the Click tree today; an allowlist would rot).

**Amendment (2026-07-14, operator-driven): the `@result` assertion must
address the result payload.** The original "at least one `@expect`"
requirement was satisfied by `@expect exit_code == 0` alone, and a large set
of result frames took that route: they proved the command exited without
proving it produced the right answer. The tightened contract requires at
least one `@expect` on the result PAYLOAD, a `result.<path>` or `result[...]`
json-path, not merely `exit_code` or the `status` envelope-spine field. A
result frame asserting only `exit_code`/`status` is an offender. The
detection helper `result_frame_asserts_result_payload` lives in the parser
(the rule's home). Enforcement is a ratcheting per-page gate
(`test_sequence_contract.py` reading `result_assertion_baseline.json`), the
same discipline as the mandatory-display fence gate of D7, so the docs build,
the check tier, and the engine's own synthetic unit tests stay green while
converters add the missing assertions. The baseline is generated from
HEAD-committed docs and only decreases; a page below its baseline passes, and
an empty baseline means every enrolled `@result` frame asserts its payload.
The gate, not a hard parse-time refusal, carries the enforcement: a raise in
the parser would need a baseline file read (wrong layering) and would break
the engine's synthetic result frames to satisfy the letter of "parse error".

### D5 — Frontend component contract: server-rendered frames progressively enhanced by a vendored framework-free widget, help keyed into a generated `cli-tree.json`

**Chosen.** The directive renders, at build time, a
`div.cadrumo-sequence[data-sequence-id]` containing (a) every frame as
static HTML in document order — the tokenised command line plus its full
output in a `pre` — and (b) one inline
`script[type="application/json"]` payload per sequence. No-JS degradation is
therefore automatic and content-identical: without JavaScript the page shows
the complete linear transcript; the widget only *enhances* (it toggles frame
visibility and adds controls, and never injects content), so there is a
single content source and the JSON payload cannot drift from the visible
frames.

Payload shape (per sequence): `sequence_id`, ordered `frames`, each frame
`{kind: command|setup|result, tokens, output: {format: json|text, body},
exit_code, expects}`. Token model: tokenisation happens in Python at build
time against the materialised Click tree (executable, verb path, option,
option value, positional value, interpolated placeholder), so highlighting
is correct by construction — never client-side bash guessing. Each verb
token carries its command-path key. Hover help: one gitignored
`cli-tree.json` projection generated per build from the
`dev/docs/cli_reference.py` machinery (`{path: {help, usage, options:
[{names, help, required}]}}`), emitted into the static output and fetched
once per page (a relative same-origin fetch of a build-emitted asset — no
external request); hovering or focusing a verb token opens a popover with
that path's live help. A documented path missing from the projection is a
build failure — the free conformance gate the research predicted.

Playback: previous/next controls step frame-by-frame (command, then its
output, then the next command), a position indicator, an optional play mode
with a fixed interval, full keyboard operability, and `prefers-reduced-motion`
respected (no typewriter animation when set). Implementation extends the
vendored `docs/_static/cadrumo-docs.js` and `cadrumo-docs.css`; zero
dependencies, zero external requests; termynal and Expressive Code are MIT
design references only, no third-party code shipped.

*Rejected:* client-side tokenisation or vendoring Shiki (a node toolchain and
a second grammar competing with the real Click tree); asciinema-player
(GPL-3.0, byte-stream replay without discrete frames); embedding per-token
help strings inline in every page (duplicates the help catalogue across
pages; one shared projection is the single-source shape); a
JS-renders-everything widget (empty page without JS — fails
self-containment's spirit and accessibility).

### D6 — Sandbox and seeding: per-sequence hermetic sandbox on the existing test substrates, seeding as executed `@setup` frames, one engine under `dev/docs/` with two invocation surfaces

**Chosen.** The executor is one engine, `dev/docs/sequences/` (docs tooling
per the tooling-separation ADR), importing the production package from
outside. Each sequence executes in full isolation: a fresh
`isolated_profile_storage_root` under a temp dir, `frozen_clock` pinned to
one project-wide fixed instant, a fixed injected `profile_id`,
`CADRUMO_OUTPUT_LANGUAGE=en`, live tests off (`CADRUMO_LIVE_TESTS_ENABLED`
never set), commands invoked in-process through `invoke_cached_cli`.
Sequences never share state — not across pages and not within a page — so
every sequence is order-independent and its goldens are self-contained.

Seeding is *executed CLI truth*, not out-of-band Python: fixture state is
built by `@setup` frames (profile create, ledger import of a synthetic CSV
under `docs/_sequences/fixtures/`), which run and golden-gate like any frame
but render collapsed. The `:seed:` option names a reusable recipe file under
`docs/_sequences/seeds/<name>.seq` — a shared fragment of `@setup` frames
inlined before the sequence's own frames — so "create profile, import the
standard quarter" is declared once and reused across pages. All fixture data
is synthetic; a sequence whose command requires live AEAT (a `pull` against
the sede) cannot be enrolled and stays a static documented fence under the
existing conformance checks.

Two invocation surfaces, one execution path (the pull==calculate analogue):
the Sphinx build runs the engine's check mode from a `builder-inited` hook in
`docs/conf.py` `setup()` (alongside the CLI-reference and glossary hooks), so
a divergence or a failed `@expect` reds the docs build; and a pytest gate at
`dev/docs/tests/` (beside `test_docs_build.py`) calls the same engine
functions so CI catches drift without a full docs build. Neither surface
re-implements execution or comparison.

*Rejected:* per-page shared sandboxes (order coupling between sequences; one
edited sequence invalidates its neighbours' goldens); Python-scripted seeding
outside the CLI (undocumented magic state the reader cannot reproduce — and
an untested second write path); subprocess-per-command execution (the
research measured the cached in-process tree as the substrate; subprocesses
re-pay tree materialisation per frame and complicate env isolation);
adopting tesh or Sybil as the execution engine (string-level comparison,
a new dependency, and no envelope-aware masking — the in-house substrate was
purpose-built for exactly this).

### D7 — Rollout: page-level opt-in, tutorials first, with a hard enrollment gate and the conformance-gate repair landing first

**Chosen.** Enrollment is per page and incremental. The first enrolled pages
are *new* tutorials under `docs/tutorials/` (the instructional surface the
docs-architecture taxonomy deferred and the research found thin) — authored
with sequences from birth, proving the pipeline end to end. The ~35 how-to
pages migrate one page per change, highest-traffic flows first; no flag day.

The enforcement gate is two-tier. A page containing at least one
`cli-sequence` directive is *enrolled*: on an enrolled page, a plain fenced
block containing an executable `aeat` invocation is refused by the gate —
enrolled pages are all-executed, with inline-backtick verb references still
permitted for narrative. Non-enrolled pages keep exactly today's checks
(verb-path and option-name conformance), so the migration pressure is
structural but not blocking. Prerequisite zero, landing before or with the
first sequence: repair the documented-command conformance gate's
rename-swept token regex so it scans `aeat` invocations again — the current
vacuity means even the static tier is not actually protecting the surface.

**Amendment (2026-07-14, operator-driven):** the enrolled-page *no-plain-fence
refusal* is withdrawn. In practice it forced multi-option commands to be crammed
into inline prose across every enrolled page, causing severe readability damage
the operator rejected. Enrolled now means only "the page carries at least one
executed, golden-backed `cli-sequence` directive"; an enrolled page MAY also
carry ordinary executable `aeat` fences, and those fences receive exactly the
same base verb-path and option-name checks every fence gets. Enrollment neither
refuses nor exempts them. The executed-vs-static distinction is a *visual and
golden-backed* one (executed frames render as a stepped, verified transcript;
plain fences are ordinary documented commands), not an exclusionary gate. The
sequence-grammar frame validation and the enrolled-surface non-vacuity tripwire
remain; only the plain-fence refusal and its shipped-page scan are retired.

**Amendment 2 (2026-07-14, operator-driven, mandatory display):** the plain-fence
*tolerance* of Amendment 1 was a remediation of inline cramming, not the end
state. The operator's end state is that EVERY `aeat` CLI command shown in user
docs renders through the implemented cli-sequence display (a step header, a
tokenised command card with the shell switcher and copy control, and, for
executed frames, its output), never a plain ` ```bash ` fence. To render a
command whose hermetic execution is impossible, a new non-executed display frame
`@static` renders the SAME unified step card but with NO output section and NO
golden (output is never fabricated, so the honesty rules hold). `@static` is the
carve-out and is admissible ONLY where the hermetic sandbox genuinely cannot run
the command: a live-AEAT read (`pull` / the `app live` group), a Google OAuth or
other interactive-consent flow, an interactive wizard, or an operator-machine-
specific path. `@static` is a sigil-prefixed command frame like `@setup` /
`@result`; its step header comes from a preceding `@step` or the leaf-help
fallback. The frame grammar carries three rules. A sequence with executed frames
keeps exactly one `@result` with `@expect`, and that `@result` must be the LAST
EXECUTED frame, so `@static` frames may follow it. An all-`@static` sequence runs
nothing, so it requires no `@result` and REFUSES the `:verify:` option (a
verification sentence would overclaim), while `:verify:` stays mandatory on a
sequence with executed frames. `@expect` and `@capture` on a `@static` frame are
parse errors, because a non-executed frame produces no output to assert or
capture. Non-`aeat` commands (`pip`, `playwright`, `ollama`, `python -m`,
`/plugin`) remain ordinary plain fences. The mandate is scoped to the `aeat`
executable. Enforcement is a ratcheting gate: a plain shell fence carrying an
`aeat` invocation in a user-docs page is a violation, governed by a checked-in
per-page baseline that only ratchets down (no page may exceed its baseline; an
empty baseline means the doctrine is fully applied), so the parallel page-by-page
conversion never reds the tree. This supersedes the plain-fence *tolerance* of
Amendment 1 while keeping its factual point that plain fences still receive the
base verb-path/option-name checks; the executed-vs-`@static` distinction stays
visual and golden-backed (executed frames carry a verified transcript; `@static`
frames a command card without output).

**Amendment 3 (2026-07-14, operator-driven): the ratcheting-gate family and its
shared robust fence strip.** The mandatory-display doctrine grew a family of
checked-in per-page ratcheting baselines that all share the fence-gate mechanics:
a page may never exceed its baseline, an absent page starts at zero, an empty
baseline means the rule is fully applied, and generation is from HEAD so the
parallel sweep never reds the tree. The family covers the plain-fence gate; an
inline-span gate closing the loophole of moving a command out of a fence into an
inline `code` span (a span carrying two or more option/argument tokens is a
violation, and the detector joins soft line wraps within a paragraph so a wrapped
span is caught as its single-line form); the em-dash and LLM-marker prose gates;
and the D4 result-payload gate. Every fence-stripping gate uses one line-based
strip that excludes a fenced block in full regardless of indentation, fence
character, or fence length, and drops an unclosed fence to end of input rather
than mis-pairing with a later fence. At conversion complete the plain-fence and
inline-span baselines are empty; the em-dash baseline retains only the
non-user-facing contributor surfaces. Separately, the golden canonicalisation
tokenises the per-run sandbox storage root, workdir, and the repository checkout
root inside envelope string values (value-anchored on the known roots), so a
command whose output echoes an absolute path (such as `config check`) is
golden-stable across runs and machine-portable for CI.

*Rejected:* flag-day migration of all how-tos (35 pages of goldens landing
at once is unreviewable and blocks every doc change on the new machinery);
directive-level opt-in with no page gate (pages drift into a mix of executed
and unexecuted commands indefinitely, and the reader cannot tell which is
which); starting migration with the how-tos (they are live operator surface;
tutorials are greenfield and lower-risk for shaking out the executor).

## Constraints

- Never live AEAT: the sandbox never sets `CADRUMO_LIVE_TESTS_ENABLED`;
  sequences build/verify/export only, never submit; live `pull` verbs are
  unenrollable.
- Synthetic data only in `docs/_sequences/`: goldens carry the redacted
  envelopes of synthetic scenarios; sensitive financial data never leaves
  secure storage; the committed fixtures are generator-produced synthetic
  artifacts.
- Licence hygiene: no asciinema-player (GPL-3.0), no byexample (unverified);
  no third-party frontend code shipped; the widget is bespoke vendored code.
- The nitpicky offline `-n -W` docs gate stays green; the executor adds
  build time, so the engine must support page-scoped execution to fit the
  existing changed-page-aware incremental build in `dev/docs/build.py`.
- Parent stability: the determinism substrate ADR is implemented at HEAD
  (verified) but its own ADR document is still marked proposed; this ADR
  treats the shipped primitives (`frozen_clock`, `GOLDEN_MASK_FIELDS`, the
  golden compare module) as the stable substrate and inherits their
  contracts rather than redefining them.
- The shared-worktree discipline applies: all work is additive under
  `dev/docs/`, `docs/`, `docs/_sequences/`, `docs/_static/`, and the two
  gate test modules.

## Implementation

Component inventory (all paths from repo root):

- `dev/docs/sequences/` — the engine: directive-body parser (frame grammar,
  `@capture`/`@expect`/`@result` semantics, seed inlining), sandbox runner
  (per-sequence `isolated_profile_storage_root` + `frozen_clock` + injected
  `profile_id` + `invoke_cached_cli`), golden reader/writer, comparison
  (delegating to `cadrumo.core.observability` primitives for JSON frames),
  Python-side tokeniser against the materialised Click tree, and the
  `refresh`/`check` CLI (`python -m dev.docs.sequences ...`).
- `dev/docs/cli_tree.py` (or an extension of `dev/docs/cli_reference.py`) —
  the `cli-tree.json` projection generator, reusing the existing
  English-pinned environment, lazy-import forcing, and param extraction.
- `docs/conf.py` — a new MyST directive registration rendering the static
  frames plus inlined JSON payload, and a `builder-inited` hook running the
  engine's check mode and emitting `cli-tree.json` into the static output.
- `docs/_static/cadrumo-docs.js` / `cadrumo-docs.css` — the stepped-player
  enhancement layer: visibility toggling, prev/next/play controls, hover/
  focus help popovers keyed into `cli-tree.json`, keyboard support,
  reduced-motion handling.
- `docs/_sequences/` — committed light data: per-page per-sequence golden
  JSON, `fixtures/` synthetic inputs, `seeds/` shared setup recipes.
- `dev/docs/tests/test_sequence_goldens.py` — the pytest gate calling the
  engine's check mode, plus the executor-level anti-tautology proof (double
  execution, pre-mask diff equals the central mask set exactly).
- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`
  — taught the sequence grammar (sigil stripping, `{name}` placeholders) and
  repaired to anchor on the `aeat` executable token; its enrolled-page
  no-plain-fence tier added.

## Rationale

Every ruling is the production-safe application of an already-accepted
pattern to a new surface. The directive-with-frame-grammar (D1) is the only
authoring shape that simultaneously stays inside the conformance gate's
generic fence scan, gives the id/seed/verify contract a typed home, and keeps
authors in markdown. Committed light goldens with CLI-owned refresh (D2) is
the Pagefind commit boundary plus the scaffolding-CLI authority discipline:
the gate needs a committed expectation to red on drift, and the golden diff
under review is precisely the behaviour-change approval step. Envelope-level
comparison with the single central mask (D3) reuses the substrate the
deterministic-output ADR built for exactly this job and refuses the one
dishonesty lever (mask widening) it warns about. The executed, semantically
asserted result frame (D4) converts the operator's "sequence result" mandate
into a machine-refusable contract while narrating it as imperative
verification guidance per the user-docs rules. Server-rendered frames with a
progressive-enhancement widget (D5) make no-JS degradation structural rather
than aspirational and keep highlighting and help correct by construction from
the live tree — the docs-cli-buildtime philosophy extended to tokens.
Per-sequence hermetic sandboxes with CLI-executed seeding (D6) reuse the
quickfile-proven substrate, keep setup itself documented truth, and keep one
execution path under two gates (the pull==calculate discipline). Tutorials-
first page-level opt-in (D7) grows the surface one reviewable page at a time
— the educational-surface ADR's own guard against a second over-build — and
the rename-swept-regex repair is sequenced first because an honest static
tier is the floor the executed tier stands on.

## Consequences

Gains. Documented commands become executed, asserted artifacts: a wrong
writeup, a renamed verb, a changed output shape, or a regression in the CLI
itself reds the docs build with a named sequence, frame, and diff. The
reader gets stepped playback, real-grammar highlighting, hover help sourced
from the live tree, and — through the result-frame narration — is taught to
verify their own runs. The thin tutorials surface gets built on rails. Setup
recipes make realistic worked examples cheap to author.

Honest difficulties. Build time grows with every enrolled page; the
page-scoped check mode and the incremental build must keep the feedback loop
tolerable, and this needs measuring in the first tutorial landing. Goldens
are a new maintenance surface: every legitimate CLI output change now
touches golden files — by design, but authors must learn the `refresh`
workflow or they will be tempted to hand-edit (the CLI-authority rule and
review discipline are the guard). The frame grammar is bespoke and must stay
small; scope creep toward a shell DSL (pipes, conditionals, loops) must be
refused — a sequence is a linear frame list. The mask-honesty proof must be
extended whenever a new nondeterministic field appears, or the gate rots.
The conformance-gate repair may surface latent doc defects the vacuous gate
has been missing since the rename; budget for a burndown when it lands.

Pathways opened. The per-sequence golden corpus is a free regression suite
over operator-facing CLI behaviour, independent of the docs. The
`cli-tree.json` projection can later serve the command palette and offline
search. Localised sequences (re-execution under another
`CADRUMO_OUTPUT_LANGUAGE`) become mechanical once the localisation decision
for the educational surface is revisited.

## Codification candidates

- **Rule slug:** `docs-sequences-are-executed-truth`.
  **Rule:** On a sequence-enrolled docs page, every executable `aeat`
  invocation lives inside a `cli-sequence` directive, executes hermetically
  at build time, and matches its committed golden; goldens are refreshed only
  via `python -m dev.docs.sequences refresh` and never hand-edited.
- **Rule slug:** `sequence-result-is-mandatory-and-asserted`.
  **Rule:** Every CLI sequence ends in exactly one terminal `@result` frame
  carrying at least one `@expect` semantic assertion, narrated user-facing as
  a singular imperative verification step.
- **Rule slug:** `sequence-mask-is-the-central-mask`.
  **Rule:** Sequence golden comparison uses exactly the central
  `GOLDEN_MASK_FIELDS` set; per-sequence mask extensions are forbidden, and a
  new nondeterministic field is enrolled centrally with the anti-tautology
  proof extended in the same change.
