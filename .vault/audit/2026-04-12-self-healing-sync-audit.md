---
tags:
  - "#audit"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
title: Self-Healing Sync Code Review
related:
  - "[[2026-04-12-self-healing-sync-adr]]"
  - "[[2026-04-12-self-healing-sync-plan]]"
---

# code review: self-healing sync (#11)

## verdict: APPROVED

All 15 checklist items PASS. Lint, typecheck, tests
(173 passed / 1 live-skipped / 8 deselected), and hooks are green.

## checklist

1. **Pydantic v2 strict invariant — PASS.** Every boundary type is
   a frozen/strict/extra=forbid pydantic v2 model.
   `DivergencePayload` uses `Field(discriminator="kind")` with
   `Literal`-pinned members (`_divergence.py:175-187`).

2. **Bounded auto-heal invariant — PASS (doubly enforced).**
   `AdditiveAllowlistStrategy.apply`
   (`_strategies/_additive_allowlist.py:47-64`) and
   `HealingDispatcher._enforce_bounded_policy`
   (`_dispatcher.py:123-145`) both block non-allowlisted kinds;
   the dispatcher downgrades any stray `AUTO_HEALED` outcome.
   `test_bounded_policy.py` parametrises every `DivergenceKind`
   under empty and full allowlists with `auto_heal=True` and
   asserts BREAKING/SUSPICIOUS always escalate. Runner-level
   end-to-end test `test_runner_bounded_policy_blocks_breaking_even_with_auto_heal`.

3. **Protocol stubs, no hard imports — PASS.** Zero imports from
   `aeat.{corpus,schema,manuals,llm,storage,auth.certificate,
   models,portals}` under `src/aeat/sync` and
   `src/aeat/entrypoints/cli/sync`. Only `aeat.adapters.outbound.aeat.browser` and `aeat.core.i18n`
   imported directly, per ADR.

4. **Public API discipline — PASS.** Everything re-exported from
   `src/aeat/application/sync/__init__.py` via `__all__`. Internal modules
   `_`-prefixed. Tests and CLI import from `aeat.application.sync`.

5. **Errors — PASS.** `SyncError(AeatError)` +
   `WireValidationError`, `DivergenceClassificationError`,
   `HealingError`, `DivergenceRepositoryError`.

6. **Logging — PASS.** Every module uses
   `aeat.core.logging.get_logger(__name__)`.

7. **Type hints + Google-style docstrings — PASS.**

8. **Tests / no mocks — PASS.** No `unittest.mock`, no
   `MagicMock`, no `patch`, no `pytest-mock`, no `unittest`
   imports. Test doubles are concrete Protocol-conforming
   classes. The sole `monkeypatch.setenv` in
   `cli/sync/test_cli.py:27` is legitimate env configuration,
   not stubbing.

9. **Live test — PASS.** Skipped unless
   `AEAT_LIVE_TESTS_ENABLED=1`; uses `pytest.importorskip` as a
   dependency gate on #8/#17.

10. **Settings alignment — PASS.** Six `AEAT_SYNC_*` fields +
    `DivergenceSink` StrEnum (`config.py:20-25, 176-202`),
    documented in `env/.env.example:77-92`; `tests/test_config.py`
    green.

11. **CLI wiring — PASS.** `aeat sync run|list-divergences|
    show-divergence|resolve-divergence` at `cli/__init__.py:51`;
    7 CliRunner tests green.

12. **Lint / typecheck / tests / hooks — PASS.**

13. **Read-only against AEAT — PASS.** `_runner.py` only calls
    `fetch_*_raw`; healing mutates only local record state.

14. **No skips / no `# type: ignore` abuse — PASS.** Zero
    `type: ignore`, `noqa`, or non-live `@pytest.mark.skip`
    under the sync tree.

15. **Commit hygiene — PASS.** Nine focused commits, each
    references `#11`.

## gate tails

- `just lint`: `All checks passed!`
- `just typecheck`: `All checks passed!`
- `just test`: `173 passed, 1 skipped, 8 deselected in 1.32s`
- `just hooks`: all 10 hooks Passed

## diff-stat drift note (not a finding)

`git diff origin/main..HEAD --stat` shows deletions under
`src/aeat/adapters/persistence/storage/`, `migrations/`, `alembic.ini`. These are
NOT authored by this branch — `origin/main` merged #10 after
the branch diverged. On rebase, the branch will cleanly
acquire the real storage module and the
`StorageDivergenceRepository` rebase-swap can follow per ADR.

## nits (non-blocking)

- `_classifier.py:192` local import of `ModeloIdentifier` inside
  `_wrap` — hoist to module top for consistency.
- `_protocols.py` names the #10 stub `StorageBackendStub` while
  the ADR listed `DivergenceRecordRepository`. The real
  `DivergenceRecordRepository` Protocol lives in
  `_repository.py:28`; cosmetic ADR/code wording drift.
- `_strategies/_benign.py:28` sets
  `resolution_state=AUTO_HEALED` on BENIGN records — overloads
  the state enum; a future `RECORDED` resolution state would
  be cleaner. Bounded-policy guarantee untouched (action is
  `RECORDED`, never `AUTO_HEALED`).
- `_runner.py:240` `_fetch_with_retry[T]` uses PEP-695 generic
  but `operation` is untyped; tightening to
  `Callable[[], Awaitable[T]]` would improve readability.

## fix list

None. Branch approved for merge after rebase onto current
`origin/main`.
