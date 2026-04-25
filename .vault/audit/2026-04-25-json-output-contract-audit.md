---
tags:
  - '#audit'
  - '#json-output-contract'
date: '2026-04-25'
related:
  - '[[2026-04-25-json-output-contract-research]]'
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-04-25-json-output-contract-plan]]'
---

# `json-output-contract` Code Review

JSON-001 | HIGH | `SecretScrubbingFilter` leaks inline sensitive text whenever a record also uses `%s` args
`src/aeat/logging.py` claims the scrubber protects message text, args, extra fields, and exception rendering, but `SecretScrubbingFilter.filter()` only scrubs `record.msg` when `record.args` is empty. When a call uses a literal sensitive fragment in the format string plus tuple args, the tuple is scrubbed but the format string is left untouched. A direct runtime probe with `logger.info("oauth_refresh_token=refresh-123 %s", "safe")` still emitted `refresh-123` verbatim. That breaks the Phase 1 record-level scrubbing invariant and can leak tokens or taxpayer identifiers through otherwise normal `%`-style logging.

JSON-002 | MEDIUM | `register_schema()` accepts non-`OutputSchema` classes, so the Phase 1 registry does not actually enforce the strict pydantic v2 contract
`src/aeat/cli/_schemas.py` describes the registry as mapping command paths to strict pydantic v2 output models, but `register_schema()` never validates the decorated class at runtime. A direct probe with `register_schema("demo")(NotOutput)` succeeded and stored a plain Python class in `SCHEMA_REGISTRY`. That means downstream Phase 2 code can silently register non-pydantic or non-strict payload types even though the docs and ADR present the registry as the authoritative contract surface.

JSON-003 | LOW | Protected `test_clave_movil` timeout looks like existing auth-test drift, not a plausible regression from this Phase 1 logging/filter work
The focused Phase 1 suites in scope passed locally. The protected `src/aeat/auth/test_clave_movil.py` module still times out once it reaches the async auth-flow tests, but the stall appears to live in protected auth code: `src/aeat/auth/_clave_movil.py` now waits in `_wait_for_post_auth_landing()` by polling `page.url`, while the protected test stand-in advances only through its `wait_for_url()` helper. The auth tests also do not assert logging output. I do not see a credible causal path from the new CLI/logging foundation modules back to that timeout, so this should be tracked as external blocker context rather than a Phase 1 defect against `#399`.

JSON-004 | LOW | No Phase 1 overclaim found in the scoped docs
`docs/json-contract.md`, `docs/exit-codes.md`, `docs/coverage/kent-capabilities.md`, the research, the ADR, and the plan all consistently describe this branch as Phase 1 foundations only. The deferred `#398` error-envelope work, command-by-command schema rollout, root `--json` wiring, and `#393` workflow adoption are called out explicitly rather than implied as already shipped.

## Disposition

- `JSON-001` fixed: `SecretScrubbingFilter` now scrubs inline message text even
  when tuple-style `%` args are present, while preserving placeholder tokens.
  `src/aeat/test_logging_scrubbing.py` includes a regression for the
  `oauth_refresh_token=... %s` leak reported by the reviewer.
- `JSON-002` fixed: `register_schema()` now rejects any decorated class that
  does not inherit from `OutputSchema`. `src/aeat/cli/test_schemas_registry.py`
  includes a runtime regression that proves the guard.
- `JSON-003` remains external blocker context: after the Phase 1 fixes and a
  full-suite rerun, the only remaining failures are the four protected
  `src/aeat/auth/test_clave_movil.py` timeout cases already called out in the
  review.
- `JSON-004` informational only.
