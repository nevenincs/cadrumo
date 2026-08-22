# Complete CLI cold-process baseline

`baseline.json` is execution evidence for every root, group, and leaf returned
by the live command walker. It is generated rather than hand-maintained:

```powershell
uv run --no-sync python -m dev.benchmarks.cli.capture_baseline --warmups 1 --samples 3 --workers 4
uv run --no-sync python -m dev.benchmarks.cli.capture_baseline --check
```

Each node has one discarded warmup followed by three independent resolution and invocation samples. Quiet
`--version` controls bracket the sweep and recur after every bounded batch, so
host drift during a long run remains visible. Controls run at the same bounded
concurrency as command batches, making the calibrated ratios honest about host
contention. Rankings use median control ratios. Raw observations retain latency, import-family membership,
Pydantic construction counts, filesystem changes and operations, storage-call
counts, exit status, and timeout/failure status. Host and tool metadata excludes
usernames and absolute storage paths.

The generator atomically checkpoints after each deterministic batch to
`baseline.partial.json`. A rerun resumes only when its sampling configuration
and complete live-path census still match; otherwise it fails rather than
combining unlike measurements. The checkpoint is deleted after the validated
final artifact is published.

Invocation mode is always labelled `help-render`. This is intentional: `--help`
exercises real Click/Typer resolution and rendering but exits before the handler.
The baseline therefore cannot delete data, write storage, contact a network,
open a browser, or submit a filing. Later execution-specific gates must provision
purpose-built fixtures for handlers; this evidence never pretends help rendering
is handler execution.

`--check` compares the artifact with the live census as an exact set and also
checks kind, execution policy, sample sufficiency, safe invocation mode, and both
rankings. Adding, removing, or reclassifying any CLI node makes the check fail;
there is no fixed command count to update.
