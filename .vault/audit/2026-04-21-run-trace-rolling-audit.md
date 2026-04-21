---
name: 2026-04-21-run-trace-rolling-audit
description: Rolling autonomous audit log for PR #140 (#99 run-trace). Each round appends findings + fixes until no new issues surface.
type: audit
tags:
  - "#audit"
  - "#run-trace"
date: 2026-04-21
related:
  - "[[2026-04-14-run-trace-research]]"
  - "[[2026-04-14-run-trace-adr]]"
  - "[[2026-04-14-run-trace-plan]]"
  - "[[2026-04-14-run-trace-phase1-summary]]"
---

# run-trace rolling audit — PR #140

Autonomous, no-human-in-the-loop audit loop on PR #140 (`feature/99-run-trace`).
Each round launches a full review pass (vaultspec-code-reviewer subagent, fresh
self-review lens, Gemini if it re-reviews). Every surfaced finding is fixed in
code and appended below. The loop terminates only when one complete round
produces zero new findings across every reviewer.

## Convergence state

**Round 0 — baseline (carried from prior sessions)**

| Sub-round | Reviewer | Findings | Commit |
|-----------|----------|----------|--------|
| 1 | Gemini original review | 5 code-level | `cf21d3e` |
| 2 | L2–L10 9-lens self-sweep | 7 code-level | `2b92166` |
| 3 | L11 fresh-eyes | 1 code-level | `653e072` |
| 4 | Gemini 2nd pass (G1–G5) | 5 code-level | `ad44f80` |
| 5 | L12–L14 ADR/charter/red-team | 1 doc-level | `391fa3e` |
| 6 | Gemini 3rd pass (G6–G7) | 2 code-level | `3ed1e51` |
| 7 | L15 signal/exception cleanup | 0 | — |

Baseline tally entering this rolling audit: **20 code-level fixes + 1 doc-level fix across 7 fix commits**. PR at HEAD `3ed1e51`, CI green Ubuntu+Windows, merge state CLEAN, 42 obs tests + 2020 full-suite pass.

Rounds 8+ below are the autonomous rolling phase.

---

## Round 8 — vaultspec-code-reviewer against 3ed1e51

*Reviewer:* `vaultspec-code-reviewer` subagent, dispatched 2026-04-21.
*Verdict:* **REVISION REQUIRED** — 1 BLOCKING, 7 SHOULD-FIX, 6 NITs.

### Findings

| ID | Severity | File:line | Finding | Resolution |
|----|----------|-----------|---------|------------|
| B1 | BLOCKING | `_fingerprint.py:74-90` + `_replay.py:118-119` | `corpus_sha256` did not include `env/.env` bytes. Operator edits to dotfile after process start could evade the drift gate because the already-loaded `Settings()` snapshot didn't reflect them. | Fold `env/.env` bytes into the hash alongside the vault tree and the Settings blob. Missing `env/.env` hashes the empty-string digest deterministically. |
| S1 | SHOULD-FIX | `_context.py:190-198` + cleanup path | `addHandler(sink)` happened BEFORE `RUN_CONTEXT_VAR.set`; `removeHandler` happened AFTER `.reset`. A concurrent thread's trailing record during those windows could land on the sink with a stale / empty run_id. | Set contextvars first, then attach sink. Mirror on exit — detach sink first, then reset contextvars. |
| S2 | SHOULD-FIX | `_recorder.py:83` | Every recorded event spammed stderr at INFO via the default handler. | Keep the `_logger.info(...)` emission (so the record reaches the sink with the correct log level), but install a `_DropRunEventFilter` on the default stderr handler that suppresses records carrying a `run_event` extra. Sink still receives them. |
| S3 | SHOULD-FIX | `_replay.py:130` | Replay safety relied on argv pattern matching. A future CLI defaulting to live mode would bypass silently. | Export `REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE"`; set it during the re-entered `app(argv)` call (restoring any prior value on exit). Submission engine / any future AEAT-write barrier can now machine-check this marker. |
| S4 | SHOULD-FIX | `_errors.py:51-53` + `cli/run/replay.py:34` | Unicode ellipsis U+2026 in error messages blew up on Windows cp1252 consoles. | Replace with ASCII `...`. |
| S5 | SHOULD-FIX | `_store.py:203` sort + `_models.py` schema | `RunTrace.started_at` / `RunEvent.timestamp` allowed naive datetimes; `iter_runs` sort crashes on mixed naive/aware. | `model_validator(mode="after")` on both models rejects naive datetimes at the pydantic boundary. |
| S6 | SHOULD-FIX | `cli/_observability.py` module docstring | Name-based secret redaction was insufficiently documented — value-side leakage (e.g. `--by "tok-…"`) is possible. | Expand the module docstring with an explicit "name-side only" caveat plus guidance for wrapped-command authors. |
| S7 | SHOULD-FIX | `_models.py` + `_context.py` + `_replay.py` | Replay produced traces indistinguishable from fresh runs — no way to chain a replay back to its original. | Added `replay_of: str \| None = None` to `RunTrace`. Default None keeps backward-compat. `replay_run` stores the original run_id in `AEAT_REPLAY_ACTIVE`; `run_context` reads it during trace construction and propagates only when the env value matches the canonical 16-hex shape (legacy "1" sentinels are ignored). |
| N1 | NIT | `_sink.py:115` | `newline=""` is correct on write mode; docstring already explains. | No change — accept as-is. |
| N2 | NIT | `_fingerprint.py:56` | Pre-resolve excluded paths once. | Already resolved in the frozenset; the `.resolve()` on `dir_path / name` is needed because `os.walk` yields non-resolved paths. Keep as-is. |
| N3 | NIT | `cli/run/replay.py:34` | Cosmetic duplication of hash info. | Left as-is; the duplication helps operators read the message without peeking at the exception type. |
| N4 | NIT | `cli/run/show.py:34-42` | `[red]` markup in piped output. | Rich already handles terminal detection; not worth a code change. |
| N5 | NIT | `_context.py:155` | Dead `step_end_emitted` flag. | Removed — the block now runs unconditionally inside the `finally`, STEP_END emits exactly once without the flag. |
| N6 | NIT | `logging.py:36-56` | Minor first-record import cost. | Cache is already populated after the first call; accepted. |

