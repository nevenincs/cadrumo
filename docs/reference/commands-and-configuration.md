# Commands and configuration

## Command and workflow-stage lookup

The command-line interface (CLI) exposes live help as the command authority.
The canonical executable is `aeat`.

| Command family | Live authority | Structured map |
| --- | --- | --- |
| Root behavior and global options | `aeat --help` | [CLI overview](../cli/index.rst) |
| Profile, authentication, diagnostics, Google, and local configuration | `aeat config --help` and leaf help | [Configuration commands](../cli/config.rst) |
| Ledger, modelo, review, live-read, export, record, and reconciliation | `aeat app --help` and leaf help | [Application commands](../cli/app.rst) |
| JSON envelopes and output schemas | Leaf help with the selected format | [Command schemas](../cli/schemas.rst) |
| Non-interactive conventions | Root and leaf help | [Automation reference](../cli/automation.rst) |

The filing stages relate as `calculate` → `review` → `verify` → `export` →
human upload → local record → reconcile. The stage names describe Cadrumo's
local workflow. Exact command definitions come from live `aeat ... --help`.
Read [the workflow explanation](../explanation/index.md) for why the stages are
separate and [the how-to guides](../how-to/index.md) for task sequences.

## Configuration ownership

| Prefix or field family | Owner | Scope |
| --- | --- | --- |
| `CADRUMO_*` / `cadrumo_*` | Cadrumo product | Local state, output, providers, profiles, credentials storage, and product behavior |
| `AEAT_*` / `aeat_*` | AEAT integration | Authority endpoints, authority credentials, live-read controls, and preserved authority terminology |

Examples of product controls include `CADRUMO_LOCAL_STORAGE_ROOT`,
`CADRUMO_SECRET_STORE_BACKEND`, `CADRUMO_SECRET_STORE_DIR`, and
`CADRUMO_OUTPUT_LANGUAGE`. `CADRUMO_SECRET_PASSPHRASE` remains a separately
governed programmatic-substrate setting; the CLI does not read it as an
operator secret-input fallback. Use the explicit leaf `--secrets-stdin` /
`--secrets-fd` pair or root `--profile-secrets-stdin` /
`--profile-secrets-fd` pair described in
[Protect access to your data](../how-to/protect-data-access.md#run-without-a-passphrase-prompt).
Live
`aeat config --help` and its leaf help define operator-facing configuration.
The [configuration map](../cli/config.rst) groups those commands. Python fields
are listed in the generated Cadrumo application programming interface
([API](../api/cadrumo.rst)).

Former product-owned `AEAT_*` state controls are not aliases for `CADRUMO_*`.
Authority-owned `AEAT_*` integration controls remain valid only when they name
the external authority boundary.
