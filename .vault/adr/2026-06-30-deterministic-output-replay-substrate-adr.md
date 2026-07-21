---
tags:
  - '#adr'
  - '#deterministic-output-replay-substrate'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-deterministic-output-replay-substrate-research]]"
---

# `deterministic-output-replay-substrate` adr: `deterministic output and golden capture substrate` | (**status:** `proposed`)

## Problem Statement

The `agent-harness` ADR (`2026-06-30-agent-harness-adr`, accepted) commits in its Q5 decision to a golden-task replay gate that asserts both the expected agent tool trajectory and the expected result payloads, plus a determinism-replay mode that re-runs a captured trajectory and asserts byte-identical output — because non-determinism in a regulated tax tool is itself an assurance failure. The grounding research (`2026-06-30-deterministic-output-replay-substrate-research`) confirms that the substrate this gate stands on does not exist at HEAD: the `replay_run` subsystem re-executes a captured argv but never captures the emitted `SchemaEnvelope`, gates only on `corpus_sha256`, and several `--format json` payloads carry wall-clock and uuid fields that cannot be isolated for replay. This ADR designs that substrate — the clock seam, the identity-determinism levers, the golden result-payload capture, and the canonicalise/mask compare layer — and resolves the four decisions the research left open. It is a new-feature, prerequisite ADR for the harness W03 vertical-slice proof; it introduces the decided shape, not code, and stops at plan approval.

## Considerations

The substrate must make any `--format json` run deterministic and assertable without weakening production behaviour, without re-introducing the process-global clock freezing the test suite bans, and without persisting real financial figures to plaintext fixtures. Four facts from the research shape every decision. First, the golden gate replays a whole CLI invocation through reconstructed argv (`replay_run` re-enters the CLI), so it physically cannot thread a per-call `clock=` parameter into the four non-isolatable timestamp sites — whole-run freezing needs a seam the argv path can reach. Second, the captured payload is the typed, registered `SchemaEnvelope` (shared spine `schema_version`/`command`/`status`/`notices` plus a `SCHEMA_REGISTRY`-bound `result`), so capture must round-trip through that schema and never degrade to a `dict[str, Any]` bag, and the spine is itself contract an agent reads. Third, `profile_id` is already caller-injectable through `register_active_profile`, while `snapshot_id` embeds an unseedable `uuid4().hex` tail and is an opaque surrogate key, not an assertable value. Fourth, the same capture/canonicalise/mask/compare logic must serve both the existing observability replay and the new operator gate, or the two drift apart.

Two parent decisions bind this work. `aeat-quality-gates` and `no-tautological-calculation-tests` mean the masking layer is the central honesty risk: a mask broad enough to hide a regression voids the gate. `sensitive-financial-data-secure-storage-only` means committed golden fixtures must carry only synthetic data; the existing DIAGNOSTIC-class trace redaction is partial masking for audit, not a licence to commit real figures.

## Considered options

**Decision 1 — Clock seam.**
- *Extend the thread-a-`clock=` convention to the four non-isolatable sites.* Faithful to the established explicit-injection convention and adds no new global state, but cannot serve the argv-driven whole-run replay the golden gate uses — it reaches unit-level action tests only, leaving the run-trace timestamps and export metadata still flapping under replay. Rejected as insufficient for the gate.
- *A `freezegun`/`time_machine` global freeze.* Rejected outright — banned in live-marked tests by `conftest.BANNED_LIVE_IMPORTS`; re-introducing it is the exact anti-pattern the suite forbids.
- **Chosen — a bounded contextvar clock seam in `core/time`, default-off, retaining explicit injection where it exists.** `now()` consults a contextvar that is unset in production (so it returns real `datetime.now(UTC)` with zero behaviour change) and settable only through a replay/test-scoped context manager that is itself forbidden in live-marked tests. The four non-isolatable sites and the run-trace timestamps consult the seam by virtue of calling `now()`; sites that already accept `clock=`/`occurred_at=` keep that convention unchanged.

