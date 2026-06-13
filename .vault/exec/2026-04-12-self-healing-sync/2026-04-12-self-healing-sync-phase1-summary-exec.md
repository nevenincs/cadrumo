---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-12-self-healing-sync-research]]"
---

# phase 1 summary — self-healing sync (issue #11)

Single-phase implementation on branch
`feature/11-self-healing-sync`. All 9 plan steps landed.

## commits

```
94bfae1 test(sync): live opt-in smoke (#11)
9788c36 feat(cli): aeat sync subcommands (#11)
cb9d378 feat(sync): settings + env documentation (#11)
2214d97 feat(sync): live sync runner orchestration (#11)
7208967 feat(sync): repository + validator (#11)
f2dfb04 feat(sync): healing strategies + dispatcher with bounded policy (#11)
fc8d631 feat(sync): divergence types + semantic classifier (#11)
2242924 feat(sync): errors, protocol stubs, wire schemas (#11)
```

## files touched

New under `src/aeat/application/sync/`:

- `__init__.py` (public re-exports only)
- `_errors.py`, `_protocols.py`, `_wire.py`, `_validator.py`
- `_divergence.py`, `_classifier.py`
- `_strategies/{__init__,_base,_additive_allowlist,_escalate,_benign}.py`
- `_dispatcher.py`, `_runner.py`, `_repository.py`
- `test_wire.py`, `test_classifier.py`, `test_strategies.py`,
  `test_bounded_policy.py`, `test_repository.py`, `test_runner.py`,
  `test_live_sync.py` (live, opt-in)

New under `src/aeat/entrypoints/cli/sync/`:

- `__init__.py`, `run.py`, `list.py`, `show.py`, `resolve.py`,
  `test_cli.py`

Modified:

- `src/aeat/entrypoints/cli/__init__.py` — added `sync_module.app` sub-app wiring.
- `src/aeat/config.py` — added `DivergenceSink` StrEnum and six
  `AEAT_SYNC_*` fields.
- `env/.env.example` — documented the new env vars and rewrote the
  mojibake section dividers as clean ASCII so
  `tests/test_config.py` stops crashing on Windows cp1252 default
  encoding.

## invariants enforced

- **Subpackage layout**: every module lives under `src/aeat/application/sync/`
  or `src/aeat/entrypoints/cli/sync/`; all internal modules are `_`-prefixed;
  callers import from `aeat.application.sync` only.
- **Pydantic v2 strict + frozen + extra='forbid'** on every
  boundary-crossing type: wire payloads, divergence payloads
  (`DivergencePayload` is a `Field(discriminator="kind")` union),
  `DivergenceRecord`, `StrategyOutcome`, `HealingPlan`,
  `SyncRunResult`. Closed enumerations are `enum.StrEnum`.
- **Protocol stubs** for every in-flight dependency (#6/#7/#8/#9/
  #10/#17/#21/#25), each documented against the owning issue.
  `aeat.adapters.outbound.aeat.browser.BrowserSession` and `aeat.core.i18n` are imported
  directly (both branches merged).
- **Bounded auto-heal invariant**: the dispatcher double-gates
  auto-apply on classification ∈ ADDITIVE AND kind ∈
  `auto_heal_allowlist`, with a second-line
  `_enforce_bounded_policy` downgrade that refuses to trust a
  misbehaving strategy. Invariant is tested across every
  `DivergenceKind` under both empty and full allowlists.
- **Errors** inherit from `aeat.core.errors.AeatError` via `SyncError`.
- **Logging** via `aeat.core.logging.get_logger(__name__)` only.
- **Tests** use pytest and real concrete Protocol-conforming test
  doubles; no `unittest.mock`, no `pytest-mock`, no `patch`, no
  skip-masking. `@pytest.mark.unit` / `@pytest.mark.live` on every
  test. Live test gated behind `pytest.importorskip` with an
  intentional `pytest.fail` in the body so the rebase of #8 + #17
  cannot silently leave it inert.

## test counts

- Sync subpackage: 54 unit tests (wire × 7, classifier × 11,
  strategies × 5, bounded policy × 23, repository × 5, runner × 5,
  smoke × 1) plus 1 deselected live test.
- CLI sub-app: 7 unit tests.
- `tests/test_config.py`: 4 alignment tests.
- **Total added by this feature: 65 unit tests + 1 opt-in live.**

## verification tails

```
$ just lint
uv run ruff check .
All checks passed!

$ just typecheck
uv run ty check src tests
All checks passed!

$ just test
...
================ 173 passed, 1 skipped, 8 deselected in 1.55s =================

$ just hooks
uv run prek run --all-files
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
detect private key.......................................................Passed
ruff (legacy alias)......................................................Passed
ruff format..............................................................Passed
ty type check............................................................Passed
```

## deviations from the plan

None.