### Additional tests landed in round 8
- `TestTimezoneAwareness` (3 cases) — naive datetimes rejected at both `RunEvent` and `RunTrace`.
- `TestReplayOfField` (2 cases) — `replay_of` default None + roundtrip.
- `TestEnvFileFingerprint` — `.env` edits change `corpus_sha256`.
- `TestStderrRunEventFilter` (2 cases) — filter drops `run_event` records, events still reach JSONL sink end-to-end.
- `TestReplayRun.test_replay_of_propagated_via_env_var` + `test_replay_of_ignored_when_env_is_non_canonical`.
- `test_refuses_on_corpus_drift` — also asserts message uses ASCII `...` not `…`.

### Totals after round 8
- 52 observability unit tests (+10 new in this round), 2030 full-suite pass.
- 8 code-level fixes (B1, S1–S5, S6-doc-only, S7) + 1 code cleanup (N5).
- Ruff + format + ty all clean.

### Next round
Round 9 will launch another `vaultspec-code-reviewer` pass against the new HEAD to verify round 8's fixes don't introduce regressions, plus re-check Gemini on the push.

---

## Round 9 — vaultspec-code-reviewer against 14f24a3

*Reviewer:* `vaultspec-code-reviewer` subagent, dispatched 2026-04-21 after round-8 commit.
*Regression review verdict:* **PASS on all round-8 items (B1, S1-S7)**.
*New findings:* 1 SHOULD-FIX, 2 NITs.
*Merge readiness verdict:* NEEDS ANOTHER ROUND.

### Regression pass on round 8
All eight round-8 fixes verified correct by inspection + existing tests:
- B1 `corpus_sha256` folding `env/.env` — `TestEnvFileFingerprint` green, cross-platform-safe.
- S1 sink ordering — set-then-attach / detach-then-reset confirmed symmetric.
- S2 stderr filter — `_DropRunEventFilter` only drops records with `run_event` extra; JSONL sink untouched; end-to-end test confirms.
- S3 `AEAT_REPLAY_ACTIVE` round-trip — non-leaking, restores prior value.
- S5 naive-datetime validators — fire at `RunEvent.timestamp`, `RunTrace.started_at`, `RunTrace.finished_at` (with None allowance).
- S7 `replay_of` — length + hex validation correctly refuses non-canonical env values.

### New findings

| ID | Severity | File:line | Finding | Resolution |
|----|----------|-----------|---------|------------|
| NEW-1 | SHOULD-FIX | `_replay.py:65-94` argv reconstruction | Boolean flags reconstructed as `--name=True` are rejected by Typer because value-less options (`typer.Option(False, "--json")`) don't take a value. Renamed flags (Python param `as_json` vs Typer flag `--json`) fail with "No such option: --as-json". | (a) Argv emission now handles booleans: `"True"` → bare flag, `"False"` → skip; (b) `ArgumentRecord` gained `cli_flag: str \| None = None` for explicit override; (c) `build_arguments` + `cli_run_context` accept `flag_map={"as_json": "--json"}` to set the override at capture time. Current wrapped commands already use CLI-flag naming as dict keys, so no caller changes are required — the escape-hatch is there for future commands that use `locals()` or have renamed flags. |
| NEW-2 | NIT | `_context.py:246` | `replay_of` acceptance lowercases via `.lower()` for defensive normalization. | Documented via comment. |
| NEW-3 | NIT | `_fingerprint.py` | `compute_corpus_sha256` walks `.vault/` on every invocation. | Documented as "follow-up optimisation"; not a regression. |

### Additional tests landed in round 9
- `TestArgvReconstruction.test_boolean_false_flag_is_skipped` — False bools omitted.
- `TestArgvReconstruction.test_boolean_true_flag_uses_bare_form` — True emits bare flag.
- `TestArgvReconstruction.test_cli_flag_override_wins_over_name_derivation` — override path.
- `TestReplayEndToEndBooleanFlag.test_replay_of_workflow_list_json` — end-to-end replay of `aeat workflow list --json` through the real Typer app.
- `TestFlagMap` (3 cases) — `build_arguments` forwards `flag_map` to `cli_flag`.

Existing `TestArgvReconstruction.test_positional_emitted_without_prefix_and_first` + `test_multiple_positionals_preserve_declared_order` + `test_flag_name_underscore_converted_to_dash` updated to expect the new bare-flag emission for True bools.

### Totals after round 9
- 59 observability unit tests (+7 new, 3 updated), 2037 full-suite pass.
- 1 code-level fix (NEW-1) covering argv-reconstruction correctness.
- Ruff + format + ty + relative-imports mandate all clean.

### Next round
Round 10 will re-dispatch `vaultspec-code-reviewer` to verify round-9's NEW-1 fix + check for any residual finding. Loop continues until a full round reports zero new code-level findings.
