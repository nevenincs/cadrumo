---
tags: ["#audit", "#workflow-engine"]
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-workflow-engine-plan]]"
---

# workflow-engine code review (issue #59)

Status: PASS - no Critical or High findings. Advisory Medium/Low items listed at the end. Safe to merge.

Scope: feature/59-workflow-engine on worktree Y:\codeeat-worktreeseature-59-workflow-engine. Read-only review.

## Criteria map

### 1. ten WorkflowStage values, in order, linear walk - PASS

- src/aeat/application/workflow/_models.py:24-41 declares the WorkflowStage StrEnum exactly once per value in the documented order: LOADING_PROFILE, SYNCING_CATALOGUES, COMPUTING_DEADLINES, CHECKING_INBOX, BUILDING_DRAFT, VALIDATING_DRAFT, RUNNING_PREFLIGHT, DRY_RUN_SUBMIT, DONE, ABORTED.
- src/aeat/application/workflow/_engine.py:248-287 walks the eight work stages sequentially in _drive; each stage has its own _stage_* method and the next is only entered after the prior returned without raising _AbortError.
- src/aeat/application/workflow/test_models.py:24-38 locks the enum shape with a tuple-equality assertion; test_engine.py:311-331 asserts the exact executed stage tuple on the happy path.

### 2. bailout matrix coverage - PASS

Every WorkflowAbortReason is reachable from the engine and has at least one dedicated unit test:

- NO_PENDING_OBLIGATION: _engine.py:464, test_engine.py:374
- DEADLINE_PASSED: _engine.py:488, test_engine.py:381
- INBOX_BLOCKING_REQUERIMIENTO: _engine.py:563, test_engine.py:396
- ALREADY_FILED: _engine.py:628, test_engine.py:410
- DRAFT_HAS_ERRORS (status path): _engine.py:673, test_engine.py:423
- DRAFT_HAS_ERRORS (validation path): _engine.py:715, test_engine.py:431
- PREFLIGHT_FAILED: _engine.py:787, test_engine.py:448
- CERT_INVALID: _engine.py:762, test_engine.py:454
- USER_CANCELLED: _engine.py:839, test_engine.py:460
- UNHANDLED_EXCEPTION: _engine.py:911 via _record_unhandled, test_engine.py:483

test_models.py:45-58 additionally pins the closed set of nine reasons.

### 3. dry-run default + double-gate enforcement - PASS

- API default: WorkflowEngine.run_next(..., dry_run: bool = True, ...) at _engine.py:140-149; same default on run_for_period at _engine.py:181-192.
- Double gate: _engine.py:827-842 - the guard "if not dry_run and not override_confirmation:" records the step and raises _AbortError(USER_CANCELLED) BEFORE any call to submit_draft. Verified by test_engine.py:460-467 asserting submit_calls == [].
- Live-with-confirmation happy path: test_engine.py:469-481 asserts submit_calls == [(False, True)].
- CLI enforcement: src/aeat/entrypoints/cli/workflow/next.py:52-56 and run.py:47-51 both reject --no-dry-run without --i-understand-this-is-real via typer.Exit(code=2); covered by test_cli.py:173-177. Flag names match the submission-engine CLI verbatim.

### 4. pydantic v2 strict + frozen + extra=forbid - PASS

- _models.py:21 defines _STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid"), applied to WorkflowStep (_models.py:85) and WorkflowResult (_models.py:127).
- _protocols.py:37 applies the same config to SubmittedFilingLike, SyncRunSummary, ExpedienteLike, RequerimientoLike - every boundary-crossing record is strict + frozen + extra=forbid.
- The sole dict[str, str] field (WorkflowStep.details at _models.py:92) is documented as the single sanctioned escape hatch in the docstring (_models.py:76-83) and in the ADR. Strict rejection of non-string values is pinned by test_models.py:99-110. No other dict[str, str] appears in the public schema.

### 5. public API discipline - PASS

