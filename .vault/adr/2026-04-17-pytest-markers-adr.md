---
tags:
  - "#adr"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-research]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-13-filing-complementaria-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
issue: "#163"
charter: "#116"
---

# `pytest-markers` adr: `granular-domain-markers-and-live-read-live-write-split` | (**status:** `accepted`)

## Problem Statement

The current pytest marker vocabulary is a binary `unit | live` pair registered in `pyproject.toml`. Two structural shortcomings follow:

- No marker expresses which `aeat.*` subpackage domain a test exercises, so scoped runs ("all financial-input tests", "everything below the storage boundary", "everything touching the AEAT remote") and CI sharding have no collection-time axis to key on.
- The `live` marker conflates reads (status probes, inbox fetch, justificante CSV round-trip, Anthropic round-trip) with writes (submission engine, filing amendment, any modelo submit path). Charter `#116` rule `R1` categorically forbids any programmatically reachable live write against AEAT Sede Electronica - AEAT has no sandbox, every successful write is a legally binding filing. Today that ban is carried purely by runtime refusal inside `SubmissionEngine.__init__` (charter `R5`) plus operator discipline around the `AEAT_LIVE_SUBMIT_ENABLED` environment variable (`R3`).

Issue `#163` requires the taxonomy to be promoted to first-class markers, the live-read / live-write distinction to be visible at collection time, and the live-write path to be structurally blocked from automated execution rather than only refused at runtime.

## Considerations

- Roughly 140 test modules live under `src/aeat/` (Rust-style colocated) plus a small `tests/` tree. 14 modules are currently `live`-marked; 0 exercise a live AEAT write under the proposed taxonomy.
- The test suite already mandates module-level colocation, so a module-level `pytestmark = [...]` convention aligns with the existing layout better than per-function marker scattering (which is the current practice in ~80% of files).
- The live-write ban must layer on top of charter `#116`, not replace any existing rule. The runtime refusal in `SubmissionEngine.__init__` (charter `R5`) and the `AEAT_LIVE_SUBMIT_ENABLED` env gate (`R3`) remain the canonical write-prevention guards. The pytest layer contributes defence in depth: a test cannot survive to runtime if it was never collected.
- Any gate that relies only on an environment variable can be flipped by a CI runner, a leaked secret, or an automation script. A TTY check adds a physical-presence factor that is orders of magnitude harder to satisfy accidentally.
- The charter `R4` operator-confirmation pattern (operator types a modelo+period phrase exactly) sets the precedent for a long, hard-to-type confirmation phrase. The pytest bypass reuses that shape.
- Nine new markers must be registered in the pyproject markers table so pytest does not emit `PytestUnknownMarkWarning` for any path in the suite.
- Env-var alignment between `env/.env.example`, `src/aeat/config.py` `Settings`, and `tests/test_config.py` is a repo-wide invariant; new env vars for the bypass must be staged in all three places in the implementation plan.

## Constraints

- **Charter `#116` R1..R6 are invariant.** This ADR cannot weaken any of them; it can only add further enforcement layers.
- **Zero `live_write` tests exist today and none are planned by this feature.** The marker and the bypass are dormant infrastructure, shipped so that any future write-shaped probe is required to carry the marker and is collection-banned by default.
- **Rust-style colocation.** Tests live inside each module directory under `src/aeat/<subpackage>/test_*.py`. Module-level `pytestmark` is cheap to apply uniformly there.
- **No mocks/patches in live tests.** `CLAUDE.md` already bans mocks in `live`-marked modules; the split inherits that ban across both `live_read` and `live_write`.
- **pyproject `testpaths` includes both `src` and `tests`.** The conftest hook must live at a location pytest picks up for items under both trees - `tests/conftest.py` is the canonical choice.
- **GitHub Actions CI runs `just test` on every PR.** `just test` must remain a fast unit-only run after the migration.

## Decision

Adopt the nine-marker taxonomy, mandate module-level application, install a collection-time integrity and ban hook, and rewrite the `just` recipes to match.

### Axis A - access level (mutually exclusive, exactly one per test)

- `unit` - deterministic, no external I/O. Mocks/stubs permitted per `CLAUDE.md`. Selected by `just test`.
- `live_read` - talks to a real external service, read-shaped operations only. Opt-in via `AEAT_LIVE_TESTS_ENABLED=1`. Google Workspace live_read additionally requires `AEAT_LIVE_TESTS_GOOGLE=1`. Selected by `just test-live`.
- `live_write` - talks to a real external service, write-shaped operations. **Collection-banned by default.** Reserved for AEAT-binding writes; Google scratch round-trips stay `live_read`.

