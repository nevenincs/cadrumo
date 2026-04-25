# Exit Codes

Issue [#399](https://github.com/wgergely/aeat/issues/399) Phase 1 ships a
stable CLI exit-code table in `src/aeat/cli/_exit_codes.py`. This is the
current machine-facing authority for process termination. Older wireframe
category drafts are not the shipped contract.

| Name | Code | Current meaning |
|---|---:|---|
| `SUCCESS` | `0` | Command completed successfully. |
| `ERROR` | `1` | Generic error when no narrower stable code applies. |
| `REFUSED` | `2` | The CLI refused the requested action. |
| `AUTH` | `3` | Authentication or authorization failure. |
| `INTEGRITY` | `4` | Integrity or trusted-input validation failure. |
| `FAIL` | `5` | Operation failed after a valid attempt. |
| `INTERNAL` | `6` | Internal AEAT CLI failure. |
| `LOCKED_BY_DESIGN` | `7` | The action is intentionally locked by product design. |
| `LOCKED_BY_CONCURRENCY` | `8` | The action is blocked by concurrent work or a held lock. |
| `NO_NETWORK` | `10` | Required network access is unavailable. |
| `USAGE` | `20` | Invalid CLI usage. |

## Representative uses

- `SUCCESS (0)`: a future shared success emitter completed and returned a
  valid `SchemaEnvelope`.
- `REFUSED (2)`: `refuse_if_stdin_non_tty()` blocked an interactive-only
  command on piped stdin.
- `LOCKED_BY_CONCURRENCY (8)`: reserved now for the later `#400`
  concurrency-lock contract.
- `USAGE (20)`: CLI invocation was structurally invalid.

## Phase 1 behavior

- `exit_with()` optionally writes one plain stderr line, then exits with the
  selected numeric code.
- Phase 1 does not emit a structured JSON error envelope.
- Machine-readable stderr error envelopes are deferred until issue
  [#398](https://github.com/wgergely/aeat/issues/398).

For the success-envelope foundations behind future `--json` rollout, see
[`json-contract.md`](json-contract.md).
