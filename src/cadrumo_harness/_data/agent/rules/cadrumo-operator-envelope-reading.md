# Reading the CLI envelope and exit codes

Every `--format json` response shares one spine. Read it the same way every time.

## Read `status`, not stdout-versus-stderr

The success envelope and the error envelope share `schema_version`, `command`,
`status`, and `notices`. Read the single `status` field to learn the outcome:

- `success` — the command completed; read `result`.
- `warning` — the command completed but attached a `warning` notice; read `result`
  AND surface the notice (see the safety rule).
- `error` — the command failed; the document is on stderr with a nested `error`
  carrying `code`, `category`, `message`, `action`, `retryable`, and `runbook_id`.

Do not branch on whether output arrived on stdout or stderr; branch on `status`.

## Exit code `1` is a verdict, not a crash

The exit-code table is meaningful, and the load-bearing distinction is:

- `0` — success.
- `1` — an expected, actionable domain verdict (for example a verify that resolves
  BLOCKED or INCOMPLETE). **Do not abort on a `1`.** Read the result, act on the
  findings, fix, and re-run.
- `2` REFUSED, `3` AUTH, `4` INTEGRITY, `5` FAIL, `7` LOCKED_BY_DESIGN,
  `8` LOCKED_BY_CONCURRENCY, `10` NO_NETWORK, `20` USAGE — each names a specific,
  recoverable condition; read the `error.code` and the `error.message`.
- `6` INTERNAL is reserved for a genuine crash. Only a `6` is an abort-and-report.

## Follow the refusal action algorithm exactly

An error document carries its recovery verdict at `error.action`. It can be `null`;
an error does not imply that a command is safe to run. Read the nested action record
before acting:

1. When `error.action.action` is non-null, use `conditionality`,
   `missing_argument_names`, and `argument_bindings` before invoking anything.
   - `immediate` requires no missing arguments and only `resolved` bindings. Execute
     the canonical `cli_path` with those resolved values. Treat
     `target_command_key` as the stable identity check; do not construct an alias or
     a command from error prose.
   - `requires_arguments` means do not issue a partial command. Obtain exactly the
     names in `missing_argument_names`, retain the already resolved bindings, then
     invoke the canonical target only after all required values are available. A
     `missing` binding is never a value to invent or pass through.
   - `not_applicable` cannot accompany an action in a valid envelope. Stop and
     report the malformed contract instead of guessing a recovery.
2. When `error.action.action` is null, require `no_recovery_outcome` and never infer
   a command from the error code, message, context, evidence, or condition id.
   - `terminal`: stop; this refusal has no recovery action.
   - `safety`: do not bypass the safety condition; surface the evidence and seek a
     safe human decision.
   - `operator_decision`: surface the facts and ask the operator to choose the next
     step; do not manufacture one.

If the record lacks the fields required by either branch, treat it as a contract
failure and report it. Never downgrade a no-recovery outcome into a retry or a
hand-written CLI invocation.

## Diagnostics ride on `notices`, nowhere else

Non-blocking advisories and next-step hints arrive only as typed `notices`
(`severity`, `code`, `message`, `action`, `context`). There is no other advisory
channel to scrape. Read `notices` on every result.
