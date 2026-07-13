---
tags:
  - '#audit'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
---

# `docs-cli-sequences` audit: `docs-cli-sequences codification candidates and follow-up register`

## Scope

This is the S38 record for the `docs-cli-sequences` campaign: it captures the codification candidates for post-cycle rule promotion and the accumulated follow-up register. It is NOT the campaign close honesty review (that is a separate fresh-context pass, gated behind S37 and the landed content wave). Per the vaultspec-codify discipline, no rule is authored yet: a candidate is promoted only after it has held across at least one full execution cycle and after the close honesty review runs. The three primary candidates below are recorded verbatim from the ADR's Codification candidates section and reconciled against what actually landed across W01 through W05; secondary emergent-pattern candidates and the follow-up register follow.

## Findings

### primary-candidate-executed-truth | candidate | On an enrolled docs page every executable aeat invocation is executed, golden-gated truth

Proposed rule slug `docs-sequences-are-executed-truth`. Obligation: on a sequence-enrolled docs page, every executable `aeat` invocation lives inside a `cli-sequence` directive, executes hermetically at build time, and matches its committed golden; goldens are refreshed only via `python -m dev.docs.sequences refresh` and never hand-edited. Origin: ADR ruling D2 (committed light goldens, CLI-owned refresh) and D7 (enrolled-page tier). Landed and gate-backed across W02 (the engine and golden store, `dev/docs/sequences/`), W03.P07.S24 (the enrolled-page no-plain-executable-fence tier in `test_documented_command_conformance.py`), W03.P08 (the build-hook and pytest gate surfaces), and W06.P11.S36 (the two-tier coexistence pin). Promotion-ready when: the first enrolled tutorial pages have shipped (W05 landed), the full docs gate suite is green (S37), and the pattern has held one full cycle with the `refresh` workflow exercised by a real golden-moving change — at which point the "never hand-edit" clause has been tested, not merely stated.

### primary-candidate-result-frame-asserted | candidate | Every sequence ends in exactly one asserted terminal @result frame

Proposed rule slug `sequence-result-is-mandatory-and-asserted`. Obligation: every CLI sequence ends in exactly one terminal `@result` frame carrying at least one `@expect` semantic assertion, narrated user-facing as a singular imperative verification step. Origin: ADR ruling D4 (sequence-result contract) and D1 (frame grammar). Landed and gate-backed in W02.P02.S06 (the parser refuses zero, multiple, or non-terminal `@result` frames, `dev/docs/sequences/_parser.py`) and W02.P04.S14 (`@expect` semantic evaluation, `dev/docs/sequences/_compare.py`), proven by the parser and comparison test suites (S08, S15) and exercised by the first tutorial's real sequences (W05.P10.S34/S35). Promotion-ready when: the tutorial content has demonstrated the contract holds against real authored sequences across a full cycle, and review discipline for the "inspection/verification verb, not a repeated mutation" author-guidance clause (D4, not machine-classified) has a worked precedent to cite.

### primary-candidate-central-mask | candidate | Sequence golden comparison uses exactly the central mask, no per-sequence extension

Proposed rule slug `sequence-mask-is-the-central-mask`. Obligation: sequence golden comparison uses exactly the central `GOLDEN_MASK_FIELDS` set; per-sequence mask extensions are forbidden, and a new nondeterministic field is enrolled centrally with the anti-tautology proof extended in the same change. Origin: ADR ruling D3 (comparison policy) built on the deterministic-output-replay substrate ADR. Landed and gate-backed in W02.P04.S13 (comparison delegates to the observability primitives with exactly the central mask, refusing per-sequence extension, `dev/docs/sequences/_compare.py`) and W02.P05.S18 (the executor-level anti-tautology proof: double execution, pre-mask differing paths equal the central mask set exactly, `dev/docs/tests/test_sequence_goldens.py`). Promotion-ready when: the anti-tautology proof has survived at least one central-mask extension (a genuinely new nondeterministic field added to `GOLDEN_MASK_FIELDS` with the proof extended in the same commit), proving the "enrol centrally, extend the proof" mechanism in practice rather than only in principle.