Exactly one of these three markers is required per collected test item. Zero or more than one is a collection error.

### Axis B - domain (one or more required per test module)

- `domain_aeat_remote` - `auth`, `browser`, `casillas`, `inbox`, `justificante`, `portals`, `status`, `sync`.
- `domain_submission` - `filing`, `submission`. Kept separate from `domain_aeat_remote` so the write-capable boundary has a dedicated audit lens under charter `R1`.
- `domain_financial_input` - `financial`, `cli/financial`.
- `domain_local_state` - `storage`, `models`, `normatives`, `manuals`, `corpus`, `schema`, `deadlines`, `cli/deadlines`.
- `domain_mediation` - `workflow`, `llm`, `i18n`, `testing`, `cli/workflow`, `cli/llm`.
- `domain_infra` - root modules (`config`, `env_io`, `errors`, `logging`), non-domain-specific `cli`, `setup`, top-level `tests/*.py`.

Every test module carries at least one domain marker. Mixed-domain modules (rare but legal) carry a list.

### Module-level application is MANDATED

All markers are applied module-level via a single `pytestmark = [...]` assignment. A typical header reads `pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]`.

Per-function domain markers are forbidden. Per-function access markers are forbidden. If a module today mixes `unit` and `live_read` functions, it must be split into two modules rather than overridden per-function. Pytest marker inheritance is additive: a function under a `unit`-marked module decorated with `@pytest.mark.live_read` ends up with both access markers, which the integrity check rejects as a usage error. Mixing is therefore not only discouraged - it is mechanically impossible to express correctly.

### Collection-time enforcement

A new hook in `tests/conftest.py` runs at `pytest_collection_modifyitems` and:

- Raises `pytest.UsageError` for any item with zero or more than one access marker.
- Raises `pytest.UsageError` for any item lacking at least one `domain_*` marker.
- **Drops** (not skips) any `live_write` item unless the three-factor bypass is satisfied.

### Three-factor `live_write` bypass

All three factors must hold simultaneously for `live_write` items to survive collection:

- `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1` in the environment.
- `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM` in the environment, equal byte-for-byte to the phrase `I ACCEPT THE RISK OF FILING A LIVE TAX RETURN`.
- `sys.stdin.isatty()` returns truthy (interactive terminal).

Missing or mismatching any one factor causes the collection hook to silently drop the item. Drop, not skip: skipped items would still appear in pytest test reports as "would have run if unskipped" and are one env-var flip away from executing; dropped items are invisible to pytest downstream of collection and cannot be reinstated by any marker-expression flag.

**The bypass is distinct from `AEAT_LIVE_SUBMIT_ENABLED`.** Setting the bypass does NOT enable a live submission: it only controls collection. A `live_write` item that survives collection still has to satisfy charter `R3` (env gate) and `R5` (`SubmissionEngine.__init__` runtime refusal), both of which remain verbatim. The bypass is strictly additive defence in depth on top of R1..R6.

### Marker integrity test

`tests/test_marker_integrity.py` (new) walks every test module under `src/aeat/` and `tests/` via `ast`, asserts each module has exactly one module-level `pytestmark = [...]` assignment, and asserts the list contains exactly one access marker plus at least one domain marker. CI reports surface this as a unit-test failure rather than a pytest usage error, which is friendlier for drift triage.

### Marker registration

pyproject registers all nine markers with human-readable descriptions under `[tool.pytest.ini_options].markers`. `addopts` becomes `-v --tb=short -m 'unit'`. The stale `live` entry is removed in the same commit as the hook and the file-level migration.

### `just` recipes

The justfile gains four recipes. `test` runs plain `uv run pytest` (unit-only via addopts). `test-live` runs `uv run pytest -m "unit or live_read"`. `test-live-read` runs `uv run pytest -m "live_read"`. `test-domain DOMAIN` runs `uv run pytest -m "unit and domain_{{DOMAIN}}"` where `DOMAIN` is the suffix after `domain_` (for example `financial_input`, `submission`, `aeat_remote`).

Neither `just test` nor `just test-live` ever selects `live_write`; the only path that touches `live_write` is a direct interactive `pytest -m live_write` run with all three bypass factors active, which still has to survive charter `R5`.

### Scratch-resource round-trips stay `live_read`

Google scratch tests (`_test_docs_live.py`, `_test_drive_live.py`, `_test_sheets_live.py`, `tests/live/test_google_fixtures_smoke.py`) write against project-owned scratch resources. Charter `R1` targets AEAT Sede Electronica specifically (legally binding writes, no sandbox); Google scratch writes are out of scope. They remain `live_read` with an explanatory comment in the marker description, and a future `live_scratch_write` marker can be introduced if the project later wants to audit them separately.

