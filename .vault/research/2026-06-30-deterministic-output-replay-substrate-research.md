---
tags:
  - '#research'
  - '#deterministic-output-replay-substrate'
date: '2026-06-30'
modified: '2026-07-17'
related: []
---

# `deterministic-output-replay-substrate` research: `deterministic output and golden capture substrate`

The `agent-harness` ADR (`2026-07-02-agent-harness-refoundation-adr`, accepted) commits, in its Q5 eval-substrate decision, to a golden-task replay gate that captures the expected tool trajectory AND the expected result payloads, plus a determinism-replay mode that re-runs a captured trajectory and asserts identical output — non-determinism is itself an assurance failure in regulated tax work. This research grounds whether the substrate that gate needs exists at HEAD, and finds it does not: a record/replay subsystem exists but captures inputs plus state fingerprints and never the result JSON, and several `--format json` payloads carry wall-clock and uuid fields that cannot be isolated for replay. The deliverable is the reusable substrate — clock seam, identity-determinism levers, golden result-payload capture, and a canonicalise/mask compare layer — that makes any `--format json` run deterministic and assertable. Authoring the AEAT-worked-example tax scenarios and the trajectory assertions is out of scope; that work belongs to the harness eval gate and stands on this substrate.

Scope and confirmation: every cited source file was read at HEAD and confirmed to have no working-tree modification, so the findings reflect committed state. The one nearby peer edit found (`src/aeat/application/user_profile/_bundle.py`) is not a file this design touches.

## Findings

### F1 — The replay subsystem captures inputs and fingerprints, never the result payload

`replay_run` (`src/aeat/core/observability/_replay.py:118-185`) loads a persisted `RunTrace`, recomputes the corpus fingerprint, refuses on drift (`AeatCorpusDriftError`), reconstructs argv from captured `ArgumentRecord` values, and re-enters the Typer CLI. It is a deterministic read-only re-execution harness — but it asserts nothing about output. The drift gate compares `corpus_sha256` only (`:150-157`) and explicitly ignores the captured `db_sha256`.

`RunTrace` (`src/aeat/core/observability/_models.py:363-409`) is a strict, frozen pydantic header carrying `run_id`, `started_at`/`finished_at`, `entrypoint`, `arguments`, `corpus_sha256`, `db_sha256`, `cert_fingerprint`, `outcome`, and `replay_of`. There is no field for stdout or the emitted result JSON. The per-run store (`src/aeat/core/observability/_store.py`) writes `trace.json` plus `events.jsonl` per `run_id`; the `RunEvent` payload union (`_models.py:276-312`) models navigation/form-fill/assertion/cache/error/step/workflow/generic events but never the command's `SchemaEnvelope`. Consequence: replay proves "the same argv re-runs without corpus drift", not "the same JSON came out". The Q5 golden gate needs the latter and the capture surface does not exist.

### F2 — The captured payload would be the typed `SchemaEnvelope` spine

Every `--format json` success response is the `SchemaEnvelope` (`src/aeat/core/json_contract.py:195-229`): a shared spine of `schema_version` (pinned `ENVELOPE_SCHEMA_VERSION = "2"`, `:65`), `command`, `status` (`EnvelopeStatus`, derived from notice severity by `derive_status`, `:141-152`), the strict per-command `result` (an `OutputSchema` subclass registered in `SCHEMA_REGISTRY`, `:235`), and the typed `notices` list (`Notice`, `:101-138`). `emit_json_success` (`:315-368`) assembles the mapping, derives `status`, runs the redaction pass (`redact_structured_for_cli_output`), and writes via `emit_json_document`. The capture target is therefore a fully-typed, registered envelope — the substrate must capture and re-validate it through that registered schema, never reduce it to a `dict[str, Any]` bag (per `aeat-architecture-boundaries`), and the spine `status`/`notices` are part of the contract an agent reads (per `cli-notices-are-the-only-diagnostic-channel`), so the golden must lock the whole envelope, not only `result`.

### F3 — The clock model is explicit injection; global freezing is banned in live tests

`core.time.now()` is a plain module-level function returning `datetime.now(tz=UTC)` (`src/aeat/core/time/_clock.py:18-25`). Determinism today is achieved by threading `clock=` / `occurred_at=` parameters into action functions; `freezegun` and `time_machine` are in `BANNED_LIVE_IMPORTS` and any file holding an `aeat_live` test that imports them is a hard `pytest.exit` (`src/aeat/tests/conftest.py:44-58`). The established convention is explicit per-call injection, not process-global freezing.

Already isolatable (a `clock=`/`occurred_at=` seam exists at the call site): ledger add/classify/verify-report, work-unit timestamps, modelo export `exported_at`, and the observability `run_id` (injectable as `run_id=` to `run_context`, `_context.py:104-125`).

Not isolatable at the call site (direct `now()` / `_utc_now()` with no override), confirmed at HEAD:

- filing/declaracion export `exported_at` — `src/aeat/application/filing/_export.py:336`.
- overview `generated_at` — `src/aeat/application/overview/_agenda.py:170`, `_calendar.py:1298` and `:1386` (`_backlog.py` / `_explain.py` per brief).
- calc-sheets `exported_at` — `src/aeat/application/storage/calc_sheets/_engine.py:128` (via `_utc_now()`; the engine docstring at `:838` already notes two runs yield the same plan "modulo the `exported_at` timestamp").
- `RunTrace.started_at` and `finished_at` — both `now()` calls inside `run_context` (`_context.py:130` for `started_at`, `:304` for `finished_at`).

