# Development run outputs

This directory is the single root for local test-run observability data.

- `test-runs/YYYY-MM-DD/<UTC timestamp>-pytest-<PID>-<nonce>/` contains one
  invocation. `run.log` is written and flushed while tests execute; `run.json`
  records the command, timestamps, log path, run id, and final exit status.
- Each invocation owns separate `artifacts/`, `cache/`, and `scratch/`
  directories. Names include a timestamp, process id, and random nonce, so a
  later run never overwrites an earlier run.
- `cache/pytest/` is the explicitly disposable cross-run pytest collection
  cache. It is separate from immutable per-run evidence.

The pytest façade announces the absolute `run.log` path before collection.
Every test identity is appended before execution and every failure, captured
stdout, and captured stderr is flushed when pytest reports it. CI continues to
stream the same terminal output into the GitHub job log.

Packaging build products remain under `var/`, and rendered documentation
remains under `docs/_build/`; those are product artifacts with existing owning
contracts, not execution logs. Advisory audit reports retain their declared
producer-owned location until those producers expose an output-root contract.

Everything below this directory except this file is ignored by Git.