**Decision 2 — Identity determinism (per field).**
- *`profile_id`: inject vs mask.* **Chosen — inject** through the already-accepted caller-minted `register_active_profile(profile_id=...)` path. The real value flows through and the golden output asserts it faithfully; masking would discard a value the substrate can pin for free.
- *`snapshot_id`: inject a uuid override vs mask at compare.* **Chosen — mask** the field at compare. Its `profile_id` prefix and timestamp are already deterministic once decision 1 and the injected `profile_id` land; only the `uuid4().hex` tail flaps, and `snapshot_id` is an opaque surrogate key with no assertable semantics. Widening `new_profile_snapshot_id` with a uuid-injection parameter purely for tests is more API surface than masking one well-known structural field is worth.

**Decision 3 — Golden-output capture.**
- *Capture canonicalised (store the already-masked, key-sorted envelope).* Rejected — bakes the mask into the artifact, so the mask set cannot later be tightened and a masked field that unexpectedly becomes deterministic can never be detected; it also stores a transformed, less-faithful record of real behaviour.
- **Chosen — capture the verbatim emitted envelope, canonicalise and mask at compare time.** The live capture stores the exact redacted `SchemaEnvelope` document as emitted; the compare primitive key-sorts and applies a declared, narrow JSON-path mask. Comparison granularity is the **full envelope** (spine plus `result`), since `status` and `notices` are contract an agent reads, not incidental. The `db_sha256` assertion is added as an **optional post-state tier** for scenarios that declare they mutate state and run against a hermetic synthetic `var/` root; `corpus_sha256` remains the replay drift gate, and `db_sha256` is not made a hard gate for all replays because the shared `var/` would flap it. Committed operator golden fixtures are the post-mask canonical expectation, synthetic-data-only.

**Decision 4 — Reuse vs new.**
- *Let the operator gate re-implement its own capture/compare.* Rejected — duplicates the masking and canonicalisation logic that is the exact drift Q4 warns against.
- **Chosen — one substrate, two consumers.** A single module owns the clock seam, the identity levers, and the capture/canonicalise/mask/compare primitive. The existing `replay_run` is extended to capture the result envelope on the original run and assert it on re-entry (closing the research F1 gap); the operator golden gate calls the same payload-determinism primitive and layers trajectory and AEAT-oracle expected-value assertions on top. Neither consumer re-implements compare.

## Constraints

This ADR depends on the accepted `agent-harness` ADR for its purpose (the Q5 gate it serves) and treats that decision as a stable parent; it is a blocking precondition for the harness W03 vertical-slice proof, not part of the harness itself. It layers on the run-trace observability subsystem (`replay_run`, `RunTrace`, the per-run store and fingerprints) as the existing record/replay foundation it extends rather than replaces, and on the `SchemaEnvelope`/`Notice` JSON contract (`cli-notices-are-the-only-diagnostic-channel`) as the typed surface it captures. No new third-party or frontier dependency is introduced: the contextvar seam, canonical JSON serialisation, and SHA-256 fingerprints are all stdlib or already in-tree.

The honesty risk is concentrated in the masking layer; its mitigation (an anti-tautology proof that the declared mask set is exactly the residual nondeterministic field set, no broader) is a hard requirement of the design, not an optional test. The clock seam carries a standing obligation to stay default-off in production and forbidden in live-marked tests; if that guard regresses, the seam becomes a production backdoor. The shared dirty worktree forbids destructive git/workspace operations; all substrate work is additive and path-scoped under `core/` plus the test surface.

## Implementation

A single substrate, built additively, with two consumers standing on it.

**Clock seam.** `core/time` gains a contextvar holding an optional frozen instant and a replay/test-scoped context manager that sets and restores it. `now()` returns the frozen instant when the contextvar is set and the real UTC time otherwise; the contextvar is never set in any production path. The manager is guarded so it refuses to activate under the live-test opt-in, keeping live-marked tests on real wall-clock plus explicit injection exactly as today. The calc-sheets `_utc_now()` helper is reconciled to route through the same seam so there is one consulted clock, not two. The four non-isolatable sites and the run-trace `started_at`/`finished_at` need no per-site change — they consult the seam through their existing `now()` call. Sites that already accept `clock=`/`occurred_at=` are left untouched.

