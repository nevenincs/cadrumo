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

## Recover from a mis-call using the instructive surface

The CLI never fails as a silent black hole. A bad `--year`/`--period` enumerates the
accepted period tokens; a bad enum value lists the accepted set; the "did you mean"
table suggests the nearest verb; and every error envelope carries a resolved
`action`. When a call is refused, read that action and the accepted set and
re-issue the corrected command yourself — you rarely need to ask the human to fix a
syntax error. An action that resolves to a no-recovery outcome is telling you the
refusal has no automatic fix; do not invent one.

## Diagnostics ride on `notices`, nowhere else

Non-blocking advisories and next-step hints arrive only as typed `notices`
(`severity`, `code`, `message`, `action`, `context`). There is no other advisory
channel to scrape. Read `notices` on every result.