- All cross-subpackage callers import only from aeat.application.workflow (test_engine.py:38-55, test_cli.py:31-35, cli/workflow/_helpers.py:25-30, cli/workflow/list_cmd.py:13, show.py:10).
- Underscored modules are only imported from within aeat/application/workflow/**; a ripgrep for aeat.application.workflow._ confirms no external deep-path imports.
- src/aeat/entrypoints/cli/__init__.py:33,65 wires the sub-typer via "from aeat.entrypoints.cli import workflow as workflow_module"; no reach into aeat.entrypoints.cli.workflow._helpers from outside the subpackage.

### 6. errors / logging / typing / docstrings - PASS

- Error hierarchy: _errors.py:16-39 - WorkflowError(AeatError), WorkflowComponentError(WorkflowError), WorkflowAbortedError(WorkflowError).
- Logging: _engine.py:29,56 and _persistence.py:15,19 both use aeat.core.logging.get_logger(__name__). No bare logging.getLogger anywhere in the subpackage.
- Typing plus Google-style docstrings: every public symbol carries explicit annotations and Args/Returns/Raises blocks where applicable.

### 7. no mocks; Protocol-conforming doubles; markers; colocation - PASS

- A ripgrep for unittest.mock, mock., MagicMock, or patch( under src/aeat/workflow returns only a docstring mention in test_engine.py:4. No imports.
- All CLI tests use real hand-rolled classes (_DeadlineEngine, _DraftBuilder, _SubmissionEngine, _InputsProvider at test_cli.py:49-118) wired via the set_test_hooks seam (_helpers.py:44-67). monkeypatch is only used to set AEAT_WORKFLOW_RUNS_DIR (test_cli.py:135), not to attribute-patch code under test.
- Every test class/function carries @pytest.mark.unit (test_models.py:20,41,61,82,126; test_engine.py:310,372; test_cli.py:161; test_persistence.py:40) or @pytest.mark.live (test_live.py:26).
- Tests are colocated under src/aeat/application/workflow/ and src/aeat/entrypoints/cli/workflow/ per the Rust-style mandate.

### 8. live-test gating + tooling - PASS

- test_live.py:22,29 imports "from aeat.entrypoints.cli._live import requires_live_enabled" and calls it at the top of the test body. No os.getenv / AEAT_LIVE lookup anywhere in the subpackage.
- Settings alignment: config.py:339-353 declares aeat_workflow_runs_dir, aeat_workflow_sync_first_default, and aeat_workflow_draft_inputs_path; env/.env.example:168-175 documents the matching env vars. The pairing is symmetric and will satisfy tests/test_config.py alignment.
- just lint/typecheck/test/hooks were not re-run in this audit per the read-only scope; no static-inspection blockers were found.

### 9. Protocol injection, no hard sibling-branch imports - PASS

- _protocols.py defines all seven Protocols as @runtime_checkable typing.Protocol and ships narrow pydantic v2 stubs for the in-flight types (SubmittedFilingLike, SyncRunSummary, ExpedienteLike, RequerimientoLike).
- _engine.py imports only aeat.core.config, aeat.domain.deadlines, aeat.core.i18n, aeat.core.logging, aeat.adapters.outbound.aeat.export, and aeat.application.workflow._* - no import from aeat.application.sync, aeat.inbox, aeat.status, or aeat.certificates.
- _adapters.py imports LiveSyncRunner / DeadlineEngine / SubmissionEngine / build_draft (all on main). The sibling-branch slots (status_reader, inbox, certificate_bundle) default to None and their stage methods degrade gracefully with "not wired" diagnostics (_engine.py:375-386, 521-532, 744-771). The CLI _helpers._build_engine raises WorkflowError pointing at #43/#46/#8 so production invocation fails fast while the engine still compiles and tests independently.

## Advisory findings (non-blocking)

- MEDIUM - bailout matrix drift (ADR vs engine). The ADR table at .vault/adr/2026-04-12-workflow-engine-adr.md:54-65 does not list UNHANDLED_EXCEPTION as reachable from COMPUTING_DEADLINES, CHECKING_INBOX, VALIDATING_DRAFT, or RUNNING_PREFLIGHT, yet the engine funnels every uncaught exception in those stages through _record_unhandled (_engine.py:434-440, 538-544, 791-797). The behaviour is strictly safer than the documented matrix; the ADR should be updated so UNHANDLED_EXCEPTION reachable from every stage is made explicit. No code change required.
- LOW - LOADING_PROFILE has no try/except. _stage_loading_profile (_engine.py:331-351) cannot actually produce UNHANDLED_EXCEPTION, yet the ADR lists the reason as reachable from the stage. Either add a trivial guard or remove the reference from the ADR.
- LOW - SubmissionEngineAdapter touches a private attribute. _adapters.py:133 reads self._engine._preflight.check(). Cross-module private access; the comment on lines 117-125 justifies it and the scope of change belongs in #42, not #59.
- LOW - JsonFileInputsProvider shape heuristic. The modelo-to-period nesting sniff at _adapters.py:227-232 silently falls back to the flat layout when the nested lookup misses. A warning log would help diagnose misconfigurations.
- LOW - test_engine.py:351-361 uses a helper (_result) that reruns the engine with sync_first=False after the test has already mutated the fixture. Asserting against the result of a single invocation directly in the test body would be clearer.

## Summary

Nine criteria, all PASS. The implementation is faithful to the ADR and plan: the ten-stage contract is locked by tests, every abort reason is reachable and covered, the dry-run / double-gate safety rule is enforced at the engine API and the CLI, pydantic models are strict+frozen+extra=forbid with a single ADR-justified dict[str, str] escape hatch, public-API discipline holds, logging and errors follow project conventions, tests are mock-free and correctly marked, and the sibling branches (#8, #43, #46) are wired exclusively through Protocols.

Advisory findings are limited to ADR/doc drift and minor test hygiene; none block merge.
