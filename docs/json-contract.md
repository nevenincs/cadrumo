# JSON Output Contract

Branch `feature/399-json-output-contract` ships a root `--json` flag. The
root callback enables JSON mode once and persists that state in the Click
context for participating commands.

This is a bounded shared contract, not a claim of CLI-wide adoption. The
shared registry currently covers these command paths:

- `auth list-providers`
- `auth login`
- `auth logout`
- `auth status`
- `auth whoami`
- `browser health`
- `filing reconcile`
- `modelos applicable-to`
- `modelos list`
- `modelos show`
- `modelos year-plan`
- `portals for-modelo`
- `portals list`
- `portals show`
- `sede list-expedientes`
- `sede notifications`
- `submission check-nif`
- `submission diff`
- `submission schemas`
- `submission verify`
- `workflow list`
- `workflow next`
- `workflow run`
- `workflow show`

The registry is validated against real CLI output. Documentation should not
imply broader `--json` adoption beyond this registered set.

## Success envelope

JSON-mode success output uses one shared top-level envelope:

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `string` | Shared contract version. |
| `command` | `string` | Stable space-delimited command path. |
| `result` | `object` | Command-specific success payload. |
| `warnings` | `array[string]` | Non-fatal warnings. |

Example:

```json
{
  "schema_version": "1",
  "command": "submission schemas",
  "result": {},
  "warnings": []
}
```

`submission schemas --json` now emits this shared envelope. It no longer
returns a bare JSON array.

## Error contract

In JSON mode, failures write a single-line JSON document to `stderr` only. The
top level contains an `error` object. Successful JSON-mode commands keep
`stderr` empty.

## Pipe safety

Representative root-flag commands are tested for pipe-safe behavior:

- success `stdout` is valid `jq` input
- success leaves `stderr` empty
- UTF-8 output survives a `cp1252` console path
- failures write JSON only to `stderr`

The shipped guarantee is therefore: registered commands using the shared root
flag obey the shared stdout/stderr contract under the tested representative
paths. It is not yet a blanket statement about every CLI command.

## Boundaries

- The contract is shared through the root callback and Click context state.
- The command set is explicitly bounded by the populated registry above.
- Failure output is already structured in JSON mode.
- Coverage claims should stay conservative until more commands are registered
  and verified.
