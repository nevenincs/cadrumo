# Complete CLI cold-process baseline

`baseline.json` is the compact index for every root, group, and leaf returned
by the command walker in one immutable pre-optimization source snapshot. It is
generated rather than hand-maintained:

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

`--check` proves source-bound internal integrity: it authenticates and decompresses
`baseline.raw.json.gz`, recomputes every distribution, control ratio, failure
index, and ranking, and requires the compact index to be an exact derivation of
the lossless observations. It independently authenticates `baseline.census.json`,
which binds the frozen source digest to every path, kind, owner, and execution
policy, then requires exact observation-set and metadata equality. `--check-fresh` adds current-source manifest and
dynamic census/metadata comparison. Once development moves beyond the frozen
snapshot, freshness must fail; that is a useful staleness signal, not a waiver.
There is no fixed command count to update.

The compact index remains reviewable while the content-addressed deterministic
gzip retains every imported module, import-family member, and storage symbol and
call count. Latency samples, model constructions, filesystem effects, exit status,
and failure kind are also unaggregated. The rejected first attempt is documented
separately; none of its mutable-tree samples appear in the accepted baseline.

`current-source-delta.md` records nodes added after this pre-optimization freeze.
Post-optimization capture and performance gates must dynamically enroll those
nodes (and any later additions); this historical baseline must not be described
as current-tree complete.
