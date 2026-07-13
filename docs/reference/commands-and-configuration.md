# Commands and configuration

## Command and workflow-stage lookup

Until S74 regenerates the command reference, live help is authoritative for
command paths, arguments, options, refusals, and root behavior. Start with
`cadrumo --help`, then append `--help` to the command family or leaf you need.
The canonical human executable is `cadrumo`; `cadrumo-mcp` is the separate MCP
executable.

The generated pages below are a pending S74 snapshot. Their structure remains
useful for locating a family, but stale headings or executable spellings are
not canonical until regeneration completes.

| Need | Pending generated lookup |
| --- | --- |
| Profile, authentication, diagnostics, Google, and local configuration | [Configuration commands](../cli/config.rst) |
| Ledger, modelo, review, live-read, export, record, and reconciliation commands | [Application commands](../cli/app.rst) |
| JSON envelopes and output schemas | [Command schemas](../cli/schemas.rst) |
| Non-interactive and machine-facing conventions | [Automation reference](../cli/automation.rst) |

The filing stages relate as `calculate` → `review` → `verify` → `export` →
human upload → local record → reconcile. The stage names describe Cadrumo's
local workflow. Until S74 completes, exact command definitions come from live
`cadrumo ... --help`; the generated pages above are navigation snapshots only.
Read [the workflow explanation](../explanation/index.md) for why the stages are
separate and [the how-to guides](../how-to/index.md) for task sequences.

## Configuration ownership

| Prefix or field family | Owner | Scope |
| --- | --- | --- |
| `CADRUMO_*` / `cadrumo_*` | Cadrumo product | Local state, output, providers, profiles, credentials storage, and product behavior |
| `AEAT_*` / `aeat_*` | AEAT integration | Authority endpoints, authority credentials, live-read controls, and preserved authority terminology |

Examples of product controls include `CADRUMO_LOCAL_STORAGE_ROOT`,
`CADRUMO_SECRET_STORE_BACKEND`, `CADRUMO_SECRET_STORE_DIR`,
`CADRUMO_SECRET_PASSPHRASE`, and `CADRUMO_OUTPUT_LANGUAGE`. Live
`cadrumo config --help` and its leaf help define operator-facing configuration;
the [pending generated configuration snapshot](../cli/config.rst) is refreshed
by S74. Python configuration fields are listed under the generated
[Cadrumo API](../api/cadrumo.rst).

Former product-owned `AEAT_*` state controls are not aliases for `CADRUMO_*`.
Authority-owned `AEAT_*` integration controls remain valid only when they name
the external authority boundary.