The critical structural fact for the clock decision: the golden gate replays a whole CLI invocation through reconstructed argv (`replay_run` re-enters the CLI), so it cannot thread a `clock=` parameter into these sites. Threading reaches unit-level action tests but cannot freeze an argv-driven whole-run re-entry. The calc-sheets `_utc_now()` is a parallel helper to `core.time.now()`; any seam must be the single clock both route through.

### F4 — Identity fields: `profile_id` is already injectable, `snapshot_id` carries an unseedable uuid tail

`new_profile_id()` returns `str(uuid4())` (`src/aeat/domain/user_profile/_values.py:102-112`) — intrinsically nondeterministic. But the orchestration already accepts a caller-minted `profile_id`: `register_active_profile(..., profile_id=...)` (`src/aeat/application/user_profile/_orchestration.py:224-283`) threads it straight to `ProfileRepository.create(profile_id=...)`, and it keys the bucket directory, keystore, secure-object key, and active-profile pointer. Injection is a viable, already-supported lever for `profile_id`.

`new_profile_snapshot_id(profile_id, created_at=...)` returns `f"{profile_id}:{instant.strftime(...)}:{uuid4().hex}"` (`_values.py:115-118`). Of its three components: `profile_id` is deterministic when injected, the timestamp is deterministic when the clock is frozen, and the trailing `uuid4().hex` is intrinsically nondeterministic with no injection parameter. It accepts a `created_at` but not a uuid override. `snapshot_id` is an opaque surrogate key, not an assertable business value.

Safely deterministic already (content-only hashes, no timestamp inside the digest): `derive_import_fingerprint`, `derive_transaction_id`, `derive_work_unit_id`, and the export `file_sha256` (which carries `exported_at` as a sibling field, outside the digest). These need no intervention.

### F5 — Fingerprints, redaction, and where captures may live

`compute_corpus_sha256` (`_fingerprint.py:108-161`) folds the `.vault/` tree (excluding `.vault/data/`, the live RAG index), the `Settings` snapshot, and the `env/.env` bytes; `compute_db_sha256` (`:164-214`) hashes a curated `var/` tree, excluding caches and `var/runs/` (its own output, a self-reference). Run traces are persisted as `DIAGNOSTIC`-class data and walked by a redaction rule set (NIFs SHA-256-prefixed, URLs host-only, tokens fingerprinted) before serialisation (`_store.py:8-16`) — redaction is partial masking for audit, not removal, so it is NOT a substitute for keeping real financial figures out of committed golden fixtures.

Two distinct capture homes follow. The observability replay's own captures are transient, live under `var/runs/<run_id>/`, and are redacted DIAGNOSTIC data — fine to capture raw there. The operator golden FIXTURES that the Q5 gate asserts against must be committed in the test surface and must contain only SYNTHETIC profiles and figures, per `sensitive-financial-data-secure-storage-only` (no real financial values in plaintext fixtures). The two consumers share the capture/compare logic but not the storage location or the data provenance.

### F6 — The masking layer is the honesty risk and needs an anti-tautology proof

`aeat-quality-gates` and `no-tautological-calculation-tests` bind the compare layer: a mask broad enough to hide a real regression defeats the gate. Once the clock seam is frozen and `profile_id` injected, the only residually nondeterministic JSON leaves are a small, enumerable set — the `snapshot_id` uuid tail, the observability `run_id`, and any wall-clock field the seam does not reach. The mask must be a declared, narrow, reviewed allowlist of JSON paths, and must be itself falsifiable: a proof test captures the same scenario twice with the seam frozen and identity injected and asserts that, WITHOUT masking, the only differing fields are exactly the declared mask set — so the mask cannot silently grow to cover a genuine output diff.

### F7 — Reuse surface: one substrate, two consumers

The Q5 decision chose "a separate operator golden-task replay gate that reuses the methodology, not the brief." The capture+canonicalise+mask+compare logic is the methodology and must live in one place. Two consumers stand on it: (a) the existing `replay_run`, extended to capture the result envelope on the original run and assert it on re-entry — closing the F1 gap; and (b) the operator golden gate, which layers trajectory assertions and AEAT-oracle expected casilla values ON TOP of the same payload-determinism primitive. The operator gate must not re-implement capture or compare; duplicating that logic is exactly the drift Q4 warns against.

### F8 — Coordination with the ledger-add idempotency brief

The ledger-add idempotency fix is a separate brief, but the two interact in two ways. First, that fix must not reduce clock-isolatability (it must keep threading `clock=`/`occurred_at=` rather than reaching for a bare `now()`). Second, this substrate should make the retried-add no-op assertable: a golden scenario that issues an add twice, run against a hermetic synthetic `var/` root, can assert `db_sha256` is identical after the second add — proving the retry is a true no-op. This is the concrete motivation for the optional post-state fingerprint assertion tier (decision 3 in the ADR).

## Open questions carried to the ADR

The four decisions the ADR resolves: (1) clock seam shape — extend threading to the four non-isolatable sites versus a bounded contextvar seam in `core/time`; (2) identity determinism per field — inject versus mask for `profile_id` and `snapshot_id`; (3) golden capture shape — capture-raw-then-mask versus capture-canonicalised, comparison granularity, and whether the gate asserts `db_sha256`; (4) how one substrate serves both the observability replay and the operator gate without duplication.
