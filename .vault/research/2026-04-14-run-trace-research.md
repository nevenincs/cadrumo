---
name: run-trace observability research
description: Research notes on project-wide run_id propagation, JSONL audit log, and deterministic dry-run replay for AEAT CLI runs
tags:
  - "#research"
  - "#run-trace"
date: 2026-04-14
modified: '2026-04-14'
related:
  - "[[2026-04-12-workflow-engine-research]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-14-run-trace-adr]]"
---

# run-trace observability research

## context

Issue [#99](https://github.com/wgergely/aeat/issues/99) targets the gap between
the workflow engine's local `run_id` and the rest of the project. Today only
`aeat.application.workflow._models.compute_run_id` exists; nothing in
`aeat.adapters.outbound.aeat.export`, `aeat.application.sync`, `aeat.inbox`, `aeat.status` propagates a run
identifier, there is no JSONL audit log of what happened during a run, and
there is no way to replay a recorded run deterministically for audit.

This document captures the prior art surveyed on 2026-04-14 and the
constraints that shape the architecture decision.

## current state

- `src/aeat/logging.py` is a 53-line factory that configures a single stderr
  `StreamHandler` via `dictConfig`. No filters, no contextvars, no JSONL sink.
  It exposes `configure_logging()` and `get_logger(name)`.
- `src/aeat/application/workflow/_models.py::compute_run_id` hashes
  `(tax_id, modelo, period, started_at)` into a 16-char hex prefix. It is the
  only place a run identifier is minted.
- `WorkflowResult.run_id` is a 16-char hex string, strict pydantic v2
  (`ConfigDict(strict=True, frozen=True, extra="forbid")`).
- `grep -ri run_id src/aeat/{submission,sync,inbox,status}` returns nothing:
  the identifier never crosses a subpackage boundary.
- `aeat.entrypoints.cli` already has a `workflow run` subcommand
  (`src/aeat/entrypoints/cli/workflow/run.py`) — the new CLI surface must be a separate
  top-level `aeat run` namespace to avoid colliding with it.
- No use of `contextvars` anywhere in the codebase.
- No directory or module named `observability`, `trace`, or similar.
- `tests/test_config.py` asserts `Settings.env_var_names()` is bijective with
  the uppercase env names extracted from `env/.env.example` via
  `^([A-Z_][A-Z0-9_]*)=`. Any Settings addition must land in both places.
- `aeat.core.errors.AeatError` is the hierarchy root; subclasses carry structured
  attributes (e.g. `SiteHealthError` carries a `SiteHealthStatus`).

## sibling branches in flight

The following branches are active and must not be stepped on:

- `feature/117-live-submit-hardening` owns the internals of
  `src/aeat/adapters/outbound/aeat/export/` and may rename or restructure internal modules. This
  feature wraps the *outermost* submission public entry point only (e.g.
  `SubmissionEngine.submit_draft`) and never imports underscored submission
  modules. Settings additions must be purely additive.
- `feature/74-transaction-catalogue` owns
  `src/aeat/domain/financial/transactions/` — Track B, no overlap.
- `feature/106-n26-research` is research-only.

`src/aeat/domain/modelos/`, `src/aeat/domain/financial/providers/`, and `src/aeat/application/workflow/`
are stable on `origin/main` and safe to import.

## constraints

1. **Pydantic v2 mandate.** Every record persisted to disk or crossing a
   subpackage boundary must be a strict, frozen, `extra="forbid"`
   `BaseModel`. Closed enumerations are `enum.StrEnum`. No dataclasses for
   boundary-crossing types. No bare `dict[str, Any]` in public signatures
   or JSONL lines.
2. **Contextvars must survive awaits.** `contextvars.ContextVar` already
   propagates through `asyncio` tasks; no special copy_context() needed if
   we enter the context manager at the outermost call.
3. **Every public CLI entry point must emit ≥1 `RunEvent`.** The wiring is
   outermost-only: the context manager enters once, records `STEP_START` /
   `STEP_END` events bracketing the phase, and downstream code calls
   `record_event(kind, payload=...)` additively. Internal submission modules
   are off-limits (#117 territory) — the submission wrap sits at
   `SubmissionEngine.submit_draft` / `submit_amendment` only.
4. **Replay is dry-run only.** Replay never contacts AEAT. The replay surface
   reconstructs `ArgumentRecord`s, verifies `corpus_sha256` hasn't drifted,
   and re-enters the same CLI path with `dry_run=True`. If the current corpus
   sha differs from the recorded one, replay refuses with a typed error.
5. **JSONL is append-only and fsync'd.** One `events.jsonl` per run under
   `var/runs/<run_id>/`, plus a `trace.json` holding the `RunTrace` metadata.
   Both round-trip via the pydantic models.
6. **No Actions CI.** Local gates (`just lint/typecheck/test/hooks`) are the
   only gate. No workflow file under `.github/workflows/`.
7. **Live env var canonical name** is `AEAT_LIVE_TESTS_ENABLED`, not
   `AEAT_LIVE_TESTS`.

## prior art surveyed

- OpenTelemetry Python (`opentelemetry.context`) uses contextvars under the
  hood; we reject the full OTel backend because it adds a cross-cutting
  exporter contract we do not need. We adopt only the contextvars pattern.
- `structlog` provides context binding via its own context class. Rejected
  because it would replace `logging.Logger` usage across the project; we
  prefer a minimal logging filter that augments existing records.
- The existing `WorkflowResult` is the closest prior art. The new `RunTrace`
  is *not* a replacement — it records the CLI entry point (arguments, fingerprints,
  outcome) rather than workflow-internal stages. A single run may produce at
  most one `RunTrace` and zero-or-one `WorkflowResult` (if it invoked the
  workflow engine). The two are orthogonal.
- `hashlib.sha256` is used throughout the project for deterministic IDs;
  corpus and db sha256 follow the same pattern.

## open questions resolved during research

- **Q:** Should the run id be generated by observability or reused from
  `aeat.application.workflow.compute_run_id`?
  **A:** Observability mints its own 16-char hex run id when the CLI enters
  `run_context(entrypoint=...)` at the outermost call. When the workflow
  engine runs inside this context, its `WorkflowResult.run_id` is a separate
  field and we record the mapping via a `WORKFLOW_STARTED` event carrying
  both ids in its payload. The observability run id is the audit anchor.
- **Q:** How do we compute `corpus_sha256`?
  **A:** Hash the sorted tuple of relative paths under `.vault/` plus the
  serialized `Settings` object (pydantic `model_dump_json()`). Deterministic,
  already on-disk, no network round-trip.
- **Q:** How do we compute `db_sha256`?
  **A:** Hash the sorted tuple of `(rel_path, file_sha256)` pairs under
  `var/` excluding `var/runs/` (self-reference) and `var/browser-traces/`
  (Playwright noise). Stable across a run.
- **Q:** How do we compute `cert_fingerprint`?
  **A:** Delegate to `aeat.adapters.outbound.aeat.auth` if available; otherwise record the SHA-256
  of the DER body of the active certificate. When no certificate is loaded
  (many CLI paths), record the empty string — the `RunTrace` model accepts
  an empty fingerprint as "no certificate bound to this run".
- **Q:** Where do colocated tests live?
  **A:** `src/aeat/core/observability/test_*.py` — matches the Rust-style
  colocated test convention used elsewhere in the repo
  (e.g. `src/aeat/entrypoints/cli/test_*_cli.py`).

## references

- `src/aeat/logging.py:1-53`
- `src/aeat/errors.py:1-69`
- `src/aeat/config.py:43-498`
- `src/aeat/application/workflow/_models.py:110-187`
- `src/aeat/entrypoints/cli/__init__.py:45-96`
- `src/aeat/entrypoints/cli/workflow/run.py:13-59`
- `tests/test_config.py:1-76`
