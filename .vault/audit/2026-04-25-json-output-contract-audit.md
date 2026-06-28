---
tags:
  - '#audit'
  - '#json-output-contract'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - '[[2026-04-25-json-output-contract-research]]'
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-04-25-json-output-contract-plan]]'
---

# `json-output-contract` Code Review

JSON-001 | HIGH | `SecretScrubbingFilter` leaks inline sensitive text whenever a record also uses `%s` args
`src/aeat/logging.py` claims the scrubber protects message text, args, extra fields, and exception rendering, but `SecretScrubbingFilter.filter()` only scrubs `record.msg` when `record.args` is empty. When a call uses a literal sensitive fragment in the format string plus tuple args, the tuple is scrubbed but the format string is left untouched. A direct runtime probe with `logger.info("oauth_refresh_token=refresh-123 %s", "safe")` still emitted `refresh-123` verbatim. That breaks the Phase 1 record-level scrubbing invariant and can leak tokens or taxpayer identifiers through otherwise normal `%`-style logging.

JSON-002 | MEDIUM | `register_schema()` accepts non-`OutputSchema` classes, so the Phase 1 registry does not actually enforce the strict pydantic v2 contract
`src/aeat/entrypoints/cli/_schemas.py` describes the registry as mapping command paths to strict pydantic v2 output models, but `register_schema()` never validates the decorated class at runtime. A direct probe with `register_schema("demo")(NotOutput)` succeeded and stored a plain Python class in `SCHEMA_REGISTRY`. That means downstream Phase 2 code can silently register non-pydantic or non-strict payload types even though the docs and ADR present the registry as the authoritative contract surface.

JSON-003 | LOW | Protected `test_clave_movil` timeout looks like existing auth-test drift, not a plausible regression from this Phase 1 logging/filter work
The focused Phase 1 suites in scope passed locally. The protected `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` module still times out once it reaches the async auth-flow tests, but the stall appears to live in protected auth code: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py` now waits in `_wait_for_post_auth_landing()` by polling `page.url`, while the protected test stand-in advances only through its `wait_for_url()` helper. The auth tests also do not assert logging output. I do not see a credible causal path from the new CLI/logging foundation modules back to that timeout, so this should be tracked as external blocker context rather than a Phase 1 defect against `#399`.

JSON-004 | LOW | No Phase 1 overclaim found in the scoped docs
`docs/json-contract.md`, `docs/exit-codes.md`, `docs/coverage/kent-capabilities.md`, the research, the ADR, and the plan all consistently describe this branch as Phase 1 foundations only. The deferred `#398` error-envelope work, command-by-command schema rollout, root `--json` wiring, and `#393` workflow adoption are called out explicitly rather than implied as already shipped.

JSON-005 | HIGH | JSON-mode failures still write to stdout and bypass the shared stderr error contract
The new rollout mixes success serialization with ad hoc failure handling instead of routing failures through `src/aeat/entrypoints/cli/_errors.py` and `render_error_json()`. Representative sites include `src/aeat/entrypoints/cli/submission/check_nif.py:49-57`, `src/aeat/entrypoints/cli/submission/diff.py:107-211`, `src/aeat/entrypoints/cli/submission/verify.py:142-228`, `src/aeat/entrypoints/cli/workflow/_helpers.py:121-150`, `src/aeat/entrypoints/cli/workflow/show.py:48-49`, and `src/aeat/entrypoints/cli/auth/__init__.py:781-925`. Focused runtime probes against `.venv\Scripts\aeat.exe` confirm the break: `aeat --json submission check-nif X1234567Z` exits `2` with a JSON object on stdout and empty stderr, while `aeat --json workflow show missing-run-id` exits `1` with plain `not found: ...` on stdout and empty stderr. That violates the research/ADR contract that machine-mode stdout carries exactly one success document and failures serialize only on stderr.

JSON-006 | MEDIUM | The shipped shared success envelope is still dead code, so the public JSON contract cannot version itself
`src/aeat/_json_contract.py:44-52` defines `SchemaEnvelope` with `schema_version`, `command`, `result`, and `warnings`, and both the research and ADR present that outer envelope as the compatibility boundary for the shared contract. The newly registered emitters do not use it: they write raw objects or arrays directly from command code in `src/aeat/domain/modelos/_cli.py:95,150,255`, `src/aeat/domain/portals/_cli.py:87,143`, `src/aeat/entrypoints/cli/auth/__init__.py:518,808,854,860,945,1025`, `src/aeat/entrypoints/cli/workflow/_helpers.py:104`, `src/aeat/entrypoints/cli/submission/check_nif.py:54,61`, `src/aeat/entrypoints/cli/submission/diff.py:114,125,158,176,200,354`, and `src/aeat/entrypoints/cli/submission/verify.py:185,299,317,329`. A direct probe of `aeat --json modelos show 303` returns a bare metadata object with no `schema_version` or `result`, and `src/aeat/entrypoints/cli/test_json_schema_conformance.py:167-169` then locks that raw shape into the registry tests. Shipping command rollout without the advertised envelope turns later envelope adoption into a breaking change instead of the forward-compatible version gate the research asked for.

