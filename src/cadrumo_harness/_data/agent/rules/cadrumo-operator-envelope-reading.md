# Reading tool results, refusals and CLI envelopes

Read the structured result before deciding what happened. Report the actual verdict and
findings; never invent an exit code or a success envelope. Run `aeat` with
`--format json` so its result is an envelope.

## Tool-server outcomes

- `outcome: refused` carries a `code`. Report it and follow only recovery that the
  tool's or operation's contract supports. A refusal for want of a sign-in, or of an
  act that is the person's, carries a `remedy`: pass it on.
- `outcome: unresolved` means the reply did not establish what happened. Keep the
  `request_id` and other correlation fields; a request ID is not a receipt, and the
  effect may already be committed. Do not repeat the call. The reply's
  `unknown_outcome` says what to read instead: the operation with `observe` or
  `result`, or the installation action named in `outcome_read_by`. Only an `execute`
  that carried an `idempotency_key` may be repeated, with the same key, operation and
  payload.
- `outcome: submitted` carries a `receipt`. Submission is not completion: keep the
  receipt and `observe` the operation's state. If the nested `start` is unresolved,
  reconcile the recorded operation before starting or resuming it again.
- `outcome: reply` wraps a runtime `reply` or a result `document`. Read its
  discriminator and nested outcome; it can hold an access refusal or a refused
  observation or result. Use `result` for the settled projection and `result_page`
  for further pages.
- An operation that settled `refused` or `failed` has no result. The `result` reply
  carries `error_detail` beside the refused document: the registered `error_code`, the
  `message_key`, the `context` and any `precondition_verdict_json`, which is what the
  command line prints for the same refusal. Report them. Without `error_detail`, the
  observation's `refusal_ref` or `failure_error_code` carries the code.
- `status`, discovery and `authority` have their own result shapes: read the fields
  returned. The MCP error flag marks a refused reply only; an unresolved outcome is not
  an error and is not to be retried as one.
- Reading a review applies nothing. `respond` (inspect, apply or reject) works only
  under the originating session's response authority, with the returned operation,
  interaction and revision coordinates.
- To recover, `search` for the recovery operation, `describe` it, and submit it once its
  inputs are known and, for a destructive act, the person has given the go-ahead;
  otherwise report the missing inputs.

## CLI envelopes: read `status`, not stdout versus stderr

Success and error documents share `schema_version`, `command`, `status` and
`notices`. Branch on `status`:

- `success`: the command completed; read `result`.
- `warning`: it completed but attached a `warning` notice. Read `result` and surface
  every `warning` notice to the taxpayer with its resolved `action`; never proceed as
  if the command fully succeeded.
- `error`: it failed; the nested `error` carries `code`, `category`, `message`,
  `action`, `retryable` and `runbook_id`.

Advisories and next-step hints arrive only as typed `notices` (`severity`, `code`,
`message`, `action`, `context`); there is no other channel to scrape. Read `notices`
on every CLI result. Tool-server replies carry no CLI `notices`: read the findings,
events and projections their contract supplies.

## Exit codes

`0` is success. `1` is an expected domain verdict, for example a verify that resolves
BLOCKED or INCOMPLETE: do not abort, read the result, act on the findings, fix and
re-run. `2` REFUSED, `3` AUTH, `4` INTEGRITY, `5` FAIL and `7` LOCKED each name a
specific condition: read `error.code` and `error.message`. `6` INTERNAL is reserved
for a crash; only a `6` is abort and report.

## Follow the refusal action algorithm exactly

An error's recovery verdict is at `error.action`, which can be `null`. An error never
implies a command is safe to run.

1. When `error.action.action` is non-null, read `conditionality`,
   `missing_argument_names` and `argument_bindings` before invoking anything.
   - `immediate`: no missing arguments and only `resolved` bindings. Run the canonical
     `cli_path` with those values only, as an `aeat` command the person approves. Use
     `target_command_key` as the stable identity check; never build an alias or a
     command from error prose.
   - `requires_arguments`: issue no partial command. Obtain exactly the names in
     `missing_argument_names`, keep the resolved bindings, and invoke the target only
     when every value is known. A `missing` binding is never a value to invent.
   - `not_applicable` cannot accompany an action in a valid envelope: stop and report
     the malformed contract.
2. When `error.action.action` is null, require `no_recovery_outcome` and never infer a
   command from the code, message, context, evidence or condition id.
   - `terminal`: stop; this refusal has no recovery action.
   - `safety`: do not bypass the condition; surface the evidence and seek a safe human
     decision.
   - `operator_decision`: surface the facts and ask the person to choose the next
     step; do not manufacture one.

A record missing the fields either branch needs is a contract failure: report it.
Never turn a no-recovery outcome into a retry or a hand-written command.
