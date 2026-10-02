# Reading tool results, refusals, and CLI reference envelopes

Read the response contract of the interface you are using. MCP returns a
structured tool result and the same JSON as text content. Read that result and
any nested operation response before deciding what happened.

## Read MCP outcomes and nested operation responses

- `outcome: refused` carries a `code`. Report that code and follow only recovery
  supported by the current tool or registered operation contract.
- `outcome: unresolved` means the reply did not establish what happened. Preserve
  the returned `request_id` and other correlation fields. A request ID is not an
  operation receipt, and an unresolved reply is not evidence that an effect failed.
- `outcome: submitted` carries a `receipt`. Submission does not establish
  completion. Preserve the receipt and use `observe` to read the operation's
  current state. If the nested `start` is unresolved, reconcile the recorded
  operation before deciding whether a start or resume is needed.
- `outcome: reply` wraps a runtime `reply` or a result `document`. Read its
  discriminator and nested outcome. A reply can contain an access refusal, a
  refused observation, or a refused result document. Use `result` for the settled
  projection and `review` for a review projection; follow their declared schemas.
- `status`, discovery, authorization, authentication, and `authority` have their
  own result shapes. Read the fields actually returned by that tool.

The MCP error indicator can mark a refused or unresolved response. Read the
structured response even when that indicator is set. Report the actual operation
verdict and findings; do not invent a CLI exit code or success envelope for it.

## Recovery must remain eligible in the current interface

Use `status` to check the connection's exact profile and current authorization.
Discover a recovery operation with `search`, then read its current contract and
input schema with `describe`. A CLI recovery path or a procedure is a workflow
reference; it does not establish MCP exposure, permission, or payload shape.
Submit recovery only when the operation is available, its required values are
known, and the user authorized the action. Otherwise report the missing authority
or inputs for human handoff. Never bypass a refusal by executing a CLI path.

Reading a review does not apply it. Use `respond` only under the originating
session's response authority and with the returned operation, interaction, and
revision coordinates. Preserve operation receipts across disconnects and
reconcile uncertain effects before submitting them again.

## CLI reference: read `status`, not stdout-versus-stderr

For a separately authorized CLI invocation, use `--format json`. Its success and
error envelopes have the following contract. These fields and process exit codes
describe the CLI interface.

The success envelope and the error envelope share `schema_version`, `command`,
`status`, and `notices`. Read the single `status` field to learn the outcome:

- `success` — the command completed; read `result`.
- `warning` — the command completed but attached a `warning` notice; read `result`
  AND surface the notice (see the safety rule).
- `error` — the command failed; the document is on stderr with a nested `error`
  carrying `code`, `category`, `message`, `action`, `retryable`, and `runbook_id`.

Do not branch on whether output arrived on stdout or stderr; branch on `status`.

## CLI reference: exit code `1` is a verdict, not a crash

The exit-code table is meaningful, and the load-bearing distinction is:

- `0` — success.
- `1` — an expected, actionable domain verdict (for example a verify that resolves
  BLOCKED or INCOMPLETE). **Do not abort on a `1`.** Read the result, act on the
  findings, fix, and re-run.
- `2` REFUSED, `3` AUTH, `4` INTEGRITY, `5` FAIL, `7` LOCKED_BY_DESIGN,
  `8` LOCKED_BY_CONCURRENCY, `10` NO_NETWORK, `20` USAGE — each names a specific,
  recoverable condition; read the `error.code` and the `error.message`.
- `6` INTERNAL is reserved for a genuine crash. Only a `6` is an abort-and-report.

## CLI reference: follow the refusal action algorithm exactly

An error document carries its recovery verdict at `error.action`. It can be `null`;
an error does not imply that a command is safe to run. Read the nested action record
before acting:

1. When `error.action.action` is non-null, use `conditionality`,
   `missing_argument_names`, and `argument_bindings` before invoking anything.
   - `immediate` requires no missing arguments and only `resolved` bindings. Execute
     the canonical `cli_path` with those resolved values only through the
     separately authorized CLI interface. In MCP, apply the recovery eligibility
     rule above. Treat
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

## CLI reference: diagnostics ride on `notices`, nowhere else

Non-blocking advisories and next-step hints arrive only as typed `notices`
(`severity`, `code`, `message`, `action`, `context`). There is no other advisory
channel to scrape. Read `notices` on every CLI result. In MCP, read the actual
operation findings, events, and result or review projections supplied by its
contract; do not assume every tool response contains CLI `notices`.