JSON-007 | MEDIUM | Root `aeat --json` is not actually CLI-wide because the `sede` emitters ignore inherited JSON mode
The rollout treats root `--json` as a shared machine-mode switch, but `src/aeat/entrypoints/cli/sede/__init__.py:149-150` and `:282-283` only honor the leaf `json_output` flag and never check `json_output_requested()`. That diverges from the rest of the branch, where root state is consulted explicitly in `src/aeat/entrypoints/cli/browser/health.py:215-216`, `src/aeat/entrypoints/cli/filing/_reconcile.py:131,164`, and `src/aeat/entrypoints/cli/workflow/list_cmd.py:54-55`. Both `sede` commands are still registered in `SCHEMA_REGISTRY`, so the shared contract advertises JSON support that `aeat --json sede list-expedientes ...` and `aeat --json sede notifications ...` do not actually honor unless the leaf flag is repeated.

JSON-008 | LOW | The public JSON-contract docs still describe a Phase 1-only branch that no longer matches the shipped surface
`docs/json-contract.md:3-4` says the root CLI does not yet expose a global `--json` flag, `:46-47` says no production command is registered, and `:98-104` defer root wiring plus workflow adoption to future phases. The current branch now adds a root callback in `src/aeat/entrypoints/cli/__init__.py:72`, registers command schemas across auth/workflow/modelos/portals/submission/sede, and adds root-alias coverage in `src/aeat/entrypoints/cli/test_root_json_alias.py`. That leaves operators and reviewers with a stale contract narrative: the docs under-claim the shipped surface while the code itself still does not satisfy the documented envelope and stderr guarantees.

JSON-009 | HIGH | `filing reconcile` is still registered as a shared JSON-contract command but leaks failure prose to stdout in JSON mode
`src/aeat/entrypoints/cli/filing/_reconcile.py` now emits the shared success envelope on happy paths, but its refusal and error paths still bypass the JSON stderr boundary. Representative sites are `_reconcile_cmd()` at `:145-161`, `_load_draft()` at `:181-204`, and `_resolve_session()` at `:234-248`, all of which print human prose and raise `typer.Exit` without switching to the structured stderr path when JSON mode is active. A real probe with `aeat --json filing reconcile missing-draft` against a missing drafts directory exited `1` with prose on stdout and empty stderr. Because `filing reconcile` is still advertised as part of the shipped registered contract set in `docs/json-contract.md` and `src/aeat/entrypoints/cli/test_json_schema_conformance.py`, this remains a live contract break for stderr failure routing, root-flag JSON mode, and docs accuracy rather than an unshipped edge surface.

## Disposition

- `JSON-001` fixed: `SecretScrubbingFilter` now scrubs inline message text even
  when tuple-style `%` args are present, while preserving placeholder tokens.
  `src/aeat/test_logging_scrubbing.py` includes a regression for the
  `oauth_refresh_token=... %s` leak reported by the reviewer.
- `JSON-002` fixed: `register_schema()` now rejects any decorated class that
  does not inherit from `OutputSchema`. `src/aeat/entrypoints/cli/test_schemas_registry.py`
  includes a runtime regression that proves the guard.
- `JSON-003` remains external blocker context: after the Phase 1 fixes and a
  full-suite rerun, the only remaining failures are the four protected
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` timeout cases already called out in the
  review.
- `JSON-004` informational only.
- `JSON-005` fixed: JSON-mode failures now route through the shared CLI error
  boundary and emit a single structured JSON document on `stderr`, while
  success keeps `stdout` to exactly one success envelope. Regression coverage
  now includes the stderr-only failure path in
  `src/aeat/entrypoints/cli/test_json_pipe_safety.py`.
- `JSON-006` fixed: registered command emitters now write the shared success
  envelope (`schema_version`, `command`, `result`, `warnings`) instead of bare
  root payloads. Conformance and command-level JSON tests unwrap and validate
  the nested `result` payload against the registered schema.
- `JSON-007` fixed: `sede list-expedientes` and `sede notifications` now honor
  inherited root JSON mode through `json_output_requested()`, so
  `aeat --json sede ...` uses the same contract as the rest of the registered
  command set.
- `JSON-008` fixed: `docs/json-contract.md`, `docs/exit-codes.md`, and
  `docs/coverage/kent-capabilities.md` now describe the shipped branch
  accurately, including the root `--json` callback, bounded registered command
  set, shared success envelope, and structured stderr error path.
- `JSON-009` fixed: `filing reconcile` now routes JSON-mode refusal and setup
  failures through `CliRefusedBoundaryError`, so `aeat --json filing
  reconcile ...` keeps `stdout` empty and emits the structured error envelope
  on `stderr`. Regression coverage now includes both the unit-level root alias
  check in `src/aeat/entrypoints/cli/filing/test_reconcile_cli.py` and the real-entrypoint
  subprocess probe in `src/aeat/entrypoints/cli/test_json_pipe_safety.py`.
