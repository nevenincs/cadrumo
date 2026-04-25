# JSON Output Contract

Issue [#399](https://github.com/wgergely/aeat/issues/399) currently ships
Phase 1 foundations for a shared `--json` contract. The root CLI does not
yet expose a global `--json` flag, and the shared contract is not yet wired
across the CLI.

## Shipped In Phase 1

Phase 1 ships reusable transport primitives through `aeat.cli`:

- `OutputSchema` is the strict base model for command-specific JSON payloads.
- `SchemaEnvelope` is the shipped success envelope for future shared emitters.
- `register_schema()` and `SCHEMA_REGISTRY` provide the shared schema
  registry.
- `ExitCode` and `exit_with()` provide the stable process-exit surface.
- TTY and log-level helpers provide the shared transport rules that later
  root-callback wiring will use.

### Shipped Success Envelope

The current `SchemaEnvelope` shape is:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `str` | Defaults to `"1"`. |
| `command` | `str` | Stable space-delimited command path. |
| `result` | `OutputSchema` | Command-specific success payload. |
| `warnings` | `list[str]` | Defaults to `[]`. |

Example shape:

```json
{
  "schema_version": "1",
  "command": "some command",
  "result": {},
  "warnings": []
}
```

`status` and `metadata` are not part of the shipped Phase 1 envelope.

### Registry Status In Phase 1

The registry API is shipped, duplicate-safe, and rejects blank command
paths. No production command is registered against it yet in the current
tree.

### Shared Transport Helpers In Phase 1

- `AEAT_LOG_LEVEL` is the shipped log-level environment variable.
- Allowed `AEAT_LOG_LEVEL` values are `quiet`, `default`, `verbose`, and
  `debug`.
- Log-level resolution is flags first, then `AEAT_LOG_LEVEL`, then
  `default`.
- Invalid `AEAT_LOG_LEVEL` values raise a typed resolution error.
- `NO_COLOR` disables ANSI colour output.
- `NO_COLOR` wins over `AEAT_FORCE_COLOR`.
- `AEAT_FORCE_COLOR` forces ANSI colour output.
- Rich progress is only safe when both stdout and stderr are TTYs and the
  caller is not in quiet, JSON, or no-progress mode.
- Interactive commands can refuse non-TTY stdin through a typed
  `NonTtyRefusedError`.
- Logging scrubbing is active at the logging layer before formatting.

For the current stable process-exit table, see
[`exit-codes.md`](exit-codes.md).

## Existing Command-Local JSON Today

Some commands already expose their own `--json` flags. Those outputs are
existing command-local behavior, not the shared `#399` contract rollout.

For example, `aeat submission schemas --json` currently writes a bare JSON
array to stdout. It does not emit `SchemaEnvelope`, and it is not routed
through `SCHEMA_REGISTRY`.

## Deferred Pipe-Safety Goal

The Kent-facing end state for `#399` is still:

```text
aeat X --json | jq ...
```

Phase 1 does not claim that this works across every command yet. The shared
primitives that make that rollout possible are shipped; the CLI-wide command
adoption remains deferred.

## Deferred Until #398

The following work is intentionally not shipped in Phase 1 and depends on
issue [#398](https://github.com/wgergely/aeat/issues/398):

- shared `ErrorEnvelope` integration
- machine-readable JSON errors on stderr
- root-level `--json` wiring across non-workflow commands
- per-command schema registration and shared envelope adoption
- CLI-wide enforcement of the wireframe stdout/stderr discipline

## Deferred Until #393

Workflow `run` and `next` adoption stay deferred until issue
[#393](https://github.com/wgergely/aeat/issues/393).
