---
tags:
  - '#adr'
  - '#json-output-contract'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-json-output-contract-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
---



# `json-output-contract` adr: `phase-1 foundations for the json output contract` | (**status:** `accepted`)

## Problem Statement

Kent needs `aeat <command> --json | jq ...` to be pipe-safe across the CLI.
The current tree has command-local JSON flags, ad hoc UTF-8 stream handling,
and no shared output-schema registry, exit-code table, TTY contract, or
log-level resolver. The contract also has sibling-branch dependencies:
`#398` owns the error envelope and registry, while `#393` owns the workflow
CLI files that will eventually need the root-level `--json` flag.

## Considerations

- The controlling design comes from iteration 7 of the CLI wireframe
  reference, with iteration 6 defining the failure-envelope boundary and
  iteration 12 extending the scrubber surface.
- The issue explicitly phases the work:
  - Phase 1: standalone foundations only
  - Phase 2: consume `#398` and wire `--json` across non-workflow commands
  - Phase 3: after `#393`, wire workflow `run` / `next`
- The branch must not touch `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`, `src/aeat/entrypoints/cli/workflow/run.py`,
  `src/aeat/entrypoints/cli/workflow/next.py`, or any `#398` registry/decorator code.
- The project mandates strict pydantic v2 models, stable exit-code behavior,
  `aeat.core.errors.AeatError` inheritance, and stdout/stderr discipline that is
  safe on Windows and in pipelines.
- External CLI references support keeping the first machine contract narrow:
  `gh` uses explicit `--json`, `kubectl`/AWS/Docker show that additional
  output dialects and built-in query languages multiply quoting and
  compatibility risk. This issue should stay with one machine format:
  JSON emitted to stdout, with users composing external `jq`.

## Constraints

- `#398` is not merged yet, so this branch must not duplicate its
  `ErrorEnvelope`. Phase 1 may only provide a transport-ready helper layer
  and TODO markers for the rebase step.
- `#393` is in flight, so workflow root-flag wiring must remain deferred.
- The issue is load-bearing for downstream work (`#400`, `#405`, `#406`),
  so the Phase 1 module shapes must already be stable enough for reuse.
- The solution must keep the current repo test suite viable on Windows and
  must not depend on mocks, monkeypatches, or sibling-branch source edits.

## Implementation

- Add `src/aeat/entrypoints/cli/_schemas.py` as the single Phase 1 registry surface:
  `OutputSchema`, `SchemaEnvelope`, `SCHEMA_REGISTRY`, and a duplicate-safe
  `register_schema()` decorator. Phase 1 registers no command bindings yet;
  it defines the schema contract and public import surface only.
- Add `src/aeat/entrypoints/cli/_exit_codes.py` with the eleven-code table required by
  issue `#399`. This branch treats the table as authoritative for success,
  refusal, auth, integrity, failure, internal, locking, no-network, and
  usage/programming exits. The helper emits plain stderr until `#398` lands.
- Add `src/aeat/entrypoints/cli/_tty.py` with probes for stdin/stdout/stderr TTY state,
  colour resolution that honors `AEAT_FORCE_COLOR` and `NO_COLOR`, progress
  gating, and a typed non-TTY stdin refusal error.
- Add `src/aeat/entrypoints/cli/_log_levels.py` with the four named levels
  (`quiet`, `default`, `verbose`, `debug`), CLI/env precedence resolution,
  and a root-logger application helper.
- Extend `src/aeat/logging.py` with a record-level `SecretScrubbingFilter`
  and a shared `SCRUB_FIELD_PATTERNS` constant. The scrubber runs before
  formatting and protects message text, args, extra fields, and exception
  rendering.
- Re-export the public foundation symbols from `aeat.entrypoints.cli` so callers do not
  import private underscore modules directly.
- Defer command bindings, root `--json` callbacks, and error-envelope imports
  until the Phase 2 rebase onto `#398`, then defer workflow CLI bindings until
  the Phase 3 rebase onto `#393`.

## Rationale

- The research shows the safest first machine contract is explicit `--json`
  with one stable success shape and clean stdout, not a general `--output`
  multiplexer or built-in query language.
- A dedicated schema registry and exit-code table let downstream issues
  consume stable interfaces before the full command-by-command rollout lands.
- Record-level scrubbing is the right boundary because every existing
  `logger.info(...)` or `logger.exception(...)` call automatically benefits
  without command authors having to remember per-call redaction.
- Separating Phase 1 from `#398` and `#393` avoids merge-conflict churn in
  precisely the files those sibling branches already own.
- Keeping the log-level resolver and TTY helpers standalone now allows the
  eventual root callback to compose them later without re-designing the API.

## Consequences

- Phase 1 intentionally stops short of wiring the root-level `--json` flag.
  That means the repo will ship foundations, tests, docs, and vault artifacts
  now, then absorb the actual command adoption after the sibling merges.
- The current branch must document the Phase 2 and Phase 3 rebase steps very
  explicitly so the deferred work is mechanical instead of interpretive.
- The output schema envelope defined here may need small adjustments when
  the real `ErrorEnvelope` from `#398` lands; the ADR constrains that drift by
  fixing the registry location, version field, stdout/stderr roles, and
  phasing strategy in advance.
