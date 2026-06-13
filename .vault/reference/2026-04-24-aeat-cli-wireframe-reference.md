---
tags:
  - '#reference'
  - '#aeat-cli-wireframe'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
---




# `aeat-cli-wireframe` reference: `hardening iterations 6 through 33`

## Purpose

This reference supplements the CLI wireframe ADR with hardening pass
iterations 6 through 33. The ADR itself was growing past policy size
limits, so iterations beyond the core tree and pre-approval blocker
were moved here verbatim. Each section remains the authoritative record
for its hardening pass.

The ADR (`2026-04-24-aeat-cli-wireframe-adr`) carries iterations 1
through 5, which cover the foundational 13-root tree, the revise
`--kind` matrix, the evidence-bundle manifest, the advanced quarantine
allocation, and the pre-approval blocker for the workflow live-flag
excision.

This reference carries iterations 6 through 33, which cover error
taxonomy, output contract, determinism and undo, internationalization,
migration phasing, multi-profile support, credential hygiene,
onboarding UX, test-layer harness, telemetry, performance budgets,
backup and restore, modelo expansion, corpus bundle signing, LLM
quality metrics, portal-drift management, Windows cross-platform
catalogue, release process, structural audit harness, runbook
authoring, per-profile master keys, Autoliquidación Rectificativa IVA,
GDPR and retention compliance, collaboration with accountants,
sandbox and dry-run mode, deadline-pressure UX, regional tax regimes,
and post-filing AEAT response monitoring.

Every hardening pass maps to a tracked GitHub issue under EPIC 392
(the hardening rollout coordinator). Issue bodies link back to the
corresponding `## Hardening pass iteration N` section in this
reference (or in the ADR for iterations 1-5).

## Hardening pass iteration 6 (2026-04-24)

Iteration 6 focus: formal CLI error category taxonomy, stable stderr prefix
vocabulary, stable exit code table, redirect-message shape, and a
machine-readable JSON error envelope for automation. Kent roleplay covers
five common failure modes. This section fills a hardening gap in iterations
1 through 5: they specified what each root does but not how errors speak
back.

### Error category taxonomy

Every CLI error falls into exactly one closed-set category. Categories are
the contract. New categories require an ADR amendment.

| Category | stderr prefix | Exit | Meaning |
| --- | --- | --- | --- |
| `user_input_invalid` | `ERROR:` | `2` | Click or domain-level input validation failure (wrong format, unknown option). |
| `required_state_missing` | `ERROR:` | `3` | Prerequisite state is not present (no baseline, no draft, no transactions). |
| `unsupported_target` | `ERROR:` | `4` | `(modelo, ejercicio, kind, stage)` combination is not supported today. |
| `live_write_refused` | `REFUSED:` | `5` | Live-execution flag rejected without the four-factor gate. |
| `auth_failed` | `AUTH:` | `6` | AEAT auth session is unavailable or expired. |
| `integrity_violation` | `INTEGRITY:` | `7` | Checksum mismatch, replay-corrupt bundle, tampered evidence. |
| `concurrency_locked` | `LOCKED:` | `8` | Another process holds the workspace lock on this resource. |
| `deprecated_alias` | `[deprecated]` | `0` or forward exit | Alias still runs; stderr notice only. |
| `moved_alias` | `[moved]` | Forward exit | Alias forwards transparently; stderr notice only. |
| `system_failure` | `FAIL:` | `10` | I/O, parse, external-tool crash. |
| `internal_error` | `INTERNAL:` | `20` | Unexpected exception; indicates a bug. Verbose mode prints traceback. |

Contract rules:

- Exit codes `0`, `1`, and `2` remain reserved per Click convention. All
  AEAT-specific codes start at `3` to avoid collision.
- Every error emits its stderr prefix plus exactly one whitespace plus the
  message. The prefix is machine-grep-stable.
- Live-write refusals never silently forward to a non-live path; they emit
  `REFUSED:` and exit `5`. Automation relies on this.
- Deprecated and moved alias notices emit to stderr while the command's
  actual stdout remains clean for pipelines.
- `internal_error` implies a bug. Any occurrence must be reproducible and
  filed against the repo.

### Redirect-message shape

Errors that know the next step speak in this exact shape. No freeform.

```text
<prefix>: <one sentence problem statement>
  -> Run `<exact command Kent should type next>`
  <optional second line with why, under 80 columns>
```

The arrow is the ASCII sequence `->` (never a Unicode glyph, per
Windows-terminal-safe mandate). The suggested command must be copy-paste
ready: no placeholders, no ellipses, no prose in backticks.

When multiple recovery commands exist, list them on separate bulleted lines
under the first arrow:

```text
ERROR: Modelo 130 ejercicio 2024 has no rectificativa path.
  -> For corrections that reduce liability, use `aeat revise start 130 --period 2024Q1 --kind complementaria` with a negative delta.
  -> Or upload manually through the AEAT portal; see `aeat advanced reference portals show 130`.
```

### Machine-readable JSON error envelope

When the invocation carries `--json`, errors emit a single JSON line to
stderr in addition to the human-readable stderr. Stdout stays clean for
pipelines.

```json
{
  "error": {
    "category": "required_state_missing",
    "code": "E_NO_BASELINE",
    "prefix": "ERROR",
    "exit_code": 3,
    "message": "No baseline submission found for (303, 2024Q2).",
    "suggestion": "aeat revise import-baseline ./303-2024Q2-justificante.pdf",
    "context": {
      "modelo": "303",
      "period": "2024Q2",
      "profile_tax_id": "X1234567L",
      "command": "revise start"
    },
    "docs_anchor": null,
    "retryable": false
  }
}
```

Field rules:

- `category` is one of the closed categories above.
- `code` is a stable `E_*` constant that scripts can branch on. Codes live in
  a central registry module; adding a code requires an ADR amendment.
- `prefix`, `exit_code`, and `category` must match the stderr output.
- `suggestion` is a single copy-paste-ready command (or null).
- `context` contains every structured field relevant to the failure. Keys
  are snake_case and use the same vocabulary as record fields
  (`modelo`, `period`, `profile_tax_id`, `command`, `draft_id`, etc.).
- `retryable` is true only when the failure is transient (network timeout,
  browser session expired). Never true for policy refusals.

### Kent roleplay on five common failures

Scenario A: Kent runs `aeat draft create 303 --period 2024Q1` without
importing data.

```text
ERROR: Data readiness for (303, 2024Q1) is not complete.
  -> Run `aeat data readiness 303 --period 2024Q1` to see what is missing.
  -> Then `aeat data import statement ./<path>.pdf` or `aeat transactions automate --period 2024Q1`.
```

Exit `3`. Category `required_state_missing`. Code `E_DATA_NOT_READY`.

Scenario B: Kent runs `aeat revise start 303 --period 2024Q2 --kind
complementaria` without a baseline.

```text
ERROR: No baseline submission found for (303, 2024Q2).
  -> Run `aeat revise import-baseline ./303-2024Q2-justificante.pdf`.
```

Exit `3`. Category `required_state_missing`. Code `E_NO_BASELINE`.

Scenario C: Kent runs `aeat audit export 303 --period 2024Q1` but the
persisted formula ledger is missing.

```text
INTEGRITY: Evidence bundle for (303, 2024Q1) is incomplete.
  missing: formulas/ledger.json
  missing: formulas/audit.json
  -> Run `aeat audit verify 303 --period 2024Q1` to see the full gap list.
  -> The persistence work tracked under the audit lineage epic must land before audit export can emit.
```

Exit `7`. Category `integrity_violation`. Code `E_BUNDLE_INCOMPLETE`.

Scenario D: Kent runs `aeat export modelo 390 --period 2024`.

```text
ERROR: Modelo 390 ejercicio 2024 export is not supported today.
  supported: 130 (2024, 2025); 303 (2024, 2025)
  -> Track the 390 export epic or upload manually through the AEAT portal (`aeat advanced reference portals show 390`).
```

Exit `4`. Category `unsupported_target`. Code `E_MODELO_EJERCICIO_UNSUPPORTED`.

Scenario E: Kent runs `aeat status backlog show --from 2023Q1 --to 2025Q4`
and his AEAT auth session expired mid-command.

```text
AUTH: AEAT live session expired at 14:03:22Z.
  -> Run `aeat auth login --provider certificate`.
  partial results printed above reflect local truth only; AEAT columns are marked `blocked`.
```

Exit `6`. Category `auth_failed`. Code `E_AUTH_EXPIRED`. Retryable: true.

In every scenario the suggestion is a single copy-paste-ready command, not
a general pointer. This is the hard contract.

### Stderr noise and clean-stdout contract

- Alias notices, `REFUSED:` blocks, `AUTH:` hints, and `INTEGRITY:` reports
  all go to stderr.
- Every command's stdout is Kent-facing human-readable by default or
  machine-readable under `--json`. Stdout never carries error framing.
- A script that does `aeat status show 303 --period 2024Q1 --json | jq
  .reconciliation_state` must work cleanly even when an alias deprecation
  notice fires.
- Commands that print no stdout on success (e.g., `configure defaults set`)
  exit `0` silently. They do not emit success banners.

### Error-code registry module

Error codes live in a single source of truth at
`src/aeat/core/errors/_registry.py` as a frozen Pydantic v2 model. Each entry:

```text
ErrorCode:
  code: str                     # E_*, uppercase_snake_case
  category: ErrorCategory        # closed enum
  default_message_es: str        # authoritative Spanish
  default_message_en: str        # English
  default_message_hu: str        # Hungarian
  default_suggestion: str | None
  retryable: bool
  docs_anchor: str | None
```

A registry test asserts that every `raise` of an `AeatError` subclass in
`src/aeat/` carries a `code` attribute that exists in the registry.
Freeform error messages bypass the registry and fail the test.

### Hardening rules derived from iteration 6

- Every CLI error raises an `AeatError` subclass whose constructor takes a
  registered `code`. Freeform `raise ValueError(...)` in CLI paths is
  banned.
- The CLI writer wraps every command with an error-handler decorator that
  maps `AeatError` to the human-readable stderr form and, under `--json`,
  also emits the JSON envelope.
- Suggested commands are validated at test time: every registered
  `default_suggestion` must parse cleanly through Click's parser against
  the current CLI tree.
- Exit codes are stable across releases within a major version. Breaking
  changes require an ADR amendment and a migration note in RELEASING.md.
- Internationalization of error messages follows iteration 9's contract
  (deferred). Until iteration 9 ships, default language stays `es` per
  project mandate.

### Open risks added by iteration 6

- Error category taxonomy may not cover every current error site. A code
  sweep under `src/aeat/` must enumerate every CLI-reachable exception and
  assign a category; unassigned sites fail the registry test.
- Exit code space is finite. Reserving `3..20` for AEAT-specific categories
  leaves `21..127` for future categories; this must stay disciplined or
  scripts break.
- Suggestion commands rot when the CLI renames. The test that parses every
  suggestion against the current CLI tree is the only line of defence.
  Without it, iteration-4 migrations silently break redirect messages.
- `--json` error output on stderr may surprise users who redirect stderr
  expecting freeform. Document the contract in docs/cli-output.md before the
  contract ships.
- Retryable errors must not encourage scripts to retry indefinitely; a
  documented backoff expectation should accompany the `retryable: true`
  contract.

## Hardening pass iteration 7 (2026-04-24)

Iteration 7 focus: formal output-format contract for every Kent-first
command. Two modes (human default, machine under `--json`); stable exit
codes; stdout/stderr discipline; non-TTY detection; logging-level
contract; progress reporting; secrets scrubbing. This closes the
automation-readiness gap in iterations 1 through 6: those specified what
commands do, not how pipelines consume them.

### Mode contract

Every command runs in one of two output modes, selected by the presence or
absence of `--json`.

Human mode (default):

- ASCII-safe. No Unicode glyphs required for meaning. Windows-terminal-safe
  per the project mandate.
- stdout carries Kent-facing results: prose, tables, single-line summaries.
- Tables use ASCII box drawing (`+`, `-`, `|`). Column widths adapt to the
  terminal but never require Unicode.
- ANSI colour is opt-in. Default off; `--color auto` enables colour only
  when stdout is a TTY.

Machine mode (`--json`):

- stdout emits exactly one JSON document terminated by newline.
- No prose, no banners, no progress bars on stdout.
- Errors still emit the iteration-6 JSON error envelope to stderr; stdout
  remains empty on failure.
- Every Kent-first command supports `--json`. Exceptions must be enumerated
  and justified in an ADR amendment.

### Stable exit-code table

| Code | Meaning | Category link (iteration 6) |
| --- | --- | --- |
| `0` | success | - |
| `1` | generic Click/runtime error | - |
| `2` | usage or input invalid | `user_input_invalid` |
| `3` | required state missing | `required_state_missing` |
| `4` | unsupported target | `unsupported_target` |
| `5` | live write refused | `live_write_refused` |
| `6` | auth failed | `auth_failed` |
| `7` | integrity violation | `integrity_violation` |
| `8` | concurrency locked | `concurrency_locked` |
| `10` | system failure (I/O, parse) | `system_failure` |
| `20` | internal error (bug) | `internal_error` |

Codes `0`, `1`, `2` remain reserved for Click convention. Codes `3..20` are
the AEAT-specific contract. Codes `21..127` are reserved for future
categories; adding one requires ADR amendment plus migration notes in
`RELEASING.md`. Codes above `127` are reserved for signal-derived exits and
must never be used explicitly.

### Per-command JSON shape

Every `--json` response is an object with this minimum envelope:

```json
{
  "command": "status.today",
  "status": "ok",
  "result": { ... },
  "metadata": {
    "aeat_cli_version": "0.X.Y",
    "invoked_at": "2026-04-24T12:00:00Z",
    "profile_tax_id": "X1234567L",
    "invocation": ["status", "today"]
  }
}
```

`command` is the dot-path of the invocation. `status` is `ok` on success;
on error the envelope is replaced by the iteration-6 error envelope on
stderr while stdout stays empty. `result` is the command-specific payload.
`metadata` is stable across commands and scripts can rely on its shape.

Each command's `result` shape is registered in a JSON-schema catalogue at
`src/aeat/entrypoints/cli/_schemas.py`. A regression test loads every registered
schema and asserts the command under `--json` emits a conforming document.
Drift from the schema fails the test.

Representative `result` shapes:

- `status.today.result`: array of `AgendaItem` objects with fields
  `modelo`, `period`, `profile_tax_id`, `due_at`, `urgency` enum, `blocker`
  enum, `next_action` (short string), `resume_command` (copy-paste ready
  CLI invocation).
- `status.show.result`: single `ObligationCase` with fields `modelo`,
  `period`, `profile_tax_id`, `applicable`, `due_at`, `draft_state`,
  `submission_state`, `aeat_state`, `notice_state`, `reconciliation_state`,
  `next_action`.
- `draft.create.result`: `{ draft_id, modelo, period, profile_tax_id,
  status, created_at }`.
- `compare.show.result`: `ComparisonCase` with `against`, `discrepancies`
  array, `blocking_count`, `non_blocking_count`, `next_action`.
- `export.modelo.result`: `{ fichero_path, sha256, modelo, period,
  profile_tax_id, kind, byte_size }`.
- `audit.export.result`: `{ bundle_path, bundle_id, modelo, period,
  profile_tax_id, checks_passed, checks_failed }`.
- `review.approve.result`: `{ item_id, prior_status, next_status,
  approved_at, approved_by, review_checksum }`.
- `transactions.automate.result`: `{ total, classified, categorized,
  unresolved, resume_token }`.

Commands that mutate state (create, import, approve, export) return the
new identifier and the new state. Commands that inspect return the full
inspected object. Commands that enumerate return an array.

### stdout and stderr discipline

The following invariants are tested and enforced.

- stdout is never polluted with error framing. Alias `[deprecated]` and
  `[moved]` notices go to stderr, even in human mode.
- stderr carries: errors, warnings, progress bars, deprecation and move
  notices, auth prompts, debug output.
- A script running `aeat status show 303 --period 2024Q1 --json | jq
  .result.reconciliation_state` works cleanly when deprecation notices
  fire on stderr.
- A command that prints no stdout in human mode (for example `configure
  defaults set`) still emits a `{ "command": "configure.defaults.set",
  "status": "ok", "result": {}, "metadata": {...} }` document under
  `--json` so automation can confirm success.
- Success exits `0` regardless of mode.

### Non-TTY detection

Every command detects:

- stdout not a TTY: colour off; progress reporting line-based not
  spinner-based; tables emit plain ASCII without live-refresh.
- stderr not a TTY: progress silent by default.
- stdin not a TTY: interactive prompts refuse with category
  `required_state_missing`, code `E_TTY_REQUIRED`, exit `3`, suggestion
  pointing to the non-interactive flag equivalent.

Examples of non-TTY refusals:

```text
ERROR: `aeat auth login --provider certificate` requires an interactive terminal for certificate selection.
  -> Re-run in a TTY, or use `aeat advanced providers oauth-client refresh` for non-interactive OAuth flows.
```

Live-write prompts never accept non-TTY input. The four-factor gate always
includes an interactive confirmation; absence of a TTY is an automatic
refusal per the safety charter.

### Logging-level contract

Four levels map to CLI flags and one env var:

- `--quiet`: errors only; warnings silent; no progress.
- default: warnings plus stable notices to stderr (deprecation, auth hints,
  alias moves).
- `--verbose`: adds info-level messages with operation summaries.
- `--debug` or `AEAT_DEBUG=1`: adds debug plus trace; includes IDs,
  timings, and file paths.

Rules:

- Sensitive fields are scrubbed at log emission time: NIE/NIF, justificante
  CSV, OAuth tokens, AEAT session cookies, browser trace paths, LLM API
  keys.
- A scrubbing filter runs before every stderr write. The scrubber uses a
  closed allow-list for visible identifiers (`draft_id`, `run_id`,
  `submission_id`, `amendment_id`, `bundle_id`) and redacts everything
  else under `--debug`.
- `--debug` output carries `[debug]` prefix on every line so it is
  grep-strippable.
- Log level does not affect stdout. Kent-facing results remain on stdout
  at every level.

### Progress reporting

Long-running commands emit progress to stderr:

- Human mode TTY: single-line spinner with a description and a count
  (`building transactions: 1203 / 2995`). Uses carriage return for
  in-place refresh.
- Human mode non-TTY: one line per 10-percent progression, no carriage
  returns.
- Machine mode (`--json`): newline-delimited JSON events on stderr with
  `{ "type": "progress", "command": "...", "current": N, "total": M,
  "elapsed_ms": X }`. Final result still goes on stdout.
- `--no-progress` disables all progress output on stderr.

Progress emission is rate-limited to at most 10 updates per second so
automation is not overwhelmed.

### Secrets scrubbing

The scrubbing filter operates on every stderr write and every structured
log record. Fields in the scrub list:

- Taxpayer identifier fields: `nie`, `nif`, `tax_id`, `cif`,
  `profile_tax_id` (only under `--debug`; otherwise allowed for
  operational context).
- AEAT-issued codes: `justificante_csv`, `justificante_pdf_path`,
  `aeat_session_id`.
- Provider secrets: `oauth_client_secret`, `oauth_refresh_token`,
  `oauth_access_token`, browser cookies, HTTP authorization headers.
- LLM keys and request identifiers that carry prompt content.

Scrubbing produces a stable marker such as `<redacted:taxpayer_id>` or
`<redacted:oauth_token>` so the log remains diff-friendly. Integration
tests assert that every log line for a live-mode invocation matches an
allow-list regex.

### Pipe-safety and automation contracts

Canonical automation patterns must work without manual escaping:

- `aeat status today --json | jq '.result[] | select(.urgency == "overdue")'`
- `aeat draft create 303 --period 2024Q1 --json | jq -r .result.draft_id | xargs -I{} aeat review approve {}`
- `aeat audit export 303 --period 2024Q1 --json | tee audit-log.json`
- `aeat compare show 303 --period 2024Q1 --against aeat --json | jq .result.blocking_count`

A regression test runs each canonical pattern against a fixture workspace
and asserts the pipeline succeeds.

### Hardening rules derived from iteration 7

- Every Kent-first command supports `--json` or is explicitly exempted in
  an ADR amendment.
- Every `--json` result is schema-checked at test time against the
  registry at `src/aeat/entrypoints/cli/_schemas.py`.
- stdout is reserved for primary results (human or JSON). stderr carries
  everything else.
- Exit codes come from the registered set. An `if` that returns a bare
  `sys.exit(42)` fails the registry test.
- Non-TTY stdin refuses interactive prompts with `E_TTY_REQUIRED`.
- Non-TTY stdout disables colour and live-refresh progress automatically.
- Secrets scrubbing is mandatory and tested on every log path.
- Progress output is rate-limited and silent in `--quiet` mode.
- Canonical pipe patterns are covered by integration tests.

### Open risks added by iteration 7

- JSON schemas drift across command renames from iteration 4 migrations.
  The schema-registry test must evolve with each rename or pipelines
  break silently.
- Progress output is heuristic per command; a slow command without
  progress feels broken in a TTY. A uniform default is needed.
- Colour-off default versus colour-on-TTY auto-detect creates a subtle
  cross-platform difference (Windows Terminal versus legacy cmd.exe).
  Default remains colour-off; users opt in explicitly.
- Secrets scrubbing misses when new sensitive fields are introduced
  without scrub-list updates. A static-analysis pass over structured log
  call sites can catch new fields.
- Interactive prompts inside CI (for example `auth login` under a CI
  runner) require a documented non-interactive path per provider; the
  AuthProvider abstraction (#279) owns this, but the CLI must expose the
  error cleanly until then.

## Hardening pass iteration 8 (2026-04-24)

Iteration 8 focus: determinism, idempotency, undo semantics, and
concurrency discipline. Kent runs a production financial toolkit. He must
be able to re-run commands safely, reverse accidental actions, and work in
parallel terminals without corrupting local state. This iteration fills
the operational-safety gap in iterations 1 through 7.

### Command mutability classification

Every Kent-first command belongs to exactly one mutability class. The
class is declared in a central registry `src/aeat/entrypoints/cli/_mutability.py` as a
frozen Pydantic v2 model. Freeform mutation escapes the registry.

| Class | Definition |
| --- | --- |
| `read_only` | No side effects on disk, network, or memory beyond the command's own run. |
| `local_state_mutating` | Writes to the local workspace state (configure, data, transactions, draft, review, revise records). |
| `filesystem_emitting` | Writes a new file to a user-controlled path (export modelo, audit export). Does not mutate workspace state. |
| `live_read` | Reads from AEAT through the auth session; does not write. |
| `live_write` | Writes to AEAT. Reserved for 1.0.0 reintroduction. Not in the default tree. |

Classification table (abridged; the full table lives in the registry):

| Command | Class |
| --- | --- |
| `status today`, `status show`, `status history` | `read_only` |
| `status backlog show`, `status resume` | `read_only` |
| `data show`, `data readiness` | `read_only` |
| `draft show`, `draft list`, `draft validate` | `read_only` |
| `review queue`, `review show`, `review history` | `read_only` |
| `compare show`, `compare explain`, `compare verify` | `read_only` |
| `export schemas`, `export verify`, `export diff` | `read_only` |
| `audit show`, `audit verify`, `audit manifest`, `audit replay` | `read_only` |
| `records *` | `read_only` |
| `configure profile set`, `configure modelos add/remove`, `configure defaults set` | `local_state_mutating` |
| `data import *`, `data edit *`, `data link *` | `local_state_mutating` |
| `transactions build`, `transactions automate`, `transactions classify`, `transactions categorize`, `transactions edit`, `transactions link` | `local_state_mutating` |
| `draft create` | `local_state_mutating` |
| `review approve`, `review unapprove` | `local_state_mutating` |
| `revise start`, `revise import-baseline`, `revise resume` | `local_state_mutating` |
| `compare fix` | `local_state_mutating` |
| `export modelo`, `export preflight`, `export dry-run` | `filesystem_emitting` |
| `audit export` | `filesystem_emitting` |
| `auth login`, `auth logout`, `auth status`, `auth whoami` | `live_read` |
| `records aeat fetch` | `live_read` |
| `status aeat *` (under `status show --include aeat`) | `live_read` |

### Idempotency contract

Every command declares an `idempotency` rule in the mutability registry.
Scripts and users can re-run without fear when the command is marked
idempotent.

| Rule | Meaning |
| --- | --- |
| `idempotent_pure` | Re-running with identical args against identical state yields identical output and zero additional side effects. |
| `idempotent_last_wins` | Re-running overwrites the prior state with the new inputs; final state is deterministic by last invocation. |
| `idempotent_guarded` | Re-running is a no-op if state already matches; otherwise refuses with a clear reason. |
| `non_idempotent_append` | Re-running creates a new record (amendment, import batch, login session). Safe but additive. |
| `non_idempotent_external` | Re-running invokes an external non-deterministic process (LLM, browser, network). Results may differ. |

Representative assignments:

| Command | Rule |
| `configure profile set` | `idempotent_last_wins` |
| `configure modelos add`/`remove` | `idempotent_guarded` |
| `data import statement <path>` | `idempotent_guarded` (duplicate file detected by SHA-256) |
| `transactions build --period <p>` | `idempotent_pure` |
| `transactions automate --period <p> --with llm` | `non_idempotent_external` |
| `transactions classify <id>` | `idempotent_last_wins` |
| `transactions edit <id>` | `idempotent_last_wins` |
| `draft create <modelo> --period <p>` | `idempotent_guarded` (same content-addressed draft_id returns existing) |
| `draft validate <modelo> --period <p>` | `idempotent_pure` |
| `review approve <item_id>` | `idempotent_guarded` (re-approve on same checksum is no-op; stale checksum refuses) |
| `review unapprove <item_id>` | `idempotent_guarded` |
| `revise start <modelo> --period <p> --kind <k>` | `non_idempotent_append` (new amendment per invocation) |
| `revise import-baseline <path>` | `idempotent_guarded` (same PDF yields same SubmittedFiling) |
| `export modelo <modelo> --period <p>` | `idempotent_pure` (byte-identical fichero from identical draft) |
| `export preflight`, `export dry-run` | `idempotent_pure` |
| `audit export <modelo> --period <p>` | `idempotent_pure` (content-addressed bundle_id) |
| `audit verify` | `idempotent_pure` |
| `audit replay` | `idempotent_pure` |
| `auth login` | `non_idempotent_append` (new session record) |

### Determinism contract

Every content-addressed identifier is deterministic and uses SHA-256.
Scripts can compute identifiers ahead of time without running the CLI.

| Identifier | Construction rule |
| `draft_id` | SHA-256 of `(modelo, period, profile_tax_id, schema_version, sorted_values)` truncated to 16 hex chars. |
| `submission_id` | SHA-256 of `(draft_id, attempt_ordinal)` truncated to 16 hex chars. |
| `run_id` | SHA-256 of `(profile_tax_id, modelo, period, started_at)` truncated to 16 hex chars. |
| `bundle_id` | Full SHA-256 of the sorted concatenation of `path\0sha256\n` across bundle contained files. |
| `amendment_id` | SHA-256 of `(parent_submission_id, amendment_kind, created_at)` truncated to 16 hex chars. |
| `fichero` bytes | Byte-deterministic emission from `(draft, schema_version)` tuple. |

A regression test asserts every identifier construction matches the rule
against a fixture dataset. Drift fails the test and blocks merge.

### Undo semantics

Kent can reverse every mutating command through a documented undo path.
Absent an undo path, the command refuses to mutate.

| Mutating command | Undo path | Constraint |
| --- | --- | --- |
| `configure profile set` | `configure profile revert --to-snapshot <n>` | Last 5 snapshots retained. |
| `configure modelos add <m>` | `configure modelos remove <m>` | - |
| `configure defaults set` | `configure defaults revert --to-snapshot <n>` | Last 5 snapshots. |
| `data import statement <path>` | `data delete statement <import_id>` | Cascades to derived transactions; refuses if any derived row is referenced by an approved draft. |
| `data edit invoice <id>` | `data edit invoice <id>` with prior values | History log keeps prior values for 30 days. |
| `data link receipt ...` | `data unlink receipt ...` | - |
| `transactions automate` | `transactions revert --run <run_id>` | Reverses assignments to prior state; per-transaction `transactions classify` overrides remain preferred. |
| `transactions classify <id>` | `transactions classify <id>` with prior class | History log. |
| `transactions edit <id>` | `transactions edit <id>` with prior values | History log. |
| `draft create <modelo> --period <p>` | `draft delete <draft_id>` | Refuses if approved. |
| `review approve <item_id>` | `review unapprove <item_id>` | Always reversible. |
| `review unapprove <item_id>` | `review approve <item_id>` | Same. |
| `revise start <modelo> --period <p> --kind <k>` | `revise cancel <amendment_id>` | Refuses after export. |
| `revise import-baseline <path>` | `records receipts delete <submission_id>` | Refuses if amendment chain references. |
| `export modelo` | no undo; artifact is a file Kent owns. | `--output <path>` refuses to overwrite without `--force`. |
| `audit export` | no undo; bundle is a file Kent owns. | Same. |
| `auth login` | `auth logout` | - |

New undo commands introduced by this iteration (not yet implemented):

- `configure profile revert --to-snapshot <n>`
- `configure defaults revert --to-snapshot <n>`
- `data delete statement <import_id>`
- `transactions revert --run <run_id>`
- `draft delete <draft_id>`
- `revise cancel <amendment_id>`
- `records receipts delete <submission_id>`

Each new command inherits the error-taxonomy, output-contract, and
concurrency contracts from iterations 6, 7, and below.

### Concurrency and locking

Kent may run two AEAT terminals at once (a long `transactions automate` in
one, a quick `status today` in another). The CLI uses cooperative file
locks keyed to the granularity of mutation.

Lock granularity:

- Per-profile lock at `var/locks/profile-{profile_tax_id}.lock`. Held by
  `configure profile set`, `configure defaults set`, and `auth login`.
- Per-case lock at `var/locks/{modelo}-{period}-{profile_tax_id}.lock`.
  Held by every mutating command scoped to a filing obligation: `data
  import`, `transactions *`, `draft create`, `review approve/unapprove`,
  `revise *`, `compare fix`, `export modelo/preflight/dry-run`,
  `audit export`.
- Per-record lock at `var/locks/transaction-{transaction_id}.lock` for
  fine-grained single-row edits (`transactions edit`,
  `transactions classify`, `transactions categorize`). Held for short
  durations.
- Per-import lock at `var/locks/import-{sha256}.lock` held while a file
  is being ingested (prevents duplicate concurrent import of the same
  statement).

Read-only commands never take a lock. They read the workspace in a
snapshot-consistent manner and may observe an intermediate state while a
mutation is in flight; the mutation's atomicity guarantees the snapshot is
never structurally inconsistent.

Lock acquisition rules:

- Non-blocking by default. If the lock is held, the command exits `8`
  (`concurrency_locked`) with the holder's PID and command name in the
  error message.
- `--wait <seconds>` flag queues the command for up to N seconds.
- Stale locks (PID no longer running) are reclaimed automatically on the
  next acquisition attempt. The reclaim is logged to stderr.
- Lock files carry `{ pid, command, started_at, profile_tax_id }` as JSON
  so debugging is explicit.

Kent roleplay: he runs `aeat transactions automate --period 2024Q1 --with
llm` in terminal A; he then runs `aeat transactions classify tx_123` in
terminal B.

```text
LOCKED: (303, 2024Q1, X1234567L) is locked by PID 12345
        command: `aeat transactions automate --period 2024Q1 --with llm`
        started: 2026-04-24T14:00:00Z
  -> Wait for the other process to finish.
  -> Or retry with `aeat transactions classify tx_123 --wait 300` to queue.
```

Exit `8`. Category `concurrency_locked`. Code `E_CASE_LOCKED`.

### Interrupt safety and atomic writes

Every long-running mutating command is interrupt-safe. SIGINT never leaves
a half-written record.

Rules:

- Every write to a persisted JSON file uses a `write-rename` pattern:
  write to `<path>.tmp-{pid}`, `fsync`, then atomic rename. Partial writes
  are never observed.
- Batch operations (`transactions automate`, `data import statement`,
  `audit export`) checkpoint after each unit. SIGINT aborts between
  checkpoints; the command exits with `SIGINT` code (`130`) and emits a
  resumable-session marker.
- Resume commands (`transactions resume`, `revise resume`, `status
  resume`) pick up from the last checkpoint.
- `export modelo` and `audit export` are fully atomic: the output is
  either a complete valid artefact or the file is absent. The fichero is
  written to a temp path and renamed at the end; the bundle is finalised
  only after every contained file is present and `manifest.json` is
  written last.

Progress bars (iteration 7) also emit checkpoint IDs so the resume command
can locate the resume point.

### Hardening rules derived from iteration 8

- Every mutating command declares `class` and `idempotency` in
  `src/aeat/entrypoints/cli/_mutability.py`. Missing declarations fail the registry
  test.
- Every undo path is registered and testable. Commands without an undo
  path refuse to mutate unless explicitly exempted in an ADR amendment
  (for example `export modelo`, which produces a user-owned artefact).
- Every content-addressed identifier follows the SHA-256 rule table.
  Drift fails a regression test.
- Every mutating command acquires a lock at the declared granularity
  before touching disk. Acquiring bypass requires ADR amendment.
- Every file write uses `write-rename` atomic replacement. Torn writes
  are a bug, not a configuration.
- Every long-running command is checkpoint-based and SIGINT-safe.
- A test suite exercises two concurrent terminals on the same workspace
  and asserts exit `8` on the second terminal when the first holds the
  lock.
- A test suite kills long-running commands mid-flight and asserts no
  partial records remain on disk.

### Open risks added by iteration 8

- Windows file-lock semantics differ from POSIX. The lock implementation
  must use a cross-platform library and explicit Windows integration
  tests; otherwise stale-lock recovery may fail silently on Windows.
- LLM-based `transactions automate` is `non_idempotent_external`. Kent
  scripts that retry on failure may accumulate drift. The command must
  attach an `automation_run_id` so retries can be reconciled via
  `transactions revert --run <id>`.
- Per-case lock granularity may cause unnecessary serialization when Kent
  wants to run `draft validate` (read-only) against a case held by
  `transactions automate`. Validation here: read-only commands never
  take locks; they snapshot-read. This risk is closed by the rule; the
  test suite must verify.
- Snapshot retention for `configure profile revert` could grow unbounded
  if snapshots are not pruned. Retention policy: last 5, auto-prune.
- `records receipts delete` risks breaking amendment chains. The command
  must refuse when a downstream amendment references the receipt;
  refusal message cites the referencing amendment id.
- `transactions revert --run <id>` on a run whose classifications were
  already overridden by `transactions classify` must preserve the
  override, not undo it. The revert semantics are per-transaction,
  last-writer-wins.

## Hardening pass iteration 9 (2026-04-24)

Iteration 9 focus: the internationalization contract across Spanish,
English, and Hungarian. The project mandate fixes the language set and
forbids gettext and `.po` files, so the hardening work is about the shape
of in-tree translation storage, the selection chain, fallback discipline,
and what never translates. Kent roleplay covers a mixed-language terminal
session.

### Language policy summary

- Spanish (`es`) is authoritative for AEAT terminology and the default
  output language. `AEAT_OUTPUT_LANGUAGE` default is `es`.
- English (`en`) is the operator-friendly fallback for non-Spanish
  speakers and the language of code and docs.
- Hungarian (`hu`) is optional and opt-in through
  `AEAT_OUTPUT_LANGUAGE=hu`.
- Every stored user-facing string uses the `Translatable` nested-dict
  TypedDict. No gettext. No `.po` files. No lazy i18n middleware.

### `Translatable` TypedDict contract

Every persistent record that carries user-facing text uses this shape:

```python
class Translatable(TypedDict):
    es: str                       # required, authoritative
    en: str                        # required, operator fallback
    hu: NotRequired[str]           # optional, opt-in
```

Fields include: error default messages, error suggestions, category
names, normative notes, amendment-kind notes, readiness-check reasons,
progress descriptions, table headers.

A Pydantic v2 validator refuses records with missing `es` or `en`. Missing
`hu` is allowed; the fallback chain picks it up.

### Language selection chain

Priority order evaluated at CLI startup once per invocation:

1. `--lang <es|en|hu>` explicit CLI flag.
2. `AEAT_OUTPUT_LANGUAGE` environment variable.
3. Workspace default set via `configure defaults set language <lang>`.
4. Project default `es`.

The selected language remains stable for the whole invocation, including
every subcommand and every log emission. Mid-command language switch is
disallowed: the contract is one language per process.

### Fallback chain

When a `Translatable` record is missing the requested language key:

1. Fall back to `es` (authoritative).
2. If `es` missing, fall back to `en`.
3. If both missing, render the marker `<missing translation: {key}>` and
   log a warning under `--verbose`.

Fallback never silently switches language class: the selected language
survives for strings that have it; only the missing string falls back.

Fallback emissions are counted per invocation and reported in
`--debug` mode so the catalogue gap is discoverable.

### What never translates

Regardless of selected language, these stay in Spanish:

- Modelo identifiers (`130`, `303`, `390`, `100`, `111`, `115`, etc.).
- Amendment kind values (`complementaria`, `rectificativa`, `sustitutiva`)
  inside `--kind` options and in the revise support registry.
- Fichero BOE field names (`casilla`, `clave`, `ejercicio`, `periodo`) in
  verify and diff output — these are AEAT-authoritative and translating
  breaks reproducibility.
- Proper nouns inside normative citations (`Ley 37/1992`, `Real Decreto
  1624/1992`, `BOE-A-1992-28740`).
- AEAT-issued strings: error codes, rejection reasons, notification
  subjects as received.
- Justificante CSV codes (opaque strings).

Everything else is translatable: help text, error messages, error
suggestions, narratives, status-row labels, progress messages, table
headers, `audit show` verdict prose, `status today` agenda labels,
redirect messages.

### Central catalogue

Translatable strings live in a central catalogue module at
`src/aeat/core/i18n/_catalog.py`. Each entry is keyed by a dot-path that
combines command and role:

```python
CATALOG: dict[str, Translatable] = {
    "status.today.header": {
        "es": "Agenda de hoy",
        "en": "Today's agenda",
        "hu": "Mai napirend",
    },
    "status.today.empty": {
        "es": "No hay autoliquidaciones pendientes para hoy.",
        "en": "No filings pending today.",
        "hu": "Nincs ma esedekes filing.",
    },
    "error.no_baseline.message": {
        "es": "No se encontro una autoliquidacion base para ({modelo}, {period}).",
        "en": "No baseline submission found for ({modelo}, {period}).",
        "hu": "Nincs rogzitett alap-filing ({modelo}, {period}) eseten.",
    },
    "error.no_baseline.suggestion": {
        "es": "Ejecuta `aeat revise import-baseline ./<justificante.pdf>` primero.",
        "en": "Run `aeat revise import-baseline ./<justificante.pdf>` first.",
        "hu": "Eloszor futtasd: `aeat revise import-baseline ./<justificante.pdf>`.",
    },
    ...
}
```

Rules:

- Keys are dot-path strings under a command namespace or an `error.*`
  namespace.
- Every key has a non-empty `es` and `en`.
- Placeholders use `{name}` format and are expanded at render time from
  structured context.
- The catalogue is machine-enumerable. A test enumerates every key used
  in the codebase and asserts catalogue coverage.

### Render helper

A `t()` helper reads the catalogue at render time:

```python
from aeat.core.i18n import t, select_language

lang = select_language()
print(t("status.today.header", lang=lang))
print(t("error.no_baseline.message", lang=lang, modelo="303", period="2024Q2"))
```

Click help strings use the helper at command-registration time with the
`select_language()` result cached for the process lifetime.

Freeform strings in user-facing paths fail a static-analysis test that
scans for `print(`, `click.echo(`, `sys.stderr.write(`, `logger.info(`,
`logger.warning(`, and `logger.error(` call sites and asserts the
argument is either a `t()` call or a module-level constant derived from
the catalogue.

### Error-message translation

The error-code registry from iteration 6 already defines
`default_message_es`, `default_message_en`, `default_message_hu` on every
entry. The error emitter reads the registry and renders in the selected
language; the catalogue is the single source of truth.

Under `--json`, the error envelope's `message` and `suggestion` fields
carry the rendered language, and a `language` field records the selected
language for downstream consumers:

```json
{
  "error": {
    "category": "required_state_missing",
    "code": "E_NO_BASELINE",
    "language": "en",
    "message": "No baseline submission found for (303, 2024Q2).",
    "suggestion": "aeat revise import-baseline ./303-2024Q2-justificante.pdf",
    ...
  }
}
```

### Numeric and date formatting

Human output formats numbers and dates per locale conventions.

| Locale | Decimal | Thousand | Date format |
| --- | --- | --- | --- |
| `es` | `,` | `.` | `dd/mm/yyyy` |
| `en` | `.` | `,` | `yyyy-mm-dd` |
| `hu` | `,` | ` ` | `yyyy. mm. dd.` |

Machine output (`--json`) always uses ISO-8601 dates and decimal-point
numbers regardless of language. This is the pipeline contract.

Integration tests assert a fixture dataset renders each number and date
in each language exactly, and that `--json` renders the same value in the
same canonical machine form.

### Terminal Unicode capability

Spanish and English fit Latin-1 extended. Hungarian requires code points
beyond Latin-1: `ő` (U+0151) and `ű` (U+0171) specifically. Windows
consoles that default to cp1252 or cp437 cannot render these glyphs.

Startup rules:

- Detect terminal encoding via `sys.stdout.encoding`.
- If encoding supports UTF-8 natively (Windows Terminal, PowerShell 7,
  VS Code integrated terminal, modern POSIX), proceed.
- If encoding is cp1252/cp437 and requested language is `hu`: emit a
  warning to stderr and fall back the selected language to `en` for
  the remainder of the invocation. Log the fallback with code
  `I_LANG_FALLBACK_TERMINAL`.
- If encoding is cp1252/cp437 and requested language is `es`: proceed;
  Spanish Latin-1 characters render on both cp1252 and cp437 with
  correct mapping.

A regression test exercises the fallback on a cp1252-simulated terminal
and asserts the warning plus the English rendering.

### Kent roleplay

Kent uses English in his shell.

```text
$ AEAT_OUTPUT_LANGUAGE=en aeat status today
Today's agenda:
  303/2024Q1   due tomorrow    ready to approve   aeat review approve draft 303/2024Q1
  130/2024Q1   overdue 2 days  not started        aeat draft create 130 --period 2024Q1

2 filings pending today.
```

Kent switches to Spanish for an official export context.

```text
$ AEAT_OUTPUT_LANGUAGE=es aeat status today
Agenda de hoy:
  303/2024Q1   vence manana       lista para aprobar   aeat review approve draft 303/2024Q1
  130/2024Q1   vencida hace 2 dias no iniciada         aeat draft create 130 --period 2024Q1

2 autoliquidaciones pendientes hoy.
```

Note: the Spanish label uses `autoliquidaciones` (AEAT-authoritative
term) rather than a borrowed English "filings". Proper tax terminology
belongs in the `es` strings.

Kent tries Hungarian on a Windows Terminal with UTF-8.

```text
$ AEAT_OUTPUT_LANGUAGE=hu aeat status today
Mai napirend:
  303/2024Q1   holnap esedekes   jovahagyasra kesz   aeat review approve draft 303/2024Q1
  130/2024Q1   2 napja lejart    nem kezdodott el    aeat draft create 130 --period 2024Q1

2 filing esedekes ma.
```

Kent tries Hungarian on a legacy cp1252 terminal.

```text
$ AEAT_OUTPUT_LANGUAGE=hu aeat status today
[warning] terminal cannot render hu glyphs; falling back to en for this session.
Today's agenda:
  303/2024Q1   due tomorrow    ready to approve   aeat review approve draft 303/2024Q1
  ...
```

### Hardening rules derived from iteration 9

- Every user-facing persistent string uses the `Translatable` TypedDict
  with `es` and `en` required. A Pydantic validator enforces this.
- Every user-facing render goes through the `t()` helper with a
  registered catalogue key. Static analysis detects freeform strings.
- Language selection runs once per invocation and stays stable.
- Fallback chain is deterministic: requested language, then `es`, then
  `en`, then marker.
- Closed list of terms that never translate: modelo IDs, amendment-kind
  values, casilla/clave/ejercicio/periodo field names, normative proper
  nouns, AEAT-issued strings, CSV codes.
- `--json` output remains machine-canonical: ISO-8601 dates,
  decimal-point numbers, independent of selected language.
- Terminal Unicode capability check downgrades `hu` to `en` on legacy
  Windows consoles with an explicit warning.
- Catalogue coverage is machine-enforced: every registered key has at
  least `es` and `en`; every used key is registered.

### Open risks added by iteration 9

- Translation coverage is only as good as manual curation. A missing
  `hu` entry silently falls back to `es`, which may not be Kent's
  expected experience. Catalogue audits are a recurring maintenance
  cost.
- AEAT-specific vocabulary sometimes has no Hungarian equivalent.
  `autoliquidacion`, `modelo 303`, `casilla` may stay Spanish inside
  Hungarian prose. Translators must be aware.
- `--lang` flag combined with non-TTY output could create subtle bugs
  if the flag is not propagated to subprocesses invoked by the CLI
  (for example the LLM prompt context). The language must be passed
  through to every subprocess.
- Windows UTF-8 enablement varies by version and shell. The check at
  startup may misreport capability on exotic terminals; fallback is the
  safe default.
- Catalogue keys are strings; typos in call sites are not caught at
  compile time. The static-analysis coverage test must run on every
  PR or drift accumulates.
- Spanish authoritative rule may be inverted for specific strings
  imported from English-source material (LLM output, AEAT portal
  English translations). Those strings have `en` as authoritative and
  `es` as translation; the catalogue shape already permits this but
  the validator must accept it.

## Hardening pass iteration 10 (2026-04-24)

Iteration 10 focus: concrete migration rollout sequence across releases,
from the pre-approval blocker closure to the 1.0.0 live-submit
reintroduction. Every iteration 1 through 9 defined contracts; iteration
10 defines the order in which those contracts actually ship without
breaking Kent's current workflows.

### Phase model

The migration runs across five phases labelled A through E. Each phase
maps to a release cycle. The phase boundary is a real release tag; the
phase contents are a coherent bundle of PRs that can ship together
without exposing Kent to inconsistent state.

| Phase | Release | Theme | User-visible effect |
| --- | --- | --- | --- |
| A | next patch | infrastructure and blocker closure | only the workflow flag excision is visible; everything else is internal |
| B | next minor | new roots behind feature flag | default users see nothing; opt-in users see the new tree in preview |
| C | minor after B | flip the default | new tree is default; old commands route through `advanced aliases` with deprecation notices |
| D | minor after C | sunset wave 1 | sunset aliases fail with clear migration guidance |
| E | 1.0.0 | live-submit reintroduction | `advanced workflow run --live` under AuthProvider + four-factor gate |

Each phase ships behind its own safety net: feature flags in B,
deprecation notices in C, explicit refusal in D, four-factor gate in E.
No phase ships without the preceding phase tagged.

### Phase A: infrastructure and blocker closure

Scope: internal plumbing plus the one Kent-visible excision.

PR list:

1. Close the workflow live-flag leak per iteration 5. Single PR touching
   `src/aeat/entrypoints/cli/workflow/run.py`, `src/aeat/entrypoints/cli/workflow/next.py`, and
   `src/aeat/entrypoints/cli/workflow/__init__.py`, with regression tests.
2. Introduce the error-code registry at `src/aeat/core/errors/_registry.py`
   per iteration 6. `AeatError` subclasses carry a `code` attribute
   mapped to the registry. Add the error-emission decorator.
3. Introduce the CLI mutability and idempotency registry at
   `src/aeat/entrypoints/cli/_mutability.py` per iteration 8. Classify every
   existing CLI leaf and add the registry enforcement test.
4. Introduce the i18n catalogue infrastructure at
   `src/aeat/core/i18n/_catalog.py` per iteration 9 plus the `Translatable`
   Pydantic validator and the `t()` helper. Populate initial ES and
   EN strings for every existing CLI command's help text.
5. Introduce the `--json` output envelope and the per-command schema
   registry at `src/aeat/entrypoints/cli/_schemas.py` per iteration 7. Wire the
   envelope into every existing command without renaming. `--json`
   support becomes uniform.
6. Persist `ComputationLedger` and `AuditReport` to
   `var/audit/{modelo}/{period}/` per iteration 3. Migrate
   `formulas.audit` and the filing validator to read from persisted
   records; no Kent-facing API change yet.
7. Persist `VerificationVerdict` to
   `var/audit/{modelo}/{period}/verify-results/` per iteration 3.
8. Introduce `ApprovalLedgerEntry` and persist decision journal entries
   under `var/audit/{modelo}/{period}/approval-journal/` per iteration
   3. Extend `review approve`/`unapprove` to append.
9. Add `profile_tax_id` and `corpus_sha256` to `WorkflowResult` per
   iterations 1 and 3.

DoR for Phase A:

- Every PR has Kent-observable acceptance (blocker closure is Kent-visible;
  the rest are infrastructure with developer-observable acceptance and
  Kent-invisible effect).
- Every PR has a regression test.

DoD for Phase A:

- `aeat workflow run --help` and `aeat workflow next --help` no longer
  advertise live-write flags.
- Error-code, mutability, i18n, schema, and evidence-persistence
  registries all pass their enforcement tests.
- No Kent-visible behaviour change outside the workflow flag excision.
- Coverage floor 60 percent preserved.

Rollback for Phase A:

- Each PR is independently revertible. The workflow flag PR must land
  first because it is the pre-approval blocker for the ADR.

### Phase B: new roots behind a feature flag

Scope: implement every hardened root and gate them behind
`AEAT_KENT_CLI_PREVIEW=1`.

PR list:

10. Feature-flag scaffold: when `AEAT_KENT_CLI_PREVIEW=1` is set, the
    CLI exposes the new root tree alongside the old one. Flag is
    documented in `.env.example` and in `docs/cli-preview.md`.
11. Implement `status` root: `today`, `show`, `backlog *`, `resume`,
    `history`. Reads existing persisted records; no schema changes.
12. Implement `data` root: `import statement|invoice|receipt`,
    `link invoice|receipt|attachment`, `edit invoice|receipt`, `show`,
    `readiness`.
13. Implement `transactions` root: `build`, `automate`, `classify`,
    `categorize`, `edit`, `link`, `inspect`, `resume`, `show`.
    Wraps existing `financial txs` internals.
14. Implement `draft` root: `create`, `show`, `validate`, `list`.
    Retires the developer `--inputs` JSON path.
15. Implement `compare` root: `show`, `explain`, `fix`, `verify`
    each accepting `--against aeat|receipt|export`. Wraps existing
    submission diff and formula discrepancy semantics.
16. Implement `export` root: consolidate `submission preflight`,
    `submission dry-run`, `submission export`, `submission verify`,
    `submission diff`, `submission schemas` under `export *`.
17. Implement `audit` root: `show`, `verify`, `export`, `replay`,
    `manifest`. Depends on Phase A evidence persistence.
18. Implement `revise` root: `start --kind <k>`, `import-baseline`,
    `status`, `resume`, `show`. Introduces
    `RevisionSupportRegistry` per iteration 2.
19. Implement `records` root: `filings`, `receipts`, `notifications`,
    `amendments`, `aeat fetch/show`. Consolidates inventory across
    `filing list`, `submission list`, `inbox list`, `status
    expedientes`.
20. Parity test suite: every new command has an integration test that
    invokes the new command and the old equivalent against a shared
    fixture and asserts identical results.

DoR for Phase B:

- Phase A is tagged and released.
- Every new root has a Kent-capability acceptance line.
- The feature flag is documented and CI matrix includes both paths.

DoD for Phase B:

- `AEAT_KENT_CLI_PREVIEW=1 aeat --help` shows the 13-root tree.
- Parity test suite is green.
- Default `aeat --help` is unchanged.
- Opt-in users can perform every Kent-first task end to end.

Rollback for Phase B:

- Feature flag off reverts behaviour. Individual root PRs can be
  reverted without cascading.

### Phase C: flip the default

Scope: new tree becomes default; old commands become `advanced aliases`.

PR list:

21. Remove the `AEAT_KENT_CLI_PREVIEW` gate. The new tree is the
    default.
22. Introduce the `advanced` quarantine root and move every
    non-Kent-first surface into its closed buckets per iteration 4's
    allocation table.
23. Implement `advanced aliases` leaves for every deprecating-forward
    command per iteration 4. Deprecation notices active.
24. Place `doctor` at root; ensure help text reflects its Kent
    question.
25. Remove `hello` with the explicit removal message.
26. Merge `deadlines` into `status today` and
    `configure modelos calendar`; retain `deadlines` as an alias for
    one release.
27. Merge `inbox` into `records notifications`; retain `inbox` as an
    alias.
28. Update `docs/coverage/*.md` to the new vocabulary. Update
    `CONTRIBUTING.md`, `ROADMAP.md`, and `RELEASING.md` to reflect
    the tree change.

DoR for Phase C:

- Phase B tagged and released.
- Parity test suite remained green across the Phase B release cycle.
- Alias behaviours (forward, refuse-on-live-flags, exit-2 on
  manual-migration-required) are specified in tests.

DoD for Phase C:

- `aeat --help` shows the 13-root tree.
- Old invocations still succeed through aliases where possible.
- Deprecation notices fire on every deprecating alias.
- Documentation reflects the new tree.
- No live-write flag appears in any default help surface.

Rollback for Phase C:

- Phase C is the highest-risk phase. The rollback path is a revert of
  PRs 21 and 22; advanced bucket moves can stay. Users fall back to
  the old root but the new tree remains available.

### Phase D: sunset wave 1

Scope: remove the first batch of aliases after one release cycle of
deprecation.

PR list:

29. Remove sunset aliases: `financial-txs *`, `financial-invoices *`,
    `financial-profile *`, `filing-build *`, `filing-show *`,
    `filing-list *`, `filing-validate *`,
    `filing-import-from-justificante *`,
    `submission-preflight *`, `submission-dry-run *`,
    `submission-export *`, `submission-verify *`,
    `submission-diff *`, `submission-schemas *`.
30. Remove `deadlines` alias; remove `inbox` alias.
31. Remove `workflow-run *` and `workflow-next *` aliases; the
    `advanced workflow` namespace remains.

DoR for Phase D:

- Phase C tagged and released.
- Release notes for Phase C explicitly announced sunset dates.
- Migration docs exist and have been linked in deprecation notices.

DoD for Phase D:

- Removed aliases fail with the migration-required error pattern
  (exit `2`, category `user_input_invalid`, suggestion pointing to
  the new invocation).
- Reference-noun aliases (`schema`, `modelos`, `normatives`,
  `manual`, `casillas`, `categories`, `vat`, `portals`) remain;
  they are `moved` not `deprecated` and do not sunset.

Rollback for Phase D:

- Individual alias removals can be reverted if a heavy user base
  blocks the sunset. The ADR should be amended to record the
  extension.

### Phase E: 1.0.0 live-submit reintroduction

Scope: reintroduce live execution behind the AuthProvider abstraction
and the four-factor gate.

PR list:

32. Land the AuthProvider abstraction per epic #279.
33. Introduce `advanced workflow run --live` that routes through
    AuthProvider and requires all four factors:
    `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1`, `AEAT_LIVE_SUBMIT_ENABLED=1`,
    `--live` flag, interactive per-submission prompt.
34. 1.0.0 release candidate: full Kent-first tree, hardened aliases,
    live reintroduction. Announce via `RELEASING.md` and
    `ROADMAP.md`.

DoR for Phase E:

- Phases A through D tagged and released.
- AuthProvider abstraction is complete and tested.
- Live-submit reintroduction has its own ADR (not this one).

DoD for Phase E:

- Live execution is available to expert users through a single
  well-gated leaf.
- No live-write path is discoverable from the default Kent root.
- 1.0.0 ships with full documentation and migration notes.

Rollback for Phase E:

- 1.0.0 is a commitment. Rollback is a patch release that disables
  the `--live` flag. The rest of the tree stays.

### Dependency graph (simplified)

Phase A PR 1 (workflow flag excision) blocks ADR approval but does not
block other Phase A PRs. PRs 2 through 9 can ship in parallel.

Phase B depends on Phase A. PRs 11 through 19 can ship in parallel after
PRs 2 through 9. PR 20 (parity tests) lands alongside each root PR.

Phase C depends on Phase B. PR 21 (default flip) blocks PRs 22 through
28 within Phase C.

Phase D depends on Phase C plus one full release cycle of deprecation
notices shipping.

Phase E depends on Phase D plus the AuthProvider abstraction (#279).

### CI coverage requirements

- Phase A adds enforcement tests for every registry introduced.
- Phase B adds the parity test suite running on both the preview and
  default trees.
- Phase C strips the old-tree parity tests once aliases are in place;
  alias tests replace them.
- Phase D removes alias tests for sunsetted commands; migration-error
  tests replace them.
- Phase E adds four-factor gate tests for every live-capable leaf.

Windows integration tests run on every phase. The cross-platform locking
work from iteration 8 lands in Phase A and is exercised in every later
phase.

### Kent roleplay across phases

Phase A: Kent types `aeat workflow run --no-dry-run
--i-understand-this-is-real`. Refused. Every other command works
identically to today.

Phase B: Kent with `AEAT_KENT_CLI_PREVIEW=1` in his shell types
`aeat status today`. Sees the agenda. Types `aeat financial txs
classify tx_123` and it works (old tree still present).

Phase C: Kent types `aeat status today` without a flag. Sees the
agenda. Types `aeat financial txs classify tx_123`. Sees a
`[deprecated]` notice and the command succeeds.

Phase D: Kent types `aeat financial txs classify tx_123`. Exit `2`.
Message: "use `aeat transactions classify tx_123`". He updates his
script.

Phase E: Kent types `aeat advanced workflow run --modelo 303
--period 2024Q1 --live` after setting both environment variables.
Interactive prompt confirms. Live submission runs.

### Hardening rules derived from iteration 10

- No phase ships without the preceding phase tagged and stable for one
  release cycle.
- Every phase carries a feature-flag, alias, or gate safety net. No
  phase exposes users to unrecoverable state.
- Parity tests are the gate for Phase B to C transition.
- Alias sunset horizons are announced in release notes at the phase
  where the alias is introduced, not when it is removed.
- The ADR flips to `proposed (approval-ready)` only after Phase A PR 1
  lands. The ADR flips to `accepted` only after the user approves the
  complete multi-phase plan.
- Every phase has a rollback path documented in this section.
- Documentation, coverage matrices, and release notes move with the
  phase, not behind it.

### Open risks added by iteration 10

- Feature-flag codepaths in Phase B are expensive to maintain. If the
  Phase C flip is delayed, the parallel trees drift. Mitigation: Phase
  B to C horizon is capped at one release cycle.
- Phase C carries the highest rollback cost because aliases reshape
  documentation. Rollback keeps the new tree available but restores
  the old default; docs revert must run together with the default
  revert.
- The AuthProvider abstraction (#279) is upstream of Phase E. Delays
  in #279 push Phase E; the rest of the tree is independent.
- Windows-specific regressions (terminal, locking, codepage) may land
  late in the phase cycle if coverage is thin. Windows CI must run at
  every phase.
- The coverage floor of 60 percent must hold across phase transitions;
  Phase C is the highest-risk transition because it rewrites surface
  area. Pre-phase audits must verify the floor holds against the new
  surface before flipping.
- Documentation drift between phases is the single most common failure
  mode in multi-phase migrations. A per-phase docs checklist is
  required as a Definition-of-Done item.

## Hardening pass iteration 11 (2026-04-24)

Iteration 11 focus: multi-profile support. Kent is a Spanish autonomo
today, but a real production tool must accommodate the reality that an
autonomo often operates multiple tax identities: personal NIE, a sociedad
limitada CIF, occasionally a second autonomo NIE under a different
activity, or a trusted family member's NIE. `profile_tax_id` already
threads through every persisted record (iterations 1 and 3), but the CLI
layer currently assumes a single implicit active profile. This iteration
makes multi-profile a first-class contract.

### Profile model

A profile is a persisted record representing one tax identity. Stored as
a frozen Pydantic v2 model at `var/profiles/{profile_id}/profile.json`:

- `profile_id`: Kent-chosen stable short identifier (`personal`,
  `company-sl`, `friend-juan`). Slug-style; machine-safe.
- `tax_id`: the NIE/NIF/CIF string.
- `tax_id_kind`: closed enum (`NIE`, `NIF`, `CIF`).
- `display_name`: Kent-facing label (`"Kent Personal"`,
  `"Kent Consulting SL"`).
- `residency`: ISO-3166 country code (`ES` for Kent).
- `modelos_tracked`: ordered list of modelo identifiers this profile
  files (for example `["130", "303", "390"]` for personal autonomo).
- `auth_provider_default`: default auth provider for this profile
  (`certificate`, `clave-permanente`, `clave-movil`, `clave-pin`).
- `created_at`: ISO-8601 UTC.

Profiles are append-only in practice: removal is destructive and
requires `--force` plus a double confirmation.

The active profile is recorded as a single line pointer at
`var/active_profile` containing the active `profile_id`. Commands read
it at startup once per invocation.

### Workspace isolation

Every persisted workspace record lives under the owning profile:

```text
var/
|-- active_profile                          # one-line pointer
|-- profiles/
|   |-- index.json                          # list of known profiles
|   |-- personal/
|   |   |-- profile.json
|   |   |-- auth/                           # per-profile session state
|   |   |-- drafts/
|   |   |-- submissions/
|   |   |   `-- amendments/
|   |   |-- transactions/
|   |   |-- evidence/                       # statements, invoices, receipts
|   |   |-- decisions/                      # approval journal
|   |   |-- audit/                          # ledger, audit reports, verify verdicts
|   |   `-- locks/                          # per-case concurrency locks
|   `-- company-sl/
|       `-- ...
|-- corpus/                                 # shared: manual, normative, schema, ruleset registries
`-- cache/
    |-- llm/                                # keyed by (profile_id, prompt_hash)
    `-- readiness/                          # keyed by (profile_id, modelo, period)
```

Cross-profile data sharing is forbidden except for the corpus (shared
reference) and cache (keyed by profile). An audit test asserts that no
profile directory contains records with a `profile_tax_id` that does not
match the owning profile.

### Command scoping

Every Kent-first command accepts an optional `--profile <profile_id>`
flag that overrides the active profile for this invocation only.

Resolution chain:

1. `--profile <id>` CLI flag.
2. `AEAT_ACTIVE_PROFILE` environment variable.
3. Workspace active profile pointer at `var/active_profile`.
4. If none set and command requires a profile: refuse with
   `E_NO_ACTIVE_PROFILE`.

Commands classified as profile-scoped:

- `status *`, `data *`, `transactions *`, `draft *`, `review *`,
  `compare *`, `export *`, `audit *`, `revise *`, `records *`.

Commands that may be profile-scoped or global:

- `auth *`: per-profile sessions; default to active profile's
  `auth_provider_default`.
- `configure profile *`: operates on specified profile (`add`/`show`/
  `remove`/`use`) or the active profile (`set`).
- `configure modelos add/remove`: applies to active profile by default.
- `configure defaults set/show`: applies to active profile by default.

Commands that are profile-agnostic:

- `aeat --help`, `aeat --version`.
- `doctor` (reports workspace health across profiles).
- `configure profile list`.
- `advanced *` reference/providers/diagnostics (no profile context).

### Configure commands (extended from iteration 1)

| Command | Behaviour |
| --- | --- |
| `configure profile add --id <id> --tax-id <id> --kind <nie\|nif\|cif> --display-name <name>` | Create a new profile record. First profile automatically becomes active. |
| `configure profile list` | Tabular list of all profiles; asterisk marks active. |
| `configure profile show <profile_id>` | Full profile record. |
| `configure profile use <profile_id>` | Set active profile. Fails if unknown. |
| `configure profile remove <profile_id> --force` | Destructive. Refuses without `--force`; prompts interactively for confirmation. Cascades to every record owned by the profile. |
| `configure profile rename <old_id> <new_id>` | Rewrites every persisted reference. Heavy operation; requires a workspace lock. |
| `configure modelos add <modelo> [--profile <id>]` | Appends modelo to the profile's `modelos_tracked` list. |
| `configure modelos remove <modelo> [--profile <id>]` | Removes modelo. Refuses if any draft, submission, or amendment exists under that modelo for the profile. |

### Active-profile banner

Every Kent-facing command that consumes a profile prints a compact banner
on stderr declaring the profile:

```text
[profile] personal (X1234567L)
```

The banner is suppressed in `--json` mode and under `--quiet`. It is
always printed in human mode when the profile in use differs from the
active workspace profile (because of `--profile` flag or
`AEAT_ACTIVE_PROFILE` env).

### Records and cross-profile views

By default, `records *` commands operate on the active profile only.
Cross-profile views require opt-in:

- `records filings list` shows active profile only.
- `records filings list --profile company-sl` shows specified profile.
- `records filings list --all-profiles` shows every profile, grouped.

This matches the determinism contract from iteration 8: default behaviour
is narrow and predictable; cross-cutting views are explicit.

### Auth scoping

Auth sessions are per-profile. `var/profiles/{profile_id}/auth/`
contains the session state (certificate thumbprint, OAuth tokens, Cl@ve
tokens). Iteration 12 covers credential hygiene in depth.

- `aeat auth login` logs in for the active profile using its
  `auth_provider_default`.
- `aeat --profile company-sl auth login --provider certificate`
  overrides both.
- `aeat auth status --all-profiles` enumerates session state across
  profiles.
- Session state never leaks across profiles.

### Tax-id-kind compatibility

Every modelo declares supported `tax_id_kind` sets:

| Modelo | Supported `tax_id_kind` |
| --- | --- |
| `100` | `NIE`, `NIF` |
| `111` | `NIE`, `NIF`, `CIF` |
| `115` | `NIE`, `NIF`, `CIF` |
| `130` | `NIE`, `NIF` |
| `200` | `CIF` |
| `202` | `CIF` |
| `303` | `NIE`, `NIF`, `CIF` |
| `390` | `NIE`, `NIF`, `CIF` |

`draft create` and `revise start` consult the modelo registry and refuse
when the profile's `tax_id_kind` is incompatible. Error code
`E_TAX_ID_KIND_MISMATCH`, exit `4`.

### Amendment chain binding

Every `FilingAmendment` carries `profile_tax_id`. Amendment chain walks
(iteration 2) never cross profiles. `revise import-baseline <path>`
parses the justificante's embedded NIE and refuses to link the baseline
to the active profile if the NIEs differ:

```text
ERROR: The justificante PDF identifies NIE X7654321L, but the active profile 'personal' owns X1234567L.
  -> Switch to the matching profile: `aeat --profile <id> revise import-baseline <path>`.
  -> Or inspect profiles: `aeat configure profile list`.
```

Exit `4`. Category `unsupported_target`. Code `E_PROFILE_TAX_ID_MISMATCH`.

### Kent roleplay: add a second profile

```text
$ aeat configure profile add --id personal --tax-id X1234567L --kind NIE --display-name "Kent Personal"
[profile] personal (X1234567L)
Profile 'personal' created.
Active profile: personal (first profile auto-activated).

$ aeat configure profile add --id company-sl --tax-id B12345678 --kind CIF --display-name "Kent Consulting SL"
[profile] personal (X1234567L)
Profile 'company-sl' created.
Active profile: personal (unchanged).

$ aeat configure profile list
Profiles:
  personal    X1234567L   NIE  Kent Personal            * active
  company-sl  B12345678   CIF  Kent Consulting SL

$ aeat configure modelos add 200 --profile company-sl
[profile] company-sl (B12345678)
Added modelo 200 to profile 'company-sl'.

$ aeat status today
[profile] personal (X1234567L)
Today's agenda:
  303/2024Q1   due tomorrow    ready to approve   aeat review approve draft 303/2024Q1

$ aeat --profile company-sl status today
[profile] company-sl (B12345678)
Today's agenda:
  200/2023     overdue 30 days draft exists       aeat compare show 200 --period 2023 --against aeat
```

### Kent roleplay: accidental profile switch

Kent switches active profile but forgets he tracks modelo 130 only under
the personal profile.

```text
$ aeat configure profile use company-sl
Active profile: company-sl (was: personal).

$ aeat draft create 130 --period 2024Q1
[profile] company-sl (B12345678)
ERROR: Modelo 130 is not tracked by profile 'company-sl'.
  tracked modelos: 303, 390, 200, 202
  -> Run `aeat --profile personal draft create 130 --period 2024Q1`.
  -> Or `aeat configure modelos add 130 --profile company-sl` if you want this profile to track it.
  -> Modelo 130 requires NIE or NIF; profile 'company-sl' is a CIF, so the add would still be refused.
```

Exit `4`. Category `unsupported_target`. Code `E_MODELO_NOT_TRACKED`.

### Lock scoping with profiles

Per iteration 8, locks use `(modelo, period, profile_tax_id)` as the
key. Multi-profile makes this explicit in the lock path:

```text
var/profiles/personal/locks/303-2024Q1.lock
var/profiles/company-sl/locks/303-2024Q1.lock
```

Both can be held concurrently because they address different profiles.
The profile-scoped lock discipline prevents accidental cross-profile
contention.

### Profile deletion and rename

`configure profile remove <id> --force`:

- Interactive confirmation prompt repeats the profile_id twice.
- Refuses under non-TTY unless `--yes-i-want-to-delete-everything` is
  explicitly passed.
- Cascades: deletes every record under the profile directory.
- Writes a tombstone at `var/profiles/_tombstones/{profile_id}.json`
  with deletion timestamp and caller for audit.

`configure profile rename <old_id> <new_id>`:

- Takes workspace lock across every profile directory.
- Renames `var/profiles/{old_id}/` to `var/profiles/{new_id}/`.
- Rewrites every cache key that references the old id.
- Updates `var/active_profile` if it matched.
- Leaves a forwarding pointer at `var/profiles/_aliases.json` so
  scripts using the old id fail with a clear redirect.

Rename is heavy and rare. Kent roleplay: only during profile cleanup.

### Hardening rules derived from iteration 11

- Every profile-scoped command acquires the active profile via the
  resolution chain. Commands that operate without a resolved profile
  refuse with `E_NO_ACTIVE_PROFILE`.
- Workspace records are stored under `var/profiles/{profile_id}/`.
  Cross-profile record access requires `--profile <id>` or
  `--all-profiles` explicit flag.
- A workspace audit test asserts that no record under
  `var/profiles/{id}/` carries a `profile_tax_id` that does not match
  the owning profile's `tax_id`.
- Every Kent-facing human-mode command emits a `[profile]` banner on
  stderr when the profile differs from the workspace active profile or
  when the invocation is ambiguous about scope.
- Tax-id-kind compatibility is enforced at `draft create` and
  `revise start` against a modelo-registry truth table.
- Amendment chains never cross profiles. `revise import-baseline`
  refuses on NIE mismatch.
- Auth sessions are per-profile and never leak across profiles.
- Lock paths include the profile. Cross-profile contention is
  impossible.
- Profile deletion is destructive, requires force plus confirmation,
  and writes a tombstone.
- Profile rename rewrites every persisted reference inside one
  workspace lock.

### Open risks added by iteration 11

- Workspace size scales linearly with profile count. Kent with ten
  profiles has ten copies of the directory tree; backup-restore
  (iteration deferred) must account for this.
- LLM cache invalidation across profile rename is tricky; a bad cache
  key could leak one profile's classification suggestions into
  another's results. The cache key must include profile_id explicitly.
- Cross-profile reporting (`--all-profiles`) may leak Kent's private
  LLC activity into a combined view he meant to share narrowly; the
  flag must be opt-in and never default.
- `configure profile list` shows every profile including sensitive LLC
  identities. Masking (`X1234*67L`) should be available for shared
  screens.
- The first profile auto-activating on `profile add` is a convenience
  that may surprise scripted operators who run two `profile add`
  commands back to back expecting the second to activate. The rule is
  `first profile auto-activates; subsequent adds leave active
  unchanged`.
- `configure profile rename` requires rewriting ledger entries,
  approval journals, and amendments that reference the profile_id in
  any field. Missing rewrite sites leave orphaned references; a
  coverage test must walk every persisted model and confirm the
  rename sweep.
- Corpus sharing across profiles is safe for read-only reference data
  but must never include per-profile derived state (category profiles,
  usage ratios, classification overrides). A linter asserts
  `var/corpus/` contains only reference material.

## Hardening pass iteration 12 (2026-04-24)

Iteration 12 focus: credential hygiene and security contract. Kent's
workspace holds FNMT certificates, Cl@ve credentials, OAuth tokens for
Google Workspace, Playwright browser sessions, and LLM API keys. Each has
different sensitivity, different rotation, and different blast radius on
compromise. This iteration specifies storage locations, encryption, file
permissions, scrubbing, rotation, emergency revocation, and non-
transferability.

### Credential inventory

| Credential | Source | Lifetime | Persisted | Sensitivity |
| --- | --- | --- | --- | --- |
| Certificate (FNMT-RCM digital certificate) | FNMT issuance, user import | 3 years typical | yes (PFX + OS keystore handle) | very high |
| Cl@ve Permanente password | user input each session | one session | no | very high |
| Cl@ve Movil OTP code | SMS/app per authentication | ~30 seconds | no | very high |
| Cl@ve PIN temporary code | user-requested one-time | ~15 minutes | no | very high |
| OAuth refresh token (Google Workspace) | OAuth flow | until revoked | yes (encrypted) | high |
| OAuth access token (Google Workspace) | refresh flow | ~1 hour | no (in-memory only) | high |
| Browser session cookies (Playwright) | AEAT portal login | session lifetime | yes (encrypted) | high |
| LLM provider API key | user env var | until rotated | no | high |
| Workspace state encryption key | derived at first run | until revoked | OS keystore only | highest |

### Storage locations and permissions

Every persisted credential lives under the profile that owns it:

```text
var/profiles/{profile_id}/auth/
|-- certificate.pfx                  # mode 600
|-- certificate.meta.json            # mode 600; metadata only (serial, expiry, subject)
|-- oauth/
|   `-- google_workspace.json        # mode 600; encrypted
|-- browser/
|   `-- session.json                 # mode 600; encrypted
`-- events/                          # mode 700
    `-- {yyyy-mm-dd}.jsonl           # mode 600; append-only auth event log
```

Directory permissions for `auth/` and its subdirectories are mode `700`.
Startup check refuses to load any credential file whose mode is broader
than `600` on POSIX or whose ACL grants read to non-owner on Windows.
The check fails the command with `INTEGRITY:` prefix and exit `7`.

Workspace state encryption key is never persisted under `var/`. It lives
in the OS keystore:

- Windows: Windows Credential Manager via `win32crypt` / `keyring` backend
  (`keyring.backends.Windows.WinVaultKeyring`).
- macOS: Keychain Access via `keyring.backends.macOS.Keyring`.
- Linux: Secret Service API via `keyring.backends.SecretService.Keyring`
  (GNOME Keyring, KWallet). Fallback for headless Linux:
  `keyrings.alt.file.EncryptedKeyring` with passphrase prompt at first
  unlock.

The keystore stores a random 256-bit master key; that key unlocks
AES-256-GCM encryption over file-level credentials.

### Encryption-at-rest contract

- Algorithm: AES-256-GCM.
- Per-file nonce: 96-bit random, stored alongside ciphertext.
- AAD includes `profile_id`, `credential_kind`, and a version integer so
  file substitution is detected.
- Key derivation: HKDF-SHA-256 from the keystore master key using a
  per-credential-kind salt so compromise of one encryption key does not
  cascade.

Rotation of the master key re-encrypts every file in-place via
`aeat auth rotate-master-key`. Rotation is a local-state-mutating
command under iteration 8 contract.

### What never persists

Cl@ve credentials are never written to disk:

- Cl@ve Permanente password: typed per invocation, held in memory only,
  zeroed on command exit.
- Cl@ve Movil OTP: typed per invocation, expires in seconds anyway.
- Cl@ve PIN: typed per invocation, expires in minutes.

LLM API keys are read from environment variables only:

- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, provider-specific env vars.
- The workspace never persists these. A linter fails if any persisted
  record field looks like an API key (regex match on common key
  prefixes).

OAuth access tokens are in-memory only; only the refresh token persists.

Workspace state encryption keys, master keys, and derived encryption
keys are never written outside the OS keystore.

### Log scrubbing (extends iteration 7)

Additional scrub targets on top of iteration 7's list:

- Certificate serial numbers: redacted to last 4 hex digits
  (`<cert:....A3F2>`).
- OAuth access tokens: always redacted even at `--debug`.
- OAuth refresh tokens: always redacted (`<oauth:refresh:redacted>`).
- Browser cookie values: always redacted.
- Cl@ve passwords, OTPs, PINs: impossible to log because they are never
  handed to the logger; defence in depth removes any code path that
  could log them.
- LLM API keys: recognised by prefix regex (`sk-ant-`, `sk-`, etc.) and
  redacted even in `--debug`.
- LLM prompt content is scrubbed of NIE/NIF/CIF before being sent to
  the provider and before being logged locally.

An integration test captures every log line produced by a live-read
flow and asserts every scrub-target regex matches zero times in the
captured output.

### Prompt leakage to LLM

When `transactions automate --with llm` runs, the CLI sends transaction
descriptions to an external LLM. The scrubbing rules are:

- NIE/NIF/CIF patterns (`[XYZ]?\d{7,8}[A-Z]` for NIE,
  `[A-HJ-NP-SUVW]\d{7}[A-J0-9]` for CIF, etc.) are redacted before
  prompt emission.
- `profile_tax_id` is never included in the prompt context.
- Counterparty names are retained (business-sensitive but not secret;
  Kent's acceptance is required for LLM usage in general).
- Amounts are retained (required for classification).
- Every outbound prompt and its response is persisted at
  `var/profiles/{profile_id}/audit/llm-prompts/{run_id}.jsonl` so Kent
  can audit exactly what was sent.
- `aeat transactions automate --with llm --llm-audit` prints the scrub
  diff before sending and requires interactive confirmation on TTY.

### Credential rotation

Certificates expire. The CLI surfaces expiry on every `auth status`:

- Warning at 30 days remaining.
- Loud warning at 7 days remaining (prepend `WARNING:` to stderr).
- Refuse `auth login` at 0 days remaining; direct Kent to renew at
  FNMT.

OAuth refresh tokens that rotate on use replace the persisted token
atomically (write-rename). If the provider invalidates the refresh
token, the next use returns `AUTH:` error with code `E_OAUTH_INVALID`
and directs Kent to re-run the OAuth flow.

Cl@ve credentials rotate user-side; no CLI action needed.

LLM API keys rotate when Kent updates his environment; no CLI action
needed.

Master encryption key rotation runs via
`aeat auth rotate-master-key`:

- Generates a new 256-bit key in the OS keystore.
- Re-encrypts every file-level credential using the new key.
- Wipes the old key from the keystore on completion.
- Writes an audit event.

### Emergency revocation

One command wipes every persisted credential:

```text
aeat auth revoke --all --confirm
```

Behaviour:

- Interactive confirmation required (re-type the literal word
  `revoke-all`).
- Deletes every file under `var/profiles/*/auth/`.
- Deletes every tombstone that references a revoked credential.
- Removes the master key from the OS keystore.
- Writes an audit event per profile.
- Prints next-steps instructions: revoke FNMT certificate at source,
  revoke OAuth client at provider, rotate LLM keys.

Scoped revocation:

```text
aeat auth revoke --provider certificate
aeat auth revoke --provider oauth --oauth-client google_workspace
aeat auth revoke --profile company-sl --all
```

Every scoped revocation is atomic and audit-logged.

### Non-transferability

Credentials stored in a workspace are bound to:

- The current OS user (file permissions).
- The current OS keystore (master key is not portable).

Copying `var/profiles/{id}/auth/` to another machine yields unreadable
ciphertext. This is by design.

Backup-restore (iteration deferred) explicitly does not back up
`auth/` directories. Restore on a new machine requires Kent to re-run
`aeat auth login` for every profile; the workspace state records are
all restored intact but without credentials.

### Auth event audit log

Every auth event appends to
`var/profiles/{profile_id}/auth/events/{yyyy-mm-dd}.jsonl`:

```json
{
  "event_id": "uuid-v4",
  "timestamp": "2026-04-24T14:03:22Z",
  "profile_id": "personal",
  "provider": "certificate",
  "event_kind": "login|logout|refresh|revoke|expire_warn",
  "outcome": "success|failure|refused",
  "actor": "cli:aeat@v0.18.2",
  "certificate_last_4": "A3F2",
  "error_code": null,
  "client_ip": null
}
```

No full credential ever appears in the log. `client_ip` is null for
local-only flows; populated only on live auth requests where the AEAT
portal reports it.

### Kent roleplay: certificate expiring soon

```text
$ aeat auth status
[profile] personal (X1234567L)
Provider:  certificate
Subject:   Kent L, NIE ****67L
Issued:    2023-05-20
Expires:   2026-05-20 (26 days remaining)
Status:    active

WARNING: certificate expires in 26 days. Renew at FNMT before then or auth will fail.
  -> https://www.sede.fnmt.gob.es/certificados/persona-fisica/renovar
```

### Kent roleplay: laptop stolen

```text
$ aeat auth revoke --all --confirm
[warning] This command deletes every persisted credential on this machine.
Type the literal word `revoke-all` to confirm: revoke-all

Revoking credentials across 2 profiles...
  profile 'personal':
    [ok] deleted certificate.pfx (last 4: A3F2)
    [ok] deleted oauth/google_workspace.json
    [ok] cleared browser/session.json
    [ok] wiped auth/events/ index
  profile 'company-sl':
    [ok] deleted certificate.pfx (last 4: 7B9D)
    [ok] deleted oauth/google_workspace.json
    [ok] cleared browser/session.json
    [ok] wiped auth/events/ index

Master key wiped from OS keystore.

Next steps to fully secure:
  1. Revoke your FNMT certificate at https://www.sede.fnmt.gob.es/certificados/revocar
  2. Revoke your Google OAuth client at https://myaccount.google.com/permissions
  3. Rotate LLM API keys at your provider.
  4. If the machine itself is compromised, consider rotating Cl@ve credentials too.
```

### Kent roleplay: OS keystore unavailable

On a headless Linux system without Secret Service, first run prompts for
a passphrase:

```text
$ aeat auth login --provider certificate
[profile] personal (X1234567L)
No system keystore available. A passphrase-protected local keystore will
be used instead. You will be prompted for this passphrase on each
invocation that needs credentials.

Enter workspace passphrase (will not echo):
Confirm passphrase:

Keystore initialised at var/.keystore/local.enc (mode 600).
```

The passphrase unlocks the master key on subsequent runs. Lost passphrase
requires `aeat auth revoke --all` and re-establishing credentials.

### Hardening rules derived from iteration 12

- Cl@ve credentials (password, OTP, PIN) never persist. Typed per
  session. Code paths that could log them are removed at source.
- Persisted credentials are AES-256-GCM encrypted at rest with keys held
  in the OS keystore.
- File permissions for credential files are mode `600` in directories
  mode `700`; startup refuses broader permissions.
- Credential scrubbing is mandatory on every log path. An integration
  test enumerates live-flow logs and asserts zero scrub-target matches.
- LLM prompts are scrubbed of NIE/NIF/CIF before emission and persisted
  for audit.
- Certificate expiry warnings at 30 and 7 days; refuse at 0.
- OAuth refresh-token rotation replaces the persisted token atomically.
- Master key rotation re-encrypts every file-level credential in place.
- Emergency revocation is a first-class command with explicit
  confirmation and next-steps output.
- Credentials are non-transferable; backups exclude `auth/` directories.
- Every auth event appends to the per-profile audit log in append-only
  JSONL.

### Open risks added by iteration 12

- Headless Linux without Secret Service falls back to a passphrase-
  protected local keystore; automation under CI is fragile unless the
  passphrase is supplied through a secure secrets manager at the CI
  layer.
- Python `keyring` library has transitive dependencies that vary by
  platform. Integration tests on Windows, macOS, and Linux are
  mandatory; a single platform regression silently locks Kent out of
  credentials.
- LLM prompt scrubbing misses non-standard tax identifiers (Andorran
  residents, legacy NIF-H formats, some older CIF prefixes). Regex
  library must be kept current against a curated fixture set.
- `ps` / `/proc/<pid>/environ` on multi-user systems can leak
  env-var-held LLM keys to other logged-in users. The CLI cannot
  prevent this at the OS layer; document the risk in `docs/security.md`.
- OS keystore compromise cascades to every file-level credential. This
  is inherent to any encrypted-at-rest scheme; the mitigation is
  master-key rotation plus OS-level hardening guidance.
- Certificate auto-renewal is not possible without Kent's action at
  FNMT. The CLI can warn but not renew; a 7-day warning creates
  calendar pressure that may conflict with Kent's other work.
- Browser session cookies captured during AEAT portal flows may include
  CSRF tokens with broad scope. The Playwright integration must scope
  the session narrowly (single-tab, single-origin) so cookie capture
  cannot leak into other tabs.
- `aeat auth revoke --all` is destructive and cannot be undone. The
  confirmation-prompt pattern (re-type `revoke-all`) must survive the
  migration to `advanced` quarantine; moving it to `advanced auth
  revoke` may reduce discoverability and increase risk.
- Workspace state encryption key rotation is not per-profile. A
  profile-scoped compromise would require re-encrypting every profile's
  credentials, not just the compromised one. Consider per-profile
  master keys in a future iteration.

## Hardening pass iteration 13 (2026-04-24)

Iteration 13 focus: day-0 onboarding UX. Kent has just installed `aeat`
for the first time. He opens a terminal. What does he see, and how does
he go from zero to exporting his first fichero in under thirty minutes?
This iteration specifies first-run detection, the interactive profile
wizard, the `doctor` dominance rule, empty-state help on every command,
and progressive-disclosure banners on first encounters with key concepts.

### First-run detection

On any `aeat` invocation, the CLI classifies the workspace state at
startup:

- `pristine`: `var/` directory does not exist. First touch.
- `no_profile`: `var/` exists but `var/profiles/` is empty.
- `no_active_profile`: one or more profiles exist but
  `var/active_profile` is missing.
- `onboarding_incomplete`: active profile exists but
  `var/onboarding.json` has unset flags for core first-time concepts.
- `onboarded`: core onboarding flags all set.

The state is computed once per invocation and carried through the CLI
context. Commands that need a fully onboarded workspace refuse earlier
states with redirect messages; commands that do not need onboarding
(such as `aeat doctor`, `aeat --help`, `aeat --version`,
`aeat configure profile *`) run at any state.

### Welcome banner on `pristine` state

Kent types `aeat` with no arguments on a pristine workspace:

```text
$ aeat
Welcome to aeat. File your Spanish tax returns: produce, verify, and
export AEAT-ready drafts and records.

This is a first-run workspace. To get started:
  1. Create your taxpayer profile:   aeat configure profile add
  2. Check workspace health:          aeat doctor
  3. See what applies to you:         aeat configure modelos calendar

For full help: aeat --help
```

Exit `0`. No error. The banner prints only on pristine state and is
suppressed on subsequent runs.

### Interactive profile wizard

`aeat configure profile add` with no arguments and an interactive stdin
launches a guided wizard:

```text
$ aeat configure profile add
Welcome. Let us set up your first taxpayer profile.

Profile ID (short slug, for example 'personal', 'company-sl'): personal
Tax identifier (NIE/NIF/CIF): X1234567L
Tax ID kind (NIE/NIF/CIF) [NIE]:
Display name [Kent Personal]: Kent Personal
Residency (ISO-3166-1 alpha-2) [ES]:
Modelos to track (space-separated, default "130 303 390"): 130 303 390
Default auth provider (certificate|clave-permanente|clave-movil|clave-pin) [certificate]:
Default output language (es|en|hu) [es]:

Profile 'personal' created.
Active profile set to 'personal' (first profile auto-activated).

Next step: `aeat doctor` to check workspace health.
Or: `aeat auth login --provider certificate` to connect to AEAT.
```

Every field has a default appropriate for a Spanish autonomo. Invalid
input loops with a specific error:

- Profile ID reserved words (for example `index`, `default`, `_`):
  refuse with reason.
- Tax ID fails format validation: show the expected pattern.
- Tax ID kind disagrees with the ID format: refuse with an explicit
  mismatch explanation.
- Display name empty: repeat the prompt with the inferred default.

Wizard behaviour on non-TTY stdin:

```text
$ aeat configure profile add < /dev/null
ERROR: `aeat configure profile add` requires an interactive terminal for the guided wizard.
  -> Provide flags non-interactively:
     aeat configure profile add --id personal --tax-id X1234567L --kind NIE --display-name "Kent Personal" --modelos "130 303 390" --auth-provider certificate
  -> Or re-run in a TTY.
```

Exit `3`. Category `required_state_missing`. Code `E_TTY_REQUIRED`.

Non-interactive form is fully supported. Every wizard field has a
corresponding `--flag` so automation can provision profiles without
human input.

### Doctor dominance

`aeat doctor` is the first-line diagnostic and the command that the rest
of the CLI redirects to when workspace state is unclear.

Doctor output:

```text
$ aeat doctor
[profile] personal (X1234567L)
Checking workspace health...

  python version           [ok]        3.11.7
  workspace dir            [ok]        ./var
  profile record           [ok]        personal
  active profile           [ok]        personal
  tracked modelos          [ok]        130, 303, 390
  corpus: schemas          [missing]   aeat advanced reference schema refresh
  corpus: normatives       [missing]   aeat advanced reference normatives refresh
  corpus: manuals          [missing]   aeat advanced reference manuals refresh
  auth session             [missing]   aeat auth login --provider certificate
  os keystore              [ok]        windows-credential-manager
  output language          [ok]        es (AEAT_OUTPUT_LANGUAGE default)
  terminal utf-8           [ok]        supported
  filesystem permissions   [ok]        var/ is private to current user
  concurrency lock dir     [ok]        var/profiles/personal/locks/

status: 4 actionable issues.
next: `aeat advanced reference schema refresh` then `aeat auth login --provider certificate`.
```

Rules:

- Every check is actionable; a missing item includes the exact command
  that resolves it.
- Columns are ASCII-safe; width adapts to the terminal.
- Exit code reflects the severity:
  - `0` when all checks pass.
  - `3` when onboarding is incomplete (actionable but not broken).
  - `7` when workspace state is corrupt (profile file unparseable,
    permissions invalid, keystore unreachable).
- Under `--json`, doctor emits the full check list with structured
  `{ name, status, detail, suggestion }` records.

Every error message in the CLI that reflects workspace-state ambiguity
suggests `aeat doctor` as the first recovery step.

### Empty-state help on every command

Every Kent-first command handles the empty-state case by emitting a
next-action hint:

```text
$ aeat status today
[profile] personal (X1234567L)
No filings are in the tracked calendar yet.

To populate the calendar:
  aeat configure modelos calendar --ejercicio 2024

Or adjust tracked modelos:
  aeat configure modelos add 303 --profile personal
```

```text
$ aeat transactions show tx_123
[profile] personal (X1234567L)
No transaction with id 'tx_123' in profile 'personal'.

The transaction catalogue for this profile is empty.
To populate it:
  aeat data import statement ./path/to/statement.pdf
  aeat transactions build --period 2024Q1
```

```text
$ aeat audit show 303 --period 2024Q1
[profile] personal (X1234567L)
No audit bundle exists for (303, 2024Q1) yet.

The evidence bundle is assembled on demand from filing, draft, export,
and formula records. Prerequisites:
  aeat draft create 303 --period 2024Q1
  aeat review approve draft 303/2024Q1
  aeat export modelo 303 --period 2024Q1

Then:
  aeat audit show 303 --period 2024Q1
```

Empty-state output:

- Always names the profile.
- Always says what is missing.
- Always lists the canonical command sequence to fix.
- Never prints a zero-row table with no guidance.

### Progressive-disclosure banners

The workspace tracks which onboarding banners Kent has seen in
`var/onboarding.json`:

```json
{
  "version": 1,
  "workspace_created_at": "2026-04-24T12:00:00Z",
  "banners_seen": {
    "welcome": true,
    "first_profile_added": true,
    "first_doctor_run": true,
    "first_corpus_refresh": false,
    "first_auth_login": false,
    "first_status_today": false,
    "first_data_import": false,
    "first_transactions_automate": false,
    "first_draft_create": false,
    "first_review_approve": false,
    "first_export": false,
    "first_audit_show": false,
    "first_compare": false,
    "first_revise_start": false
  }
}
```

When a command fires for the first time in a workspace, it prints a
short banner introducing the concept, then flips the flag. Subsequent
runs suppress the banner.

First draft create, for example:

```text
$ aeat draft create 303 --period 2024Q1
[profile] personal (X1234567L)
Building draft for 303/2024Q1...
  [ok] transactions classified: 1203
  [ok] transactions categorized: 1203
  [ok] invoice links resolved: 47
  [warn] 3 findings require review

Draft 303/2024Q1 created. Draft ID: f2a1c8e4d5b7a309

=== first draft tour ===
A draft is a local filing object. Until you approve it, it is editable.
  inspect findings:   aeat draft show 303 --period 2024Q1
  review & approve:   aeat review queue --modelo 303 --period 2024Q1
  export after approval: aeat export modelo 303 --period 2024Q1

You can hide these tours: aeat configure defaults set tutorial_banners false
```

The tour block prints only the first time; subsequent `draft create`
invocations print only the machine result.

Disabling tutorial banners:

```text
$ aeat configure defaults set tutorial_banners false
[profile] personal (X1234567L)
Tutorial banners disabled for profile 'personal'.
To re-enable: aeat configure defaults set tutorial_banners true
```

### Non-interactive onboarding

Kent in a container or CI pipeline cannot rely on the wizard. Every
onboarding action has a non-interactive path:

- `aeat configure profile add --id ... --tax-id ... --kind ...` creates
  a profile without prompts.
- `aeat advanced reference schema refresh` fetches the corpus; works
  offline if a corpus bundle is preplaced at `var/corpus/_import.zip`.
- `aeat auth login --provider certificate --certificate-path ./cert.pfx
  --certificate-password-stdin` reads the password from stdin in a
  single line.
- `aeat configure defaults set tutorial_banners false` disables banners
  in scripted flows.

A scripted setup can reach `onboarded` state without any interactive
input:

```text
aeat configure profile add \
    --id personal \
    --tax-id X1234567L \
    --kind NIE \
    --display-name "Kent Personal" \
    --modelos "130 303 390" \
    --auth-provider certificate
aeat configure defaults set tutorial_banners false
aeat advanced reference schema refresh --ejercicio 2024
aeat advanced reference normatives refresh
aeat advanced reference manuals refresh
aeat auth login --provider certificate --certificate-path ./cert.pfx
aeat doctor
```

The script is safe to re-run: every command is idempotent or
idempotent-guarded per iteration 8.

### Kent roleplay: first full journey in 30 minutes

Minute 0 to 2: Kent installs and runs the wizard. Profile created.

Minute 3 to 5: Kent refreshes corpus (`aeat advanced reference schema
refresh`, normatives refresh, manuals refresh). Each emits a short
status report. The first refresh for each corpus prints a banner
explaining what that corpus is for.

Minute 6 to 10: Kent runs `aeat auth login --provider certificate`. A
browser window opens, Kent selects his FNMT certificate. Session
recorded. `aeat doctor` now shows everything green.

Minute 10 to 15: Kent imports a bank statement
(`aeat data import statement ./bbva-2024q1.pdf`). First banner explains
data vs transactions boundary. Transactions are built.

Minute 15 to 20: Kent runs `aeat transactions automate --period 2024Q1
--with llm`. First banner warns about prompt leakage (per iteration 12)
and requires interactive confirmation. Kent confirms. Classifications
complete.

Minute 20 to 25: Kent runs `aeat review queue --modelo 303 --period
2024Q1`. Reviews three findings. Approves the draft with
`aeat review approve draft 303/2024Q1`.

Minute 25 to 28: Kent runs `aeat export modelo 303 --period 2024Q1`.
Fichero written. First banner explains upload flow (fichero BOE is for
manual AEAT portal upload, no automatic submission).

Minute 28 to 30: Kent runs `aeat audit show 303 --period 2024Q1` out of
curiosity. Banner explains the evidence-bundle concept. Audit verdict
is `complete`.

Kent has gone from pristine workspace to approved, exported, and
audit-covered first filing in 30 minutes.

### Workspace-reset command

For testing and for Kent's explicit retry:

```text
$ aeat configure reset-workspace --confirm
[warning] This command deletes every persisted workspace record except
corpus and credentials. You will need to re-run onboarding.

Type the literal word `reset-workspace` to confirm: reset-workspace

[ok] removed var/profiles/
[ok] removed var/active_profile
[ok] removed var/onboarding.json
[ok] corpus preserved at var/corpus/
[ok] credentials preserved in OS keystore

Workspace is pristine. Run `aeat configure profile add` to start over.
```

This command is under `advanced aliases` because it is destructive and
not Kent-first.

### Hardening rules derived from iteration 13

- First-run detection classifies workspace state at startup; commands
  use the state to choose between welcome banners, wizard, empty-state
  help, or normal behaviour.
- `aeat configure profile add` is the canonical first action; it has an
  interactive wizard and a fully supported non-interactive form.
- `aeat doctor` is the central diagnostic and the default redirect
  target for ambiguous state. Doctor exit codes reflect workspace
  health.
- Every Kent-first command emits empty-state help that names the
  profile, says what is missing, and lists the canonical recovery
  sequence.
- Progressive-disclosure banners fire once per concept per workspace
  and can be disabled with `configure defaults set tutorial_banners
  false`.
- Onboarding state is persisted in `var/onboarding.json` and tracked
  per workspace (not per profile).
- Non-interactive onboarding is a first-class path with full flag
  coverage.
- `aeat configure reset-workspace` is a destructive test-and-retry
  command under advanced quarantine.

### Open risks added by iteration 13

- Interactive wizard on legacy Windows terminals with limited raw-input
  capability may misbehave. Non-interactive path must remain the
  supported automation surface.
- Tutorial banners on repeated onboarding flows (user deletes and
  recreates workspace) will re-fire. Kent may find them annoying if he
  resets frequently for testing; the `configure reset-workspace`
  command could preserve banners_seen as an option.
- Empty-state help must stay in sync with the real empty state. If a
  refactor changes the canonical command sequence, empty-state hints
  rot silently. A test harness must run every empty-state command
  against a pristine workspace and assert the suggested commands parse.
- Corpus refresh on first run downloads multiple files. Offline
  environments need a preplaced `var/corpus/_import.zip` bundle; the
  bundle format must be versioned and content-addressed.
- Doctor output grows as checks are added. A long doctor report becomes
  noisy; categorisation (environment, workspace, corpus, auth) may be
  required once the check list exceeds twenty.
- Wizard defaults for `modelos_tracked` assume Spanish autonomo
  (130/303/390). A sociedad limitada wizard needs different defaults
  (303/390/200/202); the wizard should branch on `tax_id_kind` to pick
  sensible modelo defaults.
- Non-interactive onboarding scripts risk committing tax-id values to
  shell history or CI logs. The CLI cannot prevent this but must
  document the risk in `docs/onboarding.md`.
- Progressive-disclosure banner vocabulary must be in the i18n
  catalogue from iteration 9. Missing translations leave banners in
  Spanish only; a coverage test must verify every banner key exists in
  every supported language.

## Hardening pass iteration 14 (2026-04-24)

Iteration 14 focus: test-suite strategy. The project mandates pytest-only
with strict marker discipline, no mocks in live tests, colocated unit
tests, and a coverage floor. Iterations 1 through 13 created many
contracts (registries, schemas, taxonomies, lock semantics). This
iteration maps those contracts to layered tests, fixture workspaces,
Kent-journey coverage, concurrency and interrupt safety, cross-platform
matrix, and regression-prevention discipline.

### Test layering

Seven layers, each with clear purpose and marker discipline. All axes
follow the project-mandate marker contract:
`pytestmark = [pytest.mark.<access>, pytest.mark.<domain>]` at module
level, never per function.

| Layer | Scope | Access marker | Domain marker | Colocation |
| --- | --- | --- | --- | --- |
| 1 | Registry enforcement | `unit` | `domain_infra` | alongside the registry module |
| 2 | Command-level unit | `unit` | per subpackage domain | alongside the command module |
| 3 | Kent-journey end-to-end | `unit` | `domain_local_state` or `domain_submission` | `tests/journey/` |
| 4 | Concurrency and interrupts | `unit` | `domain_infra` | `tests/concurrency/` |
| 5 | Cross-platform | `unit` | `domain_infra` | `tests/platform/{os}/` |
| 6 | Live-read | `live_read` | `domain_aeat_remote` | `tests/live/` |
| 7 | Migration parity | `unit` | `domain_local_state` | `tests/migration/` (Phase B only) |

Live-write layer does not exist: `live_write` tests are collection-
banned per project mandate, with three-factor interactive bypass only.

### Layer 1: registry enforcement

Every registry introduced by iterations 1 through 13 has a single
enforcement test that asserts the registry is well-formed and that
every call site registered in the registry is consistent with live
code.

Registries and their tests:

- `src/aeat/core/errors/_registry.py` (iteration 6): `test_error_registry.py`
  asserts every `AeatError` subclass carries a registered `code`, every
  code has `default_message_es` and `default_message_en`, and every
  `default_suggestion` parses against the current CLI.
- `src/aeat/entrypoints/cli/_mutability.py` (iteration 8): `test_mutability.py`
  asserts every Click leaf declares a class and an idempotency rule.
- `src/aeat/entrypoints/cli/_schemas.py` (iteration 7): `test_output_schemas.py`
  asserts every Kent-first command has a registered schema and that
  each schema is a valid JSON Schema document.
- `src/aeat/core/i18n/_catalog.py` (iteration 9): `test_i18n_catalog.py`
  asserts every catalogue entry has non-empty `es` and `en`, no
  catalogue key is unused by any call site, and no call site references
  a key absent from the catalogue.
- `src/aeat/revise/_registry.py` (iteration 2):
  `test_revise_support_registry.py` asserts every
  `(modelo, ejercicio, kind)` triple has a truthy `supported` or
  `notes_*` explanation.
- `src/aeat/audit/_manifest_schema.py` (iteration 3):
  `test_manifest_schema.py` asserts bundle manifest JSON round-trips
  and content_kind is closed-set.
- `src/aeat/configure/_profile_schema.py` (iteration 11):
  `test_profile_schema.py` asserts tax-id-kind to modelo compatibility
  is truthful.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_credential_schema.py` (iteration 12):
  `test_credential_schema.py` asserts no credential kind persists Cl@ve
  material and every persisted kind has an encryption-at-rest rule.
- `src/aeat/onboarding/_banners.py` (iteration 13):
  `test_onboarding_banners.py` asserts every registered banner has
  matching catalogue keys for every supported language.

A meta-test `test_registries_all_covered.py` enumerates every module
named `_registry.py`, `_schema.py`, `_catalog.py`, or `_manifest_*.py`
under `src/aeat/` and asserts a matching test file exists.

### Layer 2: command-level unit tests

Every Kent-first command has at minimum four unit tests, colocated with
the command module:

- `test_<cmd>_help_ascii_safe.py`: render `--help` under Click's test
  runner; assert ASCII-only, no Unicode, no wiki-links, stable output
  matching a committed fixture.
- `test_<cmd>_json_schema_conformance.py`: run against a fixture
  workspace; capture stdout; validate against registered schema.
- `test_<cmd>_empty_state.py`: run against a pristine or empty
  fixture; assert empty-state help fires and names a recovery command
  that itself parses.
- `test_<cmd>_error_taxonomy.py`: force each failure path; assert
  correct category, prefix, exit code, and suggestion from
  iteration 6's registry.

Additional per-command tests as needed for the mutability class (for
example, `idempotent_guarded` commands get a double-invocation test
that asserts the second run is a no-op).

### Layer 3: Kent-journey end-to-end

`tests/journey/` contains end-to-end scenarios that walk Kent's full
path for each milestone of the roadmap. Each scenario invokes the CLI
against a fixture workspace and asserts the visible end state.

Core journeys:

- `test_journey_first_export.py`: pristine workspace, profile setup,
  data import, transactions automate, draft create, review approve,
  export modelo. Asserts fichero byte-identical to a committed
  fixture.
- `test_journey_audit_bundle.py`: onboarded workspace with an approved
  draft; run `audit export` and assert bundle matches fixture
  (bundle_id stable).
- `test_journey_revise_complementaria.py`: baseline justificante
  imported; revise start; edit; export complementaria; amendment
  record persisted.
- `test_journey_revise_rectificativa.py`: modelo 303 post-2023;
  revise start with `--kind rectificativa`; assert registry permits;
  fichero generated.
- `test_journey_backlog_recovery.py`: multi-year backlog fixture;
  `status backlog show/import/scaffold/resume` walk.
- `test_journey_multi_profile.py`: two profiles; active-profile
  switch; `--profile` override; records isolation.
- `test_journey_compare_discrepancy.py`: local draft vs imported
  receipt; compare show, explain, fix, verify cycle.

Each journey test is named after the Kent question it answers. Adding a
new Kent capability requires adding a journey test.

### Layer 4: concurrency and interrupt safety

`tests/concurrency/` exercises real subprocesses and real signals. No
mocks.

- `test_concurrent_same_case_refuses.py`: spawn subprocess A running
  `transactions automate`; in the main process run
  `transactions classify` against the same case; assert exit `8` with
  holder PID in the error message.
- `test_wait_flag_queues.py`: spawn subprocess A; run command B with
  `--wait 3`; assert B succeeds after A completes.
- `test_stale_lock_reclamation.py`: write a lock file pointing to a
  dead PID; invoke a mutating command; assert the lock is reclaimed
  with a stderr notice.
- `test_sigint_atomic_export.py`: start `export modelo` against a
  large draft; signal SIGINT after 50 ms; assert no partial `.boe`
  file remains (only `.tmp-{pid}` if anything).
- `test_sigint_resumable_automate.py`: start
  `transactions automate` with 1000 fixture transactions; SIGINT
  after 200 classified; assert checkpoint file exists; run
  `transactions resume`; assert total becomes 1000.
- `test_sigkill_leaves_no_corrupt_records.py`: spawn subprocess
  running `draft create`; SIGKILL; assert no partial JSON files.

Cross-platform: these tests run on Ubuntu and Windows. Windows uses
`SIGTERM` equivalent where `SIGINT` behaviour differs.

### Layer 5: cross-platform

`tests/platform/` branches per operating system. Conditional skips via
`@pytest.mark.skipif(sys.platform != "win32", ...)` at module level.

Windows-specific tests:

- `tests/platform/windows/test_file_locks.py`: Windows file-lock
  semantics; stale-lock reclamation under Windows handle semantics.
- `tests/platform/windows/test_keystore_credential_manager.py`: OS
  keystore integration via Windows Credential Manager.
- `tests/platform/windows/test_terminal_encoding.py`: cp1252 fallback;
  Windows Terminal UTF-8 detection.

POSIX-specific tests:

- `tests/platform/posix/test_file_perm_600.py`: mode 600 files;
  startup refuses broader permissions.
- `tests/platform/posix/test_keystore_secret_service.py`: GNOME
  Keyring integration; passphrase fallback.

macOS-specific tests:

- `tests/platform/macos/test_keystore_keychain.py`: Keychain Access
  integration.

CI matrix runs every platform on every push; regressions caught before
merge.

### Layer 6: live-read

`tests/live/` requires `AEAT_LIVE_TESTS_ENABLED=1` and a Kent-provided
test-only NIE. Strict discipline:

- No mocks. No fakes. No stubs. No recorded cassettes.
- Tests hit the real AEAT portal in read-only mode.
- Tests never mutate AEAT state.
- Tests fail loudly when the portal behaviour drifts; drift is signal,
  not noise.

Core live-read tests:

- `test_live_auth_status.py`: login with a certificate; verify
  session; logout.
- `test_live_inbox_fetch.py`: fetch notifications for a test
  profile; assert structure matches known shape.
- `test_live_filing_history_fetch.py`: fetch historical filings;
  assert pagination works.
- `test_live_status_expedientes.py`: fetch expedientes; assert the
  typed record shape.

Live-read tests are gated in CI: a dedicated live-CI job with secrets
configured runs them on a schedule (not on every PR). Regular PR CI
skips them per marker.

### Layer 7: migration parity (Phase B only)

`tests/migration/` exists only during Phase B from iteration 10. Each
test invokes the old command and the new command against the same
fixture and asserts identical results.

- `test_parity_financial_txs_vs_transactions.py`
- `test_parity_filing_build_vs_draft_create.py`
- `test_parity_submission_export_vs_export_modelo.py`
- `test_parity_inbox_list_vs_records_notifications.py`
- `test_parity_formulas_audit_vs_audit_show.py`

Parity tests retire at Phase D cutover when the old commands sunset.

### Fixture workspaces

`tests/fixtures/workspaces/` contains committed workspace snapshots as
content-addressed directory trees. Each snapshot has a `_fixture.json`
manifest listing every file with its SHA-256.

Canonical fixtures:

- `pristine/`: empty workspace.
- `onboarded/`: one profile, corpus refreshed, no drafts.
- `mid-journey/`: one profile, transactions imported, draft created
  (unapproved).
- `complete/`: one profile, draft approved and exported.
- `multi-profile/`: two profiles with disjoint states.
- `multi-amendment/`: one profile with a complementaria chain of
  length three.
- `backlog/`: multi-year backlog with missing, filed, and
  locally-known periods.
- `schema-drift/`: draft pinned to 2022 schema; current corpus has
  2024 schema.

A fixture-integrity test hashes every file in every fixture and
compares against `_fixture.json` at test startup. Corruption fails the
whole suite.

### Regression-prevention per Kent wall

Project mandate: "Every PR closing a Kent wall MUST ship a
regression-prevention test."

Convention:

- PR title tags the wall with `kent-wall:<slug>`.
- Test file is `tests/regression/test_kent_wall_<slug>.py`.
- Test replays the wall scenario against a pinned fixture and asserts
  the wall is no longer present.

A static-analysis pass in CI enumerates every `kent-wall:*` reference
in PR titles (or referenced issues) over the last milestone and asserts
a matching test file exists and is maintained.

### Help-text fixture regression

Every Kent-first command has a committed `--help` fixture at
`tests/fixtures/help/<command_dotpath>.txt`.

Help-text regression rules:

- Any help-text change updates the fixture in the same PR.
- Tests assert byte-identical match.
- Tests assert ASCII-only output.
- Tests assert no `[[wiki-links]]` or markdown URLs.
- Tests assert the help output does not leak internal vocabulary
  (iteration 1 retirement table).

### Coverage floor

`just test-cov` asserts coverage on `src/aeat/`:

| Subpackage | Floor |
| --- | --- |
| `auth` | 80 percent |
| `submission`, `audit`, `revise` | 75 percent |
| everything else | 60 percent |

Floors may rise per milestone; they never drop. A CI check refuses PRs
that lower any floor.

Coverage reports break down by file; files under 60 percent are listed
as maintenance backlog items, not hard fails.

### Test-suite performance budget

Full unit layer targets:

- Local developer workstation: under 60 seconds.
- Ubuntu CI: under 5 minutes.
- Windows CI: under 10 minutes.

Tests exceeding 2 seconds individually are flagged as slow and must
either be optimised or moved to `tests/slow/` with
`pytestmark = [pytest.mark.slow]`. Slow tests run on a separate CI
job and are excluded from the default run.

### Structural audit harness

Per project mandate: monthly coverage, duplication, code-health, and
Kent-regression audits plus quarterly charter-compliance and
architectural audits.

Iteration 14 adds:

- `tests/audit/test_no_absolute_aeat_imports.py`: AST-scan `src/aeat/`
  and assert no `import aeat.*` absolute imports.
- `tests/audit/test_no_bare_dicts_at_boundaries.py`: AST-scan function
  signatures crossing subpackage boundaries; assert no bare `dict`
  arguments or returns (Pydantic v2 mandate).
- `tests/audit/test_no_default_live_write.py`: scan
  `SubmissionEngine(...)` constructor sites in `src/aeat/`; assert
  `live_transport_supported=True` appears only in test files.
- `tests/audit/test_vocabulary_leakage.py`: scan CLI help output and
  error messages for banned internal terms per iteration 1 retirement
  table.
- `tests/audit/test_pytest_markers.py`: scan every test module;
  assert exactly one `pytestmark` at module level with correct axes.
- `tests/audit/test_live_tests_have_no_mocks.py`: scan `tests/live/`;
  assert no imports of `unittest.mock`, `pytest_mock`, or any mocking
  library.

These tests run in every PR's CI.

### Hardening rules derived from iteration 14

- Test-layer structure is fixed: registry enforcement, command unit,
  Kent journey, concurrency and interrupts, cross-platform,
  live-read, migration parity.
- Every registry introduced by any hardening iteration has an
  enforcement test. The meta-test enforces the mapping.
- Every Kent-first command has help, JSON schema, empty-state, and
  error-taxonomy tests at minimum.
- Every Kent journey in the roadmap has an end-to-end test.
- Concurrency and interrupt tests use real subprocesses and real
  signals.
- Fixture workspaces are content-addressed and hash-verified at
  suite startup.
- Help-text fixtures are committed and byte-compared.
- Coverage floors per-subpackage; security-critical subpackages have
  higher floors.
- Test-suite wall-clock budget is enforced; slow tests move to a
  separate job.
- Structural-audit tests guard charter-compliance mandates.
- No mocks in live tests; no `unittest.mock` imports anywhere under
  `tests/live/`; a test asserts this.
- `live_write` tests remain collection-banned.

### Open risks added by iteration 14

- Fixture workspace maintenance grows with test count. A weekly
  fixture-drift audit may be needed to keep fixtures coherent.
- Migration parity tests (Phase B) double the test wall clock; they
  retire at Phase D but until then add cost.
- Live-read tests depend on the AEAT portal being reachable and a
  valid test certificate. A portal outage fails live CI even though
  nothing in `src/aeat/` is broken. A transient-failure policy is
  required.
- Cross-platform CI burns developer cycles. Parallelism and caching
  must compensate.
- Mutation testing (catching tests that pass on broken code) is not
  in scope for v1; coverage alone cannot guarantee test quality.
- AST-scan audits are brittle across Python version changes; the
  tests must be upgraded alongside Python.
- `test_vocabulary_leakage.py` depends on iteration 1's retirement
  table staying current; a migration that adds a new leaked term
  silently passes unless the table is updated first.
- Help-text fixture churn during migration phases makes PR diffs
  noisier; reviewers must learn to scan fixture diffs as readable
  intent, not noise.
- LLM prompt-scrubbing tests require realistic NIE/NIF/CIF fixtures
  that are not real identities; generating valid-format but fake
  identifiers requires a dedicated helper.

## Hardening pass iteration 15 (2026-04-24)

Iteration 15 focus: telemetry and observability contract. Kent's
workspace handles personal tax data. The observability surface must be
rich enough to diagnose a slow LLM run or a stale auth session, yet
strict enough that nothing sensitive leaves the machine without explicit
consent. This iteration specifies local-first observability primitives,
opt-in remote telemetry tiers, dual-pass scrubbing, retention policy,
and Kent-facing diagnostic commands.

### Principles

- **Local-first**: every observability signal stays on Kent's machine
  by default.
- **No default network**: the CLI does not phone home under any
  default configuration.
- **Explicit remote opt-in**: remote telemetry requires both an
  environment variable and a persisted workspace setting.
- **Zero PII on remote**: even under opt-in, no NIE, NIF, CIF,
  amounts, counterparty names, draft IDs, or file paths that carry
  identifiers leave the machine.
- **Audit before send**: Kent can inspect every outbound record
  verbatim before it is flushed.
- **Consent revocable**: turning telemetry off purges the outbox and
  stops future emission.

### Local observability primitives

Five sinks live under each profile. All are append-only JSONL files
with date-stamped filenames so rotation is a no-op:

```text
var/profiles/{profile_id}/
|-- logs/
|   `-- {yyyy-mm-dd}.jsonl         # structured log events
|-- metrics/
|   `-- {yyyy-mm-dd}.jsonl         # per-command metrics
|-- workflow/
|   `-- {run_id}.json              # RunTrace records (iterations 1, 8)
|-- auth/events/
|   `-- {yyyy-mm-dd}.jsonl         # auth event log (iteration 12)
`-- audit/llm-prompts/
    `-- {run_id}.jsonl             # LLM prompt audit (iteration 12)
```

Every sink is local-only by default; none are flushed to a network
endpoint unless opt-in is explicit (see remote telemetry below).

### Structured log sink

Every CLI invocation appends to
`var/profiles/{profile_id}/logs/{yyyy-mm-dd}.jsonl`.

Event shape:

```json
{
  "ts": "2026-04-24T14:03:22.105Z",
  "level": "info|warning|error|debug",
  "invocation_id": "018f5b21-...-0001",
  "profile_id": "personal",
  "command": "status.today",
  "event_kind": "start|progress|complete|error|audit",
  "duration_ms": 43,
  "exit_code": 0,
  "error_code": null,
  "message": "<scrubbed one-line summary>",
  "context": { "...": "scrubbed structured fields" }
}
```

Rules:

- `invocation_id` is UUIDv7 or UUIDv4 generated at CLI startup; stable
  for the whole process.
- `level` is one of the four standard levels.
- `message` and `context` pass through the iteration 7 and 12 scrubber
  pipeline before emission.
- `event_kind=audit` is reserved for audit events that must never be
  scrubbed beyond the standard scrub list (for example approval
  events).
- On `event_kind=complete`, `duration_ms` and `exit_code` are mandatory.
- On `event_kind=error`, `error_code` is mandatory and matches the
  iteration 6 registry.

### Metrics sink

Every mutating or long-running command appends a single metrics record
on completion to
`var/profiles/{profile_id}/metrics/{yyyy-mm-dd}.jsonl`:

```json
{
  "ts": "2026-04-24T14:03:22Z",
  "invocation_id": "018f5b21-...-0001",
  "profile_id": "personal",
  "command": "transactions.automate",
  "duration_ms": 43210,
  "exit_code": 0,
  "metric_kind": "command_complete|command_failed|command_aborted",
  "counters": {
    "transactions_processed": 1203,
    "classifications_applied": 1198,
    "warnings": 3
  },
  "timings_ms": {
    "llm_request": 41000,
    "persistence": 2100,
    "output": 110
  }
}
```

Counters and timings keys are registered per command in
`src/aeat/core/observability/_metrics_registry.py`. Emitting an unregistered
key fails a startup-check test in development builds and is silently
dropped in release builds (never silently added to the schema).

### Retention policy

Defaults:

| Sink | Default retention |
| --- | --- |
| `logs/` | 90 days |
| `metrics/` | 180 days |
| `workflow/` (RunTrace) | 365 days |
| `auth/events/` | 365 days |
| `audit/llm-prompts/` | 365 days |

Retention is enforced by a daily prune at CLI startup that deletes
files older than the retention window. Kent can override any window:

```text
aeat configure defaults set log_retention_days 180
aeat configure defaults set metrics_retention_days 365
aeat configure defaults set runtrace_retention_days 1095
```

A retention-0 setting disables the sink entirely. A test asserts
retention enforcement does not touch any file that would still be
within its window.

### Local aggregation commands

Local-only diagnostic commands aggregate the JSONL sinks without any
network access. All live under `advanced diagnostics`:

| Command | Output |
| --- | --- |
| `advanced diagnostics telemetry show --days N` | Commands per day, failure rates, latency summary. |
| `advanced diagnostics errors list --days N` | Every logged error grouped by code with counts. |
| `advanced diagnostics latency [--command <dot>] [--days N]` | P50, P95, P99 per command, median breakdown by timing segment. |
| `advanced diagnostics llm-usage --days N` | LLM token usage, cache hit rate, per-provider cost estimate. |
| `advanced diagnostics runs list [--modelo <m>] [--period <p>]` | RunTrace summary. |

Every diagnostic emits human or JSON per iteration 7. Nothing leaves
the machine.

### Kent roleplay: slow LLM run

Kent suspects `transactions automate --with llm` is too slow.

```text
$ aeat advanced diagnostics latency --command transactions.automate --days 7
[profile] personal (X1234567L)

transactions.automate (7 runs over 7 days)
  P50:    32s     P95:    51s     P99:    67s
  median breakdown:
    llm_request       28 000 ms   (88%)
    persistence        2 500 ms   (8%)
    output               300 ms   (1%)
    other                700 ms   (3%)

next step: inspect LLM cache hit rate with `aeat advanced diagnostics llm-usage --days 7`.
```

Kent immediately knows the LLM provider is the bottleneck, not the CLI.

### Kent roleplay: error pattern

Kent wonders why his workflow breaks occasionally.

```text
$ aeat advanced diagnostics errors list --days 30
[profile] personal (X1234567L)

counts by error code (30 days):
  E_AUTH_EXPIRED           12   retryable
  E_CASE_LOCKED             4   non-retryable
  E_NO_BASELINE             2   user error
  E_TTY_REQUIRED            1   automation context

suggest: rotate certificate early if E_AUTH_EXPIRED is frequent.
  see `aeat auth status` for expiry.
```

### Opt-in remote telemetry

When Kent explicitly enables remote telemetry:

```text
aeat configure defaults set telemetry_opt_in true
aeat configure defaults set telemetry_endpoint https://telemetry.example.com
aeat configure defaults set telemetry_tier off|crash_only|full
```

The environment variable `AEAT_TELEMETRY_ENDPOINT` overrides the
persisted endpoint for the current process; the opt-in flag must still
be `true` in the workspace config.

Three tiers:

| Tier | Sent |
| --- | --- |
| `off` (default) | Nothing. No outbox write. |
| `crash_only` | `command_failed` and `command_aborted` events only. |
| `full` | All command-complete events. Counters and timings. |

With `off`, remote telemetry is fully disabled regardless of endpoint
setting or env var.

### Outbox and flush

On emission, remote-eligible records are written to a local outbox
first:

```text
var/telemetry-outbox/{yyyy-mm-dd}.jsonl
```

A flush command is explicit:

```text
aeat advanced diagnostics telemetry flush [--dry-run] [--days N]
```

The default flush cadence is Kent-driven: he runs the command when he
wants to. An optional background cadence requires
`configure defaults set telemetry_flush_cadence daily|weekly`; Kent
activates it consciously.

### Dual-pass scrubbing for remote payloads

Local logs already pass through the iteration 7 and 12 scrub pipeline.
Remote outbox records pass through a second scrubber with a stricter
rule set:

- `profile_id` replaced with `workspace_hash` = SHA-256 of
  (workspace root path plus a random per-workspace salt generated at
  opt-in time).
- `profile_tax_id` removed entirely (never allow-listed on remote).
- `modelo`, `period`, `command`, `exit_code`, `error_code`,
  `duration_ms`, `invocation_id` retained (non-identifying).
- `counters` retained with registered keys only; any unregistered
  counter is dropped.
- `timings_ms` retained.
- `message` removed entirely (may contain unscrubbed content under
  edge cases).
- `context` removed entirely on remote; local context stays local.

The second-pass scrubber is a pure function with a tested spec. A
property test asserts that for any input record, the output contains
zero NIE/NIF/CIF regex matches, zero amounts, zero file paths, zero
counterparty names.

### Dry-run inspection

Kent can inspect exactly what would be sent before flushing:

```text
$ aeat advanced diagnostics telemetry flush --dry-run --days 1
[profile] personal (X1234567L)

Would flush 42 records to https://telemetry.example.com
First record (scrubbed, remote-pass):
{
  "ts": "2026-04-24T14:03:22Z",
  "invocation_id": "018f5b21-...-0001",
  "workspace_hash": "3f1a...",
  "command": "transactions.automate",
  "duration_ms": 43210,
  "exit_code": 0,
  "metric_kind": "command_complete",
  "counters": { "transactions_processed": 1203, "classifications_applied": 1198, "warnings": 3 },
  "timings_ms": { "llm_request": 41000, "persistence": 2100, "output": 110 }
}

Use `--days N --show-all` to print every record. No data leaves the
machine under `--dry-run`.
```

### Outbox inspection and purge

```text
aeat advanced diagnostics telemetry outbox --show --days N
aeat advanced diagnostics telemetry purge-outbox
```

Purging clears the outbox without flushing. Useful when Kent revokes
consent mid-batch.

### Consent revocation

```text
aeat configure defaults set telemetry_opt_in false
aeat advanced diagnostics telemetry purge-outbox
```

On opt-out:

- The outbox is purged.
- Future records are not written to the outbox.
- Endpoint and tier settings are retained (not wiped) so re-enabling
  is symmetric; wiping requires
  `configure defaults unset telemetry_endpoint`.
- Past flushed records are the endpoint's responsibility; the CLI can
  issue a deletion request via
  `aeat advanced diagnostics telemetry request-deletion` if the
  endpoint exposes a documented API.

### Metrics schema registry

Per-command metric keys live in
`src/aeat/core/observability/_metrics_registry.py`:

```python
class MetricSchema(BaseModel):
    command: str                         # dot-path
    counters: dict[str, CounterSpec]     # closed set
    timings_ms: dict[str, TimingSpec]    # closed set

class CounterSpec(BaseModel):
    description: Translatable
    unit: Literal["count", "bytes", "ratio"]
    remote_allowed: bool                 # if False, stripped on remote
```

A test asserts every command that writes metrics writes only registered
keys. Adding a key requires an ADR amendment (lightweight; sub-ADR
acceptable).

### Kent roleplay: remote opt-in walk

Kent decides to contribute anonymised telemetry to help the project
improve. He runs:

```text
$ aeat configure defaults set telemetry_opt_in true
[profile] personal (X1234567L)
Remote telemetry is now allowed. Current settings:
  telemetry_tier:     off (no records will flush until you set a tier)
  telemetry_endpoint: (not set; requires configure defaults set telemetry_endpoint <url>)

Next:
  aeat configure defaults set telemetry_tier crash_only
  aeat configure defaults set telemetry_endpoint https://telemetry.aeat-cli.org
  aeat advanced diagnostics telemetry flush --dry-run
```

Each step is deliberate. Kent never emits remote telemetry until he
has set tier, endpoint, and verified the dry-run.

### Hardening rules derived from iteration 15

- Local observability sinks are always on. Remote telemetry is off by
  default and requires explicit opt-in plus tier plus endpoint.
- Dual-pass scrubbing: local scrubber plus a stricter remote scrubber
  that removes `profile_tax_id`, `message`, and `context` entirely
  and replaces `profile_id` with `workspace_hash`.
- Property tests assert remote payloads contain zero NIE/NIF/CIF,
  amounts, paths, or counterparty names across a wide fuzz input.
- Kent can dry-run flush, inspect the outbox, and purge at any time.
- Metrics schema is registered; unregistered keys are silently dropped
  in release builds and failure-raising in development builds.
- Retention policy is explicit per sink and enforced by a daily prune.
- Consent revocation is fully reversible without data loss for the
  local sinks.
- Tier `off` wins over endpoint and env var settings; no telemetry
  fires under `off`.
- Every diagnostic command runs against local JSONL files; no
  diagnostic command issues a network request.

### Open risks added by iteration 15

- Scrubber gaps: adding a new field to a metric record without
  updating the scrub allow-list allows it onto the remote payload.
  Discipline: scrub rules allow-list fields, not deny-list. Property
  tests enforce the rule.
- Workspace hash re-identification: the same workspace always produces
  the same hash, which enables long-term tracking at the endpoint.
  Mitigation: the salt is rotatable via
  `configure defaults set telemetry_workspace_salt_new <value>`.
- Counter drift: release builds silently drop unregistered counters.
  This prevents remote schema corruption but hides bugs in emitters.
  A dev-mode assertion catches them early.
- Endpoint compromise leaks `workspace_hash` fingerprints. The
  outbox contains no PII by construction, so compromise impact is
  limited, but Kent should still treat endpoint choice as a trust
  decision.
- LLM token counts require per-provider pricing tables; the table
  drifts and Kent's cost estimate may be off. The diagnostic should
  date-stamp the pricing table used so Kent can recalibrate.
- Retention pruning runs at startup and is a disk I/O cost on cold
  starts with large logs. A background prune during idle moments
  would be preferable but adds daemon-like complexity.
- Outbox flush is explicit; Kent may accumulate weeks of records and
  then discover the endpoint rejects a huge batch. A soft cap on
  outbox size should refuse new emissions past a threshold and point
  Kent at the flush or purge command.
- Deletion-request API is endpoint-dependent; not every endpoint
  exposes one. Documentation must be clear that flushed records may
  not be easily recallable.

## Hardening pass iteration 16 (2026-04-24)

Iteration 16 focus: performance and scale envelope. Kent is not a toy
user. An autonomo who files 130, 303, and 390 for ten years, maintains
2995 transactions per year, and accumulates a decade of amendments
generates tens of thousands of records. Plus a sociedad limitada
profile. The CLI must stay responsive from pristine to tenth-year
state. This iteration specifies per-command budgets, scale targets,
indexing strategy, streaming discipline, memory ceilings, LLM
throughput expectations, and the benchmarking harness.

### Scale targets

The CLI must stay fully functional at these envelope sizes:

| Scale dimension | Target |
| --- | --- |
| Transactions per profile | up to 50 000 |
| Filings per profile | up to 100 (20+ years of quarterly modelos) |
| Evidence files per profile (statements, invoices, receipts) | up to 10 000 |
| Amendments per filing chain | up to 10 (deep rectificativa chains) |
| Profiles per workspace | up to 5 |
| Corpus size | up to 200 MB (schemas, normatives, manuals, rulesets) |
| Workspace total disk usage | up to 10 GB |
| Cold-start to first output | under 5 seconds |

Scale tests cover 10-year / 30 000-transaction / 5-profile fixtures.

### Per-command wall-clock budgets

Targets on a reference mid-range laptop (2021 Intel i5 or Apple M1,
16 GB RAM, NVMe SSD). Budgets are P95; P99 may exceed by up to 50
percent before flagging.

| Command family | Budget | Notes |
| --- | --- | --- |
| `aeat --version`, `aeat --help` | < 100 ms | minimal import path |
| `aeat doctor` | < 2 s | first-time and periodic |
| `aeat status today` | < 200 ms | opens every morning |
| `aeat status show <m> --period <p>` | < 300 ms | on-demand lookup |
| `aeat status backlog show --from <Y1> --to <Y2>` | < 3 s | 10-year range on 30 000 tx |
| `aeat status resume` | < 300 ms | |
| `aeat data readiness <m> --period <p>` | < 500 ms | |
| `aeat data import statement <path>` | < 30 s per 10 MB | PDF parse dominates |
| `aeat data import invoice/receipt <path>` | < 3 s per file | |
| `aeat transactions build --period <p>` | < 5 s for 5 000 transactions | deterministic |
| `aeat transactions automate --with llm` | LLM-bound; CLI overhead < 2 s per 1 000 tx | see LLM section |
| `aeat transactions classify/categorize/edit <id>` | < 200 ms | single row |
| `aeat transactions inspect --group-by merchant` | < 1 s on 30 000 tx | indexed |
| `aeat transactions show <id>` | < 200 ms | |
| `aeat draft create <m> --period <p>` | < 5 s | formula engine + validation |
| `aeat draft show <m> --period <p>` | < 500 ms | |
| `aeat draft validate <m> --period <p>` | < 3 s | |
| `aeat draft list` | < 300 ms even for 100 drafts | indexed |
| `aeat review queue [--kind <k>]` | < 500 ms | multi-row listing |
| `aeat review approve <id>` | < 1 s | approval basis + journal |
| `aeat compare show <m> --period <p> --against <b>` | < 2 s | case diff |
| `aeat compare explain` | < 3 s | per-casilla explanation |
| `aeat export modelo <m> --period <p>` | < 3 s | deterministic emission |
| `aeat export preflight <m> --period <p>` | < 2 s | |
| `aeat export verify <path>` | < 2 s | parse + structure |
| `aeat export diff <a> <b>` | < 2 s | |
| `aeat audit show <m> --period <p>` | < 1 s | metadata only |
| `aeat audit verify <m> --period <p>` | < 5 s | checksums + formula replay |
| `aeat audit export <m> --period <p>` | < 10 s | bundle assembly |
| `aeat audit replay <m> --period <p>` | < 10 s | full re-execution |
| `aeat records filings list [--all-profiles]` | < 500 ms for 100 filings | indexed |
| `aeat advanced diagnostics latency --days 30` | < 500 ms | aggregates JSONL |

Budget violations in the scale-test suite fail the release branch.

### Memory ceilings

Per-process resident memory limits enforced at runtime:

| Command class | Soft ceiling | Hard ceiling |
| --- | --- | --- |
| Read-only | 256 MB | 512 MB |
| Mutating default | 512 MB | 1 GB |
| LLM automation | 1 GB | 2 GB |
| Bulk operations (backlog scan, audit export across many filings) | 512 MB | 1 GB |

The hard ceiling is enforced through a Python-level memory watchdog.
Exceeding fails with `E_MEMORY_EXHAUSTED`, category
`system_failure`, exit `10`, and suggestion to split the operation:

```text
FAIL: Memory ceiling exceeded (process used 1.12 GB, hard limit 1.00 GB).
  -> Split the operation into smaller batches.
  -> For `transactions automate`, pass `--batch-size 200` (default 500).
  -> For `status backlog show`, narrow the date range with `--from` and `--to`.
```

### Indexing strategy

For scale, read-heavy commands maintain derived SQLite indexes:

```text
var/profiles/{profile_id}/
|-- transactions/
|   |-- records/                      # JSONL source of truth
|   |   `-- {yyyy-mm}.jsonl
|   `-- index.sqlite                  # derived index
|-- drafts/
|   |-- records/
|   `-- index.sqlite
|-- submissions/
|   |-- records/
|   `-- index.sqlite
```

Index schemas:

- `transactions.index`: `(transaction_id, profile_id, period, classification_state, merchant, amount_cents, imported_at, last_classified_at)`.
- `drafts.index`: `(draft_id, profile_id, modelo, period, status, created_at, approved_at)`.
- `submissions.index`: `(submission_id, profile_id, modelo, period, status, submitted_at)`.

Indexing rules:

- JSONL records remain the source of truth. SQLite is derived.
- Index schema version is stamped in a `_meta` table.
- `aeat advanced diagnostics reindex [--subset transactions|drafts|submissions]`
  rebuilds from JSONL.
- Any JSONL record change triggers an incremental index update within
  the same workspace lock.
- Schema-version mismatch on startup triggers automatic reindex.
- A check at startup asserts row count in index matches record count
  in JSONL; divergence reindexes.

SQLite dependency is a core Python stdlib module. No external
SQLite binary required.

### Streaming discipline

Commands that may process large data sets iterate in batches rather
than materialising everything in memory:

- `transactions build` reads derived transactions in batches of 500.
- `transactions automate` classifies in batches of 500 (LLM token
  budget) and checkpoints after each batch (iteration 8).
- `data import statement` parses PDF pages one at a time.
- `status backlog show --from <Y1> --to <Y2>` streams filings per year.
- `audit export` writes the bundle file-by-file with chunked ZIP
  writes; never materialises the whole bundle in memory.
- `records filings list --all-profiles` streams per profile.
- JSON output for streaming commands uses newline-delimited JSON on
  stdout when the result set exceeds a threshold (100 rows by
  default); downstream `jq -c` can consume.

A memory-profile integration test runs each streaming command against
the 10-year scale fixture and asserts peak RSS stays within the
command class ceiling.

### Cold-start optimisation

Python CLI cold start is a common Windows pain. Mitigations:

- `aeat` entry point imports only `aeat.__init__`, Click, and the
  top-level group. Subcommand modules import lazily on dispatch.
- `aeat --version` takes a fast path that bypasses Click command
  registration entirely.
- `aeat doctor` imports on demand; the doctor check list is declared
  as lightweight metadata and modules load only when the check runs.
- Heavy imports (Pydantic v2 models, i18n catalogue, LLM client) are
  deferred past the `--help` path.
- A cold-start test asserts `aeat --version` completes under 500 ms
  on Windows CI and under 200 ms on POSIX CI.

### LLM throughput

LLM automation is the dominant wall-clock consumer. Targets:

- Batch size: 500 transactions per LLM call, bounded by a ~30 000
  prompt-token ceiling.
- Wall-clock: approximately 30 s per 1 000 transactions at provider-
  typical latency (network plus model). This is provider-bound; the
  CLI overhead is under 2 s per 1 000 tx.
- Concurrency: up to 3 parallel LLM calls by default
  (`AEAT_LLM_CONCURRENCY` env overrides; provider rate-limit-aware).
- Cache hit rate: 40 percent or higher after one month of regular use
  because Kent's merchants recur. Cache keys per (merchant normalised,
  amount rounded, period context).
- Cost tracking: per-provider pricing table stamped with its
  retrieval date feeds the `advanced diagnostics llm-usage` command
  (iteration 15).

A rate-limit handler handles HTTP 429 by exponential backoff up to
three retries, then queues the batch for later. Retries reuse the
cache where possible.

### Scale-test fixture

`tests/fixtures/workspaces/scale-10-years/` contains a synthetic
workspace generated by a script:

- 1 profile (personal autonomo).
- 10 years of quarterly filings for 130, 303, 390.
- 30 000 derived transactions with realistic merchant diversity.
- 3 000 invoices.
- 500 receipts.
- Full amendment chains on 10 filings (deep rectificativa for 303).

A separate fixture `scale-5-profile-5-year/` covers multi-profile
scale.

Scale tests under `tests/scale/` marked `@pytest.mark.slow` run on a
dedicated weekly CI job:

- `test_scale_status_backlog.py`
- `test_scale_transactions_automate.py`
- `test_scale_audit_export_batch.py`
- `test_scale_compare_cycle.py`
- `test_scale_multi_profile.py`

Each test asserts the relevant wall-clock budget and the memory
ceiling.

### Performance regression detection

Nightly CI benchmarks a canonical scale fixture against every command
with a budget:

- Regression criterion: P50 wall-clock exceeds the previous release by
  20 percent.
- Regressions fail the nightly job and open a triage issue
  automatically (per iteration 4's issue templates).
- Regression budgets tighten per release as the codebase matures.

Benchmarks run on a dedicated CI runner with stable hardware and no
noisy neighbours. Measurement variance is minimised with 5 warm-up
runs plus 10 measured runs; median is reported.

### Kent roleplay: full ten-year journey

Kent onboards a 10-year-old autonomo. He runs:

```text
$ aeat data import statement ./historic-statements/*.pdf
[profile] personal (X1234567L)
Importing 40 statements over 10 years...
  [progress] 40 / 40    elapsed 8m 12s

$ aeat transactions build --period all
[profile] personal (X1234567L)
Building transaction catalogue...
  [progress] 30 103 / 30 103    elapsed 42s

$ aeat transactions automate --with llm --period all
[profile] personal (X1234567L)
Classifying 30 103 transactions in 61 batches of 500...
  [progress] 30 103 / 30 103    elapsed 12m 47s
  cache hits: 38%  (slower early batches; cache warms up)

$ aeat status backlog show --from 2015Q1 --to 2024Q4
[profile] personal (X1234567L)
                     130            303            390
  2015   [..........] 4 filed       [..........] 4 filed       [........] filed
  2016   [..........] 4 filed       [..........] 4 filed       [........] filed
  ...
  2024   [pp..      ] 2 missing     [..........] 4 filed       [........] filed

3 periods missing across 10 years:
  2024Q3   130  missing
  2024Q4   130  missing
  [...]

next: `aeat status resume 130 --period 2024Q3`
```

End-to-end time for a 10-year backlog ingest and classification is
about 25 minutes on a mid-range laptop, dominated by PDF parsing and
LLM latency.

### Windows-specific performance

Windows Python startup is slower than POSIX. The `aeat --version`
cold-start target on Windows CI is 500 ms (POSIX is 200 ms). Lazy
imports and deferred Click registration are the primary levers.

Windows file-IO overhead on many-small-files is higher than POSIX.
Indexes (SQLite) are especially important on Windows because they
replace many-small-files reads with a single indexed query.

### Disk usage envelope

Typical Kent (1 profile, 5 years active):

| Component | Size |
| --- | --- |
| Transaction JSONL records | ~50 MB |
| Drafts, submissions JSON | ~20 MB |
| Evidence PDFs | ~500 MB (depends on Kent's filing habits) |
| Audit bundles | ~100 MB |
| Corpus (shared) | ~100 MB |
| Logs, metrics | ~50 MB |
| SQLite indexes | ~20 MB |
| **Total** | **~800 MB** |

Heavy Kent (5 profiles, 10 years, rich amendment chains): 8 to 10 GB.
Workspace total budget alerts at 15 GB via `aeat doctor`.

### Hardening rules derived from iteration 16

- Every Kent-first command has a documented wall-clock budget in this
  iteration's table. Budgets live in `src/aeat/entrypoints/cli/_perf_budgets.py`.
- Scale fixture exists at `tests/fixtures/workspaces/scale-10-years/`
  and is regenerated when the schema changes.
- SQLite indexes are derived, never source-of-truth, and are
  auto-rebuilt on schema drift.
- Streaming iteration is required for any command that may scale.
  Memory-profile tests enforce peak RSS against command-class
  ceilings.
- Memory watchdog enforces hard ceilings at runtime; exceeding fails
  cleanly with `E_MEMORY_EXHAUSTED`.
- Cold-start entry path imports minimally; heavy imports are lazy.
- Windows cold-start budget is 500 ms for `--version`; POSIX is 200 ms.
- LLM throughput targets are documented; cache hit rate is tracked
  and reported.
- Nightly performance-regression CI runs the scale benchmark and
  fails on greater than 20 percent regression.
- `aeat advanced diagnostics profile <command>` runs a command under
  cProfile for Kent-initiated performance debugging.
- Disk usage envelope is documented; `aeat doctor` alerts at 15 GB
  workspace size.

### Open risks added by iteration 16

- SQLite is a standard-library module on CPython but not on every
  build. A fallback that linear-scans JSONL must exist for builds
  without SQLite; performance degrades but correctness holds.
- LLM provider latency is the single largest unoptimisable cost. If
  provider SLOs degrade, Kent's wall clock scales with them.
- Scale fixture generation is non-trivial and must stay truthful
  across schema changes. The generator script is itself under test.
- Performance-regression CI requires stable hardware. Noisy runners
  produce false positives. A moving-median baseline mitigates but
  cannot eliminate.
- Memory watchdog on Windows is imprecise because Python's memory
  accounting differs from the OS's view. The hard ceiling check
  should use `psutil` RSS for consistency.
- Cold-start budgets regress silently if someone adds a heavy import
  at the top of a module. A static-analysis test on the entry-point
  import graph catches new heavy imports at the top level.
- Streaming JSON output (newline-delimited) for large result sets
  breaks strict JSON parsers that expect a single document.
  Documentation must flag this; `--json` output semantics should
  declare NDJSON when streaming.
- The 10-year scale fixture grows linearly with schema fields. As
  iterations add fields, the fixture size grows; regeneration cost
  grows with it.
- LLM cache key design affects hit rate. A poor key (for example
  over-specific) tanks hit rate; a sloppy key (for example
  over-generic) mis-classifies. The key design is a subtle
  quality-vs-cost trade-off that iteration 20 (LLM quality) must
  address.

## Hardening pass iteration 17 (2026-04-24)

Iteration 17 focus: backup, restore, and cross-machine workspace
portability. Kent's workspace holds ten years of financial records.
Disk failure, stolen laptops, moves between machines must never cost
him his records. This iteration specifies what is backed up, what is
not, the backup archive format, the restore flow, cross-machine
portability, partial restores, integrity verification, incremental
chains, and the retention responsibility split between CLI and OS.

### What is backed up

Included:

- `var/profiles/{id}/profile.json`: profile record.
- `var/profiles/{id}/drafts/`: local filing drafts.
- `var/profiles/{id}/submissions/`: submission records plus amendment
  chains.
- `var/profiles/{id}/transactions/records/`: JSONL source of truth.
- `var/profiles/{id}/evidence/`: statements, invoices, receipts as
  imported.
- `var/profiles/{id}/audit/`: persisted ledgers, verify verdicts,
  approval journals.
- `var/profiles/{id}/workflow/`: RunTrace records.
- `var/profiles/{id}/logs/` and `metrics/`: subject to retention, see
  `--include-logs`.
- `var/profiles/{id}/audit/llm-prompts/`: LLM prompt audit (iteration
  12).
- `var/active_profile`, `var/onboarding.json`, `var/profiles/index.json`,
  `var/workspace-version.json`.
- `var/corpus/` (optional; `--include-corpus` flag).

Excluded by design:

- `var/profiles/{id}/auth/`: credentials, keystore handles, browser
  sessions. Non-transferable by design (iteration 12).
- `var/profiles/{id}/locks/`: ephemeral.
- `var/profiles/{id}/*/index.sqlite`: derived; reindexed on restore
  (iteration 16).
- `var/cache/`: ephemeral.
- `var/telemetry-outbox/`: ephemeral unless `--include-outbox` flag.
- `var/.keystore/` (fallback passphrase keystore on headless Linux):
  never backed up; must be recreated on restore.

### Backup archive format

Archive shape when written as a single file:

```text
aeat-backup-{yyyy-mm-dd}-{workspace_hash_short}.zip
|-- backup-manifest.json                     # authoritative index
|-- workspace-version.json
|-- active_profile
|-- onboarding.json
|-- profiles/
|   |-- index.json
|   |-- personal/
|   |   |-- profile.json
|   |   |-- drafts/
|   |   |-- submissions/
|   |   |-- transactions/records/
|   |   |-- evidence/
|   |   |-- audit/
|   |   |-- workflow/
|   |   |-- logs/                            # if --include-logs
|   |   |-- metrics/                         # if --include-metrics
|   |   `-- audit/llm-prompts/
|   `-- company-sl/
|       `-- ...
`-- corpus/                                  # if --include-corpus
```

`backup-manifest.json` shape:

```json
{
  "manifest_version": "1.0",
  "backup_id": "sha256-of-contained-files",
  "workspace_hash": "0f3b...",
  "created_at": "2026-04-24T02:00:00Z",
  "created_by": "aeat-cli 0.18.2",
  "source_workspace_version": "1.0",
  "encryption": "none|aes-256-gcm",
  "incremental_base_id": null,
  "included_profiles": ["personal", "company-sl"],
  "contained_files": [
    { "path": "profiles/personal/profile.json", "sha256": "...", "size_bytes": 432 },
    ...
  ]
}
```

`backup_id` is the SHA-256 of the sorted `{path}\0{sha256}\n`
concatenation across `contained_files`, matching the bundle_id pattern
from iteration 3. This is the archive's content-addressed identity.

### Backup command

```text
aeat configure backup create \
    --output <path> \
    [--profile <id>]                   # single profile, else all
    [--encrypt]                        # AES-256-GCM with passphrase
    [--include-logs]                   # default: false
    [--include-metrics]                # default: false
    [--include-corpus]                 # default: false (large, usually re-downloadable)
    [--incremental --base <prev.zip>]  # incremental mode
    [--compression zip|tar.gz]         # default zip
```

Behaviour:

- Writes to a temp path, fsyncs, renames atomically. A partial write
  never appears valid (iteration 8 write-rename rule).
- Refuses to overwrite existing file without `--force`.
- Emits progress to stderr; `--quiet` silences.
- Prints `backup_id` and output path on success.

Kent runs a daily backup via his OS scheduler. The CLI does not
include a daemon; scheduling is OS responsibility (cron, systemd
timer, Windows Task Scheduler, macOS launchd). `docs/backup.md`
ships examples.

### Restore command

```text
aeat configure backup restore <path> \
    [--dest <workspace>]                # default: current workspace
    [--dry-run]
    [--profile <id>]                    # partial: single profile
    [--from <period> --to <period>]     # partial: period window
    [--force]                           # required to restore over existing workspace
    [--passphrase-stdin]                # for encrypted backups
```

Behaviour:

- Verifies manifest integrity first: every file's SHA-256 against the
  manifest. Mismatch refuses with `INTEGRITY:` prefix and exit `7`.
- Refuses to restore over an existing non-empty workspace without
  `--force`.
- `--dry-run` prints the restore plan without writing anything.
- Partial restore copies only the matching files and fixes up any
  cross-references.
- Reindexes SQLite after restore.
- Does not restore credentials. Prints a clear summary of what Kent
  must re-run.
- Writes an audit event at `var/profiles/{id}/audit/events/` for the
  restore.

### Cross-machine portability

A workspace restored on a new machine:

- Profile records intact.
- Drafts, submissions, audit bundles intact with original SHA-256.
- Transaction history intact.
- RunTrace records intact; replay works against matching
  `corpus_sha256`.
- Credentials: absent. Kent re-runs `aeat auth login --provider <p>`
  for each profile.
- Master encryption key: not present. Regenerated on first
  credential write to the new keystore.
- Indexes: auto-rebuilt from JSONL on first read.
- Fallback passphrase keystore (headless Linux): not present. New
  passphrase prompted on first credential write.

Restore clearly instructs Kent:

```text
[profile] personal (X1234567L)
Restore complete. Credentials must be re-established:
  aeat auth login --provider certificate
[profile] company-sl (B12345678)
Restore complete. Credentials must be re-established:
  aeat auth login --provider certificate

Recommended next steps:
  aeat doctor
  aeat auth status --all-profiles
  aeat advanced diagnostics reindex
```

### Partial restore

Partial restore is supported by profile, by period range, or both:

```text
aeat configure backup restore ./my-backup.zip --profile personal --from 2024Q1 --to 2024Q4
```

This restores only records under `var/profiles/personal/` whose period
falls within the window. Cross-references (for example an amendment
pointing at a baseline outside the window) are detected and reported:

```text
WARNING: 2 amendments reference baselines outside the restore window.
  amendment 9f2e11 references submission 3a8d01 (303/2023Q4, outside --from)
  -> Widen --from to include 2023Q4, or run `aeat records amendments list` after restore to inspect.
```

### Workspace versioning

Every workspace writes `var/workspace-version.json` at first run:

```json
{
  "schema_version": "1.0",
  "created_at": "2026-04-24T12:00:00Z",
  "tool_version_at_creation": "0.18.2"
}
```

Restore validates `schema_version` against the current tool's
compatibility window. Incompatible versions refuse restore and point
Kent at the migration tool (separate iteration).

### Integrity verification

```text
aeat configure backup verify <path> [--passphrase-stdin]
```

Reads the manifest, hashes every contained file, reports:

- `backup_id` matches or not.
- Every file's SHA-256 matches or not.
- Total bytes, included profiles, timestamp, tool version.
- Any inconsistency between manifest and archive.

Verify is read-only and does not restore. Useful for Kent confirming a
backup on external storage is still intact.

### Encryption

Optional `--encrypt` uses AES-256-GCM with an Argon2id-derived key
from Kent's passphrase. The derivation parameters and salt are
embedded in `backup-manifest.json` under `encryption`:

```json
{
  "encryption": {
    "algorithm": "aes-256-gcm",
    "kdf": "argon2id",
    "kdf_params": { "t": 3, "m": 65536, "p": 4 },
    "salt": "base64..."
  }
}
```

Encryption applies to individual file contents, not the outer zip
index. The manifest itself is encrypted; a bootstrap header outside
encryption carries only KDF parameters and the manifest nonce so the
restore tool can prompt for the passphrase.

Lost passphrase is unrecoverable. Kent is warned explicitly on
`--encrypt`:

```text
WARNING: Keep your passphrase safe. There is no recovery path. Losing
the passphrase makes this backup permanently unreadable.
```

### Incremental backups

For large workspaces (iteration 16 heavy Kent at 8 to 10 GB),
full-every-time backups are expensive.

```text
aeat configure backup create --incremental --base ./aeat-backup-full-2026-04-15.zip --output ./aeat-backup-incr-2026-04-22.zip
```

Incremental rules:

- Base must be readable and pass `backup verify`.
- Incremental archive stores only files whose SHA-256 differs from
  the base's manifest or files not present in the base.
- `backup-manifest.json` carries `incremental_base_id` pointing at the
  base's `backup_id`.
- Restore walks the chain: base plus all incrementals in order. A
  missing link in the chain refuses restore.

Chain length is Kent's responsibility. Recommendation in
`docs/backup.md`: one full backup per month, daily incrementals,
rotate quarterly.

### Backup retention and rotation

The CLI does not manage retention. Kent uses his OS tooling. Example
POSIX cron for weekly rotation of 12 weeks:

```text
0 2 * * 0 aeat configure backup create --encrypt --output ~/backups/aeat-weekly-$(date +\%F).zip
0 3 * * 0 find ~/backups -name 'aeat-weekly-*.zip' -mtime +84 -delete
```

Windows Task Scheduler equivalent is documented in
`docs/backup-windows.md`.

### Kent roleplay: new laptop

Kent's laptop died. He has last week's encrypted backup on an
external drive. On his new laptop:

```text
$ aeat configure backup verify /media/backup/aeat-weekly-2026-04-20.zip
Verifying backup integrity...
  passphrase: (prompt)
  files: 4 321
  sha256 matches: 4 321 / 4 321
  [ok] manifest valid
  source_workspace_version: 1.0 (compatible)
  created_at: 2026-04-20T02:00:00Z
  included profiles: personal, company-sl

$ aeat configure backup restore /media/backup/aeat-weekly-2026-04-20.zip
[first-run] workspace is pristine.
Restoring from /media/backup/aeat-weekly-2026-04-20.zip...
  passphrase: (prompt)
  profile 'personal':  restored  (drafts 12, submissions 8, amendments 3, audit 2)
  profile 'company-sl': restored  (drafts 4, submissions 2)
  30 102 transactions, 153 invoices, 47 receipts

[ok] workspace restored.

Credentials were not in the backup.
Next steps:
  aeat auth login --provider certificate   (profile 'personal')
  aeat auth login --provider certificate   (profile 'company-sl')
  aeat doctor

$ aeat auth login --provider certificate
...
$ aeat doctor
[profile] personal (X1234567L)
  ...
  auth session             [ok]
  ...
status: all checks passed.
```

### Kent roleplay: selective restore

Kent wants a clean workspace but wants to keep his 2024 records:

```text
$ aeat configure backup restore ./aeat-backup.zip --profile personal --from 2024Q1 --to 2024Q4 --dry-run
[profile] personal (X1234567L)
Dry-run restore plan:
  include 4 drafts (303 Q1..Q4, 130 Q1..Q4)
  include 4 submissions (303 Q1..Q4)
  include 1 audit bundle (303/2024Q1)
  include transactions for 2024Q1..2024Q4 (12 048 rows)
  include invoices/receipts imported 2024-01-01..2024-12-31

WARNING: amendment 9f2e11 references submission 3a8d01 (303/2023Q4, outside --from)
  -> widen --from to include 2023Q4 or the amendment chain will be truncated.

No files were written. Run without --dry-run to apply.
```

### Hardening rules derived from iteration 17

- Auth directories never back up.
- Backup archives are content-addressed by SHA-256 and carry a
  manifest for integrity verification.
- Restore is atomic: temp path plus fsync plus rename; no partial
  restore appears valid.
- Restore verifies every file's SHA-256 before writing anything.
- Restore over an existing workspace requires `--force`.
- Partial restore supports profile and period filters; broken
  cross-references are reported but do not silently break.
- Encrypted backups use AES-256-GCM with Argon2id KDF; passphrase
  loss is unrecoverable and clearly warned.
- Incremental chains are SHA-256 linked; a missing base refuses
  restore.
- Workspace schema-version compatibility is checked at restore.
- CLI does not manage backup retention; OS scheduling is documented
  in `docs/backup.md`.
- Backup integrity verification is a separate command from restore;
  Kent can verify external-storage backups any time.

### Open risks added by iteration 17

- Encrypted backup with lost passphrase is permanently unreadable.
  Kent's documentation must lead with this warning.
- Backup files themselves are sensitive (the full ledger of Kent's
  tax data). External storage choice is Kent's responsibility; the
  CLI cannot prevent backups to an unencrypted USB drive.
- Incremental chains break if any base is lost. Recommendation:
  monthly full backup rotation; never-rotate policy is a footgun.
- Bit-rot on external storage silently corrupts files.
  `backup verify` detects it; Kent must run `verify` regularly.
- Restore on top of an existing workspace is a conflict-resolution
  problem. `--force` overwrites, which is dangerous; a safer
  `--merge` mode may be required, though merge semantics are
  non-trivial across profiles.
- Workspace-version compatibility breaks when a future tool release
  changes the schema. A migration iteration must specify the
  forward-migration path.
- Partial restore with broken cross-references leaves amendment
  chains truncated. The warning is clear but Kent may miss it; a
  blocker flag (`--fail-on-cross-ref`) forces strict enforcement.
- Large workspaces (10 GB) take time to back up and restore; the
  progress indicator must be accurate so Kent trusts the wait.
- Windows path-length limits (260 chars without long-path support)
  may be triggered by deep archive paths. The backup writer must
  flatten or refuse paths exceeding the limit with a clear error.
- Backups performed by cron or Task Scheduler run without Kent's
  interactive passphrase. Encrypted automated backups require a
  secret store on the backing system; without it, automated
  encrypted backups are impractical.

## Hardening pass iteration 18 (2026-04-24)

Iteration 18 focus: modelo coverage expansion strategy. Iterations 1
through 17 treat modelos 130, 303, and 390 as the canonical scope. Kent
in reality files a wider set, and the project will grow over time. This
iteration specifies the contract for adding a new modelo, the support
matrix per capability, per-ejercicio versioning, the informativa versus
autoliquidacion split, AEAT portal compatibility tracking, deprecation
policy, and the contributor workflow.

### Kent's realistic modelo set

| Modelo | Purpose | Class | Kent scope |
| --- | --- | --- | --- |
| `100` | IRPF annual declaration | `autoliquidacion` | Phase B expansion |
| `111` | Retenciones trabajadores y profesionales (quarterly) | `informativa` | Phase C |
| `115` | Retenciones arrendamientos inmuebles (quarterly) | `informativa` | Phase C |
| `130` | IRPF pagos fraccionados autonomos | `autoliquidacion` | Phase A (core) |
| `200` | Impuesto sobre sociedades annual | `autoliquidacion` | Phase D |
| `202` | IS pago fraccionado | `autoliquidacion` | Phase D |
| `303` | IVA autoliquidacion | `autoliquidacion` | Phase A (core) |
| `347` | Declaracion informativa operaciones con terceros | `informativa` | Phase E |
| `349` | Declaracion recapitulativa operaciones intracomunitarias | `informativa` | Phase E |
| `369` | OSS IVA | `autoliquidacion` | Phase G |
| `390` | IVA resumen anual | `informativa` | Phase A (core) |
| `036` | Declaracion censal de alta/baja/modificacion | `informativa` | Phase F |
| `037` | Declaracion censal simplificada | `informativa` | Phase F |

Phase naming here is orthogonal to iteration 10's CLI migration phases.
It describes modelo-feature expansion within the already-migrated tree.

### Modelo registry shape

A single frozen Pydantic v2 record per `(modelo, ejercicio)` lives in
`src/aeat/modelos/_registry.py`:

```python
class ModeloEntry(BaseModel):
    modelo: ModeloId
    ejercicio: Year
    tipo: Literal["autoliquidacion", "informativa"]
    display_name: Translatable
    supported_tax_id_kinds: frozenset[TaxIdKind]
    filing_cadence: Literal["monthly", "quarterly", "annual", "on_event"]
    due_rule: DueRule
    schema_version: SchemaVersion
    ruleset_id: RulesetId | None           # informativa may lack calculations
    revise_support: RevisionSupport        # iteration 2
    fichero_format: FicheroFormat
    portal_url: HttpUrl
    manual_refs: tuple[ManualRuleRef, ...]
    normative_refs: tuple[LegalCitationRef, ...]
    last_verified_at: datetime
    deprecated: DeprecationInfo | None
```

Every capability is declared in the registry. A command that operates
on a modelo reads the registry; there is no hidden logic about which
modelo does what.

### Support matrix per capability

Each (modelo, ejercicio) declares support level per capability:

| Capability | Level values |
| --- | --- |
| Applicability (who must file) | `known`, `partial`, `unknown` |
| Schema | `full`, `partial`, `pending` |
| Draft build | `full`, `partial`, `blocked` |
| Validation | `full`, `partial`, `none` |
| Export fichero | `supported`, `pending` |
| Verify | `supported`, `pending` |
| Diff | `supported`, `pending` |
| Revise complementaria | `supported`, `unsupported`, `not_applicable` |
| Revise rectificativa | `supported`, `unsupported`, `not_applicable` |
| Revise sustitutiva | `supported`, `unsupported`, `not_applicable` |
| Audit ledger persistence | `persisted`, `in_memory_only` |
| Portal reference | `present`, `missing` |
| Normative citations | `present`, `missing` |
| Manual citations | `present`, `missing` |

The matrix surfaces through two commands:

- `aeat configure modelos show <m> [--ejercicio <y>]`: Kent-facing
  human view.
- `aeat export schemas`: machine-readable summary, one row per
  (modelo, ejercicio, capability, level).

### Per-ejercicio versioning

AEAT changes schemas annually. The registry is always keyed by
`(modelo, ejercicio)`. Adding a new ejercicio for an existing modelo:

- Fetch new schema via
  `aeat advanced reference schema refresh --modelo <m> --ejercicio <y>`.
- Update formula ruleset per changes in casilla derivations.
- Update validators per rule changes.
- Add casilla rename entries if casilla IDs changed:
  ```python
  class CasillaRename(BaseModel):
      modelo: ModeloId
      from_ejercicio: Year
      to_ejercicio: Year
      from_casilla: str
      to_casilla: str
      semantics_preserved: bool
      migration_note: Translatable
  ```
- Add a regression test: prior ejercicio's fichero still parses
  byte-identical.

Revise flows honor the baseline's `schema_version` (iteration 2). A
revise of `303/2022Q1` uses 2022 schema, 2022 formula ruleset, 2022
validators, even when Kent runs the command in 2026.

### Autoliquidacion versus informativa

Every modelo is tagged by tipo. The tag controls:

| Behaviour | `autoliquidacion` | `informativa` |
| --- | --- | --- |
| Formula ruleset | required | usually absent |
| Validation findings | casilla rules plus totals | shape and cross-reference rules |
| Revise `--kind complementaria` | usually supported | not applicable |
| Revise `--kind rectificativa` | supported per modelo policy | may be present as `correccion` |
| Revise `--kind sustitutiva` | not applicable | usually supported (full replacement) |
| Fichero BOE structure | envelope plus numeric casillas | envelope plus record rows |
| Filing cadence | quarterly or monthly | annual for most informativas, monthly for 349 |

The revise support registry from iteration 2 extends to cover all
modelos and their tipo-appropriate kinds.

### AEAT portal compatibility tracking

Every modelo registry entry carries `portal_url` and
`last_verified_at`. A quarterly live-read audit (iteration 14 Layer 6)
visits the portal in read-only mode and asserts:

- Portal page is reachable.
- Casilla labels on the portal match the current `ManualRule`
  citations.
- Declaration import/download flows still return the expected file
  shape.
- Any deviation writes a `PortalDriftEvent` record under
  `var/audit/portal-drift/{yyyy-mm-dd}.jsonl` with the detected change
  summary.

If the live-read audit detects drift, the CLI registers a banner on
`aeat doctor`:

```text
  portal drift                [warn]   modelo 303 portal changed on 2026-04-12
                                       `aeat advanced reference schema refresh --modelo 303 --ejercicio 2026`
                                       may be required before the next filing.
```

### Deprecation policy

AEAT deprecates modelos occasionally. The registry tracks:

```python
class DeprecationInfo(BaseModel):
    deprecated_after_ejercicio: Year
    successor_modelo: ModeloId | None
    reason: Translatable
    migration_note: Translatable
```

Rules:

- Deprecated modelos remain readable for historical records and audit
  bundles.
- `draft create` refuses deprecated modelos for ejercicios past the
  deprecation year and redirects to the successor.
- `revise start` on a deprecated modelo for a pre-deprecation ejercicio
  remains supported for corrections.
- `records filings list` includes deprecated-modelo filings; they are
  not hidden.

### Contributor workflow: adding modelo 100

1. Open an ADR at `.vault/adr/yyyy-mm-dd-modelo-100-adr.md` describing
   scope, ejercicios covered, applicability rules, revise-kind
   decisions, and the fichero format reference.
2. Run the research skill against AEAT's official modelo 100
   publication to gather schema, rules, and normative citations.
3. Add registry entries:
   - `src/aeat/modelos/_registry.py`: `ModeloEntry` for each
     (100, ejercicio).
   - `src/aeat/domain/schema/_100_<ejercicio>.py`: schema definition.
   - `src/aeat/domain/formulas/_100_<ejercicio>.py`: formula ruleset.
   - `src/aeat/application/filing/_validators/_100_<ejercicio>.py`: finding rules.
   - `src/aeat/revise/_registry.py`: add revise-kind entries.
4. Implement fichero BOE serializer at
   `src/aeat/adapters/outbound/aeat/export/_serializers/_100.py`.
5. Implement fichero BOE deserializer at
   `src/aeat/adapters/outbound/aeat/export/_deserializers/_100.py` for verify and diff.
6. Add portal URL, manual references, normative citations.
7. Write journey test
   `tests/journey/test_journey_modelo_100_first_export.py` against a
   curated fixture.
8. Add help fixture for every command that now exposes modelo 100
   (`test_export_modelo_help` etc.). Existing catch-all help tests
   must pass for modelo 100 per iteration 14.
9. Update `docs/coverage/modelos.md` with new support rows.
10. Regenerate scale fixture if the addition materially changes sizes.
11. Run full CI including scale and migration parity tests.
12. PR references the ADR and closes the modelo-expansion issue.

A scaffolding command assists:

```text
aeat advanced reference schema scaffold --modelo 100 --ejercicio 2024 --output ./modelo-100-scaffold/
```

This emits skeleton files for registry entry, schema, formula,
validator, serializer, and test. The contributor fills in the
AEAT-specific content.

### Kent-facing modelo discovery

Kent can discover his tracked modelos and their support:

```text
$ aeat configure modelos show 303 --ejercicio 2024
[profile] personal (X1234567L)

modelo 303 (IVA autoliquidacion) ejercicio 2024

applicability:         known          Spanish autonomos with IVA activity
schema:                full
draft build:           full
validation:            full
export fichero:        supported
verify:                supported
diff:                  supported
revise complementaria: supported
revise rectificativa:  supported      (Autoliquidacion Rectificativa IVA; post-2023 only)
revise sustitutiva:    not_applicable
audit ledger:          persisted
portal reference:      present        https://www.agenciatributaria.gob.es/.../modelo-303.html
manual citations:      present        47 references
normative citations:   present        Ley 37/1992; Real Decreto 1624/1992
last portal check:     2026-04-01
deprecated:            no
```

### Kent-facing coverage matrix

```text
$ aeat export schemas
[profile] personal (X1234567L)

modelo  ejercicio  schema  draft  export  verify  revise-c  revise-r  revise-s
------  ---------  ------  -----  ------  ------  --------  --------  --------
100     2024       full    full   pending pending yes       yes       n/a
111     2024       full    full   pending pending n/a       n/a       yes
130     2024       full    full   ok      ok      yes       no        n/a
130     2025       full    full   ok      ok      yes       no        n/a
303     2024       full    full   ok      ok      yes       yes       n/a
303     2025       full    full   ok      ok      yes       yes       n/a
390     2024       full    full   ok      ok      n/a       yes       yes
390     2025       full    partial pending pending n/a      yes       yes
347     2024       pending pending pending pending n/a      no        yes
```

Kent sees exactly which flows ship today and which remain on the
roadmap.

### Kent roleplay: first modelo 100 filing

Kent's accountant reminds him about annual IRPF:

```text
$ aeat draft create 100 --period 2024
[profile] personal (X1234567L)
Building draft for 100/2024...
  [ok] applicability check passed
  [ok] 1 203 transactions in scope
  [ok] 47 invoices linked
  [ok] formula ruleset 100-2024-v1 applied
  [warn] 2 findings require review

Draft 100/2024 created. Draft ID: 8a1f9e23d7c4b012

=== first modelo 100 filing ===
Modelo 100 is your annual IRPF return.
  inspect findings:   aeat draft show 100 --period 2024
  review & approve:   aeat review queue --modelo 100 --period 2024
  export after approval: aeat export modelo 100 --period 2024

Modelo 100 revise paths: complementaria and rectificativa both supported.
```

The first-time banner fires because `first_modelo_100_draft` flipped
from false to true in the onboarding state.

### Hardening rules derived from iteration 18

- Every modelo is registered in `src/aeat/modelos/_registry.py` as a
  frozen Pydantic v2 entry.
- Support matrix values come from the registry; no command infers
  support from elsewhere.
- Per-ejercicio versioning is mandatory: `(modelo, ejercicio)` is
  the primary key.
- Autoliquidacion versus informativa tipo tag controls formula,
  validation, revise, and fichero emission.
- Casilla renames are tracked; revise honors baseline schema version.
- Portal compatibility is tracked via `last_verified_at`; quarterly
  live-read audit detects drift.
- Deprecation is explicit; deprecated modelos remain readable but
  refuse new drafts.
- Contributor workflow is a 12-item checklist; scaffolding command
  reduces friction.
- Every modelo addition has a journey test, help fixtures updated,
  coverage matrix updated, and scale fixture regenerated.
- The coverage matrix command `aeat export schemas` is the truth
  surface; help commands and roadmap entries reference it.

### Open risks added by iteration 18

- AEAT publishes schemas on its own cadence; a new ejercicio can land
  late and gate Kent's ability to file on time. Mitigations: manual
  schema curation, AEAT portal integration, and a late-schema alert.
- Codebase grows linearly with modelos times ejercicios. The modelo
  registry must stay the single source of truth; drift into per-year
  hardcoding is a structural regression.
- Informativa revise via sustitutiva differs per modelo (347, 349,
  390 have different replacement rules). The registry must
  distinguish; a single `sustitutiva` kind hides real differences.
- Contributor onboarding for a new modelo is heavyweight. The
  scaffolding command reduces friction but cannot replace domain
  expertise in the modelo's fichero format.
- Portal-drift detection depends on live-read CI running regularly.
  If the live job fails silently for weeks, portal drift accumulates
  unnoticed.
- Deprecated modelos remain readable but require schema files to stay
  loadable indefinitely. A pruning policy risks breaking historical
  audits.
- Casilla renames between ejercicios can be subtle semantic changes
  disguised as simple renames. The `semantics_preserved` flag must
  be conservatively false; a false-true triggers silent incorrect
  migrations.
- Portal URL rot over time: AEAT restructures their website. Every
  portal URL needs periodic revalidation beyond the drift audit.
- Kent-facing coverage matrix (`aeat export schemas`) grows wide as
  modelos and capabilities expand. Pagination or filter flags may be
  needed after the modelo count passes 20.
- The scaffolding command generates boilerplate that must stay
  in sync with the registry shape; changes to `ModeloEntry` shape
  must update scaffolding templates.

## Hardening pass iteration 19 (2026-04-24)

Iteration 19 focus: corpus bundle format for offline installs and
air-gapped workspaces. The shared corpus holds modelo schemas, formula
rulesets, legal citations, manual rule excerpts, portal references,
and the modelo registry itself. Iterations 1 through 18 assumed the
corpus is available; this iteration specifies where it comes from, how
it is signed and verified, how incremental updates work, and how Kent
installs it on a no-internet machine.

### Corpus contents

The corpus is read-only reference material shared across profiles
(iteration 11). Contents:

- `corpus/schemas/{modelo}-{ejercicio}.json`: modelo schema records
  per iteration 18.
- `corpus/rulesets/{ruleset_id}.json`: formula ruleset definitions.
- `corpus/normatives/{citation_id}.json`: `LegalCitation` records.
- `corpus/manuals/{modelo}-{ejercicio}/{rule_id}.json`: `ManualRule`
  records.
- `corpus/portals/modelos.json`: modelo portal URLs with
  `last_verified_at` stamps.
- `corpus/modelos/registry.json`: `ModeloEntry` records.
- `corpus/casilla-renames.json`: `CasillaRename` map per iteration 18.
- `corpus/sha256sums.txt`: every file's SHA-256 for post-install
  verification.
- `corpus/installed-bundle.json`: workspace-local record of which
  bundle is installed.

### Bundle archive shape

A corpus bundle is a single ZIP archive:

```text
aeat-corpus-{bundle_version}.zip
|-- corpus-manifest.json           # authoritative index + signature
|-- schemas/
|   |-- 130-2024.json
|   `-- ...
|-- rulesets/
|-- normatives/
|-- manuals/
|-- portals/
|-- modelos/
|-- casilla-renames.json
`-- sha256sums.txt
```

`corpus-manifest.json` shape:

```json
{
  "manifest_version": "1.0",
  "bundle_version": "2026.04.24",
  "bundle_id": "sha256 over contained_files",
  "created_at": "2026-04-24T00:00:00Z",
  "expires_at": "2027-04-24T00:00:00Z",
  "aeat_cli_compat": ">=0.18.0,<1.0.0",
  "signing": {
    "key_id": "aeat-corpus-signing-key-2026",
    "algorithm": "ed25519",
    "signature": "hex ed25519 signature over (manifest_without_signing_field + contained_files table)",
    "signed_at": "2026-04-24T00:01:00Z"
  },
  "base_bundle": null,
  "covered_modelos": {
    "100": ["2024"],
    "130": ["2024", "2025"],
    "303": ["2024", "2025"],
    "390": ["2024", "2025"]
  },
  "contained_files": [
    {
      "path": "schemas/303-2024.json",
      "sha256": "...",
      "size_bytes": 12345,
      "content_kind": "modelo-schema",
      "modelo": "303",
      "ejercicio": "2024",
      "version": "2024.1"
    },
    ...
  ]
}
```

`bundle_id` is the SHA-256 of the sorted `{path}\0{sha256}\n`
concatenation across `contained_files`, matching the bundle_id pattern
from iterations 3 and 17.

### Content-kind closed set

```text
modelo-schema
ruleset
legal-citation
manual-rule
portal-reference
modelo-registry-entry
casilla-rename-map
```

New content kinds require an ADR amendment and a bundle-version minor
bump. Unrecognised kinds cause install to refuse with
`E_BUNDLE_UNKNOWN_CONTENT_KIND`.

### Signature verification

Corpus bundles are signed with ed25519. The CLI ships with an embedded
public-key ring in `src/aeat/corpus/_signing_keys.py`:

```python
TRUSTED_KEYS: tuple[TrustedKey, ...] = (
    TrustedKey(
        key_id="aeat-corpus-signing-key-2026",
        public_key_hex="...",
        valid_from=date(2026, 1, 1),
        valid_until=date(2027, 12, 31),
    ),
    TrustedKey(
        key_id="aeat-corpus-signing-key-2025",
        public_key_hex="...",
        valid_from=date(2025, 1, 1),
        valid_until=date(2026, 6, 30),
    ),
    ...
)
```

Rules:

- Bundles signed by an unknown key id refuse install with
  `INTEGRITY:` prefix, exit `7`, code `E_BUNDLE_UNTRUSTED_SIGNER`.
- Bundles signed past the key's `valid_until` refuse install with
  `E_BUNDLE_KEY_EXPIRED`.
- Bundles whose signature does not verify refuse install with
  `E_BUNDLE_SIGNATURE_INVALID`.
- Bundles whose `signed_at` predates the key's `valid_from` refuse
  install with `E_BUNDLE_KEY_NOT_YET_VALID`.
- Key rotation ships through a tool release. Old bundles remain
  readable as long as their key is retained in the ring.

### Compatibility window

Every bundle declares an `aeat_cli_compat` semver range. Install
refuses when the current tool version is outside the range:

```text
INTEGRITY: Corpus bundle 2026.10.01 requires aeat-cli >=0.19.0,<1.0.0 but installed tool is 0.18.2.
  -> Upgrade the tool: see release notes at https://...
  -> Or install an older corpus bundle compatible with 0.18.2.
Exit 7.
```

Tool versions within the range install successfully.

### Bundle install command

```text
aeat advanced reference corpus install <path> [--force] [--skip-signature]
```

Default flow:

1. Open archive; read `corpus-manifest.json`.
2. Verify manifest schema against the embedded schema.
3. Verify `bundle_id` against `contained_files`.
4. Verify ed25519 signature against trusted keys.
5. Verify compatibility window against current tool version.
6. Verify every `contained_files[*].sha256` against the actual file
   bytes.
7. If incremental, verify base bundle is installed and
   `base_bundle_id` matches.
8. Unpack into `var/corpus/`; atomic rename per iteration 8.
9. Update `var/corpus/installed-bundle.json` with the new
   `bundle_version` and manifest snapshot.
10. Rebuild derived indexes.
11. Emit install summary.

`--skip-signature` is banned in default behaviour; it exists only for
development builds and is refused in release builds. The check is
enforced by a startup assertion: `if is_release() and
args.skip_signature: exit 2`.

### Bundle verify and status

```text
aeat advanced reference corpus verify <path>
aeat advanced reference corpus status
aeat advanced reference corpus current
```

- `verify <path>` runs the install-time checks without writing. Useful
  to confirm a downloaded bundle's integrity before trusting it.
- `status` shows the currently installed bundle with `bundle_version`,
  `bundle_id`, install timestamp, expiry, covered modelos, and any
  warnings (expired, drift detected).
- `current` prints just the `bundle_version` for scripting.

### Online refresh

`aeat advanced reference corpus refresh` fetches the latest bundle
from an official endpoint.

Default endpoint: `https://corpus.aeat-cli.org/latest/`. Override via
`AEAT_CORPUS_ENDPOINT` env var or `configure defaults set
corpus_endpoint <url>`.

Fetch flow:

1. GET `<endpoint>/manifest.json` over HTTPS with TLS certificate
   pinning to a curated set of expected endpoints.
2. Parse manifest; compare `bundle_version` against installed.
3. If newer, fetch `<endpoint>/bundle-{version}.zip`.
4. Run install flow against the downloaded bundle.

Integrity of transit is defence-in-depth: the signed bundle is the
source of trust, not TLS alone. A man-in-the-middle who swaps the
bundle for an unsigned or untrusted-key version is refused at signature
check.

### Incremental bundles

Full bundles can be large (100 MB plus). Incremental bundles ship only
the files that changed from a declared base:

```json
{
  "bundle_version": "2026.05.01",
  "base_bundle": {
    "version": "2026.04.24",
    "bundle_id": "..."
  },
  "contained_files": [
    { "path": "manuals/303-2024/rule-47.json", "sha256": "...", "size_bytes": 1234, "content_kind": "manual-rule", "..." }
  ],
  "removed_files": ["manuals/303-2024/rule-old-12.json"]
}
```

Install rules for incremental:

- `base_bundle.version` must match the currently installed bundle.
- `base_bundle.bundle_id` must match the installed `bundle_id`.
- Missing base refuses with `E_BUNDLE_BASE_MISSING`.
- Removed files are deleted from `var/corpus/` before new files are
  unpacked.
- `sha256sums.txt` is regenerated after install to cover the new
  state.

Chain compression: periodically, a full bundle re-baselines the chain
so that new installs do not need to walk long incremental histories.

### Air-gapped install

Kent on a no-internet machine:

1. On a connected machine:
   ```text
   curl -O https://corpus.aeat-cli.org/latest/bundle-2026.04.24.zip
   curl -O https://corpus.aeat-cli.org/latest/bundle-2026.04.24.zip.sig  # optional detached signature for extra assurance
   ```
2. Transfer to the air-gapped machine via USB or internal network.
3. On the air-gapped machine:
   ```text
   aeat advanced reference corpus install ./bundle-2026.04.24.zip
   ```
4. No network call is made. Signature verification runs against
   embedded trusted keys.

Auto-bootstrap: if `var/corpus/_import.zip` exists at first run,
`aeat doctor` offers to install it with confirmation:

```text
$ aeat doctor
[first-run] workspace is pristine.

  corpus                   [missing]   bootstrap bundle found at var/corpus/_import.zip
                                       install? `aeat advanced reference corpus install var/corpus/_import.zip`
  ...
```

### Expiry and staleness

Every bundle declares `expires_at` (typically one year from
`created_at`). Past expiry:

- Install emits a warning but proceeds (Kent's choice to run outdated
  corpus).
- `aeat doctor` warns: `corpus bundle expired on YYYY-MM-DD; refresh
  recommended`.
- The warning fires on every invocation that reads corpus until
  refreshed.

Expiry is not a hard cutoff. AEAT does not change schemas on calendar
boundaries; the expiry is a conservative nudge.

### Signing process

The project build pipeline for corpus releases:

1. Aggregates latest schemas, rulesets, normatives, manuals from
   curation sources and portal snapshots.
2. Validates aggregate against the bundle's schema registry.
3. Computes SHA-256 per file; produces `sha256sums.txt`.
4. Assembles `corpus-manifest.json` (less the signature field).
5. Computes ed25519 signature over the manifest skeleton plus
   `contained_files` table.
6. Inserts the signature into the manifest.
7. Packages into the ZIP archive.
8. Uploads to `corpus.aeat-cli.org/`.

The signing private key is held by project maintainers under standard
code-signing discipline. Rotation procedure is documented in
`docs/corpus-signing-rotation.md`.

### Kent roleplay: online refresh

```text
$ aeat advanced reference corpus refresh
Fetching manifest from https://corpus.aeat-cli.org/latest/...
  [ok] new version 2026.05.01 available (installed: 2026.04.24)

Downloading incremental bundle (42 MB)...
  [progress] 42.0 / 42.0 MB

Verifying bundle...
  [ok] signed by aeat-corpus-signing-key-2026 (valid until 2027-12-31)
  [ok] compatibility: tool 0.18.2 satisfies bundle >=0.18.0,<1.0.0
  [ok] bundle_id matches contained_files digest
  [ok] base_bundle 2026.04.24 matches installed

Installing incremental update...
  3 schema updates
  12 manual rule updates
  2 new normative citations
  1 file removed

Installed 2026.05.01.
```

### Kent roleplay: air-gapped install

```text
# On connected machine
$ curl -O https://corpus.aeat-cli.org/latest/bundle-2026.04.24.zip

# Transfer to air-gapped machine via USB drive

# On air-gapped machine
$ aeat doctor
  corpus                   [missing]   offline bundle?
                                       `aeat advanced reference corpus install /media/usb/bundle-2026.04.24.zip`

$ aeat advanced reference corpus install /media/usb/bundle-2026.04.24.zip
Verifying bundle...
  [ok] signed by aeat-corpus-signing-key-2026
  [ok] compatibility: tool 0.18.2 satisfies bundle >=0.18.0,<1.0.0
  [ok] 4 321 files, 105 MB

Installing corpus...
  [progress] 4 321 / 4 321

Installed 2026.04.24.

$ aeat doctor
  corpus                   [ok]        2026.04.24, installed 2026-04-24T14:03:22Z
```

### Endpoint trust and verification

TLS certificate pinning for `corpus.aeat-cli.org`:

- Expected SHA-256 fingerprints of the endpoint's public key are
  embedded at build time.
- Fingerprint mismatch refuses the fetch with `E_CORPUS_TLS_PINNING_FAILED`.
- Pinning is defence-in-depth; the signed bundle remains the primary
  source of trust.

Custom endpoints via `AEAT_CORPUS_ENDPOINT` do not inherit pinning.
They rely on standard OS trust store plus bundle signature. The CLI
warns when using a non-pinned endpoint:

```text
[warning] Using custom corpus endpoint (not pinned). Bundle signature remains the primary trust anchor.
```

### Hardening rules derived from iteration 19

- Corpus bundles are signed with ed25519 using keys from a trusted
  ring embedded in the tool.
- Bundle integrity is content-addressed; `bundle_id` matches the
  SHA-256 of the sorted `path\0sha256\n` file table.
- Compatibility window is declared per bundle and enforced at
  install.
- Incremental bundles chain from a declared base; missing base
  refuses install.
- Air-gapped install requires no network; signature trust is
  embedded.
- `--skip-signature` is banned in release builds.
- TLS pinning protects the default endpoint; custom endpoints fall
  back to standard trust plus signature.
- Expiry warns but does not block.
- Content-kind is a closed set; extensions require ADR amendment.
- Corpus releases are independent of tool releases and vice versa.

### Open risks added by iteration 19

- Signing key compromise requires immediate rotation via a tool
  release. Kent must upgrade to receive the new trusted ring.
  Mitigation: key rotation schedule is proactive (annual) so a
  compromise window is short.
- Bundle distribution endpoint availability is a single point of
  failure. Mirrors under documented fingerprints reduce risk but the
  first-level endpoint must be highly available.
- Incremental chain walks grow long over time. Full bundles must
  re-baseline the chain periodically; cadence documented in
  `docs/corpus-release-cadence.md`.
- Expired bundles silently drift from current AEAT rules. The
  `aeat doctor` warning must be prominent or Kent files against
  stale rules.
- Air-gapped install relies on Kent's transfer discipline. A user-
  transferred bundle that was corrupted in transit fails at signature
  check (good), but a malicious-file-substitute cannot be detected if
  the signature verifies against a trusted key (the signed bundle is
  the only trust anchor).
- Modelo coverage in a bundle lags AEAT's real schema publication.
  Kent may need a schema before the corpus release covers it;
  manual-curation path for individual schema files should be
  supported.
- Casilla-rename maps must ship atomically across schema updates. A
  partial install that updates a schema without its rename map
  corrupts historical revise flows.
- Bundle size grows with modelo expansion. A typical bundle reaches
  100 MB and may exceed 500 MB as all Kent-relevant modelos ship.
  Incremental updates mitigate refresh cost but not first-install
  cost.
- Endpoint pinning is brittle when the project rotates TLS
  certificates. Pinning must be rotated in tool releases in sync with
  certificate rotation, or Kent's `corpus refresh` breaks.
- The bundle-signature private key is a critical project asset. Loss
  or theft requires emergency rotation and a coordinated tool release.
  Key-management documentation must be explicit and tested.

## Hardening pass iteration 20 (2026-04-24)

Iteration 20 focus: LLM automation quality metrics. Iteration 16 sized
the LLM throughput budget, iteration 12 specified prompt scrubbing,
iteration 8 classified `transactions automate --with llm` as
`non_idempotent_external`. This iteration specifies how the CLI
measures whether the LLM is helping Kent or hurting him. Confidence
thresholds, rule-agreement checks, human-override tracking, drift
detection against pinned benchmarks, sampling, cost accounting, cache
effectiveness, and rollback on quality regression.

### Classifier provenance

Every LLM-backed classification persists with full provenance:

```python
class ClassificationHistoryEntry(BaseModel):
    transaction_id: str
    classified_at: datetime
    run_id: str
    classifier: Literal[
        "llm:anthropic:claude-sonnet-4-6:v1",
        "llm:openai:gpt-5-1:v1",
        "rules:v47",
        "human:<actor_id>",
    ]
    result: ClassificationResult               # business, category, ratio
    confidence: ConfidenceScores | None        # present only when classifier=llm
    llm_metadata: LlmMetadata | None
    rules_agreement: RulesAgreement | None
    human_override: HumanOverride | None
```

The record persists alongside the `Transaction` at
`var/profiles/{profile_id}/transactions/records/{yyyy-mm}.jsonl` with
an append-only chain per transaction; the most recent entry determines
current state, older entries preserve history.

### Confidence scores and thresholds

Every LLM response carries per-field self-reported confidence in
`[0.0, 1.0]`. The CLI evaluates each result against thresholds:

- `confidence >= 0.85` on every field: accepted silently, classifier
  record keeps `confidence_band=high`.
- `0.65 <= confidence < 0.85` on any field: accepted with
  `confidence_band=medium`; added to `review queue` with kind
  `transaction.confidence_medium`.
- `confidence < 0.65` on any field: not applied to the transaction;
  classifier record keeps `confidence_band=low`; added to `review
  queue` with kind `transaction.confidence_low` for manual
  classification.

Thresholds are configurable per profile:

```text
aeat configure defaults set llm_confidence_high 0.85
aeat configure defaults set llm_confidence_medium 0.65
```

### Rule-agreement check

For every LLM-eligible transaction the CLI also runs the deterministic
rule-based classifier. The two results are compared:

- `rules_agreement.agrees` is true when business, category, and ratio
  match within tolerance (ratio within 5 percentage points).
- Disagreement flips `confidence_band` to `medium` regardless of LLM
  confidence and enqueues `review queue` kind
  `transaction.disagreement` with both results side by side.

The rule classifier acts as a safety net: an overconfident LLM that
picks a business category the rules disagree with is caught at review
time, not after export.

### Human override tracking

When Kent overrides an auto-applied classification through
`transactions classify`, `transactions edit`, or via the review queue,
the override is recorded on the original classification record:

```python
class HumanOverride(BaseModel):
    overridden_at: datetime
    actor: str                  # profile identifier or configured username
    previous_result: ClassificationResult
    new_result: ClassificationResult
    reason: str | None
```

Override rate per field feeds quality diagnostics.

### Diagnostic command

```text
aeat advanced diagnostics llm-quality --days 30
```

Output:

```text
[profile] personal (X1234567L)

LLM automation quality (30 days)

  total classifications         12 048
    auto-accepted (high conf)    11 301  94.0%
    queued medium confidence         541  4.5%
    queued low confidence             91  0.75%
    queued disagreement             115  0.95%

  Human override stats
    override rate overall         2.1%
    override by field
      business                    1.8%
      category                    0.9%
      ratio                       3.2%

  Drift vs pinned baseline (2026-03-01 snapshot)
    accuracy delta              +0.4 pp
    avg confidence delta        +0.02
    merchant coverage delta     +8.0 pp
    override rate delta         -0.4 pp (improvement)

  Cost
    prompt tokens               14.4 M
    completion tokens            1.2 M
    estimated cost              US $18.42
    cost per 1 000 classified   US $1.53
    pricing table dated         2026-04-01
```

All figures come from local JSONL metrics (iteration 15); no network
request.

### Sampling for silent regression

Even high-confidence classifications are sampled at a configurable
rate for human review:

- Default sampling rate: 1 percent of auto-accepted classifications.
- Sampled rows appear in review queue with kind `transaction.sample`.
- Kent confirms or corrects; the confirm/correct delta calibrates
  future confidence thresholds.

Sampling rate is configurable:

```text
aeat configure defaults set llm_sample_rate 0.01
```

Sampled transactions are chosen deterministically by hash of
`(transaction_id, classified_at, sample_salt)` so re-runs cover the
same rows.

### Pinned benchmark fixture

A pinned benchmark set lives at
`tests/fixtures/llm-benchmark/benchmark-{yyyy-mm-dd}.json` with 100 to
500 curated transactions whose correct classification is known. Kent
or the project runs the benchmark weekly:

```text
aeat advanced diagnostics llm-drift --benchmark 2026-03-01
```

Output:

```text
Running benchmark 2026-03-01 against current LLM configuration...
  transactions: 200

Result vs baseline (2026-03-01 initial run):
  accuracy          92.0%  (baseline 91.5%, +0.5 pp)
  mean confidence   0.87   (baseline 0.84, +0.03)
  median latency    1.2s   (baseline 1.8s, -0.6s)
  cost per 1 000    $1.52  (baseline $1.60, -$0.08)

Per-field accuracy:
  business          94.5%
  category          91.0%
  ratio             86.0%

Drift status: within tolerance (accuracy delta <5 pp).
```

Drift outside tolerance flips the command to exit `4`
(`unsupported_target`) with suggestion:

```text
ERROR: LLM drift of -8.4pp accuracy against baseline 2026-03-01.
  -> Pin an earlier model: `aeat configure defaults set llm_model "claude-sonnet-4-5"`.
  -> Inspect drift detail: `aeat advanced diagnostics llm-drift --benchmark 2026-03-01 --per-row`.
  -> Or update the baseline if the new behaviour is intentional: `aeat advanced diagnostics llm-drift --benchmark new --save`.
```

### Rollback on drift

Model drift is handled by pinning. The LLM client consults the
workspace configuration for a specific model version; the default
pins to a known-good version.

```text
aeat configure defaults set llm_model "claude-sonnet-4-6"
aeat configure defaults set llm_model_rollback "claude-sonnet-4-5"
```

`llm_model_rollback` is the version the CLI falls back to when drift
is detected or Kent invokes `aeat advanced diagnostics llm-rollback`.

### Cost tracking

Pricing tables live at
`src/aeat/adapters/outbound/llm/_pricing.py` with a `retrieved_at` date stamp per
provider:

```python
PRICING_TABLE = PricingTable(
    retrieved_at=date(2026, 4, 1),
    entries={
        ("anthropic", "claude-sonnet-4-6"): PricingEntry(
            prompt_per_1k_tokens=Decimal("3.00"),
            completion_per_1k_tokens=Decimal("15.00"),
            currency="USD",
        ),
        ("anthropic", "claude-opus-4-7"): PricingEntry(...),
        ("openai", "gpt-5-1"): PricingEntry(...),
    },
)
```

Every LLM call records token counts; the diagnostic command multiplies
by the pricing entry valid at the call's timestamp.

Pricing drift handling:

- Pricing table updates ship in tool releases, not in the corpus
  bundle (they are tool-side, not AEAT-side).
- Diagnostic output always date-stamps the pricing table used so Kent
  knows when to recalibrate.
- Missing entries fall back to the highest recorded price (pessimistic
  estimate) and flag in output.

### Cache effectiveness

The LLM prompt cache (iteration 16) is keyed by:

```python
cache_key = sha256(
    normalize_merchant(merchant)
    + bucket_amount(amount, bucket_pct=10)
    + period_year(period)
    + profile_business_context_hash(profile)
).hexdigest()[:16]
```

Rationale:

- `normalize_merchant`: lowercase, trim, remove trailing transaction
  IDs, collapse whitespace.
- `bucket_amount`: round to within 10 percent bucket so similar
  amounts cluster.
- `period_year`: year-level context; month-level would destroy hit
  rate.
- `profile_business_context_hash`: includes Kent's tracked modelos and
  default category overrides so LLM context is consistent per profile.

Cache hit rate targets (from iteration 16):

- 40 percent after one month of use.
- 60 percent after six months as merchants recur.
- Below 30 percent at any point triggers a `cache effectiveness` alert
  in `llm-usage`.

### Fallback when LLM unavailable

If the LLM is rate-limited, down, or returns an error not resolvable
by retry:

- Falls back to rule-based classification for eligible transactions.
- Records `classifier="rules:vN"` with no LLM metadata.
- Flags the batch with `llm_unavailable=true` so Kent sees at review
  time.
- Exit code remains `0` if rules classified successfully; exit `10`
  if rules cannot classify either.

Batch-level outcome is visible in the metrics sink:

```json
{
  "command": "transactions.automate",
  "metric_kind": "command_complete",
  "counters": {
    "transactions_processed": 500,
    "classified_via_llm": 0,
    "classified_via_rules_fallback": 487,
    "unresolved": 13
  },
  "llm_unavailable": true
}
```

### Multi-provider bake-off

For Kent with multiple LLM providers configured:

```text
aeat advanced diagnostics llm-bakeoff --sample 100 --providers anthropic,openai
```

Runs the same 100-transaction sample through each provider. Output:

```text
Provider              accuracy    mean-conf    cost-per-1k    mean-latency
anthropic sonnet 4.6  94.0%       0.87         US $1.52       1.2s
openai gpt-5.1        92.5%       0.82         US $1.80       0.9s

Cost per 1 000 at 94% accuracy: anthropic sonnet 4.6 = best
Latency floor: openai gpt-5.1 = best
```

Bake-off runs against the pinned benchmark fixture to avoid mixing
real Kent data into multiple provider pipelines. Running bake-off
against real transactions is refused unless Kent passes
`--use-real-transactions` which warns about fanning out his data.

### Integration with review queue

The review queue (iteration 1) gains `kind` values:

- `transaction.confidence_low`
- `transaction.confidence_medium`
- `transaction.disagreement`
- `transaction.sample`

Kent's `review queue --kind transaction.disagreement` filters to just
disagreement items for a focused session.

### Kent roleplay: post-run inspection

```text
$ aeat transactions automate --period 2026Q1 --with llm
[profile] personal (X1234567L)
Classifying 1 203 transactions...
  [progress] 1 203 / 1 203    elapsed 43s

Results
  auto-accepted:         1 131   (94.0%)
  queued medium conf:       54   (4.5%)
  queued low conf:          10   (0.8%)
  queued disagreement:       8   (0.7%)

next: `aeat review queue --kind transaction.confidence_low`

$ aeat advanced diagnostics llm-quality --days 1
[profile] personal (X1234567L)
[... quality summary ...]

$ aeat review queue --kind transaction.disagreement
ID        merchant                        llm                 rules               next action
tx_001    Cafe Restaurant El Rincon       client_meal/0.50    personal/1.00       review
tx_004    Zara Home                       office/1.00         personal/1.00       review
...

$ aeat transactions show tx_001
[... side-by-side LLM and rules results ...]
```

### Hardening rules derived from iteration 20

- Every LLM classification persists a `ClassificationHistoryEntry` with
  classifier identity, confidence scores, rule-agreement, and optional
  human override.
- Confidence thresholds have defaults but are Kent-configurable.
- Rule-agreement check runs alongside every LLM classification;
  disagreement enqueues review.
- Sampling at 1 percent of auto-accepted classifications surfaces
  silent regressions.
- Pinned benchmark fixture drives drift detection; out-of-tolerance
  drift refuses silent continuation and suggests rollback.
- Cost tracking uses a date-stamped pricing table shipped with the
  tool.
- Cache key design is documented and tested for hit rate.
- Fallback to rule-based classification is automatic on LLM failure.
- Bake-off defaults to the benchmark fixture, not real transactions.
- Review queue kinds discriminate LLM-origin review reasons.

### Open risks added by iteration 20

- LLM confidence scores are often miscalibrated: an overconfident
  model silently bypasses the threshold gate. Calibration via
  sampling results is the long-term fix; a simple floor may not
  catch systematic overconfidence.
- Pinned benchmark fixture must be curated carefully. Benchmarks that
  do not reflect Kent's real transaction distribution miss drift that
  actually matters to him.
- Model upgrades land silently when providers rotate their named
  models. The pinned model version is the primary defence; Kent must
  re-run drift detection after any configuration change.
- Cost tracking uses a tool-shipped pricing table that drifts as
  providers change prices. Staleness produces incorrect dollar
  figures; the date stamp helps Kent calibrate.
- Cache keys are a quality-versus-hit-rate tradeoff. Aggressive
  bucketing boosts hit rate but risks cross-contaminating distinct
  merchants. Hit-rate regressions warrant a key redesign.
- Rule-based classifier accuracy must be maintained as AEAT rules
  change. A rule-LLM disagreement may be a rule bug, not an LLM bug.
- Sampling produces review-queue load. A sampling rate of 1 percent
  at 30 000 transactions per year is 300 rows of manual review;
  Kent may tune this down, defeating the purpose.
- Multi-provider bake-off on real transactions leaks data across
  providers. The `--use-real-transactions` flag must stay opt-in and
  loud.
- Fallback to rule-based classification on LLM unavailability hides
  the outage in metrics unless the `llm_unavailable` flag is surfaced
  prominently in `llm-quality`.
- Cross-profile cache reuse could leak context (for example, if a
  personal merchant also appears in the company-sl profile's
  transactions). The cache key already includes a
  `profile_business_context_hash`; this mitigates but the hash must
  be strict.
- Drift detection is a weekly cadence by default; regressions between
  checks go undetected. Kent with mission-critical automation may
  want daily drift checks, which cost LLM tokens.

## Hardening pass iteration 21 (2026-04-24)

Iteration 21 focus: AEAT portal compatibility change management. The
CLI depends on AEAT's portal remaining stable in ways that iterations
1 through 20 assume: casilla IDs, fichero formats, receipt parsing,
expediente shapes, auth flows. AEAT updates their portal on its own
schedule without notice to third-party tools. This iteration specifies
how drift is detected, classified, communicated to Kent, and
remediated during filing season.

### Portal change categories

AEAT portal changes fall into closed categories. Each has its own
detection and remediation path:

| Category | Example | Detection |
| --- | --- | --- |
| Schema change | casilla 47 renamed or removed | schema refresh diff, import parse failure |
| Endpoint change | expedientes URL path changed | live-read audit, user report |
| Authentication change | Cl@ve flow altered, session timeout shortened | live auth tests, user report |
| Format change | fichero BOE version bumped, record layout altered | export verify failure, import parse failure |
| Timing change | deadline rule adjusted, calendar entries moved | calendar diff, user report |
| Modelo change | modelo deprecated or introduced | quarterly audit, BOE monitoring |

### Portal-drift event model

Every detected change produces a `PortalDriftEvent` record:

```python
class PortalDriftEvent(BaseModel):
    event_id: str
    detected_at: datetime
    detector: Literal[
        "quarterly_audit",
        "user_import_parse_fail",
        "user_export_verify_fail",
        "maintainer_announcement",
        "community_report",
        "automated_live_check"
    ]
    category: DriftCategory         # closed enum above
    modelo: ModeloId | None
    ejercicio: Year | None
    portal_url: HttpUrl | None
    symptom: Translatable           # user-facing description
    severity: Literal["info", "warning", "critical"]
    reproducible: bool
    kent_observable: bool
    mitigation: Mitigation | None
    affected_commands: tuple[str, ...]
    status: Literal["open", "confirmed", "mitigated", "resolved", "not_reproducible"]
    resolved_in_bundle: BundleVersion | None
    resolved_in_tool: SemVer | None
```

Events persist in two places:

- Workspace-local: `var/audit/portal-drift/{yyyy-mm-dd}.jsonl` for
  events affecting the user's flow.
- Project-shared: a public dashboard distributed in the corpus bundle
  at `corpus/portal-drift/events.json`, updated each release.

### Detection mechanisms

Five detection paths, each producing `PortalDriftEvent` records:

1. **Quarterly live audit** (iteration 14 Layer 6). Project maintainers
   run a curated live-read sweep against the AEAT portal. Mismatches
   generate events with detector `quarterly_audit`.
2. **User import parse failure**. When `data import statement`,
   `revise import-baseline`, or `records aeat fetch` hits a parse
   error on authoritative AEAT material, the failure is captured as
   detector `user_import_parse_fail` and logged locally. If the user
   opts in to remote telemetry (iteration 15, crash_only tier),
   scrubbed parse-failure signatures flush to the project endpoint.
3. **User export verify failure**. `export verify <path>` against a
   fichero that AEAT accepts but the CLI rejects, or vice versa,
   produces a detector `user_export_verify_fail` event.
4. **Maintainer announcement**. BOE monitoring, AEAT sede news, and
   professional-accountant community channels feed manual
   announcements curated by project maintainers.
5. **Community report**. Kent can explicitly file a report:
   ```text
   aeat advanced diagnostics portal-drift report \
       --modelo 303 --period 2024Q1 \
       --symptom "import failed with parse error: 'unexpected tag at line 47'"
   ```
   The command creates a local record, scrubs the symptom per
   iteration 12 rules, and emits an issue-draft URL or `gh issue
   create` command for the project.

### Severity triage and Kent-facing behaviour

Severity classification gates the loudness of doctor and pre-flight
warnings:

| Severity | Kent-facing | Behaviour |
| --- | --- | --- |
| `info` | suppressed in doctor; listed under `advanced diagnostics portal-drift list` | cosmetic portal change, no action |
| `warning` | doctor yellow row; pre-flight banner on affected commands | corpus refresh recommended |
| `critical` | doctor red row; pre-flight blocker unless `--ignore-drift`; loud everywhere | filing blocked until hotfix |

### Pre-flight warning on affected commands

When a drift event has `status=open|confirmed`, every run of an
affected command checks for the event and emits a pre-flight warning:

```text
$ aeat export modelo 390 --period 2024
[profile] personal (X1234567L)
[warning] AEAT portal changed the modelo 390 fichero format on 2026-03-28.
  (severity: warning; event: pde_9f2a1c; affected: export modelo 390)
  Recommendation: `aeat advanced reference corpus refresh` to install hotfix bundle.

Continue anyway? [y/N]:
```

Critical severity refuses by default:

```text
$ aeat export modelo 390 --period 2024
REFUSED: AEAT portal changed the modelo 390 fichero format on 2026-03-28.
  Kent-observable impact: exported ficheros may be rejected by AEAT.
  Hotfix corpus required. Run: `aeat advanced reference corpus refresh`.
  To override after informed consent: add `--ignore-drift`.
Exit 4. Category: unsupported_target. Code: E_PORTAL_DRIFT_CRITICAL.
```

`--ignore-drift` is an explicit acknowledgement. The CLI logs the
override to the audit journal with Kent's reason (`--drift-reason
"filing deadline tonight; will retry with hotfix tomorrow"` required).

### Hotfix corpus path

When AEAT breaks something mid-filing-season, speed matters. The
hotfix path:

1. Project maintainers confirm the drift via quarterly-audit extension
   or community escalation.
2. They prepare a minimal corpus-hotfix bundle (iteration 19) that
   ships only the changed schema, ruleset, or manual entries.
3. The bundle is signed and uploaded with `urgent: true` in the
   manifest.
4. `aeat advanced reference corpus refresh` detects the urgent flag
   and prompts Kent immediately (non-default behaviour: the urgent
   flag changes the command from opt-in to loud-notification).
5. Kent installs the hotfix; affected drift events flip to
   `mitigated` status.

Target cycle time from detection to hotfix availability:

- `critical` severity: under 24 hours.
- `warning` severity: under 7 days.

### Per-drift command impact registry

A registry tracks which commands an event affects:

```python
@dataclass
class DriftImpact:
    event_id: str
    affected_commands: tuple[str, ...]       # full CLI invocations
    degraded_behaviours: tuple[str, ...]
    safe_workarounds: tuple[SafeWorkaround, ...]
    workaround_ui: str                       # copy-paste invocation
```

The registry lives at `corpus/portal-drift/impacts.json` and is
loaded on CLI startup so pre-flight checks are fast.

### Kent-facing inventory

```text
aeat advanced diagnostics portal-drift list [--status open|confirmed|all] [--modelo <m>]
```

Lists active events:

```text
[profile] personal (X1234567L)

Active portal-drift events (3):

  pde_9f2a1c  2026-03-28  critical    modelo 390 fichero format changed
              affected: export modelo 390
              mitigation: install hotfix corpus >= 2026.04.15
              status: confirmed (hotfix available)

  pde_2b17ff  2026-04-15  warning     modelo 303 casilla 27 label changed
              affected: draft show 303, export verify
              mitigation: install corpus >= 2026.04.17
              status: confirmed

  pde_71add3  2026-04-01  info        expediente detail page moved
              affected: (none; cosmetic)
              status: resolved
```

Kent-specific filter: `--modelo <m>` scopes to his tracked modelos.

### Mid-filing-season ambiguity handling

When AEAT changes mid-season, the CLI may be running against a draft
created before the change. Rules:

- Drafts carry `schema_version` (iteration 18). Export honors the
  draft's stored version.
- If the stored schema version is no longer loadable from the corpus
  (corpus refreshed past the old version): refuse export and direct
  Kent to install a pinned corpus with both versions.
- If the stored schema version is still loadable but the new version
  is in effect at AEAT: warn prominently and ask Kent to confirm he
  wants the older version.

Kent can inspect with:

```text
aeat draft show 303 --period 2026Q1 --show-schema-version
```

### Community reporting and deduplication

Community reports from Kent users may duplicate known events.
Deduplication logic:

- Report symptom hashed against known event signatures.
- If match within similarity threshold: attach to existing event,
  incrementing `community_report_count`.
- If no match: open new event with status `open`, route to
  maintainer triage queue.

Privacy: community reports do not send raw transaction or identifier
content. Only the scrubbed symptom line, modelo, and period flush to
the project.

### Quarterly live audit responsibility

Project maintainers run the quarterly audit:

```text
aeat advanced diagnostics portal-drift audit --live \
    --profile test-audit \
    --modelos 130,303,390,100,111,115 \
    --report ./docs/portal-drift-reports/2026-q2.md
```

This live-read command visits every relevant portal page, runs
reference imports against curated fixtures, and produces a signed
report committed to the project repo.

Audit cadence: last week of each calendar quarter.

Audit output is parsed by the release pipeline; any new `warning`
or `critical` events trigger hotfix bundle preparation within the
target cycle time.

### Kent roleplay: filing-season drift

It is April 20, 2026. Kent wants to file 303/2026Q1, due April 30.

```text
$ aeat status today
[profile] personal (X1234567L)
[alert] CRITICAL portal drift: modelo 303 fichero format changed 2026-04-15.
        hotfix corpus 2026.04.17 is available.
        run `aeat advanced reference corpus refresh` before filing.

Today's agenda:
  303/2026Q1  due in 10 days  not started

$ aeat advanced reference corpus refresh
Fetching manifest... new URGENT hotfix 2026.04.17 available.
[ok] signed by aeat-corpus-signing-key-2026
[ok] incremental from installed 2026.04.12
Installing...
  3 schema updates (modelo 303 new fichero record layout)
  1 manual rule update
  2 drift events marked mitigated
Installed 2026.04.17.

$ aeat status today
[profile] personal (X1234567L)
Today's agenda:
  303/2026Q1  due in 10 days  not started

$ aeat draft create 303 --period 2026Q1
[... proceeds normally ...]
```

### Kent roleplay: undetected drift

Kent runs `data import` against a fresh portal download. Parse fails:

```text
$ aeat data import statement ./aeat-export-2026Q1.pdf
[profile] personal (X1234567L)
FAIL: Parse error in ./aeat-export-2026Q1.pdf at line 47: unexpected token 'CLAVE'.

  This may indicate a new portal format. Would you like to report this to the project?
    [y/N]: y

  Captured fixture at var/audit/portal-drift/reports/2026-04-24T15-02-11Z.json.
  Ready to file:
    aeat advanced diagnostics portal-drift report \
        --modelo 303 --period 2026Q1 \
        --fixture var/audit/portal-drift/reports/2026-04-24T15-02-11Z.json
    gh issue create --repo wgergely/aeat --template portal-drift.md --body-file var/audit/portal-drift/reports/2026-04-24T15-02-11Z.json

Exit 10. Category: system_failure.
```

The CLI captures the parse-failure context locally (scrubbed), offers
Kent a report path, and exits cleanly. No silent failure.

### Hardening rules derived from iteration 21

- `PortalDriftEvent` records are the canonical drift representation;
  workspace-local logs plus project-shared dashboard.
- Five detector classes are closed set; new detectors require ADR
  amendment.
- Severity triage (`info`, `warning`, `critical`) gates Kent-facing
  loudness and blocking behaviour.
- `critical` events block affected commands by default; override
  requires `--ignore-drift` plus a reason captured in the audit
  journal.
- Hotfix corpus bundles flag `urgent` in the manifest; refresh
  detects and prompts installation.
- Per-event affected-command registry enables precise pre-flight
  warnings.
- `--show-schema-version` on drafts surfaces mid-season ambiguity.
- Community reporting deduplicates against known events and scrubs
  identifiers.
- Quarterly live audit is the primary structured detection cadence;
  community reports and import failures are supplementary.
- Target cycle time: critical hotfix under 24 hours, warning hotfix
  under 7 days.
- Audit reports are signed artefacts committed to the project repo.

### Open risks added by iteration 21

- Quarterly live audit depends on maintainer discipline plus live CI
  reliability. An outage during audit week delays detection by a full
  quarter.
- Community reports may be false positives (Kent misread a portal
  change, or his local corpus is stale). Deduplication must not
  silently bury a real issue as a duplicate.
- Hotfix cycle time target of 24 hours for critical events depends on
  maintainer availability across time zones. A true urgent event may
  require pager-style response.
- `--ignore-drift` exists because refusing to file is worse than
  filing against known-broken schema when the deadline is tonight.
  The flag creates a footgun; the audit-journal requirement must be
  enforced.
- Pre-flight warnings may fatigue Kent if drift events accumulate.
  A resolved event must flip quickly to `resolved` status and drop
  off pre-flight.
- Drift detection from user-import parse failures only catches
  failures at parse time. Silent semantic drift (for example a
  casilla now means something subtly different) slips through.
  Quarterly live-read with curated fixtures mitigates but cannot
  eliminate.
- Mid-filing-season schema version pinning means the corpus must
  retain old versions indefinitely. The corpus bundle size grows.
  A pruning policy risks breaking Kent's historical revises
  (iteration 2 risk carried forward).
- Maintainer announcements rely on maintainers reading BOE and AEAT
  sede promptly. A legislative change that affects modelos may land
  weeks before the portal implementation; early maintainer action
  is preferred.
- The project-shared drift dashboard in corpus bundles creates a
  release dependency: fast drift resolution requires corpus release
  cadence to match. If corpus releases are monthly, critical drifts
  may need an out-of-band release.
- Drift events may overlap: two portal changes in the same week
  affecting the same command. The registry must model `affects`
  relationships so Kent sees one consolidated block, not two stacked
  warnings that each miss the other's context.

## Hardening pass iteration 22 (2026-04-24)

Iteration 22 focus: Windows cross-platform regression catalog. Kent
runs on Windows 11 today. Iterations 1 through 21 assume cross-platform
correctness but leave Windows-specific fragility implicit. This
iteration catalogues known Windows pain points, their mitigations, and
the regression tests that guard them, establishes the catalogue's
growth discipline, and surfaces Windows-specific checks through
`aeat doctor`.

### Catalogue shape

Each entry lives at `docs/windows-catalog.md` in human form and at
`docs/_windows_catalog.json` in machine form. Entry fields:

```python
class WindowsCatalogEntry(BaseModel):
    entry_id: str                          # WIN-NNN
    added_at: date
    status: Literal["active", "mitigated", "superseded", "platform_fixed"]
    symptom: Translatable                  # Kent-observable behaviour
    root_cause: str                        # developer-facing explanation
    mitigation: str                        # how the CLI handles it today
    test_path: str                         # regression test file
    workaround: str | None                 # Kent-runnable workaround
    affected_windows_versions: tuple[str, ...]
    affected_shells: tuple[str, ...]
    discovered_in: SemVer | None           # tool version where bug surfaced
    fixed_in: SemVer | None
    follow_up_issue: IssueRef | None
```

Entries are append-only and immutable. A mitigated bug that returns
gets a new entry rather than a status flip.

### Seed catalogue (iteration 22 baseline)

The ten Windows issues known at iteration 22 time:

#### WIN-001: Stale file-lock reclamation

Symptom: `aeat transactions classify` fails with
`LOCKED: (...) is locked by PID 12345` even though PID 12345 is long
dead. Only happens after a crash or forced close.

Root cause: Windows file-locking semantics differ from POSIX. Lock
files are not automatically released when the holder process exits
abnormally; the `.lock` file remains on disk.

Mitigation: Startup check inspects every `.lock` file's PID metadata
(iteration 8). `psutil.pid_exists()` confirms liveness. Dead PID
triggers automatic reclamation with a stderr notice:

```text
[info] Reclaiming stale lock held by dead PID 12345 (command: transactions automate, started 2h ago).
```

Test: `tests/platform/windows/test_stale_lock_reclamation.py` writes a
lock file pointing to a dead PID, invokes a mutating command,
asserts reclamation.

Workaround for Kent when automation misfires:
`aeat advanced diagnostics locks --list` then
`aeat advanced diagnostics locks --reclaim --pid <dead>`.

#### WIN-002: Codepage on legacy cmd.exe

Symptom: Spanish text (`ñ`, `á`) and Hungarian text (`ő`, `ű`) render
as garbled bytes or `?` placeholders on classic cmd.exe.

Root cause: cmd.exe defaults to cp850 or cp1252 depending on system
locale. Python's stdout encoding follows the terminal.

Mitigation: At startup, detect `sys.stdout.encoding`. If not UTF-8
compatible and language is `hu`, fall back to `en` (iteration 9). For
`es`, force `chcp 65001` equivalent via Windows API
(`SetConsoleOutputCP(65001)`). Warn when fallback happens.

Test: `tests/platform/windows/test_codepage_detection.py` simulates
cp1252 stdout and asserts fallback behaviour.

Workaround: Use Windows Terminal, PowerShell 7+, or Git Bash.

#### WIN-003: Long-path support

Symptom: `aeat audit export 303 --period 2026Q1 --output
C:\Users\Kent Longname\OneDrive\Desktop\audits\aeat-audit-2026Q1-bundle.zip`
fails with `FileNotFoundError` on bundle internal paths when deep
nested structure is unpacked.

Root cause: Windows default MAX_PATH is 260 characters. The CLI
creates multi-level audit bundle paths plus per-profile directories.

Mitigation:

- Detect `LongPathsEnabled` registry value at startup.
- If enabled: proceed normally with `\\?\` prefix as needed.
- If not enabled: refuse to create paths exceeding 240 characters
  (safety margin) and emit a clear error with the registry-fix
  command.

Test: `tests/platform/windows/test_long_path_support.py` creates a
deep path and asserts correct detection or refusal.

Workaround:

```text
# PowerShell as Administrator
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' `
    -Name LongPathsEnabled -Value 1 -Type DWord
```

Documented at `docs/windows-long-paths.md`.

#### WIN-004: Keystore access under non-interactive session

Symptom: `aeat auth login` succeeds interactively, but the same
command invoked under Windows Task Scheduler as a non-interactive
user fails with `keyring.errors.KeyringError`.

Root cause: Windows Credential Manager binds user-scope credentials
to interactive sessions. Task Scheduler non-interactive runs lack the
right session context.

Mitigation:

- Document the limitation explicitly.
- For automation, use `aeat configure credentials set --stdin`
  to provide credentials fresh per run via a secret manager.
- Alternative: use `machine_scope` credentials with explicit
  consent.

Test: Limited Windows CI coverage (CI runs as a specific user);
documented in `docs/windows-automation.md`.

Workaround: Kent either interactively logs in before scheduled tasks
or uses a secret manager (HashiCorp Vault, etc.) to inject
credentials.

#### WIN-005: Ctrl-C and SIGINT on Windows

Symptom: Ctrl-C during `transactions automate` sometimes leaves the
progress bar on screen without a clean exit, and checkpoint may not
persist the final batch.

Root cause: Windows uses SIGBREAK for Ctrl-C; Python's default
SIGINT handler on Windows does not run atexit hooks in all cases.

Mitigation:

- Register Windows-specific signal handlers via `signal.signal(signal.SIGBREAK, ...)`.
- Wrap every batch write in an `atexit`-safe finalizer.
- Iteration 8's atomic write-rename pattern ensures no partial file;
  this catalogue entry covers the progress-bar cleanup and the
  checkpoint finalization.

Test: `tests/platform/windows/test_ctrl_c_atomic_checkpoint.py`
starts a batch, sends SIGBREAK, asserts checkpoint is persisted.

#### WIN-006: Cold-start performance

Symptom: `aeat --version` takes 800 ms on Windows, 150 ms on Linux.

Root cause: Python import system is measurably slower on NTFS
(many-small-file overhead), and Windows Defender's real-time scanning
amplifies the effect on `.pyc` files.

Mitigation:

- Minimal entry path in `aeat --version` and `aeat --help`
  (iteration 16).
- Lazy imports via `__getattr__` on subpackages.
- Wheel ships pre-built `.pyc` files via `PYTHONPYCACHEPREFIX` hint.
- Document Windows Defender exclusion for the installation directory
  in `docs/windows-performance.md`.

Test: `tests/platform/windows/test_cold_start_budget.py` asserts
`aeat --version` completes under 500 ms on Windows CI.

Workaround: Add the installation directory to Windows Defender
exclusions (administrator action).

#### WIN-007: Case-insensitive filesystem collisions

Symptom: Creating profile `personal` then `Personal` succeeds at CLI
level but the second profile overwrites the first's directory on
NTFS.

Root cause: NTFS is case-insensitive by default. Case-sensitive
option per-directory exists but is not universal.

Mitigation: `configure profile add --id <id>` validates that `id` is
all lowercase ASCII. Non-lowercase refuses at the CLI layer:

```text
ERROR: profile id 'Personal' is not lowercase-ASCII.
  -> Use a lowercase slug: 'personal', 'company-sl'.
```

Test: `tests/platform/windows/test_case_sensitive_profile_ids.py`.

#### WIN-008: Playwright Chromium installation

Symptom: First browser-backed command (`auth login --provider
certificate` with browser flow, or portal import) fails with
`Executable doesn't exist at .../ms-playwright/chromium-...`.

Root cause: Playwright does not auto-install Chromium; the user must
run `playwright install chromium` separately.

Mitigation: On first browser-backed command, detect missing
Chromium and offer to install:

```text
[profile] personal (X1234567L)
Browser backend (Playwright) needs Chromium.
Run `python -m playwright install chromium` (about 140 MB) and retry?
```

Alternatively run `aeat configure browser install` (wraps the
Playwright install).

Test: `tests/platform/windows/test_browser_install_hint.py`
asserts the hint fires when Chromium is missing.

Workaround: `python -m playwright install chromium`.

#### WIN-009: TLS trust store

Symptom: `aeat advanced reference corpus refresh` fails with
`ssl.SSLCertVerificationError` on corporate-managed Windows with a
custom root CA.

Root cause: `requests` uses the `certifi` bundle by default, not the
Windows certificate store. Corporate root CAs installed in Windows
are invisible to Python.

Mitigation:

- Optional integration with the `truststore` library to use Windows
  certificate store directly.
- Fallback env var `AEAT_CA_BUNDLE=/path/to/ca.pem` for explicit
  override.
- `aeat doctor` reports which trust store is active.

Test: `tests/platform/windows/test_tls_trust_store.py` verifies
fallback env var respected.

Workaround: `AEAT_CA_BUNDLE=C:\path\to\corp-ca.pem aeat advanced
reference corpus refresh`.

#### WIN-010: JSONL line endings

Symptom: Kent opens `var/profiles/personal/logs/2026-04-24.jsonl` in
PowerShell `Get-Content`; every line shows `\r\n` or tools that
parse strict NDJSON complain about trailing `\r`.

Root cause: Python default text mode on Windows translates `\n` to
`\r\n`. JSONL tools downstream expect `\n` only.

Mitigation: Every JSONL writer opens the file in binary mode and
writes explicit `\n`. No text-mode `print(..., file=f)` patterns in
the codebase for JSONL output.

Test: `tests/platform/windows/test_jsonl_line_endings.py` writes a
record on Windows and asserts no `\r` bytes.

### Catalogue growth discipline

New Windows-specific issues go through:

1. Bug report from Kent or a Windows CI failure creates an issue
   labelled `platform:windows`.
2. A reproduction is added to `tests/platform/windows/` before
   mitigation.
3. An entry is added to the catalogue with status `active`.
4. Mitigation PR updates the status to `mitigated` and links the
   fix commit.
5. When the underlying platform resolves the issue (Windows update,
   Python release), status flips to `platform_fixed` with a note.

A catalogue enforcement test asserts every entry has a valid
`test_path` pointing at an existing file under `tests/platform/windows/`.

### Doctor integration

`aeat doctor` on Windows runs Windows-specific sub-checks:

```text
  long path support           [ok]        LongPathsEnabled=1
  codepage                    [ok]        UTF-8 (65001)
  python cold-start           [ok]        420 ms (budget 500 ms)
  playwright chromium         [missing]   run `aeat configure browser install`
  tls trust store             [ok]        truststore active (Windows store)
  windows credential manager  [ok]        interactive session detected
```

Each sub-check has an `entry_id` matching a catalogue entry. Checks
with status `active` or `mitigated` that fail produce yellow or red
rows with entry-id references for grep.

### Cross-shell compatibility

The CLI supports these shells on Windows:

| Shell | Supported | Notes |
| --- | --- | --- |
| Windows Terminal (any backend) | yes | default recommendation |
| PowerShell 7+ | yes | |
| PowerShell 5.1 | yes with warnings | WIN-002 fallback applies |
| Windows PowerShell ISE | degraded | progress bars may misbehave |
| cmd.exe (classic) | yes with fallback | WIN-002 fallback applies |
| Git Bash | yes | treat as POSIX for most purposes |
| WSL (Ubuntu via WSL2) | yes | treat as POSIX |
| VS Code integrated | yes | backend-dependent |
| Cygwin | unsupported | explicit refusal at startup |

Startup detects the shell via `TERM`, `PSModulePath`, and
`ComSpec` environment variables. An unsupported shell triggers:

```text
ERROR: Cygwin-hosted terminals are not supported. Use Windows Terminal,
PowerShell, cmd.exe, or WSL2 instead. Exit 2.
```

### Windows-specific CI matrix

Per iteration 14's cross-platform layer, Windows CI runs:

- Windows Server 2022 plus Python 3.11, 3.12 for PR gates.
- Windows 11 plus Python 3.11, 3.12 weekly for extended validation.
- Windows ARM64 plus Python 3.11 monthly when GitHub Actions runners
  become available.

Every catalogue entry's test runs in every Windows CI job. A failing
test blocks the release branch.

### Kent roleplay: first-time Windows user

Kent installs `aeat` on his Windows 11 laptop:

```text
PS C:\Users\Kent> pip install aeat-cli
...
PS C:\Users\Kent> aeat doctor
Welcome to aeat. First-run workspace.

Windows-specific checks:
  long path support         [warn]      LongPathsEnabled=0 (registry)
                                        fix: see docs/windows-long-paths.md
  codepage                  [ok]        UTF-8 (65001)
  python cold-start         [ok]        420 ms
  playwright chromium       [missing]   run `aeat configure browser install`
  tls trust store           [ok]        truststore active

Next steps:
  aeat configure profile add
  aeat advanced reference corpus refresh
  aeat configure browser install
```

He enables long-path support (one-time administrator command) and
proceeds. The CLI guides him; no silent failures.

### Hardening rules derived from iteration 22

- Every known Windows fragility has a catalogue entry, a test in
  `tests/platform/windows/`, and a doctor sub-check.
- Catalogue is append-only; mitigated entries stay for history.
- Windows CI matrix runs every platform test on every PR.
- Profile IDs validate lowercase-ASCII only.
- Long-path detection refuses deep paths on legacy Windows rather
  than producing partial writes.
- JSONL writers open in binary mode with explicit `\n`.
- TLS trust store integration via `truststore` plus env-var override.
- Playwright Chromium install is guided through
  `aeat configure browser install`.
- Cygwin refused at startup; other shells supported with documented
  caveats.
- Catalogue growth discipline requires: issue, reproduction test,
  catalogue entry, mitigation PR.

### Open risks added by iteration 22

- Windows Server Core and Nano Server lack interactive keystore
  access; a Task Scheduler secret injection path is documented but
  depends on user tooling.
- Future Windows updates may regress fixed behaviour. CI catches it
  but Kent's production machine may lag.
- Windows ARM64 is emerging; runner availability gates coverage.
- Corporate-managed Windows with Group Policy restrictions may
  block registry changes (WIN-003), forcing path-length workarounds
  rather than the proper fix.
- Python 3.13 and later may change import-system behaviour; cold-
  start budgets require revalidation on every Python upgrade.
- WSL2 is treated as POSIX but shares the Windows filesystem; mixed
  semantics can produce subtle bugs when Kent alternates between a
  WSL shell and a Windows shell against the same workspace.
- Windows Defender exclusion is a manual step; Kent may never do it
  and tolerate slow cold start indefinitely.
- The catalogue risks growing into a dumping ground; a quarterly
  curation pass must mark superseded entries and prune duplicates.
- Shell detection relies on environment variables that exotic
  deployments may not set. The detector should degrade gracefully
  rather than refuse the command.
- Playwright Chromium occupies 140 MB and requires internet for
  install; offline Windows users need a documented manual install
  path with a pre-downloaded Chromium archive.
- Catalogue entries in the public repository disclose known security
  caveats and architectural details; they should not name customers
  or specific corporate configurations.

## Hardening pass iteration 23 (2026-04-24)

Iteration 23 focus: release process hardening. The project mandate
already pins versioning to `pyproject.toml` and forbids a release-
please GitHub Actions workflow; releases run locally via
`just release` and `just release-apply`. This iteration layers
release-candidate discipline, a pre-release checklist, changelog
automation, emergency-hotfix process, rollback triggers, compatibility
declarations, and post-release monitoring over that baseline.

### Release train model

Releases follow a candidate-then-stable train. No release ships
straight from main.

```text
main -> vX.Y.Z-rc.1 -> soak 48 to 72 hours -> vX.Y.Z
```

Rules:

- Every non-hotfix release starts as `vX.Y.Z-rc.1`.
- RC is uploaded to a separate distribution channel
  (`aeat-cli-beta` on PyPI, or a test PyPI index).
- RC triggers the full CI matrix including Windows, scale, live-read
  (gated), portal-drift audit, migration parity (if in Phase B), and
  cross-platform regression suite.
- RC soak period: 48 hours minimum, 72 hours default. Early adopters
  in the beta channel test against their workspaces.
- If any check fails or a community regression is reported during
  soak, the RC is abandoned. A new RC (`rc.2`) ships with the fix.
- After clean soak, the RC promotes to `vX.Y.Z` with identical
  artefacts (no code changes between RC and stable).

### Pre-release checklist

`docs/release-checklist.md` is a literal checklist the release
captain works through. Every box must be checked, in order:

- [ ] Every merged PR has a conventional-commit subject.
- [ ] `just test-cov` passes on current branch; coverage floor from
      iteration 14 holds for every subpackage.
- [ ] Scale test suite green (iteration 16; weekly CI job).
- [ ] Windows CI matrix green on Server 2022 and Windows 11 for
      Python 3.11 and 3.12 (iteration 22).
- [ ] Live-read CI green or explicitly skipped with a reason recorded
      (iteration 14 Layer 6).
- [ ] Portal-drift audit clean: no unresolved `critical` events
      (iteration 21).
- [ ] Migration parity tests green if in Phase B (iteration 10).
- [ ] Catalogue enforcement tests green (registries, i18n, schemas,
      help fixtures, mutability, manifest, vocabulary leakage).
- [ ] Structural audit harness clean (iteration 24).
- [ ] Any ADR pre-approval blocker closed.
- [ ] Version bumped in `pyproject.toml`, `src/aeat/__init__.py`, and
      `.release-please-manifest.json`.
- [ ] `CHANGELOG.md` regenerated from conventional commits.
- [ ] `docs/release-notes/v<version>.md` drafted.
- [ ] Corpus compatibility window updated if required
      (iteration 19).
- [ ] Windows and macOS release wheels produced and verified.
- [ ] Release commit signed; tag signed.
- [ ] Release signing key rotation timer checked.

The checklist is a machine-readable YAML at `docs/_release_checklist.yaml`
that a CI task validates before any release artefact is uploaded.

### Versioning discipline

Semantic versioning with pre-1.0 relaxed rules:

| Version class | Triggers | Example |
| --- | --- | --- |
| Major (`X.0.0`) | CLI command removal, required-flag addition, breaking schema migration, hardened-tree default flip (iteration 10 Phase C) | `1.0.0`, `2.0.0` |
| Minor (`X.Y.0`) | New command, new option, opt-in feature, new modelo support, deprecation notice introduction | `0.19.0`, `1.1.0` |
| Patch (`X.Y.Z`) | Bug fix, documentation, non-observable internal change, security patch | `0.18.2`, `1.0.1` |
| Release candidate | Pre-release of any of the above | `0.19.0-rc.1`, `1.0.0-rc.3` |
| Hotfix | Emergency fix cherry-picked from main | `0.19.1` via `hotfix/0.19` branch |

Pre-1.0 allows minor versions to include breaking changes, but each
breaking change must be documented in the release notes with a migration
section. Post-1.0: strict semver. Breaking changes require a deprecation
cycle of at least one minor version before the breaking major.

### Changelog automation

Conventional commits drive changelog entries:

| Commit type | Changelog section |
| --- | --- |
| `feat:` | Added |
| `fix:` | Fixed |
| `perf:` | Performance |
| `revert:` | Reverted (with pointer to reverted commit) |
| `docs:`, `refactor:`, `chore:`, `test:`, `build:`, `ci:`, `style:` | excluded from user-facing changelog |
| footer `BREAKING CHANGE:` | Breaking changes (always surfaces) |

`CHANGELOG.md` follows the Keep-a-Changelog format with semantic
headings (Added, Changed, Deprecated, Removed, Fixed, Security).

Changelog generation is mechanical: a script at
`scripts/generate_changelog.py` walks the commit range between the
previous tag and HEAD, emits the changelog entries, and the release
captain hand-edits for wording clarity (not for inclusion decisions).

### Release notes template

`docs/release-notes/v<version>.md` uses the template at
`docs/_release_notes_template.md`:

```text
# aeat-cli v<version> ({date})

## Kent-facing summary

One to three sentences. What can Kent do now that he couldn't before?
What did he lose, if anything?

## Added

- list of new capabilities

## Changed

- list of behaviour changes

## Deprecated

- list of features marked deprecated

## Removed

- list of features removed (usually after a deprecation cycle)

## Fixed

- list of bug fixes

## Security

- list of security-relevant changes

## Migration notes

If any breaking changes or corpus compatibility updates, list:
- required Kent actions
- migration commands
- deadline for sunset aliases (iteration 4)

## Upgrade

Standard pip upgrade path. Platform-specific notes if relevant.

## Known issues

Any issues not blocking release but worth flagging.

## References

- Issue numbers
- ADR references
- Related releases
```

### Emergency hotfix process

For security issues, data-loss bugs, and critical portal-drift
blockers:

1. Create a `hotfix/vX.Y` branch from the last stable tag.
2. Cherry-pick the minimal fix commit.
3. Run a fast CI subset: registry enforcement, command unit tests,
   Windows CI, plus the regression test for the fixed bug. Scale and
   live-read are skipped for speed.
4. Tag as patch (`vX.Y.Z+1`). No RC phase for hotfixes.
5. Publish release notes flagged `SECURITY` or `CRITICAL`.
6. Announce via whatever communication channels the project uses
   (GitHub release, issue comment, docs banner).
7. Update `aeat doctor` to emit an upgrade banner for installed
   versions older than the hotfix.

Target cycle time from issue confirmation to hotfix availability:

- Security issues (CVE or equivalent): under 24 hours.
- Data-loss bugs: under 24 hours.
- Portal-drift blockers: under 48 hours.
- Other critical bugs: under 72 hours.

### Rollback triggers

A release may need to be rolled back (yanked) if within 72 hours of
release:

- A data-loss or data-corruption bug is reported and confirmed.
- A security vulnerability is disclosed.
- A regression affects more than 5 percent of telemetry-reporting
  users (from iteration 15).
- A corpus compatibility declaration was computed wrong and breaks
  corpus refresh for installed users.
- A tax-liability-changing bug is discovered (for example, a formula
  producing incorrect casilla values).

Rollback process:

1. `pip` yank on PyPI using the maintainer API token (documented at
   `docs/release-yanking.md`).
2. Publish a yank advisory at `docs/release-notes/v<version>.md` with
   `YANKED` banner and reason.
3. Update `aeat doctor` to warn users on the yanked version.
4. Prepare the next release with the fix (usually a patch release
   within 24 hours).
5. Post-mortem documented at `docs/release-retro/v<version>.md`.

Yanking preserves the version number; the next good version is the
next higher patch or minor.

### Compatibility matrix

Every release declares its compatibility with Python runtimes, corpus
bundles, workspace schema, and AuthProvider API. Declared in
`src/aeat/_compat.py`:

```python
COMPAT = CompatibilityMatrix(
    python_min="3.11",
    python_max_tested="3.12",
    corpus_min="2026.01.01",
    corpus_max_known_good="2026.04.24",
    workspace_schema_min="1.0",
    workspace_schema_max="1.0",
    auth_provider_min=None,          # pre-Phase E
    auth_provider_max=None,
)
```

A test asserts the matrix matches what iterations 17 (backup
restore), 19 (corpus bundle), and 10 (AuthProvider Phase E) actually
tolerate.

### Release signing

Release artefacts are signed with a release-specific ed25519 key,
distinct from the corpus signing key (iteration 19).

Signed artefacts per release:

- Source distribution (`aeat-cli-X.Y.Z.tar.gz`): detached signature
  `.sig` file.
- Wheel (`aeat_cli-X.Y.Z-py3-none-any.whl`): detached signature.
- Signed git commit and signed git tag.
- `RELEASE.sha256`: SHA-256 of every artefact plus an ed25519
  signature.

Verification instructions in `docs/verify-release.md` let Kent (or
his security-conscious IT department) verify the install:

```text
curl -LO https://.../aeat-cli-0.19.0.tar.gz
curl -LO https://.../aeat-cli-0.19.0.tar.gz.sig
aeat-release-verify aeat-cli-0.19.0.tar.gz \
    --public-key https://corpus.aeat-cli.org/release-signing-keys.pub
```

(Tool `aeat-release-verify` is a standalone verifier distributed
outside the main CLI so installation is not a chicken-and-egg
problem.)

### Release-key rotation

Release signing keys rotate every 12 months or immediately on
suspected compromise.

Rotation procedure:

1. New key pair generated offline.
2. Public key embedded in `src/aeat/_release_signing_keys.py` with
   overlap validity windows (both old and new keys valid for 30
   days).
3. Tool release with the new public key goes through normal release
   train.
4. After 30-day overlap, old key retired from the verifier (but not
   from historical verification of older releases).
5. Compromise response: immediate yank of last key's releases,
   emergency rotation release, public advisory.

### Version check and upgrade prompt

Kent's CLI checks for new versions weekly. Results cached locally
under `var/cache/version-check.json`.

```text
$ aeat --version
aeat 0.18.2 (released 2026-04-01)
A newer version is available: 0.19.0 (released 2026-04-22).
  `pip install --upgrade aeat-cli`
  Release notes: aeat --release-notes 0.19.0
```

Opt-out:

```text
aeat configure defaults set version_check_enabled false
```

Version check never sends telemetry; it only reads a manifest from
the corpus endpoint.

### Distribution channels

- `aeat-cli` (PyPI stable): official releases after RC soak.
- `aeat-cli-beta` (PyPI prereleases): RCs and development snapshots
  for early adopters.
- Git main branch: for contributors.

Each channel has distinct version ranges and is documented at
`docs/installation.md`.

### Post-release monitoring

After each release, the release captain watches for 72 hours:

- Community issue tracker for regressions.
- Opt-in telemetry for anomalous error-rate spikes (iteration 15).
- PyPI download counts (lagging indicator).
- Community channel mentions.

At 7 days post-release, the release captain writes
`docs/release-retro/vX.Y.Z.md`:

- What went well.
- What slipped.
- What Kent-visible issues surfaced.
- What to change in the next release.

The retro is a git-tracked artefact, not a private document.

### Kent roleplay: upgrade after hotfix

```text
$ aeat status today
[profile] personal (X1234567L)
[CRITICAL] Installed version 0.19.0 has a known data-loss bug in
           `audit export`. Fixed in 0.19.1 (released 2026-04-23).

  upgrade: `pip install --upgrade aeat-cli`
  details: aeat --release-notes 0.19.1
  yank status: 0.19.0 has been yanked from PyPI. Installation blocks after pip cache purge.

Today's agenda:
  ...

$ pip install --upgrade aeat-cli
...
$ aeat --version
aeat 0.19.1 (released 2026-04-23)
```

### Kent roleplay: air-gapped release verification

Kent's IT team requires artefact verification before install:

```text
$ curl -LO https://releases.aeat-cli.org/aeat-cli-0.19.0.tar.gz
$ curl -LO https://releases.aeat-cli.org/aeat-cli-0.19.0.tar.gz.sig
$ curl -LO https://releases.aeat-cli.org/release-signing-keys.pub
$ aeat-release-verify aeat-cli-0.19.0.tar.gz \
      --public-key ./release-signing-keys.pub
[ok] signature valid (key id: aeat-release-signing-key-2026)
[ok] key valid until 2027-04-24
[ok] SHA-256 matches expected digest
$ pip install aeat-cli-0.19.0.tar.gz
```

### Hardening rules derived from iteration 23

- Every non-hotfix release flows through RC with 48-72h soak on the
  beta channel.
- Pre-release checklist is a machine-validated YAML; missing items
  block the release pipeline.
- Conventional commits drive changelog; manual edits are for wording
  only, not inclusion.
- Release notes follow a fixed template including Kent-facing
  summary, migration notes, known issues, and references.
- Emergency hotfix cycle times: 24h for security and data-loss, 48h
  for portal-drift blockers, 72h for other critical bugs.
- Rollback triggers and process are documented; yanks are visible to
  installed users through `aeat doctor`.
- Compatibility matrix in `src/aeat/_compat.py` tested against actual
  tolerance.
- Release signing distinct from corpus signing; ed25519 keys;
  verification path documented.
- Release-key rotation every 12 months or on compromise, with 30-day
  overlap.
- Version check is weekly, cached, opt-out.
- Distribution channels: `aeat-cli` stable, `aeat-cli-beta` pre-release.
- Post-release retrospective at 7 days, git-tracked.

### Open risks added by iteration 23

- 48-72h RC soak may slip for trivial patches or when maintainer
  bandwidth is constrained. Discipline requires holding the line.
- Beta channel adoption may be low, reducing pre-release defect
  detection. Explicit outreach to power users encourages adoption.
- PyPI yank is not instantaneous across CDN mirrors. Users on
  regional mirrors may install the yanked version for up to 24
  hours.
- Release signing private key loss requires the same emergency-
  rotation procedure as corpus signing. Key-management documentation
  must cover both.
- Hotfix cycle time depends on maintainer availability across time
  zones. Security-grade response requires a pager rotation that a
  small project may struggle to staff.
- Conventional-commit discipline depends on contributor compliance.
  A PR check that validates commit messages against the format
  enforces it at merge time.
- Pre-release checklist growth risks becoming ceremonial. Quarterly
  review prunes items that no longer add value.
- Compatibility matrix drift (code tolerates something the matrix
  forbids, or vice versa) silently breaks Kent's corpus refresh or
  backup restore. The enforcement test is the only defence.
- Release notes template is only effective if contributors fill it in
  during PR. Empty template sections must be flagged by the release
  script.
- Retrospectives in a public repo require sensitivity about naming
  individuals when things slipped. The template should default to
  role-based language.
- Air-gapped verification via `aeat-release-verify` requires
  distributing a separate tool; its own release process must be
  hardened the same way.

## Hardening pass iteration 24 (2026-04-24)

Iteration 24 focus: structural audit harness automation. The project
mandate already defines monthly (coverage, duplication, code health,
Kent regression), quarterly (charter compliance, architectural
review), and per-milestone (methodology) cadences, plus a
five-dimension structural-integrity audit charter. This iteration
specifies the harness that runs those audits on a schedule, how
findings persist, how trends aggregate, how severity thresholds gate
releases, and how Kent-facing coverage matrices stay accurate.

### Five-dimension audit charter

Audit dimensions, per project charter, plus what each catches:

| Dimension | Catches |
| --- | --- |
| Shadowing | Two modules or commands that answer the same Kent question through different vocabulary or routing |
| Duplication | Identical or near-identical logic in two places; copy-paste expansion opportunities |
| Location | Code that lives in the wrong subpackage; cross-subpackage imports that break the subpackage-root rule |
| Cohesion | Unrelated things clumped into one module; splitting opportunities |
| Layering | Dependencies flowing the wrong direction (for example domain imports from CLI) |

These five run together in every monthly audit and stand on their own
in per-milestone gates.

### Audit harness as tests

Every audit runs as a pytest-marked test. Location:

```text
tests/audit/
|-- test_shadowing.py                  # dimension 1
|-- test_duplication.py                # dimension 2
|-- test_location.py                   # dimension 3
|-- test_cohesion.py                   # dimension 4
|-- test_layering.py                   # dimension 5
|-- test_coverage_audit.py
|-- test_code_health.py
|-- test_kent_regression_catalogue.py
|-- test_charter_compliance.py
|-- test_methodology_gate.py
`-- test_trend_freshness.py
```

Axes per project mandate:

```python
pytestmark = [pytest.mark.audit, pytest.mark.domain_infra]
```

A dedicated `audit` axis label is the sixth access-type alongside
`unit`, `live_read`, and `live_write`. Unlike unit tests it does not
run on every PR; a separate CI job runs the audit suite on schedule
(monthly, quarterly) plus on-demand for milestone gates.

### Shadowing audit implementation

`tests/audit/test_shadowing.py` walks the CLI command registry and
the domain module tree, computes per-group signatures, and compares
against a committed baseline at
`tests/audit/_baselines/shadowing.json`.

Signature comparison:

- Command name similarity (Levenshtein plus token overlap).
- Docstring first-sentence similarity (TF-IDF cosine).
- Function signature shape (required args, option flags) hashed.
- Cross-group result overlap: if two commands produce the same
  object type, they shadow.

Threshold: similarity >= 0.80 between two commands in different
groups flags as shadowing. Baseline records known-accepted
shadowing (for example the intentional `advanced aliases` overlap
with promoted commands); new shadowing requires baseline update
plus ADR-amendment-level justification.

### Duplication audit implementation

`tests/audit/test_duplication.py` uses AST-level comparison to find:

- Identical function bodies across files.
- Near-identical bodies (AST node-type sequence match >= 95 percent)
  across files.
- String constants duplicated three or more times (extract-constant
  opportunity).
- Regex patterns duplicated twice (move-to-registry opportunity).

Output: a duplication-ratio metric and a per-file list of
duplication pairs. Baseline at
`tests/audit/_baselines/duplication.json` tracks accepted
duplication; drift above baseline fails the audit.

### Location audit implementation

`tests/audit/test_location.py` walks the import graph and asserts:

- Relative imports only inside `src/aeat/` (project mandate).
- Cross-subpackage imports reference the subpackage root only.
  Example: `from aeat.application.filing import FilingDraft` is allowed;
  `from aeat.application.filing._internal import SomeHelper` is not.
- Tests colocate with modules (Rust-style, project mandate).
- Live tests live under `tests/live/` with correct markers.
- Scale tests live under `tests/scale/` with `@pytest.mark.slow`.
- Regression tests live under `tests/regression/` with matching
  Kent-wall catalogue entries.

Violations fail the audit with the exact file path and offending
import line.

### Cohesion audit implementation

`tests/audit/test_cohesion.py` computes per-module LCOM (Lack of
Cohesion in Methods) scores and flags modules exceeding threshold.

LCOM calculation per Henderson-Sellers:

- Count method pairs that share zero attributes.
- Divide by total method pairs.
- Score above 0.75 suggests cohesion split.

Baseline at `tests/audit/_baselines/cohesion.json` tracks accepted
LCOM scores; regressions flag for refactor attention.

Cohesion audit emits warnings, not hard failures. It drives refactor
backlogs rather than blocking merges.

### Layering audit implementation

`tests/audit/test_layering.py` declares allowed dependency
directions and asserts the import graph conforms.

Allowed directions:

```text
cli/ -> (any domain)
commands/ -> (any domain)
domain/ (filing, submission, transactions, revise, compare, audit, ...)
  -> core (errors, logging, config, i18n, io)
  -> other domain (via subpackage root only)
core/ -> (nothing inside aeat, stdlib only)
```

Disallowed:

- `filing/` importing from `cli/`.
- `errors/` importing from `submission/`.
- `config/` importing from any domain.

Violations fail the audit with the exact import line and direction.

### Coverage audit

`tests/audit/test_coverage_audit.py` runs `just test-cov` and
compares per-subpackage coverage against iteration 14 floors:

- `auth`: 80 percent
- `submission`, `audit`, `revise`: 75 percent
- all others: 60 percent

Drops below floor fail the audit. Within 5 percent of floor emits a
warning and opens a tracking issue automatically.

### Code health audit

`tests/audit/test_code_health.py` runs `ruff check`, `mypy`, and
`pylint` (or the project's chosen toolchain) against `src/aeat/`.

- New errors above the baseline fail the audit.
- Warning drift within threshold is logged but not a failure.

### Kent wall regression catalogue audit

`tests/audit/test_kent_regression_catalogue.py` enumerates every
Kent wall closure recorded at `docs/_kent_wall_catalogue.json` and
asserts:

- Each entry has a matching `tests/regression/test_kent_wall_<slug>.py`.
- The matching test file's `pytestmark` module-level marker is
  present.
- The matching test is not `@pytest.mark.skip`-decorated.
- The matching test has been run in the last 30 days (via pytest
  cache timestamp).

Missing or stale entries fail the audit.

### Charter compliance audit

`tests/audit/test_charter_compliance.py` enforces every project
mandate from `.claude/rules/aeat-project-mandates.md`:

- No `live_transport_supported=True` outside test sites.
- No `import aeat.*` absolute imports inside `src/aeat/`.
- No `unittest`, `unittest.mock`, `pytest_mock`, `pytest_httpx`,
  `time_machine`, `freezegun`, or `vcr` imports anywhere.
- Pydantic v2 frozen models at every boundary-crossing structure.
- `.vault/` frontmatter integrity (`uv run vaultspec-core vault
  check` passes).
- Conventional commits on every commit since the last release tag.

Every mandate has a matching assertion. Adding a mandate requires
adding an assertion.

### Methodology gate per milestone

`tests/audit/test_methodology_gate.py` runs only when the milestone
release branch is created. Assertions:

- Every Kent-capability issue closed under the milestone has a
  regression test.
- Every issue closed has a `milestone: X.Y.Z` label.
- Coverage matrix (`docs/coverage/*.md`) reflects the milestone's
  shipped capabilities.
- No regression in coverage, duplication, or shadowing over the
  milestone window.
- Portal-drift events from iteration 21 are all `resolved` or
  `mitigated` (no `confirmed critical` at release time).

Failing the methodology gate blocks the milestone release branch.

### Audit report persistence

Each audit run emits a report at `.vault/audit/{yyyy-mm-dd}-{kind}.md`.
The report uses the vaultspec template and carries frontmatter:

```yaml
---
tags:
  - "#audit"
  - "#monthly-audit"        # or quarterly/milestone-gate/per-dimension
date: 2026-05-01
related:
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
---
```

Report sections:

- Summary: pass/warn/fail counts per dimension.
- Findings: per-issue detail with file paths and line numbers.
- Trends: comparison to the previous audit in this cadence.
- Actions: recommended GitHub issues to open (with labels and
  priority).
- References: linked ADRs and prior audits.

The report is authored by the audit harness, not a human. A human
reviews it and opens follow-up issues.

### Trend tracking

Audit results aggregate into `.vault/audit/_trends.json`:

```json
{
  "coverage_pct_by_subpackage": {
    "auth": { "2026-04": 82.3, "2026-03": 81.7, "..." },
    "submission": { "2026-04": 78.1, ... }
  },
  "duplication_ratio": { "2026-04": 0.018, ... },
  "shadowing_pairs": { "2026-04": 3, ... },
  "cohesion_warnings": { "2026-04": 7, ... },
  "layering_violations": { "2026-04": 0, ... },
  "kent_walls_closed": { "2026-04": 4, ... },
  "portal_drift_unresolved": { "2026-04": 1, ... }
}
```

`aeat advanced diagnostics audit-trends --dimension <d>` renders a
text bar chart.

### Severity tiers and release gating

Audit findings carry severity:

| Tier | Effect |
| --- | --- |
| `red` | Hard-rule violation (charter compliance, layering, coverage floor). Blocks next release. |
| `amber` | Soft-rule violation or regression within warning band. Opens tracking issue; release proceeds. |
| `green` | Within baseline. No action. |

Release pre-check (iteration 23) includes an audit-state check: the
most recent monthly audit must be `green` or `amber` for the
release to proceed. A `red` finding blocks.

### Cadence automation

Cadence enforcement via CI schedule:

- Monthly: first Monday, full audit run, report committed to
  `.vault/audit/`, findings triaged into GitHub issues.
- Quarterly: first Monday of January, April, July, October;
  charter compliance plus architectural review in addition to
  monthly suite.
- Per-milestone: triggered by the milestone-release branch creation;
  methodology gate runs; signoff required before release.
- Ad-hoc: `just audit [--dimension <d>]` runs locally.

### Audit CLI surface

Under `advanced diagnostics`:

| Command | Purpose |
| --- | --- |
| `advanced diagnostics audit run [--dimension <d>]` | Run an audit dimension ad-hoc. |
| `advanced diagnostics audit report [--date <d>]` | Render a past audit report. |
| `advanced diagnostics audit-trends [--dimension <d>] [--window <n>]` | Show trend over N months. |
| `advanced diagnostics kent-walls list` | Enumerate Kent-wall catalogue. |

All run locally against `.vault/audit/` and committed trend data.

### Kent roleplay: contributor running a local audit

```text
$ just audit --dimension shadowing
[audit] shadowing
  scanned 47 CLI commands across 13 groups.
  [ok] 3 accepted shadowing pairs (see _baselines/shadowing.json)
  [warn] new shadowing: `export verify` and `audit verify` share
         signature shape and docstring similarity 0.83.
         recommendation: distinct help text or ADR amendment.
  [red] 0

Exit 1 (warning only).

$ aeat advanced diagnostics audit-trends --dimension coverage --window 12
Coverage trend (12 months):
  month    auth   submission audit  revise  others
  2025-05  78.2%  74.1%      71.0%  70.2%   62.1%
  2025-06  79.1%  74.8%      71.5%  71.0%   62.5%
  ...
  2026-04  82.3%  78.1%      75.4%  74.8%   64.2%
```

### Kent roleplay: failing release pre-check

```text
$ just release
[pre-check] audit state
  most recent monthly audit: 2026-04-01 (30 days old)
  findings: 1 red, 2 amber

  RED: layering violation
    src/aeat/application/filing/_helpers.py:47
    imports from src/aeat/entrypoints/cli/ (CLI -> domain allowed, domain -> CLI forbidden)
    owner: @maintainer-handle
    tracking: #942

  release blocked.

Exit 7.
```

### Hardening rules derived from iteration 24

- Five-dimension audit harness is pytest-driven; dedicated `audit`
  axis; runs on scheduled CI jobs.
- Every audit dimension has its own test file under
  `tests/audit/` and a baseline at `tests/audit/_baselines/`.
- Monthly, quarterly, per-milestone cadences enforced by CI
  schedule; ad-hoc via `just audit`.
- Audit reports committed to `.vault/audit/` with vaultspec
  frontmatter.
- Trends aggregate in `.vault/audit/_trends.json`; Kent-facing
  dashboard via `audit-trends`.
- Severity tiers gate releases: `red` blocks, `amber` opens issues,
  `green` passes.
- Kent-wall catalogue is the canonical regression-test registry;
  every entry has a passing test in the last 30 days.
- Charter compliance asserts every project mandate; adding a
  mandate requires adding an assertion.
- Methodology gate runs per milestone and blocks release branches.
- Coverage audit per-subpackage floors match iteration 14.
- Code-health audit runs ruff, mypy, and pylint (or equivalents).
- New accepted baseline entries require ADR-amendment-level
  justification.

### Open risks added by iteration 24

- Baselines risk drifting into dumping grounds for "known issues"
  that never get fixed. Quarterly baseline review prunes stale
  entries.
- Audit tests are expensive; the full suite may take tens of
  minutes. Running monthly is affordable; per-PR would be
  prohibitive.
- Similarity thresholds for shadowing are heuristic. False positives
  erode contributor trust; false negatives miss real shadowing.
  Regular tuning is required.
- Cohesion LCOM scores have well-known limitations (method-count
  sensitivity). The metric suggests attention, not verdicts; taking
  it literally leads to over-refactoring.
- Layering audit depends on the import graph being complete. Dynamic
  imports, late imports, and plugin systems may dodge the static
  analysis. Additional runtime checks may be needed.
- Kent-wall catalogue is manually curated. Missing entries silently
  remove regression coverage; CI must warn when a PR closes an
  issue labelled `kent-wall` without adding a catalogue entry.
- Trend data grows linearly with audit cadence. Pruning old trend
  detail (keeping monthly medians past 24 months) keeps the file
  manageable.
- The audit harness itself is code that requires maintenance. It
  should be covered by its own tests to prevent a broken audit
  silently passing.
- Charter-compliance assertions must be fast enough to run often;
  whole-tree AST walks can be slow. Incremental caching helps but
  introduces complexity.
- `red` severity blocks releases, but a critical release (security
  hotfix) may need to ship despite an audit red. The hotfix process
  from iteration 23 bypasses audit gates; this is intentional but
  must be explicit.
- Audit reports committed to the repo are public; sensitive details
  (for example file paths in customer deployments) should never
  appear. The audit writer must scrub per iteration 12 rules.

## Hardening pass iteration 25 (2026-04-24)

Iteration 25 focus: runbook authoring and operational documentation
discipline. Iterations 6 through 24 introduced many error categories,
recovery paths, and escalation routes. A production-grade tool ships
those as runnable runbooks, not scattered prose. Kent hitting a
`REFUSED:` or `INTEGRITY:` error must land on a structured procedure,
not a blog post. This iteration specifies the runbook format, the
initial runbook catalogue, how errors link to runbooks, how runbooks
stay fresh, and how Kent surfaces them from the CLI.

### Runbook inventory (iteration 25 seed)

Seed runbooks cover the scenarios iterations 1 through 24 specified:

| ID | Title | Triggered by |
| --- | --- | --- |
| RB-001 | Portal drift | iteration 21 `REFUSED: AEAT portal changed ...` |
| RB-002 | LLM unavailable | iteration 20 fallback notifications |
| RB-003 | Lost backup passphrase | iteration 17 restore prompt |
| RB-004 | Corrupted workspace | iteration 8 integrity violation on startup |
| RB-005 | Certificate expired | iteration 12 auth-status warning |
| RB-006 | Auth session expired mid-command | iteration 6 `AUTH:` |
| RB-007 | Upgrade broke a workflow | iteration 23 rollback notes |
| RB-008 | Slow command (scale investigation) | iteration 16 latency diagnostics |
| RB-009 | Windows long-path refusal | iteration 22 WIN-003 |
| RB-010 | Cross-profile mismatch | iteration 11 `E_PROFILE_TAX_ID_MISMATCH` |
| RB-011 | Wrong revise `--kind` | iteration 2 per-modelo matrix refusal |
| RB-012 | Memory exhausted | iteration 16 `E_MEMORY_EXHAUSTED` |
| RB-013 | Workspace lock contention | iteration 8 `E_CASE_LOCKED` |
| RB-014 | Backup and restore flow | iteration 17 full happy path |
| RB-015 | Modelo not yet supported | iteration 18 unsupported-target error |
| RB-016 | Corpus bundle expired | iteration 19 expiry warning |
| RB-017 | Revise chain broken (missing baseline) | iteration 2 and iteration 17 partial restore |
| RB-018 | Accidental live flag attempt | iteration 5 `REFUSED: Live-submit flags` |
| RB-019 | LLM cost exceeded expected budget | iteration 20 `llm-usage` spike |
| RB-020 | Audit bundle `replay-degraded` | iteration 3 replay divergence |

Initial catalogue is 20 runbooks. Future issues add new runbooks
with the same discipline.

### Runbook file location and naming

Runbooks live at `docs/runbooks/RB-NNN-<slug>.md`. Naming is strict:

- `RB-NNN`: zero-padded sequence number.
- `<slug>`: kebab-case descriptive identifier.
- Example: `docs/runbooks/RB-001-portal-drift.md`.

A stable id decouples the URL from the title; renaming does not
break error-message links.

### Runbook frontmatter schema

Every runbook opens with YAML frontmatter:

```yaml
---
runbook_id: RB-001
title: "Runbook: portal drift"
slug: portal-drift
category: incident
severity: warning
symptom_keywords:
  - portal drift
  - casilla changed
  - fichero format
  - aeat portal update
triggers:
  - error_code: E_PORTAL_DRIFT_CRITICAL
  - error_code: E_PORTAL_DRIFT_WARNING
  - doctor_check: portal_drift
last_verified: 2026-04-24
verified_against_version: "0.18.2"
verified_against_corpus: "2026.04.24"
owner: maintainer-team
related:
  - ADR: 2026-04-24-aeat-cli-wireframe
  - Issue: 116 (live-write safety charter)
  - Runbook: RB-016 (corpus bundle expired)
---
```

Fields:

- `runbook_id`: stable across renames.
- `slug`: canonical human-readable token.
- `category`: one of `incident`, `maintenance`, `onboarding`,
  `recovery`, `upgrade`.
- `severity`: matches iteration 21's `info`, `warning`, `critical`.
- `symptom_keywords`: free-form list the CLI matches against Kent's
  help queries.
- `triggers`: structured list connecting this runbook to specific
  error codes or doctor checks. A regression test uses this list to
  verify every error code referenced here actually exists.
- `last_verified` / `verified_against_*`: staleness tracking.
- `owner`: the team or persona responsible.
- `related`: pointers to ADRs, issues, and other runbooks.

A Pydantic v2 model validates the frontmatter; a runbook missing any
required field fails CI.

### Runbook body structure

Every runbook body follows a fixed outline:

```text
# Runbook RB-NNN: {title}

## When to use this runbook
- bulleted symptom list
- concrete error strings Kent may have seen

## Kent question
- one-paragraph statement of Kent's goal (not the diagnostic goal)

## Prerequisites
- workspace state expected
- tool version range
- any resources needed (internet, backup file, etc.)

## Steps
1. Exact command (copy-paste ready, no placeholders)
2. Expected output excerpt
3. Next command
...

## Verification
- how to confirm the fix worked
- exact commands to run
- expected outcome

## Follow-up
- post-fix actions
- preventative measures
- when to escalate

## Why this happens
- brief technical background (Kent-facing, not developer jargon)

## Related
- links to ADRs, issues, other runbooks
```

Rules:

- Commands are copy-paste-ready. No `<placeholder>`.
- If a value must be substituted, show the exact substitution shape
  Kent sees in the CLI output of the preceding step.
- Output excerpts are real, recorded from a fixture workspace, not
  invented.
- No technical jargon without a plain-language gloss.
- Every runbook fits in one screen where possible; longer runbooks
  split into a summary plus collapsible sections.

### Runbook surfacing from the CLI

```text
aeat docs runbook <id-or-slug>
aeat docs runbook list [--category <c>] [--severity <s>]
aeat docs runbook search <keyword>
```

Behaviour:

- `runbook <id>` renders the runbook to stdout; human mode formats
  headings in ASCII (no Unicode markdown tools); `--json` dumps the
  parsed frontmatter plus markdown body.
- `runbook list` tabulates the catalogue.
- `runbook search <keyword>` full-text searches symptom_keywords,
  title, and Kent-question paragraphs.

Runbook content ships inside the CLI package (bundled at build
time) so Kent can read runbooks offline.

### Error-to-runbook linking

Every error in the error-code registry (iteration 6) optionally
carries a `runbook_id`:

```python
ErrorCode(
    code="E_PORTAL_DRIFT_CRITICAL",
    category="unsupported_target",
    runbook_id="RB-001",
    ...
)
```

Error output prepends the runbook reference:

```text
REFUSED: AEAT portal changed the modelo 390 fichero format on 2026-03-28.
  runbook: `aeat docs runbook portal-drift`  (RB-001)
  see: docs/runbooks/RB-001-portal-drift.md
Exit 4. Code: E_PORTAL_DRIFT_CRITICAL.
```

A test asserts every error code in the registry either has a
`runbook_id` pointing at a real runbook or is explicitly marked
`no_runbook_needed` with a reason.

### Runbook testability

Runbooks are executable where possible. A test harness at
`tests/audit/test_runbook_executability.py` for each runbook:

1. Parses the `Steps` block to extract commands.
2. Provisions a fixture workspace matching the runbook's
   `Prerequisites` section.
3. Executes each command, capturing output.
4. Matches the captured output against the runbook's `Expected
   output excerpt` fuzzy-match threshold (90 percent similarity on
   non-timestamp lines).
5. Runs the `Verification` block and asserts pass.

Runbooks that cannot be executed (for example `RB-003 Lost backup
passphrase` is unrecoverable by construction) carry a
`executable: false` flag in frontmatter with a reason. Tests skip
them explicitly.

### Staleness and verification cadence

`last_verified` plus `verified_against_version` track freshness.

Staleness rules:

- Any runbook past 90 days since `last_verified` is flagged by the
  monthly audit (iteration 24).
- Any runbook with `verified_against_version` more than one minor
  version behind the current tool version is flagged.
- Verification updates the frontmatter in a small PR: maintainer
  walks the runbook on a fresh workspace, confirms steps still work,
  updates `last_verified` and `verified_against_version`.

Quarterly structural audit surfaces stale runbooks in its report.

### Translation

Runbooks contain Kent-facing text. Per iteration 9's i18n contract:

- Runbook body stays in English (the authoritative contributor
  language).
- Symptom keywords include translations where useful for Kent search.
- `aeat docs runbook` in `hu` or `es` falls back to English with a
  note: "Runbook not yet translated; English follows."
- Full translation is a long-term goal; not a blocker for runbook
  inclusion.

### Runbook writing discipline

A contributor guide at `docs/runbook-authoring.md`:

- Always Kent-first: write as though Kent is typing, not as though
  a developer is debugging.
- Commands copy-paste-ready. Use fixture identifiers or show the
  exact CLI output that provides the identifier.
- Output excerpts come from a recorded fixture run, not imagination.
- Common mistakes get their own subsection if they share a
  signature.
- Cross-link to related runbooks rather than duplicating content.

### Runbook ownership

`owner` in frontmatter points at a team persona (`maintainer-team`,
`security-team`, `portal-watch-team`) rather than a named individual.
Changes in maintainership update the owner once; named-individual
commits would churn.

### Kent roleplay: error-to-runbook flow

Kent runs an export, hits drift:

```text
$ aeat export modelo 390 --period 2024
REFUSED: AEAT portal changed the modelo 390 fichero format on 2026-03-28.
  runbook: `aeat docs runbook portal-drift`  (RB-001)
  see: docs/runbooks/RB-001-portal-drift.md
Exit 4. Code: E_PORTAL_DRIFT_CRITICAL.

$ aeat docs runbook portal-drift
===========================================================
Runbook RB-001: Portal drift
===========================================================
Last verified: 2026-04-24 (tool 0.18.2, corpus 2026.04.24)

When to use this runbook
  - REFUSED: AEAT portal changed the modelo {m} fichero format
  - `export verify` reports "unexpected token" on a freshly downloaded fichero
  - `aeat doctor` shows `portal drift [warn]` or `[critical]`

Kent question
  I want to export my filing but the portal seems to have changed and the
  CLI is refusing. I need to figure out whether to update the tool, the
  corpus, or both, and then retry.

Prerequisites
  - Internet connection (for corpus refresh)
  - aeat-cli 0.18.2 or later
  - Active profile (`aeat configure profile list`)

Steps
  1. List active drift events:
     aeat advanced diagnostics portal-drift list --status open

  2. If any event is CRITICAL, install the hotfix corpus:
     aeat advanced reference corpus refresh

     Expected output:
       Fetching manifest...
       [ok] new URGENT hotfix 2026.04.17 available.
       Installing...
       Installed 2026.04.17.

  3. Confirm drift events are mitigated:
     aeat advanced diagnostics portal-drift list --status open

     Expected output:
       No open drift events.

  4. Retry the original command:
     aeat export modelo 390 --period 2024

Verification
  - Exit code 0 on the retry.
  - `aeat doctor` shows `portal drift [ok]` or `[warn]` (not critical).
  - The exported fichero passes `aeat export verify`.

Follow-up
  - If drift persists after refresh, file a community report:
      aeat advanced diagnostics portal-drift report --modelo 390 ...
  - Subscribe to release notes for future portal-drift events.

Why this happens
  AEAT updates their portal and fichero formats on their own schedule.
  The CLI ships a pinned corpus of schemas and rules; when the portal
  changes, the project ships a hotfix corpus bundle that contains the
  updated rules. `corpus refresh` installs the hotfix.

Related
  - ADR 2026-04-24-aeat-cli-wireframe (portal-drift management)
  - Runbook RB-016 (corpus bundle expired)
  - Issue #116 (safety charter)
```

### Kent roleplay: CLI suggests a runbook

```text
$ aeat transactions automate --period 2026Q1 --with llm
[warning] LLM provider returned rate-limit error (HTTP 429).
Falling back to rule-based classification for this batch.
  runbook: `aeat docs runbook llm-unavailable`  (RB-002)

$ aeat docs runbook llm-unavailable
[... runbook renders ...]
```

### Doc-discipline beyond runbooks

Runbooks are one tier of operational docs. The full doc hierarchy:

| Tier | Location | Purpose |
| --- | --- | --- |
| README | `README.md` | Project elevator pitch; install, quick start |
| Getting started | `docs/getting-started.md` | Kent's first 30 minutes (iteration 13) |
| User guide | `docs/user-guide/*.md` | Per-root walkthroughs (one per hardened root from iteration 1) |
| Migration guides | `docs/migration/vX.Y.md` | Per-release migration notes (iteration 10, 23) |
| Runbooks | `docs/runbooks/*.md` | Scenario recovery procedures (this iteration) |
| Reference | `docs/reference/*.md` | Generated CLI reference from `--help` output |
| ADRs | `.vault/adr/*.md` | Architectural decisions (this document) |
| Release notes | `docs/release-notes/vX.Y.Z.md` | Per-release changelog expansion |
| Contributor docs | `CONTRIBUTING.md`, `docs/audit-methodology.md`, `docs/runbook-authoring.md`, etc. | How to work on the project |

Each tier has its own freshness discipline:

- README: updated with each major release.
- Getting started: updated whenever iteration 13 onboarding changes.
- User guide: updated per root change (iteration 4 migration phases).
- Migration guides: required per release with breaking changes.
- Runbooks: 90-day verification (this iteration).
- Reference: regenerated on every release (from `--help` fixtures,
  iteration 14).
- ADRs: append-only; new decisions create new ADRs.
- Release notes: one per release.
- Contributor docs: updated as processes change.

### Documentation CI

A `tests/audit/test_docs_freshness.py` runs:

- Every linked runbook in README or user-guide exists.
- Every ADR has valid frontmatter (vaultspec enforcement already).
- Every runbook has valid frontmatter.
- Every `docs/release-notes/vX.Y.Z.md` exists for every tagged
  release.
- Every `docs/migration/vX.Y.md` exists for every release that
  introduced a deprecation.
- `README.md` has an up-to-date installation line for the current
  PyPI version.
- Generated CLI reference matches current `--help` output.

### Hardening rules derived from iteration 25

- Every production scenario known to iterations 1 through 24 has a
  runbook in `docs/runbooks/`.
- Runbooks follow strict frontmatter plus body structure. Deviation
  fails CI.
- Every error code in the iteration 6 registry links to a runbook or
  declares `no_runbook_needed`.
- Runbooks are surfaced from the CLI via `aeat docs runbook`.
- Runbook content bundles with the CLI; Kent reads offline.
- Runbook steps are executable against fixture workspaces where
  possible; non-executable runbooks carry an explicit flag.
- Staleness is tracked via `last_verified`; monthly audit flags
  runbooks past 90 days.
- Runbook translation is optional; English remains the authoritative
  version.
- Doc tiers are enumerated and each has a freshness discipline.
- CI verifies every cross-reference and fixture.

### Open risks added by iteration 25

- Runbooks rot silently as the tool evolves. The 90-day verification
  cadence helps but depends on maintainer discipline. An
  auto-execution harness catches drift for executable runbooks.
- Kent may not read runbooks even when prompted. Error messages must
  carry enough context that the runbook is an upgrade, not a
  requirement.
- Runbook translation burden grows with catalogue size. Deferring
  translation until catalogue stabilises is pragmatic but leaves
  non-English speakers with English runbooks.
- The executability harness requires fixture workspaces for every
  runbook. Fixture proliferation is a maintenance cost.
- Runbook step commands become inaccurate when a CLI alias sunsets
  (iteration 10 Phase D). Release-gate check must update every
  runbook that references a sunset alias.
- Runbook cross-references create a graph; dead references must be
  caught by the docs-freshness test.
- `aeat docs runbook search` is full-text search; scale depends on
  catalogue size. At 100+ runbooks the search may need indexing.
- Runbook ownership by persona rather than individual means tracking
  accountability is blurred. The team personas must map to real
  responsibilities in project governance.
- Off-line runbook bundling with the CLI increases wheel size by the
  markdown bundle. Acceptable for runbook text; unacceptable if
  we ever add screenshots.
- Runbooks disclose operational patterns; a malicious reader can
  learn how the CLI stores credentials, how the backup format works,
  and where trust anchors live. This is transparent-by-design; it
  must be balanced against the security value of obscurity, and the
  project chooses transparency. Sensitive details (private keys,
  passwords) never appear in runbooks.

## Hardening pass iteration 26 (2026-04-24)

Iteration 26 focus: per-profile master keys. Iteration 12 specified a
single workspace-wide master key that unlocks every profile's
encrypted credentials. Iteration 11 made multi-profile first class.
The combination means compromise of the single key exposes every
profile simultaneously. This iteration replaces the workspace-wide
master key with per-profile master keys, contains the blast radius,
specifies rotation and migration, and handles keystore-quota
limitations.

### Motivation

Under the iteration 12 model, compromise of the workspace master key
exposes personal certificate, company-sl certificate, OAuth refresh
tokens for every profile, and browser sessions for every profile
simultaneously. Kent's three profiles share one key-management fate.

Per-profile keys split the fate. Compromise of the personal profile's
key reveals only personal credentials; company-sl and friend profiles
stay protected. This matches the profile-isolation discipline
iteration 11 established at the data layer.

### Keystore entry shape

Each profile holds its own master key in the OS keystore under a
profile-scoped service name and username:

| Keystore slot | Value |
| --- | --- |
| service | `aeat-workspace:{workspace_hash}` |
| username | `profile:{profile_id}:master-key:v{version}` |
| secret | 256-bit random key |

`workspace_hash` is the SHA-256 of the workspace root path plus a
per-workspace salt (the same salt iteration 15 uses for telemetry).

Per-profile entry examples (three profiles, current key version 1):

```text
aeat-workspace:a1b2c3d4  profile:personal:master-key:v1        <256-bit>
aeat-workspace:a1b2c3d4  profile:company-sl:master-key:v1      <256-bit>
aeat-workspace:a1b2c3d4  profile:friend-juan:master-key:v1     <256-bit>
```

### Key derivation chain

Each profile master key derives per-credential-kind encryption keys
through HKDF-SHA-256:

```python
encryption_key = HKDF(
    master=profile_master_key,
    salt=f"aeat-v1-{profile_id}-{credential_kind}".encode(),
    info=f"aeat-credential-{credential_kind}".encode(),
    length=32,
)
```

Credential kinds: `certificate`, `oauth_refresh_token`,
`browser_session`, `workspace_config_extras`.

Derivation means a compromised sub-key reveals only one credential
kind within one profile. The master key is never used directly to
encrypt credential files.

### Key provisioning

`aeat configure profile add --id <id> ...` generates a fresh 256-bit
master key through the OS cryptographic RNG and stores it in the
keystore under the profile-scoped slot. First auth login for the
profile uses it to encrypt credentials.

If the keystore backend refuses multi-entry insertion (some legacy
Linux fallbacks are single-entry), the CLI falls back to:

- Storing one "umbrella" keystore secret per workspace.
- Deriving per-profile master keys through HKDF against the umbrella
  secret, keyed by profile_id.

This fallback partially defeats the blast-radius goal: umbrella
compromise still exposes every profile's derived keys. The fallback
is logged to `aeat doctor` as `keystore-backend-limited` and carries
a clear warning. The default path uses a true multi-entry keystore.

### Rotation

Per-profile rotation:

```text
aeat auth rotate-master-key --profile personal
```

Flow:

1. Generate a new master key v(N+1).
2. For each credential file under `var/profiles/personal/auth/`:
   a. Decrypt with current key v(N).
   b. Re-encrypt with key v(N+1).
   c. Write atomically (iteration 8 write-rename).
3. Store v(N+1) in the keystore.
4. Retain v(N) for 30 days (read-only) to absorb any torn rotation.
5. After 30 days, remove v(N) from the keystore.

Cross-profile rotation:

```text
aeat auth rotate-master-key --all-profiles
```

Iterates per-profile with independent success/failure per profile.
A failure on one profile does not rollback others; the command
reports a partial-success summary.

Scheduled rotation: `configure defaults set auth_rotation_interval_days 365`
enables automatic rotation on `aeat doctor` run after the interval.

### Migration from workspace key to per-profile keys

Existing workspaces created before iteration 26 have a single
workspace-wide master key. Migration command:

```text
aeat configure migrate-to-per-profile-keys
```

Flow:

1. Read the workspace-wide master key from the keystore.
2. Enumerate profiles.
3. For each profile:
   a. Generate a new per-profile master key.
   b. Decrypt credentials with the workspace key.
   c. Re-encrypt with the per-profile key.
   d. Insert per-profile key into keystore.
4. After all profiles migrate successfully:
   a. Delete the workspace-wide master key from the keystore.
   b. Emit an audit event per profile.
5. On any failure: rollback (re-encrypt with the workspace key,
   remove any inserted per-profile keys). Workspace-wide key
   remains intact until migration fully succeeds.

Migration is atomic at the profile level; partial migration is not
allowed because it leaves the workspace in a half-migrated state.

Migration produces a `migration-report.json`:

```json
{
  "migrated_at": "2026-04-24T14:00:00Z",
  "from_version": "workspace-wide-v1",
  "to_version": "per-profile-v1",
  "profiles_migrated": ["personal", "company-sl", "friend-juan"],
  "profiles_failed": [],
  "rollback_performed": false,
  "audit_events_written": 3
}
```

### Envelope shape

Every encrypted credential file carries an envelope that survives
key rotation:

```json
{
  "envelope_version": "2.0",
  "key_id": "profile:personal:master-key:v1",
  "credential_kind": "certificate",
  "algorithm": "aes-256-gcm",
  "kdf": "hkdf-sha256",
  "kdf_salt": "base64",
  "nonce": "base64",
  "aad": "profile:personal:certificate:v1",
  "ciphertext": "base64",
  "created_at": "2026-04-24T14:00:00Z"
}
```

`envelope_version` `1.0` was iteration 12's workspace-key envelope;
`2.0` is the per-profile envelope. Readers accept both but writers
only emit `2.0` after migration.

### Revoke scope

Iteration 12's `aeat auth revoke --all --confirm` wiped the single
workspace master key plus every credential file. The iteration 26
rewrite scopes by profile:

| Command | Effect |
| --- | --- |
| `aeat auth revoke --profile personal --provider certificate` | Delete one credential file for one profile; master key untouched. |
| `aeat auth revoke --profile personal --all` | Delete every credential file for one profile; delete that profile's master key from keystore. |
| `aeat auth revoke --all-profiles --confirm` | Iterate `--profile X --all` across every profile. |

The `--all-profiles` form is the former `--all` flag. Kent's mental
model stays the same: one command wipes everything. The guardrails
(interactive confirmation with literal `revoke-all`, next-steps
instructions per iteration 12) are unchanged.

### Compromise response

On suspected compromise of one profile's master key:

1. `aeat auth revoke --profile <id> --all` wipes that profile.
2. Kent revokes upstream credentials at the provider (FNMT, Google
   OAuth, etc.).
3. Other profiles remain unaffected.

Previously a compromise required wiping the entire workspace.
Iteration 26 narrows the response.

### Audit events

Per-profile key lifecycle events append to
`var/profiles/{profile_id}/auth/events/{yyyy-mm-dd}.jsonl`:

- `master_key_provisioned`: on first creation (profile add).
- `master_key_rotated`: with version before/after.
- `master_key_revoked`: on revoke-all.
- `master_key_migrated_from_workspace`: on iteration 26 migration.

Events carry no key material, only key IDs and timestamps.

### Keystore-quota handling

Some keystores limit entry count (for example macOS Keychain
default, SecretService on some constrained installs). Quota rules:

- CLI queries keystore quota at first provisioning.
- Quota approaching (less than 10 entries remaining): warn in
  `aeat doctor`.
- Quota exhausted: refuse `profile add` with a clear error and
  suggest either removing an unused profile or migrating to the
  HKDF-umbrella fallback.

### `aeat doctor` integration

Per-profile master-key health becomes a doctor check:

```text
  master key (personal)             [ok]       v1 active, 1 older retained
  master key (company-sl)           [ok]       v1 active
  master key (friend-juan)          [warn]     v1 is 14 months old; rotation recommended
  keystore backend                  [ok]       windows-credential-manager (multi-entry)
  keystore quota                    [ok]       12 entries used / unlimited
  workspace-wide legacy key         [ok]       not present (migration complete)
```

### Backup implications

Backups (iteration 17) already exclude `auth/`. Per-profile keys
reinforce this:

- Backups never carry keystore contents.
- Restore on a new machine prompts fresh per-profile key provisioning
  alongside `aeat auth login`.
- Because credentials are excluded from backup, fresh key
  provisioning produces a clean state with no legacy-key residue.

### Kent roleplay: compromise of friend profile

Kent helped his friend Juan with his taxes. Juan later reports his
laptop stolen. Kent needs to contain the breach.

```text
$ aeat auth revoke --profile friend-juan --all
[profile] friend-juan (Y9876543X)
[warning] This command deletes every credential for one profile and
wipes its master key from the keystore.

Type the literal word `revoke-juan` to confirm: revoke-juan

Revoking credentials for profile 'friend-juan':
  [ok] deleted certificate.pfx
  [ok] deleted oauth/google_workspace.json
  [ok] cleared browser/session.json
  [ok] wiped auth/events index
  [ok] removed master key from keystore

Next steps for profile 'friend-juan':
  1. Revoke Juan's FNMT certificate at https://www.sede.fnmt.gob.es
  2. Revoke Juan's Google OAuth client at https://myaccount.google.com/permissions
  3. Help Juan rotate any other shared credentials.

Profiles 'personal' and 'company-sl' are unaffected.
```

Kent's personal and company-sl profiles remain fully operational.

### Kent roleplay: scheduled rotation

```text
$ aeat auth rotate-master-key --profile personal
[profile] personal (X1234567L)
Rotating master key for profile 'personal'...
  current version: v1 (provisioned 2025-04-24)
  generating new version: v2

  re-encrypting credentials:
    [ok] certificate.pfx
    [ok] oauth/google_workspace.json
    [ok] browser/session.json

  storing v2 in keystore
  retaining v1 for 30 days (absorbs any torn rotation)

[ok] rotation complete.
```

### Kent roleplay: migration

```text
$ aeat configure migrate-to-per-profile-keys
Detected workspace-wide master key (iteration-12 format).
Migrating to per-profile master keys (iteration-26 format).

  profile 'personal':
    [ok] generated per-profile master key
    [ok] re-encrypted certificate.pfx
    [ok] re-encrypted oauth/google_workspace.json
    [ok] re-encrypted browser/session.json
    [ok] stored key in keystore

  profile 'company-sl':
    [ok] generated per-profile master key
    [ok] re-encrypted certificate.pfx
    [ok] re-encrypted oauth/google_workspace.json
    [ok] stored key in keystore

All profiles migrated. Removing workspace-wide legacy key.
  [ok] keystore cleaned.

Migration report: var/audit/migration-2026-04-24-to-per-profile-keys.json
```

### Hardening rules derived from iteration 26

- Each profile holds its own master key in the OS keystore under a
  profile-scoped slot.
- Credential encryption derives sub-keys from the profile master key
  through HKDF with `(profile_id, credential_kind)` in the salt.
- Per-profile rotation is a first-class command; cross-profile
  rotation iterates independently.
- Migration from workspace-wide master key to per-profile keys is a
  first-class, atomic-per-profile command with rollback.
- Envelope version 2.0 carries `key_id` so rotation is compatible
  with older envelopes during a 30-day overlap.
- Revoke scope is per-profile; `--all-profiles` iterates.
- Keystore-quota limits are detected and reported; fallback to HKDF
  umbrella mode is available for constrained keystores with a clear
  warning.
- `aeat doctor` surfaces per-profile key health, rotation age, and
  keystore capacity.
- Every key lifecycle event appends to the per-profile auth event
  log.
- Backups continue to exclude `auth/` contents; per-profile keys
  never appear in backup archives.

### Open risks added by iteration 26

- Keystore quota exhaustion on constrained platforms limits how many
  profiles Kent can maintain. The HKDF-umbrella fallback trades
  isolation for capacity.
- HKDF-umbrella fallback is a security regression relative to true
  per-profile keys. It must be the last-resort option; default path
  uses true multi-entry keystore.
- Migration from workspace-wide to per-profile keys must succeed
  atomically per profile. A torn migration (partial success) is
  possible if the keystore fails mid-operation; the rollback
  procedure must cover this.
- Keystore compromise still cascades to every profile on the same
  machine; per-profile keys do not defend against an attacker with
  full OS access, only against leaks of a single key's ciphertext.
- Rotation cadence defaults (365 days) are a policy decision Kent
  may override. A 30-day overlap during rotation risks old-key
  exposure; the overlap window is a documented trade-off.
- Audit events log key IDs but not versions; a rotation that reuses
  a key id under a new version (shouldn't happen but could via bug)
  would pollute the audit trail. The version suffix on `key_id`
  mitigates.
- HKDF info strings must be stable across releases. Changing the
  derivation formula breaks every existing envelope; such a change
  requires a new envelope version and full re-encryption.
- `aeat doctor` surfacing key age risks nagging Kent into
  unnecessary rotation. The default warn-at-12-months threshold is
  a balance; configurable.
- Per-profile keys reduce workspace blast radius but add complexity
  to the mental model: Kent must understand that revoke is scoped
  per profile. Documentation and doctor output must keep the
  per-profile nature explicit.
- Key provisioning at profile creation is blocking on keystore
  availability. A keystore outage at `configure profile add` time
  refuses the add; the CLI must report this clearly rather than
  creating a credential-less profile that silently refuses auth
  login later.
- Shared workspaces (one OS user, multiple accountants) remain
  unsupported: keystore entries are OS-user scoped. The
  delegated-access model (iteration 29) handles multi-user
  collaboration at a different layer.

## Hardening pass iteration 27 (2026-04-24)

Iteration 27 focus: Autoliquidación Rectificativa IVA deep dive. AEAT
introduced a new path for correcting IVA autoliquidaciones post-2023
that replaces the classical rectificativa for modelos 303 and 322.
Iteration 2 noted the distinction but left it as an open risk.
Iteration 18 required the support matrix to distinguish them.
Iteration 27 specifies the full semantics, registry entries,
validator rules, chain-walk behaviour, and Kent-facing guidance so
the CLI ships correct ARI handling rather than collapsing everything
under a single `rectificativa` kind.

### Two distinct rectificativa paths

Classical rectificativa (pre-2023 and legacy modelos):

- Filed as a formal request to AEAT under Article 120.3 of Ley
  58/2003 (LGT).
- Submitted through a separate AEAT portal procedure
  (`solicitud de rectificación`).
- Response timeline 6 to 12 months.
- Refunds processed through a separate devolución after AEAT
  confirms.
- Not emitted as a new autoliquidación fichero BOE.

Autoliquidación Rectificativa IVA (ARI, post-2023 for modelos 303
and 322; extended to other modelos over time):

- Filed as a new autoliquidación with an ARI indicator in the fichero
  BOE.
- Submitted through the standard modelo endpoint (same portal path
  as the original filing).
- AEAT processes directly; response timeline 1 to 3 months.
- Refunds flow through the ARI itself when casilla 73 or equivalent
  is populated.
- Replaces the prior accepted autoliquidación for the period (may
  itself be replaced by a subsequent ARI).

Kent needs both paths because:

- ARI is only available for ejercicios from 2023 onwards and only
  for modelos in the ARI-enabled set.
- Classical rectificativa remains the only path for older ejercicios
  and for modelos that AEAT has not yet brought under ARI.

### Amendment-kind enum expansion

Iteration 2 proposed three amendment kinds:
`complementaria`, `rectificativa`, `sustitutiva`. Iteration 27
replaces `rectificativa` with two distinct values:

```python
class AmendmentKind(StrEnum):
    COMPLEMENTARIA = "complementaria"
    RECTIFICATIVA_ARI = "rectificativa-ari"
    RECTIFICATIVA_CLASSIC = "rectificativa-classic"
    SUSTITUTIVA = "sustitutiva"
```

Migration from the iteration 2 enum: any persisted amendment record
with `amendment_kind="rectificativa"` is rewritten during startup
detection into the correct value per modelo plus ejercicio context:

- `(303, 2023+)` or `(322, 2023+)` migrates to `RECTIFICATIVA_ARI`.
- Otherwise migrates to `RECTIFICATIVA_CLASSIC`.

A regression test confirms migration is lossless and idempotent.

### Updated support registry

Representative rows in `src/aeat/revise/_registry.py`:

| Modelo | Ejercicio | Kind | Supported | Requires portal follow-up |
| --- | --- | --- | --- | --- |
| `130` | 2024 | `complementaria` | yes | no |
| `130` | 2024 | `rectificativa-ari` | no | n/a |
| `130` | 2024 | `rectificativa-classic` | yes | yes |
| `130` | 2024 | `sustitutiva` | n/a | n/a |
| `303` | 2022 | `complementaria` | yes | no |
| `303` | 2022 | `rectificativa-ari` | no (pre-2023) | n/a |
| `303` | 2022 | `rectificativa-classic` | yes | yes |
| `303` | 2023 | `complementaria` | yes | no |
| `303` | 2023 | `rectificativa-ari` | yes (from 2023Q4) | no |
| `303` | 2023 | `rectificativa-classic` | yes | yes |
| `303` | 2024 | `complementaria` | yes | no |
| `303` | 2024 | `rectificativa-ari` | yes | no |
| `303` | 2024 | `rectificativa-classic` | yes (residual) | yes |
| `322` | 2024 | `rectificativa-ari` | yes | no |
| `390` | 2024 | `complementaria` | n/a (informativa) | n/a |
| `390` | 2024 | `rectificativa-ari` | no | n/a |
| `390` | 2024 | `rectificativa-classic` | yes (limited) | yes |
| `390` | 2024 | `sustitutiva` | yes | no |

`RevisionSupport` records gain a `requires_portal_follow_up: bool`
field that surfaces through `aeat revise start` help:

```python
class RevisionSupport(BaseModel):
    modelo: ModeloId
    ejercicio: Year
    kind: AmendmentKind
    supported: bool
    notes_es: str
    notes_en: str
    notes_hu: str
    requires_portal_follow_up: bool
    first_supported_period: str | None       # e.g. "2023Q4" for ARI rollout
    ari_rollout_status: Literal["full", "partial", "pending", "not_applicable"]
```

### ARI filing validator rules

`src/aeat/application/filing/_validators/_ari.py` enforces:

1. `baseline_submission` must exist with `status=ACCEPTED`.
2. `baseline_submission.modelo` equals the ARI's modelo.
3. `baseline_submission.period` equals the ARI's period.
4. `baseline_submission.profile_tax_id` equals the ARI's
   `profile_tax_id`.
5. Ejercicio >= the first-supported ejercicio from the registry.
6. ARI indicator field in the fichero BOE is set to the correct
   value for the modelo.
7. Delta is computed against the baseline (not against a cumulative
   view).
8. If casilla 73 (refund) is populated, bank-account validation
   runs.
9. The draft references `parent_submission_id` pointing at the
   latest accepted filing in the chain (original or prior ARI).
10. Cumulative delta across the chain is tracked for Kent-facing
    review, not for AEAT emission.

Each rule has a dedicated finding with code, severity, and
corresponding i18n-catalogue entry.

### ARI chain semantics

ARI can stack: original filing, then ARI #1, then ARI #2, and so
on. Each ARI references the immediately prior accepted filing.

Chain walk rules (extending iteration 2):

- `latest_accepted_submission(modelo, period, profile_tax_id)`
  walks by `submitted_at` and selects the most recent
  `status=ACCEPTED` entry regardless of whether it is the original,
  a complementaria, a classical rectificativa result, or an ARI.
- ARI always references the latest accepted, not the original.
- A rejected ARI does not break the chain; Kent's next attempt
  still references the latest accepted filing, which is the
  pre-rejection state.
- Classical rectificativa followed by ARI is supported in principle;
  the classical outcome (once AEAT processes it) becomes the new
  accepted baseline, and a later ARI references that.

Chain visualisation for Kent:

```text
$ aeat records amendments list --modelo 303 --period 2024Q2
[profile] personal (X1234567L)

Amendment chain for 303/2024Q2:

  submission_id   kind                 submitted_at  status     justificante
  sf_abc123       original             2024-07-22    ACCEPTED   2024-303-Q2-X...ABC
  amd_def456      complementaria       2024-11-03    ACCEPTED   2024-303-Q2-X...DEF
  amd_xyz789      rectificativa-ari    2025-03-05    ACCEPTED   2024-303-Q2-X...XYZ
  (current baseline for future revises)
```

### Choosing between complementaria and ARI

For modelo 303 post-2023, Kent has two valid paths for corrections:

- **Complementaria**: additive correction that increases liability.
  Fast path; no baseline verification beyond the standard chain
  walk.
- **Autoliquidación Rectificativa IVA**: any correction, including
  liability decreases and refund claims. Replaces baseline; AEAT
  processes via standard autoliquidación flow.

Decision tree surfaced through `aeat revise start 303 --help`:

```text
--kind {complementaria|rectificativa-ari|rectificativa-classic}

  complementaria
    Use when the corrected figure INCREASES your IVA liability.
    Fastest path; the filing is additive and AEAT processes it in
    the normal way.

  rectificativa-ari
    Use when the corrected figure DECREASES liability or you need a
    refund, OR when AEAT has rejected a prior filing for this
    period and you need to replace it.
    Available from ejercicio 2023 onwards for modelos 303 and 322.
    AEAT processes in 1 to 3 months.

  rectificativa-classic
    Only for ejercicios or modelos where ARI is not available.
    Requires a separate formal request on the AEAT portal; the
    CLI produces supporting evidence but does not emit a fichero BOE
    for this kind.
    Processing timeline 6 to 12 months.

Registry truth for 303/2024Q2 (your request):
  complementaria        supported      increases liability only
  rectificativa-ari     supported      liability decreases or refund
  rectificativa-classic supported      residual; not usually needed
```

### `revise start` prompts on ambiguous intent

When Kent runs `aeat revise start 303 --period 2024Q2 --kind
rectificativa-ari` and the computed delta shows the liability
unchanged, the command emits a confirmation prompt:

```text
[profile] personal (X1234567L)
The computed delta for 303/2024Q2 does not change total liability.
  current baseline:   (casilla 71 = 1 200.00 EUR)
  ARI delta:          (casilla 71 = 1 200.00 EUR; no change)

ARI is typically used for liability changes or refunds. Proceed with
an ARI that carries no delta? [y/N]:
```

Similar prompt fires when the delta would increase liability and
`--kind rectificativa-ari` is chosen (suggesting complementaria as a
simpler path):

```text
The computed delta would INCREASE liability by 450.00 EUR.
Complementaria is the simpler path for liability increases.
Use ARI anyway? [y/N]:
```

### Classical rectificativa support path

`aeat revise start 303 --period 2022Q1 --kind rectificativa-classic`
cannot emit a fichero BOE (there is no AEAT fichero for classical
rectificativa). The CLI instead produces:

1. A supporting-evidence bundle:
   `var/profiles/<id>/audit/rectificativa-classic/{amendment_id}.zip`
   containing the prior filing receipt, the proposed delta, the
   referenced normatives (Art. 120.3 LGT), and a reasoned summary.
2. A guided text for the solicitud de rectificación Kent uploads
   manually through the AEAT portal.
3. An amendment record flagged `portal_follow_up=true` so `records
   amendments list` clearly shows the pending status.

```text
$ aeat revise start 303 --period 2022Q1 --kind rectificativa-classic
[profile] personal (X1234567L)
Creating classical rectificativa case for 303/2022Q1...
  baseline: submission sf_def456 (justificante: 2022-303-Q1-X...DEF)
  ejercicio: 2022 (ARI not available pre-2023)

Amendment case created: amd_old789 (portal follow-up required)

Next steps:
  1. Inspect delta: `aeat draft show 303 --period 2022Q1 --revision amd_old789`
  2. Approve: `aeat review approve amd_old789`
  3. Export evidence bundle: `aeat audit export 303 --period 2022Q1 --revision amd_old789`
  4. Upload manually at AEAT sede: follow instructions at docs/runbooks/RB-017-rectificativa-classic-upload.md

AEAT response typically 6 to 12 months. You will need to file a
separate devolución claim when AEAT accepts your rectification.
```

### Refund routing

For ARI filings that claim a refund (casilla 73 or equivalent):

- Validator verifies IBAN format and checksum.
- Validator verifies IBAN country code is ES or another SEPA-allowed
  country (configured in registry).
- Validator verifies the IBAN is persisted under `configure defaults
  set refund_iban <iban>` or passed explicitly via
  `--refund-iban <iban>`.
- Refund amount is computed from the delta and must match casilla 73
  within rounding tolerance.

For complementaria or classical rectificativa, refund casillas are
refused: those paths do not carry refund claims through the
fichero.

### Kent roleplay: forgotten deductible invoice

March 2025. Kent filed 303/2024Q2 in July 2024. He discovers a
deductible invoice he forgot to include. Liability goes down by 450
EUR; refund available.

```text
$ aeat data edit invoice inv_ccc123
[profile] personal (X1234567L)
Updated invoice inv_ccc123:
  new category: supplier_purchase (deductible)
  new period:   2024Q2

$ aeat revise start 303 --period 2024Q2 --kind rectificativa-ari
[profile] personal (X1234567L)
Creating ARI revise case for 303/2024Q2...
  baseline: amd_def456 (complementaria accepted 2024-11-03)
  ejercicio: 2024 (ARI supported from 2023)
  registry status: ARI full

Amendment case created: amd_xyz789

$ aeat draft create 303 --period 2024Q2 --revision amd_xyz789
[profile] personal (X1234567L)
Building ARI draft for 303/2024Q2...
  [ok] delta vs baseline (amd_def456):
        casilla 28 (IVA deducible): +450.00 EUR
        casilla 71 (resultado):     -450.00 EUR (refund)
  [warn] 1 finding: refund IBAN required

$ aeat configure defaults set refund_iban ES9121000418450200051332
[profile] personal (X1234567L)
Stored refund IBAN for profile 'personal'.

$ aeat draft create 303 --period 2024Q2 --revision amd_xyz789
[profile] personal (X1234567L)
Building ARI draft for 303/2024Q2...
  [ok] delta vs baseline: -450.00 EUR (refund)
  [ok] IBAN validated

$ aeat review approve draft 303/2024Q2 --revision amd_xyz789
[profile] personal (X1234567L)
Approved draft 303/2024Q2 (ARI).

$ aeat export modelo 303 --period 2024Q2 --kind rectificativa-ari --revision amd_xyz789
[profile] personal (X1234567L)
Exporting ARI fichero for 303/2024Q2...
  indicator: ARI
  baseline: 2024-303-Q2-X...DEF (accepted 2024-11-03)
  ejercicio: 2024 (ARI supported)
  refund casilla 73: 450.00 EUR to IBAN ES91 2100 0418 ...

[ok] fichero: var/profiles/personal/exports/303-2024Q2-ARI-2025-03-05.boe
     sha256: abcd1234...

Upload at AEAT sede (standard modelo 303 endpoint). ARI processing
typically 1 to 3 months.
```

### Validator for ARI-chain integrity

A dedicated validator runs on every ARI emission:

- Confirms chain integrity: every prior amendment in the chain is
  ACCEPTED.
- Confirms cumulative delta makes arithmetic sense (no rounding
  inconsistencies accumulating silently).
- Confirms no prior ARI in the chain is pending AEAT processing
  (a pending ARI means the baseline is not yet stable; Kent must
  wait).

If a prior ARI is pending, the validator refuses:

```text
REFUSED: A prior ARI (amd_prev_rst, submitted 2025-02-14) is still
pending AEAT processing. The baseline is not yet stable.
  -> Wait for AEAT acceptance, then re-run: aeat revise start 303 --period 2024Q2 --kind rectificativa-ari.
  -> Or inspect the chain: aeat records amendments list --modelo 303 --period 2024Q2.
Exit 3. Code: E_ARI_PENDING_CHAIN.
```

### Documentation and runbook

Runbook RB-021 (new) documents ARI flow: "Refund or correction for
IVA 303". It references this iteration and the registry. Also
references RB-017 for classical rectificativa fallback.

### Hardening rules derived from iteration 27

- `AmendmentKind` enum distinguishes four kinds; legacy
  `rectificativa` migrates losslessly per context.
- `RevisionSupport` registry carries `requires_portal_follow_up`,
  `first_supported_period`, and `ari_rollout_status` fields.
- ARI validator enforces baseline integrity, modelo alignment,
  ejercicio cutoff, indicator field, delta-against-baseline, and
  refund IBAN validation.
- Chain walk handles ARIs as first-class amendments; pending ARI
  blocks new ARIs.
- Help text explains kind selection with a decision tree and
  registry truth for the invocation.
- Classical rectificativa produces an evidence bundle plus portal
  follow-up instructions instead of a fichero BOE.
- Refund routing restricted to ARI and standard autoliquidación;
  complementaria and classical paths refuse refund casillas.
- `aeat revise start` prompts on ambiguous intent (no delta, or
  delta direction mismatched with kind).
- Runbook RB-021 documents the end-to-end ARI flow; RB-017 covers
  classical rectificativa.

### Open risks added by iteration 27

- AEAT may extend ARI to other modelos (322 already; future 303,
  100, 130, 349 potentially). Registry must track rollout; rollout
  updates arrive through corpus bundle (iteration 19).
- Ejercicio cutoff (2023 for 303) may shift. Registry
  per-ejercicio support matrix handles this but requires timely
  updates when AEAT shifts the cutoff.
- Classical rectificativa and ARI coexist post-2023; Kent
  mistakenly choosing classical when ARI is faster is a UX hazard.
  Decision-tree help and the ambiguous-intent prompt mitigate.
- Refund IBAN validation requires a checksum implementation for
  Spanish plus SEPA IBANs. The implementation must be tested with
  real-format fixtures.
- Pending-ARI block on new ARI may trap Kent if AEAT processing
  stalls. A manual override flag
  `--allow-pending-chain --reason <text>` exists but its use is
  logged audit-level.
- Cumulative-delta arithmetic across long chains accumulates
  rounding. The validator enforces a tolerance but cannot eliminate
  all cases; complex chains should escalate to human review.
- ARI indicator field values may change between AEAT BOE versions.
  The registry's `fichero_format` entry per iteration 18 carries
  the exact indicator; corpus updates must keep this current.
- Kent may have old `rectificativa` records from pre-iteration-27
  installs. Migration is automatic but a test must validate
  round-trip correctness across realistic fixtures.
- The classical rectificativa evidence bundle produces guidance
  text for the AEAT portal upload. That text becomes stale if AEAT
  changes the portal flow; runbook RB-017 is the source of truth
  and must be re-verified quarterly (iteration 25 cadence).
- Grupo IVA (modelo 322) is a more complex case than 303; the
  registry distinguishes them but full 322 support requires
  additional iteration beyond this one.

## Hardening pass iteration 28 (2026-04-24)

Iteration 28 focus: GDPR compliance and data retention. Kent is a
Spanish autonomo processing personal data of himself, his
counterparties, and potentially employees. The CLI holds financial
records that are legally retention-regulated and simultaneously
GDPR-regulated. This iteration specifies retention policy per
subsystem, data-subject-right support (access, portability,
erasure), subject-access-request handling for counterparty data,
consent management for LLM processing, crypto-shredding, and the
documentation stack that helps Kent stay compliant.

### GDPR framing

Kent operates in the EU; the CLI processes personal data. Roles:

- Kent is both a data subject (for his own personal data) and a
  data controller (for counterparty data in his records).
- AEAT is the recipient for filed returns.
- LLM providers (when Kent opts in) are processors of a narrow data
  slice.
- The project itself, as the CLI author, is not a controller for
  Kent's workspace; the CLI runs locally.

GDPR obligations this iteration addresses:

- Transparency: Kent can enumerate what is stored and why.
- Data minimisation: the CLI collects only what tax filing requires.
- Purpose limitation: LLM processing requires explicit consent.
- Storage limitation: retention defaults align with Spanish tax law.
- Integrity and confidentiality: per iterations 12, 26.
- Accountability: audit trails, consent logs, PIA template.

### Retention policy per subsystem

Spanish legal baselines that set minimum retention:

- LGT Art. 66 and 70: tax records at least four years (statute of
  limitations on assessments).
- Codigo de Comercio Art. 30: accounting records at least six years.
- Ley del IS: corporate-tax records at least ten years.

Default retention in the CLI reflects these baselines. Kent may
extend retention for his own reasons; retention below the legal
minimum is refused with a clear error.

| Subsystem | Default retention | Legal basis | Config key |
| --- | --- | --- | --- |
| Submissions + amendments | indefinite | LGT, Codigo de Comercio | `submissions_retention_days` |
| Drafts (approved) | indefinite | linked to submissions | `drafts_approved_retention_days` |
| Drafts (unapproved) | 365 days | work-in-progress | `drafts_unapproved_retention_days` |
| Transactions + evidence | 6 years | Codigo de Comercio | `transactions_retention_days` |
| Audit bundles | 6 years | legal evidence | `audit_bundles_retention_days` |
| Logs | 90 days (iteration 15) | operational | `log_retention_days` |
| Metrics | 180 days (iteration 15) | operational | `metrics_retention_days` |
| RunTrace | 365 days | operational | `runtrace_retention_days` |
| Auth events | 365 days | security | `auth_events_retention_days` |
| LLM prompt audit | 365 days | audit | `llm_prompt_retention_days` |
| Decision journal | indefinite | part of submitted-filing evidence | `decision_journal_retention_days` |

Retention enforcement:

- Daily prune at CLI startup deletes records past retention.
- Attempting to set retention below the legal minimum refuses with
  `E_RETENTION_BELOW_LEGAL_FLOOR` and cites the applicable article.
- Retention changes persist per-profile at
  `configure defaults set <key> <days>`.

### Data catalogue

`aeat configure data-catalogue` renders a Kent-facing inventory:

```text
$ aeat configure data-catalogue
[profile] personal (X1234567L)

Data catalogue:

  Submissions and amendments
    count:        12 filings, 3 amendments
    oldest:       2019-07-20
    retention:    indefinite (legal floor: 4 years LGT)
    location:     var/profiles/personal/submissions/

  Transactions and evidence
    count:        5 032 transactions, 247 invoices, 89 receipts
    oldest:       2019-01-05
    retention:    6 years (legal floor: 6 years CdC)
    location:     var/profiles/personal/transactions/, evidence/

  ...

Run `aeat configure data-catalogue --kind transactions --detail` to inspect.
```

The catalogue is the entry point for Kent's transparency obligation
and for any subject-access request he fields.

### Right of access (self-service)

Kent asking "what does the tool know about me?":

```text
aeat configure data-catalogue
aeat records filings list --all-profiles
aeat records receipts list --all-profiles
aeat records notifications list --all-profiles
aeat records amendments list --all-profiles
```

Every command produces the same information Kent could reach through
operational flows; nothing is hidden.

### Data portability

Per GDPR Art. 20, Kent has the right to receive his data in a
structured, commonly-used, machine-readable format.

```text
aeat configure export-personal-data --output ./kent-data-export.zip \
    [--profile <id>] [--format json|csv|both]
```

Behaviour:

- Walks every subsystem for the selected profile(s).
- Exports JSON records (canonical) plus CSV projections for the
  tabular subsystems (transactions, invoices, receipts, amendments).
- Includes PDF copies of evidence files unchanged.
- Includes a machine-readable schema directory so the recipient can
  parse without the CLI.
- Produces a manifest at bundle root with SHA-256 per file.
- Excludes auth/ (iteration 17 rule carried over).

This is distinct from `configure backup create`:

- Backup: operational snapshot for restore.
- Export-personal-data: GDPR-shaped portability artefact with
  schemas and documentation Kent can hand to anyone.

### Right to erasure

Per GDPR Art. 17, Kent has the right to have his data deleted.

```text
aeat configure erase-personal-data \
    --scope all|profile|period \
    [--profile <id>] [--from <period> --to <period>] \
    --i-acknowledge-legal-retention-obligations
```

Scope options:

- `all`: every profile's workspace records.
- `profile`: one profile.
- `period`: records within a period range under a profile.

Behaviour:

1. Verify the requested erasure does not violate a legal retention
   floor. For records within the legal floor window, refuse by
   default:

   ```text
   REFUSED: Tax law requires retention until 2028-07-20 for modelo 303/2024Q2.
     -> Wait until 2028-07-21 to erase this period.
     -> Or override with `--i-understand-legal-obligations-and-override` plus `--reason <text>`.
   Exit 4. Code: E_RETENTION_BELOW_LEGAL_FLOOR.
   ```

2. On explicit override or past-floor records:
   - Remove JSONL records and evidence files.
   - Crypto-shred encryption keys (per-profile master key if `scope=profile` or above; see iteration 26 rotation).
   - Best-effort overwrite of file contents before deletion
     (best-effort because SSDs may retain data outside the
     filesystem's view).
   - Write an audit event.
   - Emit a deletion-report under
     `var/profiles/<id>/audit/deletion-reports/{yyyy-mm-dd}.json`
     listing scope, record counts, actor, reason.

3. Never touches auth/ beyond master-key revocation; credentials
   must be revoked upstream at providers (iteration 12, 26).

4. Never modifies upstream AEAT records. Kent erasing locally does
   not erase what AEAT holds; that is AEAT's legal obligation.

Example:

```text
$ aeat configure erase-personal-data --scope period --profile personal --from 2015Q1 --to 2018Q4
[profile] personal (X1234567L)

Planned erasure scope: personal / 2015Q1 to 2018Q4

  submissions (accepted, past retention): 16
  drafts:                                    16
  transactions:                           8 342
  invoices:                                 412
  receipts:                                 128
  audit bundles:                             12
  run traces:                                64

Legal-retention analysis:
  oldest record:           2015-01-05
  legal floor expiry:     2022-12-31 (6-year CdC for 2016 records)
  request scope:          all past legal floor; no override needed

Type the literal word `erase-2015-to-2018` to confirm: erase-2015-to-2018

Erasing...
  [ok] 16 submissions removed
  [ok] 16 drafts removed
  [ok] 8 342 transactions removed
  [ok] 412 invoices removed
  [ok] 128 receipts removed
  [ok] 12 audit bundles removed
  [ok] 64 run traces removed
  [ok] deletion report written to var/profiles/personal/audit/deletion-reports/2026-04-24.json
```

### Subject access request (SAR) for counterparty data

Counterparties (vendors, clients) may request what personal data
Kent holds about them. The CLI helps Kent respond:

```text
aeat configure subject-access-request \
    --tax-id <id> \
    --output ./sar-response.zip
```

Behaviour:

- Walks every subsystem for records where the counterparty tax_id
  appears.
- Exports a single archive with JSON plus CSV projections.
- Includes scanned receipts, invoices involving the counterparty.
- Includes a human-readable narrative summary for the SAR recipient.
- Records the SAR request in Kent's audit log for accountability.
- The CLI does not remove or alter Kent's records; SAR is
  read-only.

A counterparty's right to erasure is a separate legal question that
interacts with Kent's retention obligations. The CLI helps Kent
identify records but does not automatically erase counterparty data
because Kent's retention obligations may require him to keep the
records regardless. The CLI produces a decision-support summary:

```text
$ aeat configure subject-access-request --tax-id B12345678 --output ./sar.zip
[profile] personal (X1234567L)

SAR scope for tax_id B12345678:

  invoices:           12 (2022-01-04 to 2024-03-18)
  transactions:       34 (same period)
  referenced in:       3 filings (303/2022Q1, 303/2023Q3, 130/2023Q4)

Erasure analysis:
  filing retention floors prohibit erasing 30 transactions and 10 invoices.
  2 invoices are past retention floor; erasure possible.

Exported to ./sar.zip. Deliver to the requester per your legal process.

If the counterparty requests erasure:
  aeat configure erase-counterparty-data --tax-id B12345678 --dry-run
  (Kent's retention obligations may limit what can be erased.)
```

### Consent management

LLM automation processes data at a third party. Explicit consent is
required.

```text
aeat configure consent grant llm_automation --profile personal \
    --purpose "transaction classification" \
    --provider "anthropic:claude-sonnet-4-6"
aeat configure consent list
aeat configure consent revoke llm_automation --profile personal
```

Behaviour:

- `grant`: writes a consent record with timestamp, purpose,
  provider, scope, expiry. Signed into the decision journal.
- `list`: enumerates active consents per profile with expiry.
- `revoke`: flips the consent record to revoked; disables the
  feature in practice; records the revocation.

LLM automation refuses to run without an active consent record:

```text
ERROR: No active consent for llm_automation on profile 'personal'.
  -> Grant consent: `aeat configure consent grant llm_automation ...`
  -> Or use rule-based classification only: drop `--with llm`.
Exit 3. Code: E_CONSENT_MISSING.
```

Consent records have a default 12-month expiry; Kent re-grants to
continue. Expiry reminder via `aeat doctor`.

### Crypto-shredding limits

Crypto-shredding renders ciphertext unrecoverable by destroying the
encryption key. Limitations:

- Only protects against disk forensics of the encrypted file.
- If plaintext was ever written unencrypted (shouldn't happen, per
  iterations 12, 26), shredding does nothing for that plaintext.
- SSDs retain copies outside the filesystem view (wear-levelling);
  secure erase requires OS-level `blkdiscard`, `cipher /w`, or
  vendor-specific tools.
- `aeat configure erase-personal-data` documents this limitation
  explicitly:

```text
Note: Crypto-shredding destroys the encryption key, making the
encrypted files unrecoverable. Residual plaintext may remain in OS
caches, page files, or SSD wear-levelling areas. For complete
erasure, additionally run your OS's secure-erase tool on the
workspace directory.
```

### Telemetry as GDPR concern

Iteration 15's opt-in telemetry:

- Pseudonymous via `workspace_hash`.
- Kent's explicit opt-in is the lawful basis.
- No tax_id or amount leaves the machine.
- Endpoint retention is the project's obligation; documented in the
  project's privacy policy.

Kent revokes remote telemetry at any time via iteration 15 flow
plus:

```text
aeat advanced diagnostics telemetry request-deletion \
    --endpoint-url https://... --confirm
```

This POSTs an erasure request to the endpoint's GDPR-compliant
deletion API. If the endpoint lacks such an API, the command emits
a clear error and advises Kent to contact the endpoint operator.

### Privacy documentation stack

Ships at `docs/privacy/`:

- `data-model.md`: per-subsystem description of what is stored,
  why, and for how long. Machine-generated from the retention
  registry; regenerated on release.
- `retention-policy.md`: retention defaults with legal citations
  and override instructions.
- `subject-access.md`: how Kent fields SARs; response template.
- `privacy-impact-assessment.md`: PIA template for Kent to adapt to
  his circumstances (for example, does he have employees; does he
  process clients' EU-resident data).
- `processor-list.md`: any third-party processors Kent may use
  (LLM providers) and what data they see under his explicit
  consent.

Each document carries `last_reviewed` frontmatter; quarterly audit
surfaces stale documents.

### Audit and accountability

Every privacy-relevant action writes to the decision journal:

- SAR response created.
- Consent granted, revoked, or expired.
- Erasure performed (with scope, reason, legal-floor analysis).
- Retention setting changed.
- Telemetry opt-in or opt-out.
- Counterparty data export.

Audit entries carry `privacy_event=true` tag so they can be
enumerated:

```text
aeat advanced diagnostics privacy-events list --days 365
```

### Kent roleplay: SAR from a former client

A former consulting client demands to know what Kent holds about
them.

```text
$ aeat configure subject-access-request --tax-id X9876543L --output ./sar-client-anon.zip
[profile] personal (X1234567L)

SAR scope for tax_id X9876543L:
  invoices:      3 (2022-02-15, 2022-05-10, 2022-08-22)
  transactions:  6 (same period; linked to the invoices)
  referenced in: 2 filings (303/2022Q1, 303/2022Q3)

Exported to ./sar-client-anon.zip (manifest SHA-256 f2a1...).

Next:
  - Deliver the archive to the requester per your legal process.
  - Log the SAR in your client relationship records.
  - If the requester asks for erasure, run:
      aeat configure erase-counterparty-data --tax-id X9876543L --dry-run
    to see what retention obligations apply.
```

### Kent roleplay: retention reminder

```text
$ aeat doctor
[profile] personal (X1234567L)

  retention                   [info]    transactions 2019Q1 past legal floor
                                        eligible for erasure after 2026-04-25
                                        run: `aeat configure data-catalogue --kind transactions --eligible-for-erasure`
  consent (llm_automation)    [warn]    expires in 12 days (2026-05-06)
                                        re-grant: `aeat configure consent grant llm_automation ...`
```

### Hardening rules derived from iteration 28

- Retention per subsystem is registered; defaults respect Spanish
  tax law.
- Retention below legal floor refused with explicit legal-citation
  error.
- `configure data-catalogue` enumerates storage for transparency.
- `configure export-personal-data` produces GDPR-portable archive
  with schemas.
- `configure erase-personal-data` crypto-shreds and respects legal
  retention; explicit override required.
- `configure subject-access-request` produces counterparty-scoped
  archive and a decision-support summary.
- `configure consent` manages per-profile consent with 12-month
  default expiry.
- Privacy-relevant actions write to the decision journal with
  `privacy_event=true` tag.
- Privacy documentation stack ships at `docs/privacy/`.
- Crypto-shredding limitations are documented; OS-level
  secure-erase guidance given.
- Telemetry erasure request path provided.

### Open risks added by iteration 28

- Legal landscape varies across EU states; Spanish rules are
  embedded but Kent operating across borders may need country-
  specific overrides.
- SSD crypto-shredding cannot guarantee unrecoverability at the
  hardware level; OS-level secure erase is Kent's additional step.
- Counterparty data erasure interacts with Kent's retention
  obligations in complex ways; the decision-support summary helps
  but cannot replace legal advice.
- LLM provider terms of service may retain prompt data longer than
  the CLI instructs; Kent's consent record must acknowledge this.
- Retention floors embedded in the CLI require update if Spanish
  law changes; corpus bundle (iteration 19) carries retention-floor
  updates alongside schema updates.
- SAR response may inadvertently reveal Kent's own business
  patterns through the counterparty-related records; no mitigation
  at the CLI layer, only guidance in `docs/privacy/subject-access.md`.
- `i-acknowledge-legal-retention-obligations` flag is a footgun; a
  distracted Kent may override legitimate obligations. The CLI
  reason requirement forces a pause.
- Privacy event log itself is personal data; retention of the log
  must be considered.
- The PIA template cannot substitute for a real PIA; the CLI is a
  starting point, not a compliance product.
- Cross-profile erasure may leave orphaned references in the
  remaining profiles (for example a shared counterparty). The
  erasure plan surfaces these but cleanup is Kent's manual step.
- LLM provider-side deletion is opaque; Kent can only issue a
  request and trust the provider's handling.

## Hardening pass iteration 29 (2026-04-24)

Iteration 29 focus: collaboration and delegated access. Kent does
not file alone: he may have an accountant who reviews quarterly
filings, signs off on annual returns, or advises him during an AEAT
audit. The CLI is a single-user tool by design (iterations 11, 26),
yet Kent needs a structured way to share a filing for review and
receive feedback without handing over his credentials or his full
workspace. This iteration specifies the review-package contract,
the review-only workspace mode, countersigning, feedback import,
and the audit-trail additions that keep delegated actions
accountable.

### Supported collaboration models

The CLI supports two asynchronous collaboration modes and
explicitly declines two others:

| Model | Support | Rationale |
| --- | --- | --- |
| Review package (Kent exports a signed scoped bundle; accountant reviews in a review-only workspace; accountant returns a feedback bundle) | supported | Covers quarterly review, annual signoff, and audit advisory. Data-minimisation controls. |
| Countersign on approval (accountant signs Kent's approved draft; signature attaches to the approval journal) | supported | Auditable legal-adjacent confirmation. |
| Shared workspace via sync backend | unsupported | Concurrency, conflict resolution, and credential-sharing make this unsafe for tax data. |
| Portal-level delegation (Kent grants his accountant AEAT sede access) | out of scope | Happens at AEAT, not in the CLI. `docs/collaboration.md` points at AEAT's `Apoderamientos` procedure. |

### Review package shape

A review package is a content-addressed, signed ZIP archive produced
by Kent's CLI and consumed by his accountant's CLI.

```text
aeat configure collab export-review-package \
    --modelo 303 \
    --period 2024Q1 \
    --scope draft|approved|submitted \
    --output ./review-303-2024Q1.zip \
    [--include-transactions] \
    [--include-evidence] \
    [--include-audit-bundle] \
    [--expires-in 30] \
    [--recipient-fingerprint <hex>] \
    [--encrypt-for-recipient]
```

Contents:

```text
review-package-{yyyy-mm-dd}-{short-id}.zip
|-- package-manifest.json
|-- draft/               # FilingDraft plus approval-basis + approval-journal
|-- audit/               # ComputationLedger, AuditReport, VerificationVerdict
|-- evidence/            # per the --include flags
|-- transactions/        # per --include-transactions
|-- submission/          # present when scope is approved or submitted
|-- references/          # ManualRule and LegalCitation records
|-- sender-identity.json # Kent's profile identity summary (tax_id masked unless --unmask)
`-- sender-signature.sig # ed25519 signature over package-manifest.json
```

`package-manifest.json` fields:

```json
{
  "package_version": "1.0",
  "package_id": "sha256 over contained_files",
  "scope": "draft",
  "modelo": "303",
  "period": "2024Q1",
  "sender_profile_id": "personal",
  "sender_tax_id_masked": "X*****67L",
  "sender_tax_id_full": "X1234567L",   // omitted unless --unmask
  "sender_key_fingerprint": "abcd1234",
  "created_at": "2026-04-24T14:00:00Z",
  "expires_at": "2026-05-24T14:00:00Z",
  "recipient_fingerprint": "efgh5678",
  "encryption": "none|aes-256-gcm",
  "contained_files": [...]
}
```

Rules:

- `package_id` is the SHA-256 over the sorted `{path}\0{sha256}\n`
  table, matching iterations 3, 17, 19, 26 conventions.
- `sender_signature.sig` is an ed25519 detached signature over the
  exact bytes of `package-manifest.json`. Signing key is the Kent
  profile's collab signing key (see below).
- When `--encrypt-for-recipient` is set, file contents are encrypted
  with AES-256-GCM; the key is wrapped to the recipient's public
  key (accountant's ed25519 key handled as Curve25519 for ECDH).
- Data minimisation: transactions and evidence are only included
  when Kent explicitly flags them.

### Collab signing keys

Each profile holds a dedicated collab signing key alongside the
master key (iteration 26). The keystore slot:

```text
service:  aeat-workspace:{workspace_hash}
username: profile:{profile_id}:collab-signing-key:v{version}
```

`aeat configure collab keys show` prints the public fingerprint.
`aeat configure collab keys rotate --profile <id>` cycles the key
with the standard 30-day overlap from iteration 26.

Recipient fingerprints Kent knows about live at
`var/profiles/<id>/collab/recipients.json`:

```text
aeat configure collab recipient add --name "Maria (accountant)" --fingerprint "efgh5678"
aeat configure collab recipient list
aeat configure collab recipient remove --fingerprint "efgh5678"
```

Fingerprints exchange out-of-band once; trust persists across packages.

### Review-only workspace mode

The accountant provisions a workspace dedicated to review:

```text
aeat configure init --review-only
```

Behaviour differences from a normal workspace:

- Every local-state-mutating command (iteration 8 classifications
  `local_state_mutating`) refuses with
  `E_REVIEW_ONLY_WORKSPACE`, exit `3`.
- Read-only commands work normally.
- Export modes: `compare show`, `audit export`, `draft show`,
  `records *`, `review queue --kind review-package-item`.
- `auth login` allowed (accountant may need to verify sender keys or
  use their own workspace credentials).

Review-only is a workspace property recorded at `var/workspace-version.json`
and verified on every command startup. Downgrading from review-only
requires `aeat configure unset-review-only --confirm` with an
audit entry.

### Import and review flow

Accountant imports Kent's package:

```text
aeat configure collab import-review-package ./review-303-2024Q1.zip \
    --as-profile <local-scratch-id>
```

Behaviour:

1. Verify `sender-signature.sig` against a known fingerprint or
   prompt for trust.
2. Verify `package_id` matches `contained_files` table.
3. Verify `expires_at` is in the future.
4. Decrypt (if encrypted) using the accountant's own key.
5. Unpack into `var/profiles/<local-scratch-id>/collab-imports/<package_id>/`.
6. Register the package in `var/profiles/<local-scratch-id>/collab/packages.json`.

Accountant then reviews:

```text
aeat draft show 303 --period 2024Q1 --collab-package <package_id>
aeat compare show 303 --period 2024Q1 --against receipt --collab-package <package_id>
aeat audit show 303 --period 2024Q1 --collab-package <package_id>
```

Each command reads from the imported package rather than the
workspace's own records.

### Review notes and suggestions

Accountant annotates:

```text
aeat configure collab note add \
    --package <package_id> \
    --target-kind draft|casilla|finding|transaction \
    --target-id <id> \
    --body "IVA deducible parece bajo; por favor verificar factura 3."
aeat configure collab note list --package <package_id>
aeat configure collab suggestion add \
    --package <package_id> \
    --target-kind casilla \
    --casilla 27 \
    --proposed-value 3450.00 \
    --rationale "adjust per overlooked invoice"
```

Notes are text; suggestions are structured proposals that reference
a specific value Kent might accept. Neither modifies the imported
records.

### Feedback package

Accountant produces a feedback package to return to Kent:

```text
aeat configure collab export-feedback \
    --package <package_id> \
    --output ./feedback-303-2024Q1.zip \
    [--countersign] \
    [--encrypt-for-sender]
```

Shape:

```text
feedback-package-{yyyy-mm-dd}-{short-id}.zip
|-- feedback-manifest.json       # references original package_id
|-- notes.json                   # all notes
|-- suggestions.json             # all suggestions
|-- countersign.sig              # ed25519 signature over the original package_id (if --countersign)
|-- reviewer-identity.json       # accountant's profile summary
`-- reviewer-signature.sig       # ed25519 signature over feedback-manifest.json
```

Countersign semantics:

- Countersign is a signature over the original package's
  `package_id` plus a timestamp plus a reviewer statement.
- It asserts "I, the reviewer with fingerprint X, reviewed this
  filing at time T and produced the feedback bundle Y."
- It is not a formal tax-agent attestation; it is a CLI-native audit
  artefact that supplements Kent's own approval.

### Kent imports feedback

```text
aeat configure collab import-feedback ./feedback-303-2024Q1.zip \
    [--accept-suggestions] \
    [--countersign-to-approval]
```

Behaviour:

1. Verify `reviewer-signature.sig` against a known fingerprint or
   prompt Kent for trust.
2. Verify `feedback-manifest.json` references a known sent package.
3. Store feedback at
   `var/profiles/<id>/collab/feedback/{package_id}/`.
4. Surface notes in `aeat draft show <m> --period <p>` output with
   a `Reviewer notes` section.
5. Suggestions appear in `aeat review queue --kind collab-suggestion`
   for Kent's decision.
6. If `--countersign-to-approval` is set and the draft is already
   approved, attach the countersign to the approval journal entry
   for that draft.

### Countersign on approval

Kent can attach a reviewer's countersign to his approval:

```text
aeat review approve draft 303/2024Q1 \
    --with-countersign ./feedback-303-2024Q1.zip \
    --reason "reviewed by Maria (accountant) 2026-04-24"
```

Effect:

- Normal approval (iteration 8) runs first.
- Countersign signature extracted from the feedback package is
  appended to the approval journal entry:

```json
{
  "entry_id": "uuid",
  "timestamp": "2026-04-24T14:00:00Z",
  "actor": "kent",
  "action": "approve",
  "reason": "reviewed by Maria (accountant) 2026-04-24",
  "countersigns": [
    {
      "reviewer_name": "Maria (accountant)",
      "reviewer_fingerprint": "efgh5678",
      "countersign_signature": "base64",
      "countersign_at": "2026-04-23T16:30:00Z",
      "countersign_over_package_id": "..."
    }
  ],
  "prior_review_checksum": "...",
  "next_review_checksum": "..."
}
```

- The countersign flows into audit bundles (iteration 3) so future
  `audit show` and `audit verify` surface reviewer identity.

### Accepting suggestions

For each structured suggestion, Kent can accept or reject:

```text
aeat review suggestion accept <suggestion_id>
aeat review suggestion reject <suggestion_id> --reason "disagree; see note"
```

Accepted suggestions apply to the draft the same way Kent editing
it directly would, and both the acceptance and the underlying
suggestion are recorded in the decision journal so the provenance
is clear.

Rejected suggestions remain in the feedback record (for audit
trail) but do not change the draft.

### Expiry and replay defence

Review packages carry `expires_at` (30 days default). After expiry:

- Import refuses with `E_REVIEW_PACKAGE_EXPIRED`.
- Override with `--force-import-expired` plus reason logged.

Package-id uniqueness:

- The workspace tracks `package_id` of every exported package at
  `var/profiles/<id>/collab/exports.json`.
- Re-exporting the same draft state produces the same `package_id`
  (content-addressed); Kent can detect duplicates.
- The accountant tracks imported `package_id`s; an already-imported
  package refuses re-import unless forced.

### Audit trail additions

Every collaboration action writes to the decision journal with
`collab_event=true` plus (from iteration 28) `privacy_event=true`:

- `review_package_exported` with scope, recipient fingerprint,
  included content flags.
- `review_package_imported` with sender fingerprint,
  decryption-used flag.
- `feedback_note_added`.
- `feedback_suggestion_added`.
- `feedback_package_exported`.
- `feedback_package_imported`.
- `suggestion_accepted` or `suggestion_rejected`.
- `countersign_attached_to_approval`.

Retention matches decision journal (indefinite per iteration 28).

### Data-minimisation guidance

Default export-review-package scopes are narrow:

- `--scope draft`: draft and its approval basis only; no
  transactions or evidence.
- `--include-transactions` required to ship transactions.
- `--include-evidence` required to ship receipts, invoices.

Kent's onboarding banner (iteration 13) for first collab export
reminds him of data minimisation. Documentation at
`docs/collaboration.md` lists typical scopes per use case:

| Use case | Recommended scope |
| --- | --- |
| Quarterly sanity check | draft only |
| Annual signoff | draft + evidence |
| AEAT audit advisory | approved + transactions + evidence + audit-bundle |
| Classification advisory | draft + transactions (no evidence) |

### Kent roleplay: accountant quarterly review

Kent:

```text
$ aeat configure collab recipient add --name "Maria" --fingerprint "efgh5678"
[profile] personal (X1234567L)
Added recipient 'Maria' (efgh5678).

$ aeat configure collab export-review-package \
    --modelo 303 --period 2024Q1 --scope draft --include-evidence \
    --output ./review-303-2024Q1.zip \
    --recipient-fingerprint efgh5678 \
    --encrypt-for-recipient
[profile] personal (X1234567L)
Building review package for 303/2024Q1...
  [ok] draft record (casillas 1-88)
  [ok] approval basis (draft not yet approved)
  [ok] formula ledger + audit report
  [ok] 47 invoices
  [ok] 12 receipts
  [ok] signed with collab-signing-key:v1 (fingerprint abcd1234)
  [ok] encrypted for recipient efgh5678

Package: ./review-303-2024Q1.zip (9.3 MB)
Expires: 2026-05-24T14:00:00Z

Next: send to Maria out-of-band.
```

Maria (accountant) on her own machine:

```text
$ aeat configure init --review-only
$ aeat configure collab import-review-package ./review-303-2024Q1.zip --as-profile kent-review-Q1
Verifying sender signature...
  [ok] signed by abcd1234 (known as "Kent" in recipients.json)
Decrypting with my key...
  [ok] decrypted
Importing...
  [ok] draft 303/2024Q1 into kent-review-Q1/collab-imports/...

$ aeat draft show 303 --period 2024Q1 --collab-package 9f2a1c --profile kent-review-Q1
(review-only workspace)
[... draft details ...]

$ aeat configure collab note add \
    --package 9f2a1c \
    --target-kind casilla \
    --target-id 27 \
    --body "IVA deducible parece bajo; verificar factura 3."

$ aeat configure collab suggestion add \
    --package 9f2a1c \
    --target-kind casilla \
    --casilla 27 \
    --proposed-value 3450.00 \
    --rationale "ajustar por factura omitida"

$ aeat configure collab export-feedback \
    --package 9f2a1c \
    --output ./feedback-303-2024Q1.zip \
    --countersign
Enter countersign passphrase: ****
  [ok] 1 note, 1 suggestion bundled
  [ok] countersigned with ed25519 (fingerprint efgh5678)

Feedback: ./feedback-303-2024Q1.zip
```

Kent:

```text
$ aeat configure collab import-feedback ./feedback-303-2024Q1.zip
[profile] personal (X1234567L)
Verifying reviewer signature...
  [ok] signed by efgh5678 (known as "Maria" in recipients.json)
Importing feedback...
  [ok] 1 note on 303/2024Q1 casilla 27
  [ok] 1 suggestion on 303/2024Q1 casilla 27
  [ok] countersign recorded

$ aeat draft show 303 --period 2024Q1
[... draft with reviewer-notes section ...]
  Reviewer notes (Maria, 2026-04-23T16:30:00Z):
    casilla 27: IVA deducible parece bajo; verificar factura 3.

$ aeat review queue --kind collab-suggestion
...
$ aeat review suggestion accept sug_abc123
[ok] applied casilla 27 = 3450.00 per suggestion sug_abc123.

$ aeat review approve draft 303/2024Q1 \
    --with-countersign ./feedback-303-2024Q1.zip \
    --reason "reviewed by Maria 2026-04-23"
[profile] personal (X1234567L)
[ok] approved draft 303/2024Q1
[ok] countersign attached to approval entry 7c2e
```

### Scope explicit exclusions

Collaboration deliberately does not:

- Transmit Kent's auth credentials or Kent's master key.
- Allow the accountant to file directly on AEAT.
- Enable real-time shared editing.
- Span profiles automatically (each package is per-profile).
- Modify Kent's workspace unless Kent explicitly accepts a
  suggestion or attaches a countersign.

### Hardening rules derived from iteration 29

- Review packages are content-addressed, signed by a profile-scoped
  ed25519 collab key, and can be encrypted for a known recipient.
- Review-only workspace mode refuses local-state-mutating commands
  and is enforced at every command startup.
- Feedback packages are signed by the reviewer; countersigning over
  an original package_id is a first-class artefact.
- Countersigns attach to approval journal entries and flow into
  audit bundles.
- Accountant recipient fingerprints are managed explicitly; trust is
  established out-of-band once.
- Collaboration actions are audit-logged with `collab_event` and
  `privacy_event` tags.
- Review packages expire after 30 days by default.
- Data minimisation flags default to narrow scope; Kent opts in to
  ship transactions and evidence.
- Collaboration does not share credentials, does not allow direct
  filing, and does not create a shared workspace.

### Open risks added by iteration 29

- Out-of-band fingerprint exchange is friction and a social-
  engineering attack vector. Documentation must clearly guide Kent
  on verifying the accountant's fingerprint through a trusted
  channel.
- Lost accountant signing key compromises countersigns. Kent must
  revoke the recipient fingerprint and re-verify on next exchange.
- Expired review packages with `--force-import-expired` override
  bypass a safety net; the override is logged but Kent may misuse
  it under deadline pressure.
- Suggestion acceptance may race with Kent's own edits. Accepting a
  suggestion against a draft that has been re-computed since the
  package export produces a stale-state risk; the CLI must detect
  staleness (compare the suggestion's base draft_id against the
  current draft_id) and refuse silent application.
- Countersign verification at audit-replay time requires the
  accountant's public key to travel with the audit bundle. Iteration
  3's manifest contract already accommodates arbitrary record
  attachments; adding countersigner public keys to the bundle is
  an additive change.
- Collaboration data-minimisation defaults may be too narrow for
  legitimate audit advisory; Kent must understand his scope
  responsibility. `docs/collaboration.md` provides guidance but
  cannot substitute for domain expertise.
- Review-only workspaces are per-accountant-machine; a single
  accountant serving multiple autonomos needs a separate profile
  per client to keep records isolated (iteration 11 conventions
  carry over).
- Encrypted packages require symmetric-plus-asymmetric key wrapping.
  The key-wrapping format must be versioned so future rotation is
  orderly.
- AEAT has its own `Apoderamientos` (tax-agent delegation) system.
  The CLI collaboration model is independent of AEAT-side
  delegation; Kent must not confuse the two. Documentation states
  this explicitly.
- Feedback packages that reference a suggestion accepted by Kent
  create a durable audit chain. Revoking that chain later (for
  example if the accountant turns out to be unauthorised) requires
  manual work; no automatic unwind.
- Multi-party collaboration (accountant plus second reviewer) is
  out of scope in iteration 29. Serial signing may satisfy simple
  cases; multi-party concurrent review requires a future iteration.

## Hardening pass iteration 30 (2026-04-24)

Iteration 30 focus: sandbox and dry-run mode. Kent needs safe places
to experiment: a what-if reclassification, an LLM provider bake-off,
a revise preview, an onboarding practice run. Doing any of these
against the main workspace risks polluting his audit trail or losing
real state. This iteration specifies two complementary primitives,
`--dry-run` at the command level for one-off previews and sandbox
workspaces for longer exploration, plus the isolation guarantees,
merge semantics, banner prominence, and cleanup discipline that make
sandboxes trustworthy.

### Two primitives

| Primitive | Scope | Persistence | Use case |
| --- | --- | --- | --- |
| `--dry-run` flag | single command | no side effects | preview a specific mutation |
| Sandbox workspace | multi-command session | full state, isolated | experiment, bake-off, practice, revise preview |

### `--dry-run` contract

Every local-state-mutating command (iteration 8 class) accepts
`--dry-run`. Behaviour:

- The command runs its full logic to completion.
- No record is persisted; no keystore operation performed; no
  network call made beyond what would be required for computation
  (for example, `transactions automate --with llm --dry-run` still
  calls the LLM to simulate accurately, unless `--offline-dry-run`
  is set to use rule-based classification only).
- The command emits the list of intended side effects to stdout (or
  JSON with `--json`).
- Exit codes follow the error taxonomy from iteration 6 as if the
  command had executed.

Example:

```text
$ aeat draft create 303 --period 2024Q1 --dry-run
[profile] personal (X1234567L)
[dry-run] no changes will be persisted.

Would create draft 303/2024Q1:
  content-addressed draft_id: f2a1c8e4d5b7a309
  target file: var/profiles/personal/drafts/f2a1c8e4d5b7a309.json
  schema_version: 303-2024-v1
  values: 88 casillas populated
  findings: 2 warnings
  approval_state: DRAFT

No other records would be touched.
Re-run without --dry-run to persist.
```

`--dry-run` under `--json`:

```json
{
  "command": "draft.create",
  "status": "ok",
  "dry_run": true,
  "result": {
    "would_create": {
      "kind": "draft",
      "draft_id": "f2a1c8e4d5b7a309",
      "path": "var/profiles/personal/drafts/f2a1c8e4d5b7a309.json",
      "payload_summary": "..."
    }
  },
  "metadata": { "...": "standard metadata" }
}
```

Implementation requirement: every mutating command routes writes
through a journal abstraction. `--dry-run` collects journal entries
without committing them; commit runs on non-dry-run paths. A
regression test exercises every registered mutating command under
both `--dry-run` and real runs against a fixture and asserts they
produce identical record content on commit (modulo timestamps).

### `--offline-dry-run` variant

For commands that would call external services (LLM, AEAT portal):

- `--dry-run` with external calls: simulates the call normally,
  including the network round-trip and token costs, but discards
  the persistence.
- `--offline-dry-run`: skips the external call entirely; uses a
  stubbed response or the local rule-based path; zero external
  cost. Useful for practising without burning LLM tokens.

`--offline-dry-run` implies `--dry-run`.

### Sandbox workspaces

A sandbox is a full workspace state copied from a source profile
into an isolated namespace.

Storage layout:

```text
var/
|-- profiles/
|   `-- personal/
|-- sandboxes/
|   |-- index.json                 # sandbox metadata registry
|   |-- experiment-1/
|   |   |-- sandbox.json           # sandbox metadata
|   |   |-- profiles/personal/     # full copy of source profile
|   |   |-- audit/                 # sandbox's own audit journal
|   |   |-- cache/                 # sandbox-scoped cache
|   |   `-- (no auth/ directory)
|   `-- bakeoff-anthropic/
|       `-- ...
`-- active_profile
```

Sandboxes have no `auth/` directory and no keystore entries;
sandbox sessions cannot authenticate to AEAT.

### Sandbox lifecycle commands

```text
aeat configure sandbox create --name <slug> [--from-profile <id>] [--seed synthetic]
aeat configure sandbox list
aeat configure sandbox show <slug>
aeat configure sandbox use <slug>               # sets active sandbox
aeat configure sandbox exit                       # returns to main workspace
aeat configure sandbox delete <slug> --confirm
aeat configure sandbox archive <slug> --output <path>
aeat configure sandbox restore <archive-path> --name <new-slug>
aeat configure sandbox prune --older-than 90d [--dry-run]
aeat configure sandbox merge --from <sandbox> [--to <profile>] --scope <scope>
```

`create` flavours:

- `--from-profile <id>` (default when not specified: the active
  profile): clone the profile's state into the sandbox.
- `--seed synthetic`: populate with synthetic fixture data (no real
  Kent records). Used for onboarding demos and fresh experimentation.
- `--from-sandbox <source-slug>`: fork from another sandbox for
  cascading experiments.

`use <slug>`: sets a process-wide pointer. The next commands operate
on the sandbox until `exit`. The sandbox pointer is stored at
`var/active_sandbox` and is per-shell (set via env var
`AEAT_ACTIVE_SANDBOX` or per-invocation flag `--sandbox <slug>`).

### Sandbox banner prominence

Every command run inside a sandbox emits a sandbox banner to stderr
regardless of log level (including `--quiet` which suppresses only
info-level stderr; banner survives):

```text
[SANDBOX: experiment-1] personal (X1234567L)
  not connected to AEAT; changes do not affect main workspace.
```

In JSON mode, the envelope carries:

```json
{
  "command": "draft.create",
  "status": "ok",
  "sandbox": "experiment-1",
  "sandbox_source_profile": "personal",
  ...
}
```

Exit, delete, and merge always print the sandbox name.

### Isolation guarantees

Inside a sandbox:

- `auth login` refuses with `E_SANDBOX_AUTH_BLOCKED` and redirects
  Kent to exit the sandbox for live work.
- `live_read` commands (iteration 8 classification) refuse
  similarly.
- `export modelo` is permitted so Kent can inspect the resulting
  fichero; the emitted file is tagged in its manifest with
  `produced_in_sandbox=true` to prevent accidental upload. Attempts
  to upload it via portal-integration tooling (future iteration)
  must refuse.
- `audit export` is permitted; the produced bundle carries
  `sandbox=experiment-1` in its manifest.
- `records aeat fetch` refuses.
- Telemetry (iteration 15) records sandbox events to a separate
  bucket; they never flush to remote (telemetry is disabled in
  sandboxes by default regardless of main-workspace opt-in).
- LLM cache is sandbox-scoped; sandbox LLM results never leak back
  into the main cache.

Outside a sandbox (main workspace):

- Sandboxes are invisible to `status`, `data`, `transactions`,
  `draft`, `review`, `compare`, `export`, `audit`, `revise`, and
  `records` commands.
- Only `aeat configure sandbox *` commands interact with sandbox
  state.
- Main audit journal records sandbox lifecycle events (create,
  merge, delete) with `collab_event=false` and `sandbox_event=true`
  tags.

### Merge semantics

Merge promotes selected records from a sandbox back to a profile.
Conflicts are explicit.

```text
aeat configure sandbox merge --from <sandbox> --to <profile> --scope <scope> \
    [--conflict strategy=prefer-main|prefer-sandbox|interactive] \
    [--dry-run]
```

Supported scopes:

- `classifications`: promote `transactions.classify` changes only;
  other records untouched.
- `transactions-added`: promote new transactions that exist in
  sandbox but not in main.
- `drafts`: promote draft records created in sandbox into main as
  new drafts (assigned fresh content-addressed draft_ids in main
  context; existing sandbox draft_ids are not preserved because
  they may collide with main's draft_id space).
- `invoices-edits`: promote invoice edits for invoices that exist
  in both.
- `all`: full merge; refused without an explicit conflict strategy.

Conflict detection:

- A record's `last_modified_at` in main is newer than the sandbox's
  fork point.
- A record was deleted in main since the fork.
- A record was edited in main and in sandbox independently since
  the fork.

On conflict:

- `prefer-main`: sandbox change discarded; logged.
- `prefer-sandbox`: main change overwritten; logged.
- `interactive`: prompt per-conflict with diff view; refuses under
  non-TTY.
- No default: Kent must pick explicitly.

Merge writes an audit event:

```json
{
  "event_kind": "sandbox_merge",
  "from_sandbox": "experiment-1",
  "to_profile": "personal",
  "scope": "classifications",
  "conflict_strategy": "prefer-sandbox",
  "records_merged": 42,
  "conflicts_resolved": 3,
  "records_skipped": 0,
  "merged_at": "2026-04-24T14:00:00Z",
  "actor": "kent",
  "reason": "accepted LLM bake-off winner"
}
```

### Kent roleplay: LLM bake-off

Kent wants to pick between Anthropic and OpenAI for transaction
classification on his 2024Q1 data:

```text
$ aeat configure sandbox create --name bakeoff-anthropic --from-profile personal
[ok] sandbox 'bakeoff-anthropic' created from profile 'personal'.

$ aeat configure sandbox use bakeoff-anthropic
[SANDBOX: bakeoff-anthropic]
active sandbox: bakeoff-anthropic

$ aeat transactions automate --period 2024Q1 --with llm --llm-provider anthropic
[SANDBOX: bakeoff-anthropic]
... classifies 1 203 transactions ...

$ aeat configure sandbox exit
returned to main workspace.

$ aeat configure sandbox create --name bakeoff-openai --from-profile personal
$ aeat configure sandbox use bakeoff-openai
[SANDBOX: bakeoff-openai]
$ aeat transactions automate --period 2024Q1 --with llm --llm-provider openai
... classifies 1 203 transactions ...

$ aeat configure sandbox exit

$ aeat advanced diagnostics llm-bakeoff \
    --sandbox-a bakeoff-anthropic \
    --sandbox-b bakeoff-openai \
    --period 2024Q1
[profile] personal (X1234567L)

Bake-off: bakeoff-anthropic vs bakeoff-openai on 1 203 transactions

  agreement:              92.3%
  sandbox-anthropic        confidence median: 0.87
  sandbox-openai           confidence median: 0.82
  anthropic-only decisions: 54
  openai-only decisions:    39

Accept anthropic results into main?
  aeat configure sandbox merge --from bakeoff-anthropic --to personal --scope classifications --conflict prefer-sandbox

$ aeat configure sandbox merge --from bakeoff-anthropic --to personal \
    --scope classifications --conflict prefer-sandbox
[profile] personal (X1234567L)
Merging 'bakeoff-anthropic' classifications into 'personal':
  records to merge: 1 203
  conflicts: 0 (sandbox forked at 2026-04-24T10:00, main unchanged since)
  applying...
  [ok] 1 203 classifications updated.

$ aeat configure sandbox delete bakeoff-anthropic --confirm
[ok] sandbox deleted.
$ aeat configure sandbox delete bakeoff-openai --confirm
```

### Kent roleplay: revise preview

Kent considers revising 303/2024Q1 but wants to see the fichero
first without commitment:

```text
$ aeat configure sandbox create --name revise-preview --from-profile personal
$ aeat configure sandbox use revise-preview
[SANDBOX: revise-preview]

$ aeat revise start 303 --period 2024Q1 --kind rectificativa-ari
[SANDBOX: revise-preview] ...

$ aeat data edit invoice inv_new --category deductible
$ aeat draft create 303 --period 2024Q1 --revision amd_xyz
$ aeat review approve draft 303/2024Q1 --revision amd_xyz

$ aeat export modelo 303 --period 2024Q1 --kind rectificativa-ari --output ./preview.boe
[SANDBOX: revise-preview]
Exporting ARI fichero for 303/2024Q1...
[ok] fichero: ./preview.boe (produced_in_sandbox=true)

$ aeat export verify ./preview.boe
[SANDBOX: revise-preview]
[ok] structure valid
  refund casilla 73: 450.00 EUR
  baseline: 2024-303-Q1-X...DEF

$ aeat configure sandbox exit
$ aeat configure sandbox delete revise-preview --confirm
```

Kent now knows what the ARI would look like. He can redo the flow
in main or adjust his strategy.

### Onboarding with synthetic sandbox

A brand-new Kent runs through the full flow without fear:

```text
$ aeat configure sandbox create --name practice --seed synthetic
[ok] sandbox 'practice' created with synthetic seed data.
  profile 'synthetic-personal' (X9999999Z, placeholder NIE)
  1 year of synthetic transactions, invoices, receipts

$ aeat configure sandbox use practice
[SANDBOX: practice] synthetic-personal
$ aeat status today
[... onboarding banner + agenda from synthetic data ...]

$ aeat transactions automate --period 2024Q1 --with llm --offline-dry-run
# rule-based classification only; no LLM tokens spent

$ aeat draft create 303 --period 2024Q1
$ aeat review approve draft 303/2024Q1
$ aeat export modelo 303 --period 2024Q1 --output ./practice.boe

$ aeat configure sandbox exit
$ aeat configure sandbox delete practice --confirm
```

### Stale-sandbox cleanup

A sandbox past 90 days without activity is flagged as stale:

```text
$ aeat doctor
[profile] personal (X1234567L)
  ...
  sandboxes                 [warn]     2 sandboxes older than 90 days:
                                       'bakeoff-anthropic' (118 days, 2.1 GB)
                                       'revise-2024Q1' (93 days, 0.8 GB)
                                       prune: `aeat configure sandbox prune --older-than 90d`
```

### Disk envelope

Sandboxes count against the workspace disk-size envelope from
iteration 16. `aeat configure sandbox show <slug>` reports disk
usage:

```text
sandbox 'bakeoff-anthropic'
  created_at:       2026-04-24T10:00:00Z
  source_profile:   personal
  disk_usage:       2.1 GB
  record_counts:
    transactions:   1 203
    drafts:         12
    submissions:     8
    ...
```

### Hardening rules derived from iteration 30

- `--dry-run` supported on every local-state-mutating command;
  implementation uses a journal abstraction; regression test
  ensures `--dry-run` plus commit produces identical output to a
  direct commit against the same inputs.
- `--offline-dry-run` skips external calls entirely for zero-cost
  simulation.
- Sandboxes are full workspace namespaces isolated under
  `var/sandboxes/<slug>/`.
- Sandboxes lack `auth/` and cannot authenticate to AEAT.
- Sandbox banner is emitted on every command regardless of log
  level; `--json` envelope carries the sandbox name.
- Merge is explicit with scoped selection and conflict-strategy
  requirement.
- Merge events are audit-logged in the target profile's journal.
- Stale sandboxes past 90 days are surfaced by `aeat doctor`.
- Sandboxes count against the workspace disk envelope.
- Exported ficheros from sandbox carry `produced_in_sandbox=true` in
  their manifest.

### Open risks added by iteration 30

- Kent forgetting he is in a sandbox and making decisions against
  sandbox data as if they were real. The prominent banner, the
  `--json` envelope flag, and `aeat doctor` reporting active
  sandbox mitigate but cannot eliminate.
- Sandbox proliferation accumulates disk usage and cognitive load.
  Stale-cleanup discipline plus the workspace disk-envelope alert
  from iteration 16 help.
- Merge conflict resolution is complex; `interactive` mode depends
  on a TTY. Automation pipelines must pick a deterministic
  conflict strategy.
- Draft_id collisions at merge time are possible because sandbox
  draft_ids are content-addressed to sandbox state. The merge
  command mints fresh draft_ids; the audit event records the
  mapping so Kent can retrace.
- `--dry-run` semantics must be identical between the dry-run path
  and the commit path. Drift is a silent bug; the regression test
  is the only defence.
- Sandbox-exported ficheros that Kent accidentally uploads to AEAT
  would cause real filings. The `produced_in_sandbox=true` manifest
  tag is defence in depth; a portal-integration tool (future) must
  refuse such ficheros.
- Synthetic-seed sandbox data must be clearly distinguishable from
  real Kent data. Profile names should use `synthetic-` prefix;
  tax_ids should use known placeholder ranges; transaction amounts
  should avoid patterns that could be confused for Kent's real
  history.
- LLM cost in bake-off sandboxes is real money. Kent must
  understand that `--with llm` in a sandbox spends tokens unless
  `--offline-dry-run` is used.
- Sandbox telemetry policy (disabled by default) differs from main.
  Kent running a problem in sandbox then escalating to maintainer
  support must remember to copy relevant telemetry manually.
- Merge across schema-version boundaries (sandbox forked before a
  corpus refresh that shifted schemas) needs explicit handling;
  iteration 18 schema-version pinning applies.
- Sandbox archive and restore must not permit cross-workspace
  sandbox migration by default (workspace-specific identifiers
  tied to the originating workspace's salt); an explicit
  `--cross-workspace` flag with appropriate warnings covers the
  edge case.

## Hardening pass iteration 31 (2026-04-24)

Iteration 31 focus: filing-season deadline pressure UX. Kent at 11pm
the night before a 23:59:59 deadline is a different user from
Monday-morning Kent. He is stressed, tired, prone to muscle-memory
mistakes, and likely to click through warnings. The CLI must slow
him down at dangerous inflection points, speed him up at safe ones,
surface deadline urgency everywhere, and carry him through a safe
express path when he absolutely has to file now. This iteration
specifies deadline banners, quickfile meta-command, express/safety
modes, fail-fast posture under pressure, extemporanea handling, and
the runbook paths that match.

### Deadline-aware banners

Every Kent-first command that scopes to a `(modelo, period)` or
profile computes the nearest deadline at invocation start. If the
deadline is within 24 hours, the command emits a banner to stderr
before any primary output.

Bands:

| Time to deadline | Banner |
| --- | --- |
| more than 24h | none |
| 24h to 2h | `[DEADLINE: 303/2024Q1 due in 14h 22m at 2026-04-30T23:59:59 (Madrid)]` |
| 2h to 15m | `[URGENT: 303/2024Q1 due in 1h 43m]` |
| 15m to 0 | `[CRITICAL: 303/2024Q1 due in 12m - extemporanea applies after 00:00]` |
| past deadline | `[EXTEMPORANEA: 303/2024Q1 deadline passed Xm ago - surcharges apply]` |

Banner is visible at all log levels and appears in `--json` output
metadata as `{ "deadline": { "modelo": "303", "period": "2024Q1", "due_at": "2026-04-30T23:59:59+02:00", "seconds_remaining": 51480, "band": "URGENT" } }`.

The banner is informational, not blocking. It never changes exit
codes.

### Deadline computation

Deadline per `(modelo, ejercicio, period)` comes from
`src/aeat/configure/_deadlines.py`, seeded by the modelo registry
(iteration 18):

- Standard Spanish tax deadlines (for example modelo 303 quarterly
  due on day 20 of the following month; modelo 390 due 30 January
  following year).
- Madrid time zone for cut-off interpretation.
- Bank-holiday shifts per AEAT calendar; if deadline falls on a
  Saturday, Sunday, or national holiday, AEAT shifts to the next
  business day.
- Regional calendar overrides (iteration 32 will add Basque /
  Navarra / Canarias variants).

Deadline records are sourced from the corpus bundle (iteration 19)
`corpus/calendars/aeat-{ejercicio}.json`. A staleness check runs in
`aeat doctor`: if the calendar corpus is more than 18 months old,
warn that regional holidays may be out of date.

### Doctor priority on deadline day

`aeat doctor` reorders output when a deadline is within 24 hours:

```text
$ aeat doctor
[profile] personal (X1234567L)
[DEADLINE TODAY: 303/2024Q1 due in 14h 22m at 2026-04-30T23:59:59]

Filing readiness for 303/2024Q1:
  draft exists                 [ok]        approved 2026-04-29 by kent
  approval stale               [ok]        no stale reasons
  data readiness               [ok]        statement imported, 1 203 transactions classified
  export schemas               [ok]        303/2024 supported
  portal drift                 [ok]        no open critical events
  corpus freshness             [ok]        2026-04-24 (6 days old)
  auth session                 [ok]        certificate valid 18 days

Next action:
  aeat export modelo 303 --period 2024Q1
  upload at https://www.agenciatributaria.gob.es/.../modelo-303

Environment health (non-urgent):
  long path support            [ok]
  codepage                     [ok]
  llm                          [ok]
  ...
```

Filing-readiness block appears first, with every check explicitly
named against the filing. Environment checks demote below the
fold.

### Quickfile meta-command

For Kent who wants one command to carry him through:

```text
aeat quickfile <modelo> --period <p> [--skip-llm] [--upload-reminder] [--deadline-override --reason <text>]
```

Flow:

1. Run `data readiness` for the target.
2. If missing inputs, refuse (with a `--deadline-override --reason`
   escape hatch that is audit-logged).
3. If no approved draft:
   a. Run `draft create`.
   b. Present findings summary.
   c. Prompt Kent for approval (interactive).
   d. If approved, continue; otherwise stop.
4. Run `export modelo`.
5. Print fichero path, SHA-256, and upload URL.
6. Record a `quickfile_completed` audit event including which steps
   ran interactively versus automatically.

Quickfile never:

- Submits live.
- Bypasses the four-factor live-write gate.
- Skips approval.
- Hides a `REFUSED:` or `INTEGRITY:` failure.

Quickfile does:

- Skip banners and tutorials (iteration 13 onboarding banners
  suppressed under deadline pressure).
- Aggregate progress into one consolidated view.
- Automatically chain to the next step when each step succeeds.

Example:

```text
$ aeat quickfile 303 --period 2024Q1 --upload-reminder
[profile] personal (X1234567L)
[URGENT: 303/2024Q1 due in 1h 58m]

Quickfile for 303/2024Q1:

  [1/4] data readiness              [ok]
  [2/4] draft exists + approved     [ok]
  [3/4] export modelo
        fichero: var/profiles/personal/exports/303-2024Q1-2026-04-30.boe
        sha256: abcd1234...
  [4/4] upload reminder

Upload at https://www.agenciatributaria.gob.es/.../modelo-303
Deadline: 2026-04-30T23:59:59 (1h 58m remaining).

Next: run `aeat records receipts import <justificante.pdf>` after
upload to record the AEAT confirmation.
```

### Express, safety, adaptive modes

```text
aeat configure defaults set deadline_mode safety|express|adaptive
```

- `safety` (default when unset and before Kent has filed at least
  three times): all prompts, banners, confirmations, tutorials fire
  as iterations 13 and 30 define.
- `express`: tutorials suppressed, progress condensed, default-yes
  applied to non-consequential confirmations only. Consequential
  confirmations (approve, revise `--kind`, live flags,
  `--deadline-override`) remain interactive.
- `adaptive`: safety until T-24h; express within the final 24 hours
  if Kent's filing history for this modelo shows at least three
  prior successful filings. Otherwise stays safety even under
  pressure.

Express and adaptive never:

- Bypass `--kind` selection on revise.
- Bypass approval.
- Bypass live-write gates.
- Hide `INTEGRITY:` or `REFUSED:` output.

Mode is a per-profile setting, persisted in
`var/profiles/<id>/defaults.json`. Sandbox mode (iteration 30) is
always `safety` regardless.

### Fail-fast posture under pressure

Within the deadline window (T-24h and tighter), commands apply
stricter defaults:

- Warnings that normally allow Kent to proceed become refusals
  unless overridden.
- Interactive prompts that normally default to `N` become prompts
  that require an explicit `y` or `yes`.
- `--dry-run` (iteration 30) is refused on mutating commands during
  the final hour (Kent should be committing, not previewing); the
  sandbox primitive remains available.
- `--deadline-override --reason <text>` exists for every refusal
  that Kent can legitimately override. The flag logs to the audit
  journal with timestamp, actor, reason, refused rule. Audit
  bundles carry the override record so future review sees it.

Example:

```text
$ aeat draft create 303 --period 2024Q1
[URGENT: 303/2024Q1 due in 1h 17m]
ERROR: Data readiness shows 3 unlinked receipts and 1 finding with confidence 0.62.
  This is below the deadline-window safety threshold (0.75).

  Reconcile first:
    aeat data link receipt inv_<id> receipt_<id>
    aeat transactions review --kind transaction.confidence_low
  Or override (logged to audit journal):
    aeat draft create 303 --period 2024Q1 --deadline-override --reason "..."

Exit 3. Code: E_DEADLINE_READINESS.
```

Kent picks deliberately. The override path keeps him moving while
leaving an audit trail his future self (or his accountant) can
review.

### Emergency last-minute revise

If Kent files at 23:45 and realises at 23:50 he filed something
wrong, ARI (iteration 27) is the fastest correction path.

```text
aeat revise start 303 --period 2024Q1 --kind rectificativa-ari --urgent
```

`--urgent` rules:

- Skips tutorial banners.
- Pre-fills baseline from the most recently accepted filing.
- Prints an urgency banner.
- Defaults `compare show` to `--against receipt` to show the
  smallest useful delta.

ARI filing within the same day is AEAT-legal. Kent can file the ARI
minutes after the original to correct a mistake.

### Extemporanea handling

After the deadline passes:

```text
$ aeat draft create 303 --period 2024Q1
[EXTEMPORANEA: 303/2024Q1 deadline passed 43m ago]

Surcharge tiers for late filing without prior AEAT requirement:
  within 3 months    +5% on balance due
  3-6 months         +10%
  6-12 months        +15%
  over 12 months     +20%
  with prior AEAT requirement: +50% to +150%

Proceed with extemporanea filing? [y/N]:
```

If Kent proceeds, the fichero emission carries an extemporanea
indicator and the expected surcharge is computed and displayed.

Runbook `RB-022 Extemporanea filing` documents the full flow and
cites LGT Arts. 27, 191, 198.

### Deadline-pressure audit events

Audit journal entries pick up deadline-pressure tags:

- `deadline_override_applied`: Kent used `--deadline-override`
  with a reason.
- `quickfile_completed`: Kent used `aeat quickfile`; captures which
  sub-steps ran interactively vs auto.
- `express_mode_entered`: Kent flipped to express mode for this
  session.
- `extemporanea_filed`: Kent filed after the deadline.

Audit reviewers (Kent himself next week, or his accountant) see a
filing that went live under pressure and can inspect the trail.

### Doctor weekly summary

Outside deadline windows, `aeat doctor` includes a weekly
deadline-planning section:

```text
$ aeat doctor
[profile] personal (X1234567L)

Upcoming deadlines:
  303/2025Q3    in 23 days    2025-10-20   [draft missing]
  130/2025Q3    in 23 days    2025-10-20   [draft missing]
  390/2024      in 58 days    2026-01-30   [not yet applicable]

Recommendation: start 303/2025Q3 draft within 10 days to avoid deadline pressure.
```

### Kent roleplay: express-mode filing

Kent, who has filed 303 twelve times, runs adaptive-mode at T-1h:

```text
$ aeat quickfile 303 --period 2024Q1
[profile] personal (X1234567L) (adaptive mode: express within T-24h)
[URGENT: 303/2024Q1 due in 58m]

Quickfile for 303/2024Q1:

  [1/4] data readiness              [ok]
  [2/4] draft create + approve
        review basis fingerprint fresh; approving automatically (adaptive-mode rule)
        [ok] approved
  [3/4] export modelo
        fichero: ...
  [4/4] upload reminder

Upload at https://www.agenciatributaria.gob.es/.../modelo-303
Deadline: 58m remaining.
```

In adaptive mode, the approval step auto-proceeds only because:

- Draft content matches the last successful filing's structure
  (same casilla set, same modelo, similar magnitudes).
- No findings above medium severity.
- Kent has filed this modelo three or more times.
- The draft was recomputed within the current session (freshness).

If any condition is missed, adaptive falls back to safety and
prompts Kent.

### Stress-test harness

A dedicated test at `tests/stress/test_deadline_pressure.py`:

1. Fixture workspace with deadline at `now() + 1h`.
2. Walks through full filing flow with `deadline_mode=adaptive`.
3. Asserts banners, fail-fast rules, quickfile sub-steps, and
   extemporanea handling.
4. Wall-clock budget: quickfile under 30 seconds including
   confirmations.

The test is `@pytest.mark.slow` and runs in CI weekly.

### Hardening rules derived from iteration 31

- Every Kent-first command that targets a filing computes deadline
  and emits a banner in the configured band.
- `aeat doctor` reorders output under deadline pressure, leading
  with filing readiness.
- `aeat quickfile <modelo> --period <p>` is the emergency meta-
  command; Kent-approves but otherwise one command.
- `deadline_mode` configurable: safety, express, adaptive; defaults
  to adaptive after Kent has filed the modelo three times.
- Fail-fast posture under deadline: warnings become refusals;
  `--deadline-override --reason` is the explicit escape, audit-
  logged.
- ARI `--urgent` flag supports the last-minute correction case.
- Extemporanea handling shows surcharge tiers and requires explicit
  confirmation.
- Audit events tag deadline-pressure actions for downstream review.
- Weekly deadline-planning summary in `aeat doctor`.

### Open risks added by iteration 31

- Adaptive mode may lull Kent into trusting auto-approval when a
  subtle data issue should have flagged. Safeguards (fingerprint
  freshness, finding severity, filing count) mitigate but cannot
  substitute for Kent's own judgment.
- `--deadline-override` is a deliberate footgun. The audit-log
  requirement is the only constraint; Kent under pressure may
  invent a thin reason and push through. Quarterly audit of
  override usage surfaces abuse patterns.
- Deadline computation depends on a current calendar in the corpus
  bundle. A stale corpus (bank holidays outdated, regional shifts
  missed) can mis-report deadline by 1 to 3 days; the staleness
  warning in `aeat doctor` mitigates.
- Timezone handling for Madrid time plus Canarias plus other
  regions is subtle. The `Madrid` anchor is explicit; regional
  overrides land in iteration 32.
- Extemporanea surcharge figures must track AEAT regulatory
  changes. Registry-sourced figures plus quarterly audit keep them
  current.
- Quickfile streamlines the happy path and may hide a warning
  Kent would notice in a slower flow. The consolidated progress
  view lists each step; Kent must scan the summary.
- Express mode suppression of tutorials may prevent Kent from
  learning a new concept when it matters (a new modelo's first
  filing); the `--verbose` flag re-enables tutorials and a first-
  time-concept banner always fires once regardless.
- `--dry-run` refusal in the final hour is friction; a Kent who
  wants to preview the fichero might use `export dry-run` which
  is a separate read-only command that remains available.
- The Madrid-time deadline for Kent in other time zones (Canarias
  is UTC+0, Madrid UTC+1 or +2) produces cross-timezone confusion.
  Deadline banner always prints in Madrid time; iteration 32 may
  add a secondary display in Kent's local time.
- Emergency ARI filing at 23:58 creates a record that may be
  accepted or rejected by AEAT; if rejected, Kent is in
  extemporanea territory at 00:00:30. The runbook RB-022 covers
  the contingency.

## Hardening pass iteration 32 (2026-04-24)

Iteration 32 focus: regional tax regimes beyond AEAT common. Spain
has three structurally distinct tax regimes: Territorio Común
(AEAT), Territorios Forales (Basque Country provinces plus Navarra),
and Canarias (common IRPF plus a regional IGIC instead of IVA).
Iterations 1 through 31 assume AEAT common everywhere. A Kent in
Bilbao or Pamplona or Santa Cruz de Tenerife cannot file through
AEAT; he files through his regional tax authority against regional
modelos. This iteration introduces the regime abstraction, per-
regime modelo registries, auth providers, portals, calendars, and
fichero-format variations.

### Supported regimes

Closed set for iteration 32, expandable via corpus bundle:

| Regime id | Authority | Scope |
| --- | --- | --- |
| `es-common` | AEAT | Most of peninsular Spain plus Balearic Islands |
| `es-canarias` | AEAT (IRPF) plus ATC (IGIC) | Canary Islands |
| `es-pv-bizkaia` | HFB (Hacienda Foral de Bizkaia) | Basque province of Bizkaia |
| `es-pv-gipuzkoa` | HFG (Hacienda Foral de Gipuzkoa) | Basque province of Gipuzkoa |
| `es-pv-araba` | HFA (Hacienda Foral de Araba) | Basque province of Araba / Álava |
| `es-nfn` | HTN (Hacienda Foral de Navarra) | Navarra |

The three Basque provinces are distinct regimes; they share most
rules but file through separate provincial authorities.

### Profile regime binding

Every `Profile` record (iteration 11) carries a regime:

```python
class Profile(BaseModel):
    ...
    regime: TaxRegime
    regime_authority: TaxAuthority        # derived from regime at validator time
```

`aeat configure profile add` accepts `--regime <id>` and defaults
to `es-common` when unspecified. The wizard (iteration 13) prompts
for regime after tax-id kind, with sensible defaults inferred from
Kent's stated residency (for example `es-pv-bizkaia` suggested for a
Bizkaia postal code, though Kent confirms).

Profile mutation of regime is heavy: it requires
`aeat configure profile set --regime <new> --confirm` and an
explicit migration step because records created under one regime
reference different modelo IDs, different portals, and different
calendars. The command refuses on a profile that already has
persisted drafts, submissions, or amendments unless Kent also runs
`--migrate-records` and accepts the migration outcome.

### Modelo registry by regime

Iteration 18's `ModeloEntry` gains a `regime` field:

```python
class ModeloEntry(BaseModel):
    regime: TaxRegime
    modelo_id: ModeloId
    ejercicio: Year
    ...
```

Primary key becomes `(regime, modelo_id, ejercicio)`. Same
numeric modelo id across regimes (for example `303`) is a different
record per regime with its own schema, formula ruleset, fichero
format, and portal URL.

Representative mappings (illustrative; actual registry populated
from corpus):

| Purpose | es-common | es-canarias | es-pv-bizkaia | es-nfn |
| --- | --- | --- | --- | --- |
| IRPF pago fraccionado (autónomo) | `130` | `130` | `130-F` (foral variant) | `J-10` |
| IVA / IGIC autoliquidación | `303` | `420` (IGIC) | `303-F` | `F-69` |
| VAT / IGIC resumen anual | `390` | `425` | `390-F` | `F-66` |
| IRPF declaración anual | `100` | `100` (common IRPF) | `100-F` | `J-100` |
| Retenciones trabajadores | `111` | `111` | `110` (foral) | `J-110` |
| Sociedades (LLC) | `200` | `200` | `200-F` | `S-90` |
| Declaración censal | `036`/`037` | `036`/`037` | `036-F` | `F-65` |

Numeric codes for foral and Navarra modelos are illustrative; the
registry ships actual IDs from regional publications. The migration
path between regimes mandates a mapping table from `(regime,
modelo_id)` to target `(regime', modelo_id')`.

### Portal URLs

Per-regime portal map sourced from the corpus bundle
(`corpus/portals/{regime}.json`):

| Regime | Portal base |
| --- | --- |
| `es-common` | `https://sede.agenciatributaria.gob.es/` |
| `es-canarias` | `https://sede.gobcan.es/tributos/` |
| `es-pv-bizkaia` | `https://www.bizkaia.eus/ogasuna/zerbitzu_elektronikoak/` |
| `es-pv-gipuzkoa` | `https://www.gipuzkoa.eus/oficinavirtual/` |
| `es-pv-araba` | `https://web.araba.eus/es/hacienda/` |
| `es-nfn` | `https://hacienda.navarra.es/` |

Portal drift management (iteration 21) applies per-regime; a drift
event specifies the regime so Kent only sees events relevant to his
profiles.

### Auth providers per regime

Authentication mechanisms per regime:

| Regime | Supported providers |
| --- | --- |
| `es-common` | `certificate` (FNMT), `clave-permanente`, `clave-movil`, `clave-pin` |
| `es-canarias` | same as common |
| `es-pv-*` | `bak-q`, `certificate` |
| `es-nfn` | `certificate`, `clave-permanente`, `navarra-nif` |

`bak-q` is the Basque-specific digital identity issued by the IZENPE
CA; it requires its own Cl@ve-style flow. The AuthProvider
abstraction (iteration 10 Phase E) must accept a provider class
identifier and a regime identifier together so the right flow
runs.

Per-profile default auth provider (iteration 11 profile field) is
constrained to the regime's supported set. Cross-regime provider
mismatch refuses at `configure profile add`.

### Filing-calendar overrides

Each regime has its own holiday calendar. Deadline computation
(iteration 31) adds a regime dimension:

- Bizkaia observes Aberri Eguna and other provincial holidays not
  honoured in Madrid.
- Navarra observes San Fermín on July 7.
- Canarias observes Día de Canarias on May 30 and provincial
  saint-day holidays per island.
- Andalucía (within es-common) observes Día de Andalucía; common
  regime still uses AEAT calendar, but AEAT's working-day rule may
  apply differently.

Calendar corpus: `corpus/calendars/{regime}-{ejercicio}.json`.
Deadline shifts follow the regime's own working-day rules.

### Fichero BOE variations

Regional tax agencies each publish their own fichero-format
specification. AEAT uses standard BOE layouts; HFB uses HFB-specific
layouts for modelo 303-F; Canarias uses IGIC-specific layout for
420.

Per-regime fichero serializers live under
`src/aeat/adapters/outbound/aeat/export/_serializers/{regime}/` with symmetric
deserializers. The iteration 3 evidence-bundle manifest gains
`regime` as a required field on every fichero record.

### Regional normative corpus

Iteration 19 corpus bundle grows regime-aware sections:

```text
corpus/normatives/
|-- common/
|-- canarias/
|-- basque/
|   |-- shared/              # rules common across the three provinces
|   |-- bizkaia/
|   |-- gipuzkoa/
|   `-- araba/
`-- navarra/
```

Per-profile queries filter by regime to surface only relevant
normatives.

### Cross-regime profile isolation

Iteration 11's profile isolation already prevents cross-profile data
leaks. Cross-regime isolation adds:

- A draft, submission, or amendment record is never valid across
  regimes; the regime is stamped on every record and validated at
  load time.
- `records filings list --all-profiles` groups by regime in
  output so Kent sees at a glance which filings sit under which
  authority.
- `compare show` refuses to compare a filing in `es-common`
  against a filing in `es-pv-bizkaia` because the casilla spaces
  differ; explicit explanation points Kent at the right same-regime
  comparison.

### Interchange: IVA and IGIC

Kent in Madrid (es-common) invoices a Canarias client. The invoice
is IGIC-exempt from Kent's perspective; the client may owe
reverse-charge IGIC. Kent's 303 (common) still reports the
transaction. Rules:

- The CLI does not itself compute the client's IGIC obligation.
- Kent's invoice record tags `customer_tax_region=es-canarias` so
  the 303 validator applies the correct exemption rule.
- Cross-region invoice flags surface in `compare explain` when
  relevant.

Similar interchange applies between common-regime Kent and Basque
clients, Navarra clients, and intra-EU clients.

### Migration from regime-less workspaces

Workspaces created before iteration 32 have profiles without
`regime`. Startup detection:

1. Detect absence of `regime` in `var/profiles/<id>/profile.json`.
2. Default the profile to `es-common` with a migration event logged
   to the workspace audit journal.
3. Emit a `aeat doctor` warning advising Kent to confirm regime via
   `aeat configure profile regime --set <id>`.

Kent with a non-common regime must run the confirm-and-migrate
path; his prior records are then re-keyed against the correct
regime's registry.

### Kent roleplay: Basque autónomo

```text
$ aeat configure profile add \
    --id personal \
    --regime es-pv-bizkaia \
    --tax-id X1234567L \
    --kind NIE \
    --display-name "Kent Bizkaia" \
    --modelos "130-F 303-F 390-F"
[profile] personal (X1234567L)
Profile 'personal' created with regime 'es-pv-bizkaia' (HFB).

Supported auth providers for this regime:
  bak-q (recommended)
  certificate

$ aeat auth login --provider bak-q
[profile] personal (X1234567L)
Opening HFB auth flow at https://www.bizkaia.eus/ogasuna/...
...

$ aeat status today
[profile] personal (X1234567L) (regime: es-pv-bizkaia)
Today's agenda:
  303-F / 2024Q1   due in 10 days   draft missing
  130-F / 2024Q1   due in 10 days   draft missing
```

All downstream commands use HFB schemas, HFB fichero formats, HFB
portal URLs, and the Bizkaia calendar.

### Kent roleplay: mixed profiles

Kent runs a personal autónomo in Madrid and a company SL in Bilbao.

```text
$ aeat configure profile list
[profile] personal (active)
Profiles:
  personal     X1234567L   NIE   es-common        AEAT   * active
  company-sl   B12345678   CIF   es-pv-bizkaia    HFB

$ aeat --profile personal records filings list
[profile] personal (X1234567L) (regime: es-common)
  303 / 2024Q1  accepted   AEAT
  303 / 2024Q2  accepted   AEAT
  130 / 2024Q1  accepted   AEAT
  ...

$ aeat --profile company-sl records filings list
[profile] company-sl (B12345678) (regime: es-pv-bizkaia)
  303-F / 2024Q1  accepted  HFB
  303-F / 2024Q2  accepted  HFB
  200-F / 2023    accepted  HFB
```

No cross-regime data mixing; each profile stays inside its regime.

### Kent roleplay: profile regime migration

Kent started a Madrid profile, then moved his tax residency to
Bilbao. He needs to switch regimes.

```text
$ aeat configure profile regime --set personal --to es-pv-bizkaia --migrate-records
[profile] personal (X1234567L)

WARNING: Changing a profile's regime rewrites every persisted record
to reference the new regime's registry. Records that have no
equivalent under the new regime are flagged for manual review.

Prior filings (es-common):
  303 / 2024Q1
  303 / 2024Q2
  130 / 2024Q1

Regime-mapping analysis:
  303 / 2024Q1  -> 303-F / 2024Q1 (es-pv-bizkaia equivalent exists)
  303 / 2024Q2  -> 303-F / 2024Q2 (es-pv-bizkaia equivalent exists)
  130 / 2024Q1  -> 130-F / 2024Q1 (es-pv-bizkaia equivalent exists)

CAUTION: Historical filings should stay in their original regime;
new filings should use the new regime. Migrating historical records
may misrepresent the authority they were actually filed with.

Recommended: keep profile 'personal' on es-common for historical records;
create a new profile (for example 'personal-bizkaia') with regime
es-pv-bizkaia for new filings starting from your tax-residency change
date.

Proceed with migration? [y/N]: N
Aborted.
```

The safer path for Kent: create a new profile for the new regime
and keep the old profile read-only for historical records.

### Hardening rules derived from iteration 32

- Every profile carries a `regime` field; regime informs every
  downstream resolution (modelo id, portal, auth provider,
  calendar, fichero format, normative corpus scope).
- Modelo registry keyed by `(regime, modelo_id, ejercicio)`.
- Per-regime auth providers enforced at profile creation.
- Per-regime calendar feeds deadline computation.
- Per-regime portal URL, drift events scoped to regime.
- Per-regime fichero serializers and deserializers.
- Per-regime normative corpus branches.
- Cross-regime filing or comparison refused.
- Interchange flags on transactions (e.g. `customer_tax_region`)
  feed validator rules without requiring Kent to understand
  cross-region rules directly.
- Regime-less legacy workspaces default to `es-common` with
  migration event.
- Profile regime mutation is heavy; creating a new profile is the
  safer pattern.

### Open risks added by iteration 32

- Regional tax agencies publish schemas and portal changes on
  uncoordinated schedules; the corpus bundle must stay current
  across six regimes instead of one.
- Basque Country's three provinces share most rules but not all;
  a contributor implementing province A may miss a province B
  divergence. Registry clarity and province-specific tests mitigate.
- Auth providers per regime may lack stable API docs. `bak-q` in
  particular has a narrower public spec than Cl@ve; testing requires
  a real Basque test identity.
- Interchange rules are subtle and legally dense (intra-EU VAT,
  intra-Spanish-regional VAT, Canarias IGIC exemption). Validator
  rules must be backed by normative citations.
- Profile-regime migration is destructive by default for historical
  records; the safer `new profile per regime change` pattern must
  be prominently documented in the runbook (RB-023 regional-change).
- Modelo numbers collide across regimes (303 in common and 303-F in
  Basque). The registry key is the primary defence; UI must always
  print the regime alongside the modelo number to prevent Kent's
  confusion.
- The CLI cannot automatically select a regime based on postal
  code; the wizard suggests but Kent confirms.
- Regional normatives and AEAT normatives may contradict on edge
  cases; the corpus must track contradictions so validators do not
  apply the wrong rule.
- Calendar holidays beyond the big ones (island-specific, municipal)
  may still shift deadlines; the calendar corpus covers regional
  public holidays but not municipal ones. Kent with a municipal-only
  holiday on deadline day must pre-file.
- Foral social-security rules (regional Sociales) are outside the
  CLI's scope but interact with IRPF calculations. Documentation
  must clarify what the CLI covers and what it does not.
- Regional portal APIs (where they exist) may allow live-read
  integration; that is future work, separate from this iteration.
- Basque-Navarra interchange (Kent in Bizkaia invoicing a client in
  Pamplona) has its own interchange rules distinct from
  Basque-common; registry must handle all pairs, not just
  regime-to-common.

## Hardening pass iteration 33 (2026-04-24)

Iteration 33 focus: post-filing AEAT response monitoring. After
Kent uploads his fichero, the story is not over. AEAT may issue a
justificante, request documentation, propose a different
liquidación, open an inspection, or process a refund. Each has a
deadline, a severity, and a response path. Iterations 1 through 32
covered production and export but treated post-filing as an audit
concern. This iteration defines the post-filing event model,
detection sources, guided-response commands, deadline tracking,
and doctor integration so Kent never misses an AEAT communication.

### Post-filing event kinds

Closed set:

| Event kind | Meaning |
| --- | --- |
| `justificante_issued` | AEAT accepted the filing and issued a receipt. |
| `justificante_pending` | Filing was uploaded but no receipt imported yet. |
| `notification_received` | Generic AEAT notification (catch-all; normalised into a specific kind when possible). |
| `requerimiento_subsanacion` | AEAT requires Kent to fix something specific within a deadline. |
| `requerimiento_documentos` | AEAT requires Kent to supply additional documents. |
| `propuesta_liquidacion` | AEAT proposes a different figure; Kent agrees or files allegations. |
| `liquidacion_provisional` | AEAT has issued a provisional settlement. |
| `liquidacion_definitiva` | AEAT has issued a final settlement. |
| `devolucion_pending` | Refund accepted in principle; payment pending. |
| `devolucion_authorised` | Refund authorised; payment expected. |
| `devolucion_paid` | Refund paid to the registered IBAN. |
| `devolucion_rejected` | Refund refused; reason attached. |
| `inspection_started` | Formal inspection procedure opened. |
| `inspection_closed` | Inspection concluded (with or without adjustments). |
| `filing_rejected` | Initial upload was rejected (format or content error). |
| `sancion_notificada` | Sanction or surcharge notice received. |

Adding a kind requires an ADR amendment.

### Event record shape

```python
class PostFilingEvent(BaseModel):
    event_id: str
    submission_id: str | None         # parent filing; None for workspace-wide events
    profile_id: str
    event_kind: PostFilingEventKind
    severity: Literal["info", "action-required", "urgent", "inspection"]
    detected_at: datetime
    aeat_reference: str               # AEAT's own reference code
    summary: Translatable
    detail: Translatable
    deadline_for_response: datetime | None
    source: Literal[
        "aeat-notification-pdf",
        "aeat-live-fetch",
        "user-manual-entry",
        "portal-scrape",
        "email-attachment-import",
    ]
    related_modelo: ModeloId | None
    related_period: str | None
    status: Literal["open", "acknowledged", "responded", "resolved", "escalated"]
    response: ResponseRecord | None
```

Records persist at `var/profiles/<id>/post-filing/events/{yyyy-mm-dd}.jsonl`.

### Detection mechanisms

Four sources, each producing events:

1. **AEAT notification PDF import** (manual or email-automated):
   Kent receives a PDF from AEAT, runs
   `aeat records notifications import ./aeat-notif.pdf`. A parser
   extracts structured fields (AEAT reference, kind, deadline,
   subject, relation to a prior filing) and produces an event.
2. **AEAT live fetch** (opt-in):
   `aeat records aeat fetch --scope notifications` polls AEAT's
   notification centre. Read-only. Produces events for new items.
3. **User manual entry**:
   `aeat records notifications add --kind requerimiento_documentos
   --aeat-ref REF-12345 --summary "..." --deadline ...` for cases
   where automated parsing fails.
4. **Portal scrape** (Playwright-backed):
   `aeat records aeat fetch --scope notifications --via-browser`
   used when the live-read API is insufficient (the Playwright
   backend from iteration 22 logs into the portal and scrapes the
   notifications list).

Every detection emits a `PostFilingEvent` with `source` labelled
accordingly. A test asserts every detected event is normalised into
the closed event-kind set.

### Response commands

```text
aeat records notifications list [--unread] [--action-required] [--modelo <m>]
aeat records notifications show <event_id>
aeat records notifications acknowledge <event_id>   # mark read
aeat records notifications respond <event_id> [--accept|--disagree] [--upload-ref <ref>] [--notes <text>]
aeat records notifications import <path>
aeat records notifications add --kind <k> --aeat-ref <ref> ...
```

`respond` behaviour per event kind:

- `requerimiento_subsanacion`: guided flow to prepare corrections,
  often leading Kent to `draft create --revision` or ARI path.
- `requerimiento_documentos`: prepare a documentation bundle from
  `audit export` and record Kent's upload reference.
- `propuesta_liquidacion`: record accept or disagree; if disagree,
  guide Kent into `compare show --against aeat-proposal` and the
  alegaciones path.
- `filing_rejected`: guide Kent back to `draft create` with the
  rejection reason surfaced.
- `inspection_*`: point Kent at `docs/runbooks/RB-024-aeat-inspection-response.md`
  and emphasise external legal advice.
- `devolucion_*`: informational; no mandatory response but record
  the payment for reconciliation.

Responses never submit to AEAT on Kent's behalf. They record what
Kent did out-of-band and capture the AEAT reference for audit
trail. Iteration 10 Phase E live-write may later allow automated
responses for narrowly-defined safe cases, but iteration 33 keeps
every response Kent-initiated on the portal.

### Justificante pickup

Every accepted filing should produce a justificante PDF (a receipt
with CSV verification code). Kent imports:

```text
aeat records receipts import ./justificante-303-2024Q1.pdf \
    [--submission-id sf_xyz] [--auto-link]
```

Behaviour:

- Parse the justificante PDF (iteration 18's existing parser).
- Extract CSV, acceptance timestamp, modelo, period, profile tax id.
- Match against a pending submission (either by `--submission-id`
  explicit link or by auto-match on modelo/period/profile/upload-
  time).
- Update the SubmittedFiling record with justificante CSV and PDF
  path.
- Emit a `justificante_issued` event.
- Remove the corresponding `justificante_pending` event if any.

Pending justificantes fire a doctor warning after 48 hours:

```text
  pending justificantes    [warn]    1 submission awaiting receipt
                                     sf_xyz 303/2024Q1 submitted 52h ago
                                     run `aeat records receipts import <path>` once AEAT issues the receipt
```

### Deadline-for-response tracking

Events with `deadline_for_response` feed doctor and the deadline-
banner system from iteration 31:

```text
$ aeat doctor
[profile] personal (X1234567L)

Post-filing attention required:
  requerimiento_documentos   urgent        REF-12345 (due in 3 days)
  propuesta_liquidacion      action-required  PROP-78901 (due in 11 days)
  pending justificantes      warn          1 (submitted 52h ago)
  active inspections         inspection    INSP-12345 (opened 2025-01-10)
```

The iteration 31 urgent-banner system applies to response deadlines
identically to filing deadlines; Kent sees the same urgency language.

### Devolución tracking

Refund filings carry a devolución sub-record:

```text
aeat records devoluciones list [--profile <id>] [--status <s>]
```

```text
[profile] personal (X1234567L)

Pending devoluciones:

  ref         submission       amount        status             est. payment
  DEV-11111   sf_xyz/303Q1     450.00 EUR    aeat-processing    2026-04-15
  DEV-11112   sf_www/303Q2     220.00 EUR    authorised         2026-04-22 (paid)
```

Each status transition emits a `devolucion_*` event so Kent's
audit bundle reflects the refund history.

### Inspection handling

Inspections are legally sensitive. The CLI refuses to automate
responses and instead guides Kent carefully:

```text
$ aeat records notifications show insp_ghi789
[profile] personal (X1234567L)

INSPECTION STARTED (AEAT ref. INSP-12345):
  opened at:         2025-01-10T09:00:00Z
  scope:             fiscal ejercicios 2023 and 2024 (IVA and IRPF)
  inspector:         provided in AEAT portal record
  scope expansion:   AEAT may expand scope during the inspection

This is a legal matter. The CLI will not automate any response.

Strongly recommended:
  1. Do not modify or delete any records (legal retention obligations extend for the duration).
  2. Consult your accountant or a tax attorney before responding.
  3. Prepare evidence bundles per affected filing:
       aeat audit export 303 --period 2023Q1
       aeat audit export 303 --period 2023Q2
       (etc.)
  4. Track all AEAT communications in this namespace:
       aeat records notifications list --inspection INSP-12345
  5. Log your own decisions and actor per action:
       aeat records notifications respond <event_id> --notes "..."

Runbook: `aeat docs runbook aeat-inspection-response` (RB-024)
```

During an active inspection:

- Retention cannot be lowered below the inspection scope (iteration
  28 refuses `erase-personal-data` for covered records unless the
  inspection closes first).
- Audit bundles for inspection-scoped filings are pre-built and
  stamped `inspection_ready=true`.
- Every command that mutates inspection-scoped records logs an
  `inspection_touch` event for auditability.

### Live fetch safety

Live fetch of notifications is read-only and gated by iteration 12
authentication plus iteration 6 auth errors. The command refuses
under the four-factor live-write gate (iteration 10); it is a
`live_read` per iteration 8 classification.

### Kent roleplay: routine post-filing flow

Kent filed 303/2024Q1 a week ago. He opens his terminal to check
status.

```text
$ aeat doctor
[profile] personal (X1234567L)

Post-filing attention required:
  justificante pending      warn          1 (submitted 8 days ago)
  devoluciones pending      info          1 refund awaiting processing

Next action:
  Upload your justificante PDF via `aeat records receipts import <path>`
  or fetch from AEAT: `aeat records aeat fetch --scope notifications`

$ aeat records aeat fetch --scope notifications
Fetching new notifications from AEAT (live-read)...
  [ok] 2 new events
  justificante_issued       JU-54321 (303/2024Q1)
  devolucion_authorised     DEV-11111 (303/2024Q1, 450 EUR)

$ aeat records receipts import --auto-link-from aeat
  [ok] linked JU-54321 to sf_xyz (303/2024Q1)
  [ok] justificante PDF downloaded to var/profiles/personal/submissions/sf_xyz/justificante.pdf
  [ok] pending justificantes warning cleared
```

### Kent roleplay: requerimiento

AEAT asks for supporting invoices.

```text
$ aeat records notifications import ~/Downloads/aeat-requerimiento.pdf
Parsing AEAT notification...
  [ok] event_id: req_abc123
  kind: requerimiento_documentos
  AEAT ref: REF-12345
  related to: 303/2024Q1 (sf_xyz)
  deadline: 2025-01-25 (9 days)

$ aeat records notifications show req_abc123
[profile] personal (X1234567L)

Requerimiento de documentos (AEAT ref. REF-12345):
  related:     submission sf_xyz / 303 / 2024Q1
  received:    2025-01-15T10:23:00Z
  deadline:    2025-01-25T23:59:59Z (in 9 days)
  request:     AEAT requires supporting invoices for casillas 28 through 31.
  status:      action-required

Guided response:

  1. Build a documentation bundle:
     aeat audit export 303 --period 2024Q1 --scope invoices-only
     -> var/profiles/personal/audit/bundle-303-2024Q1.zip

  2. Upload the bundle at https://sede.agenciatributaria.gob.es/.../subsanacion
     with AEAT reference REF-12345.

  3. Record the response:
     aeat records notifications respond req_abc123 \
         --upload-ref REF-67890 \
         --notes "bundle with 47 invoices"
```

Kent follows steps 1 and 2 manually, then records the response.

### Kent roleplay: propuesta de liquidación

AEAT proposes an extra 1250 EUR of liability.

```text
$ aeat records notifications show prop_def456
[profile] personal (X1234567L)

Propuesta de liquidación (AEAT ref. PROP-78901):
  related:      submission sf_xyz / 303 / 2024Q1
  AEAT figure:  1 250.00 EUR additional liability
  Kent figure:  0 EUR additional liability
  difference:   +1 250.00 EUR
  deadline:     2025-02-10T23:59:59Z (in 24 days)

Review before responding:

  aeat compare show 303 --period 2024Q1 --against aeat-proposal prop_def456

Options:

  accept:
    aeat records notifications respond prop_def456 --accept
    (AEAT issues final liquidación; Kent pays 1 250 EUR per AEAT figure.)

  disagree:
    Review the discrepancy, gather supporting evidence, and file
    alegaciones via the AEAT portal within the deadline.
    aeat records notifications respond prop_def456 --disagree \
        --upload-ref ALEG-111 \
        --notes "counter-evidence attached"
```

Kent runs `compare show`, investigates, and decides deliberately.

### Hardening rules derived from iteration 33

- Post-filing event model with closed kinds; new kinds require ADR
  amendment.
- Four detection sources; every event normalises into the closed
  kind set.
- Deadline-for-response feeds doctor banners and iteration 31
  urgency language.
- Justificante pickup auto-links to pending submissions; pending
  justificante warning at 48 hours.
- Devolución tracking per refund filing; transitions log events.
- Inspection namespace stamps records `inspection_ready=true`;
  retention-lowering refuses under active inspection.
- Responses never auto-submit; CLI records Kent's out-of-band
  action plus references.
- Live fetch is read-only and gated per iteration 8 classification.
- Runbook RB-024 documents inspection response; RB-025 documents
  propuesta de liquidación; RB-026 documents requerimiento handling.

### Open risks added by iteration 33

- AEAT notification PDF parsing depends on document structure that
  may change; the parser must fail loudly with an actionable error
  rather than silently misparse.
- Live notification fetch depends on the AEAT notification centre
  API remaining stable; portal drift (iteration 21) applies.
- Inspection handling is legally sensitive; the CLI's guidance is
  informational. Kent must consult professional advice. The runbook
  reinforces this explicitly.
- Propuesta de liquidación acceptance is binding. The CLI must not
  make the accept path easier than the disagree path, to avoid
  steering Kent into unwanted outcomes.
- Pending-justificante warning at 48 hours may fire spuriously when
  AEAT's processing is slow. A configurable threshold mitigates.
- Devolución payment estimates are AEAT-provided; actuals may
  differ. Kent should reconcile from his bank statement.
- Live fetch requires an active auth session; Kent with an expired
  certificate will see stale data. Doctor surfaces this through
  iteration 12's expiry warning.
- Event correlation across modelos (a single inspection may span
  multiple filings) requires clean parent-child relationships in
  the event store; the record shape supports it but the UX of
  cross-filing navigation is yet to be hardened.
- Response deadlines follow different arithmetic than filing
  deadlines: "10 business days" is common, with regional holiday
  effects. The calendar corpus covers this but cross-regime Kent
  with filings under different authorities gets different deadlines.
- Automated email-attachment import is convenient but introduces
  email-provider integration as a trust boundary. Iteration 33 lists
  it as a source but does not implement it here; future iteration
  covers the email-provider safety contract.
- Audit bundles for inspection-scoped filings are pre-built; the
  pre-build may run under load and slow the workspace. A background
  mode would help but adds complexity iteration 33 does not cover.
- Justificante PDFs may include sensitive content (full NIE, bank
  account fragments); retention and share rules from iteration 28
  apply but the receipts import path should not widen the scrub
  surface unintentionally.
