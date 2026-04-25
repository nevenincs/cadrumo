# Exit Codes

The CLI ships this stable process exit-code table. In JSON mode, failures are
already structured as single-line JSON on `stderr`; the numeric exit code is
still the machine-facing termination signal.

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
| `LOCKED_BY_CONCURRENCY` | `8` | Reserved for concurrency-lock failures. |
| `NO_NETWORK` | `10` | Required network access is unavailable. |
| `USAGE` | `20` | Invalid CLI usage. |

## Runtime notes

- JSON-mode failures write JSON to `stderr`, not `stdout`.
- Success keeps `stderr` empty.
- The table still reserves `8` for concurrency locking, but the current error
  boundary does not emit it yet.
- Runtime category mapping for `LOCKED` still yields `7`, not `8`.

## Representative uses

- `SUCCESS (0)`: a registered `--json` command completed and emitted the shared
  success envelope on `stdout`.
- `REFUSED (2)`: the CLI declined a requested action.
- `LOCKED_BY_DESIGN (7)`: the command is blocked by product policy or a current
  locked category mapping.
- `LOCKED_BY_CONCURRENCY (8)`: reserved in the contract table for future
  concurrency-lock emission.
- `USAGE (20)`: the invocation is structurally invalid.

For the bounded shared `--json` contract, see [`json-contract.md`](json-contract.md).