### secondary-candidate-emergent-patterns | candidate | Emergent cross-wave patterns worth watching for a second occurrence before promotion

Three durable patterns emerged across W01 through W05 that are NOT yet in the ADR's candidate list and have held for only this one campaign — recorded here so a second occurrence can trigger promotion rather than being missed. (1) One-engine-two-surfaces: the Sphinx `builder-inited` check hook and the `dev/docs/tests` pytest gate both call the same engine check functions and neither re-implements execution (ADR D6; W03.P08.S26/S27; the pull-equals-calculate discipline restated for docs). (2) Golden-store-is-CLI-owned: the `refresh`/`check` split with committed light data and gitignored heavy output (ADR D2; W02.P05.S16/S17) is the same discipline `aeat-docs-scaffolding-cli` and `modelo-locales-cli-authority` already codify for other generated surfaces — a candidate to fold into or sibling those rules rather than a standalone. (3) Static-plus-runtime shared live-refusal taxonomy: a live-AEAT `pull` sequence is refused both statically (unenrollable, stays a documented fence) and at runtime (the sandbox never sets `CADRUMO_LIVE_TESTS_ENABLED`), landed in W03.P07 (commit `b8f0612158`, statically refuse live-AEAT sequences). None is promotion-ready: each has one occurrence; the codify bar is a lesson that has held across at least one full cycle, so these wait for the close honesty review to confirm durability.

### followup-register | tracking | Accumulated deferred and latent follow-ups from W01 through W06

Five follow-ups accumulated across the campaign, none blocking closure, each recorded here as inventory for a post-cycle pass. (1) DEFERRED — `_TREE_DOC_DIRS` scope expansion (operator decision): the conformance gate's `_flat_docs()` scans `docs/*.md` flat, `docs/explanation`, `docs/how-to`, and `README.md`, but `_TREE_DOC_DIRS` does NOT include `docs/tutorials`, where the first enrolled sequence pages ship — so the shipped-enrolled-page scan (`test_shipped_enrolled_pages_have_no_plain_executable_fences`) does not currently cover the tutorial tree. Expanding the scan surface to `docs/tutorials` is an operator-gated decision because it widens the whole gate's blast radius, not only the enrolled tier. (2) OPEN — orphan-golden-dir sweep: `docs/_sequences/` accumulates per-page golden directories; a page deletion or sequence rename can strand an orphan golden dir with no live sequence, and no sweep verb yet detects them. (3) ACCEPTED-LATENT — multiline-inline-span extraction gap: `_INLINE_CODE_RE` matches single-line inline-backtick spans only (`` `[^`\n]+` ``), so an `aeat` invocation wrapped across a line break inside inline backticks is not extracted; accepted latent because the doc idiom is single-line inline references. (4) LATENT — negative-number token classification: the tokeniser's `_is_option_token` edge on a negative-number value (a bare `-5` read as an option-like token) was recorded as a review LOW in W03.P07.S22 (commit `005f470c94`); latent because no current sequence passes a negative numeric positional. (5) HYGIENE — approximately 26 exec records across the campaign shipped with template annotation blocks not yet stripped; they await a vault hygiene pass (`vaultspec-core vault check annotations --fix`, feature-scoped) once the campaign closes and no agent holds an exec record mid-edit.

## Recommendations

- Hold all three primary candidates and the three secondary emergent patterns for the campaign close honesty review; promote each only after S37 is green, the content wave has landed a full cycle, and the specific promotion-ready condition named in its finding is met. Do not author any rule in `.vaultspec/rules/` before then (the codify discipline: one full cycle held).
- Route the `_TREE_DOC_DIRS` tutorial-scope expansion to the operator as an explicit decision, flagging that until it lands the enrolled-page live scan does not cover `docs/tutorials`.
- Fold the orphan-golden-dir sweep and the annotation-hygiene pass into the post-close maintenance batch; leave the two latent tokeniser/inline-span gaps as tracked inventory until a real doc triggers them.