**Identity levers.** Golden scenarios mint a fixed `profile_id` and pass it through the existing `register_active_profile(profile_id=...)` path. `snapshot_id` is left to its natural construction and enrolled in the compare mask as an opaque-key JSON path.

**Golden capture.** The per-run store is extended to persist the verbatim emitted envelope (the redacted `SchemaEnvelope` document) as a typed per-run artifact alongside `trace.json`, re-validatable against `SCHEMA_REGISTRY[command]` on load so the captured payload never exists as a `dict[str, Any]` bag and `RunTrace` keeps its lean header role. The capture/compare primitive canonicalises (UTF-8, key-sorted, fixed indent) and applies the declared JSON-path mask allowlist, then asserts full-envelope equality. `replay_run` captures the envelope on the original run and asserts it on re-entry; the optional `db_sha256` post-state tier asserts state-transition determinism for hermetic write scenarios.

**Operator gate consumption.** The operator golden gate (owned by the harness eval, out of scope here) imports the same primitive for its payload-determinism check and adds trajectory and AEAT-oracle expected-value assertions. Its committed golden fixtures hold the post-mask canonical expectation for synthetic scenarios only.

**Test approach.** A captured run replays byte-identical after masking; the anti-tautology proof captures the same scenario twice with the seam frozen and `profile_id` injected and asserts that, before masking, the only differing JSON paths are exactly the declared mask set — falsifying the mask so it cannot silently widen.

## Rationale

Each decision is the production-safe application of a constraint the research surfaced. The contextvar seam (decision 1) is chosen over extending threading because the argv-driven whole-run replay the golden gate uses cannot receive a `clock=` parameter — threading is structurally unable to freeze the run-trace timestamps and export metadata under replay — while the seam reaches them through their existing `now()` call and stays a no-op in production. Injecting `profile_id` and masking `snapshot_id` (decision 2) follows the research finding that the former is already an accepted lever and the latter an opaque surrogate, favouring faithfulness where injection exists and narrow masking only where the value carries no assertable meaning. Capture-raw-then-mask (decision 3) keeps the stored artifact a faithful record of real behaviour (per `aeat-quality-gates`) and keeps the mask set tunable and auditable; asserting the full envelope locks the spine an agent reads; the optional `db_sha256` tier makes the ledger-add retried-no-op assertable without flaking the shared `var/`. The one-substrate-two-consumers shape (decision 4) is the direct answer to Q4's no-duplication requirement and keeps the typed-envelope capture under one conformance regime.

## Consequences

The substrate turns the observability replay from "the same argv re-runs" into "the same JSON came out", and gives the harness Q5 gate the deterministic, assertable foundation it was promised — both the harness-regression and the non-determinism failure modes become catchable. The clock seam additionally makes the four non-isolatable export/overview/run-trace timestamps deterministic for any test, not only the golden gate.

Honest difficulties. The clock seam is global state by nature; its production-off and live-test-forbidden guards are load-bearing and must be defended by test, or the seam rots into a backdoor. The masking layer is the standing honesty hazard: every new nondeterministic field must be added to the declared allowlist deliberately and proven minimal, never widened to silence a diff. Capturing the result envelope per run grows the per-run trace footprint and brings the captured payload under the same sensitive-data discipline as the rest of the trace, so the synthetic-only rule for committed fixtures must hold. Reconciling `_utc_now()` onto the single seam touches calc-sheets and must preserve its existing behaviour.

Pathways opened. Once any `--format json` run is deterministic and assertable, the same primitive serves the operator golden gate, future regression snapshots for any command, and the ledger-add idempotency proof — without re-deriving capture or compare. The substrate is the reusable floor the harness vertical-slice proof, and later operator personas, stand on.