## Implementation

High-level, sequenced in one mechanical refactor PR:

- Update `pyproject.toml`: register the nine new markers, remove `live`, change `addopts` to `-v --tb=short -m 'unit'`.
- Add `aeat_live_write_unsafe_bypass: bool = False` and `aeat_live_write_unsafe_bypass_confirm: str = ""` to `src/aeat/config.py` `Settings` with loud warning descriptions, and mirror in `env/.env.example`. `tests/test_config.py` enforces alignment.
- Rewrite `tests/conftest.py` with the `pytest_collection_modifyitems` hook shown in the research doc (three-factor bypass, drop semantics, usage-error raises).
- Add `tests/test_marker_integrity.py`.
- Migrate all ~130 test modules: insert module-level `pytestmark = [...]` with the correct access and domain markers per the inventory in the research doc, delete per-function `@pytest.mark.unit` / `@pytest.mark.live` decorators, rename remaining `@pytest.mark.live` function-level references to `live_read`.
- Update the `justfile`: rewrite `test-live`, add `test-live-read`, add `test-domain`.
- Update `CLAUDE.md` lines describing the marker taxonomy; add a `tests/README.md` documenting the taxonomy and the three-factor bypass incantation with explicit cross-reference to charter `#116`.

Verification after the refactor:

- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write` must collect zero items by default and continue to collect zero even with `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1` alone or `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM` alone.
- `tests/test_marker_integrity.py` must pass.
- `just test` must be unit-only. `just test-live` must union unit and live_read.
- `tests/test_config.py` must pass with the two new env vars.

## Rationale

- **Module-level pytestmark over per-function.** Per-function markers drift: a developer adds a new test, forgets the decorator, the item silently falls out of the suite partition. Module-level declaration co-locates the classification with the module purpose and makes the integrity check a pure AST walk. Splitting mixed-access modules instead of supporting per-function overrides keeps the inheritance semantics predictable and aligns with the Rust-style colocation convention.
- **Six domains, not five.** `domain_submission` is carved out of `domain_aeat_remote` because charter `R1` makes the write-capable boundary uniquely sensitive. Auditors and future live-write experiments need a precise lens; collapsing submission into the broader AEAT-remote domain dilutes it.
- **Drop over skip for live_write.** Skipped items appear in reports as would-have-run entries and are one env-var flip from executing. Dropped items are invisible to pytest downstream of collection. Charter `R1` demands structural invisibility, not visible deferral.
- **Three-factor bypass, not two.** A two-factor env+confirm bypass can be satisfied by any CI runner: both are environment variables and both are settable in a workflow file or a secret. The TTY check adds a physical-presence factor. The combination is consistent with the R4 operator-confirmation model (physical keystroke entry of a long phrase).
- **Bypass env names carry `UNSAFE`.** Shell history and audit-log greps surface the intent immediately. Bare `AEAT_LIVE_WRITE_BYPASS` would be ambiguous.
- **Collection-time, not runtime.** Runtime refusal already exists (charter `R5`). A collection-time layer means the test body never executes, never touches an HTTP client, never instantiates `SubmissionEngine`. Two independent guards at two independent layers is the cheapest durable defence in depth.

## Alternatives Considered

- **Per-function domain markers, no module-level mandate.** Rejected: verbose, drift-prone, requires ~900 individual decorators vs ~140 module-level assignments, and makes the integrity check an item-level walk rather than a module-level AST pass. The marker inheritance semantics also mean that per-function overrides cannot cleanly downgrade a module-level marker, so mixed-access modules remain impossible to express correctly even under this alternative.
- **Single binary `live` marker, submit-gate only.** Rejected: the existing state of the repo. Invisible to collection, conflates reads and writes, does not support scoped runs, requires developers to read test bodies to understand what a live test does, and leaves the entire live-write ban resting on a single runtime check inside `SubmissionEngine`.
- **Skip-based ban instead of drop-based.** Rejected: skipped items still surface in pytest reports as deferred work and in CI as would-have-run entries, which creates normalisation pressure to unskip. Skip is also one env-var flip from execution. Drop is invisible downstream of collection and makes the default-safe posture structural.
- **Two-factor bypass without TTY check.** Rejected: both factors would be environment variables; any CI runner, any leaked `.env`, any automation script that exports the pair would satisfy the gate. The TTY check is the only factor that a non-interactive process cannot fabricate.
- **Separate `live_scratch_write` marker for Google scratch round-trips.** Rejected for this feature: out of scope of charter `R1`, adds taxonomy surface area with no current consumer. Left as a future option if the project later wants to audit scratch writes separately.
- **Additional `domain_llm`, `domain_identity`, `domain_config`, `domain_models` carve-outs.** Rejected: sub-folders of already-covered domains, do not survive the "is it a useful scoping axis for CI shards or audits?" test. Can be introduced later if their test populations grow.
- **Placing the hook at repo-root `conftest.py` instead of `tests/conftest.py`.** Rejected for this feature: `tests/conftest.py` already exists and pytest picks it up for items under both `src/` and `tests/` because `testpaths` shares the rootdir. If verification shows items under `src/aeat/...` escape the hook, the plan verification step flags it and the fix is to add a `src/aeat/conftest.py` that re-exports the hook or to promote it to the repo root - mechanical, not architectural.
- **Removing charter `R5` runtime refusal now that the collection hook exists.** Explicitly rejected. The collection hook is additive defence in depth; `R5` remains the last-line runtime refusal and must not be weakened. The two layers are independent - removing either one weakens the safety posture.

## Consequences

### Positive

- **Scoped runs become first-class.** Developers and CI shards can select by domain, access, or any intersection. `just test-domain financial_input` becomes a one-liner.
- **Live-write path is structurally blocked at collection.** Charter `R1` gains a fourth enforcement layer that operates before any test body executes.
- **Marker drift is detectable.** `tests/test_marker_integrity.py` surfaces any test module that forgets to carry the correct markers as a normal unit-test failure.
- **PytestUnknownMarkWarning is eliminated.** All nine markers are registered.
- **Live-read vs live-write is explicit in every test.** Future charter audits can lens on `domain_submission and live_read` or `live_write` in isolation; the audit surface is precise.
- **The bypass is hard to trip accidentally.** Three independent factors, one of which requires an interactive TTY, mean no CI runner, cron job, or shell one-liner can cross the gate without human physical presence.

### Negative

- **One-time migration cost.** ~130 test modules need module-level `pytestmark` insertion and per-function decorator deletion. Mitigated by mechanical refactor in a single PR, plus the integrity test as the migration acceptance gate.
- **Mixed-access modules must be split, not overridden.** A handful of modules may need to be factored into two files. Rare (no known case as of the research survey); cost bounded.
- **Extra env vars in Settings and .env.example.** Two new vars (`AEAT_LIVE_WRITE_UNSAFE_BYPASS`, `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM`), both documented with loud warnings. The cost is modest; `tests/test_config.py` alignment prevents drift.
- **Documentation churn.** `CLAUDE.md`, `tests/README.md` (new), and possibly `scripts/README.md` all need updates to reference the new taxonomy and the bypass incantation.

### Neutral

- **CI behaviour is identical for default runs.** `just test` remains a fast unit-only selection. `just test-live` gains a `live_read` semantic but continues to be opt-in and never touches `live_write`.
- **Charter #116 R1..R6 are untouched.** This ADR is additive only. `SubmissionEngine` runtime refusal, `AEAT_LIVE_SUBMIT_ENABLED` env gate, operator confirmation patterns, and all prose rules of the charter remain verbatim. The pytest layer is a new enforcement surface on top of those rules, not a replacement.
- **Existing live-marked modules migrate one-for-one to live_read.** No test meaning changes; no test body changes. The 14 live-marked modules become `live_read`; zero `live_write` modules exist at commit time.
- **Google scratch tests continue to behave as today.** `live_read` plus the orthogonal `AEAT_LIVE_TESTS_GOOGLE=1` gate remains the opt-in mechanism.

## References

- Research: `[[2026-04-17-pytest-markers-research]]` - full current-state survey, per-module classification inventory, hook source sketch, recipe shapes.
- Charter #116 (live-AEAT-write safety charter): rules R1..R6 referenced inline; R1 (no automated live write), R3 (`AEAT_LIVE_SUBMIT_ENABLED` must never be set in pytest context), R4 (operator confirmation phrase pattern), R5 (`SubmissionEngine.__init__` runtime refusal under `PYTEST_CURRENT_TEST`).
- Prior audit: `[[2026-04-16-live-write-test-audit-adr]]` and `[[2026-04-16-live-write-test-audit-research]]` - established marker integrity as the primary test-boundary tripwire; this ADR formalises that principle into nine markers, a hook, and an integrity test.
- Submission engine: `[[2026-04-12-submission-engine-adr]]` - source of the runtime refusal (R5) that this ADR layers on top of.
- Filing complementaria: `[[2026-04-13-filing-complementaria-adr]]` - consumer of the dry-run-only live submission path that remains `live_read` after the split.
- Module structure: `[[2026-04-12-base-module-structure-adr]]` - Rust-style colocated tests convention that module-level `pytestmark` aligns with.
- Issue #163 - originating feature request.
