---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:785696e8545f5bf1d93796d3c54259f04d01d8989c3d9027728cdf606917a4b4'
step_id: 'S69'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Close the three cross-platform defects the serial wedge had been hiding

## Scope

- `dev/packaging/installed_mcp_oracle.py`

## Changes

- `M` `dev/packaging/installed_mcp_oracle.py`
- `M` `dev/packaging/tests/test_missing_llm_extra_refuses_instructively.py`
- `M` `dev/packaging/tests/test_distribution_evidence_emit.py`
- `verify:` `ruff check` -> `pass`
- `verify:` `python -m dev.quality.types` -> `pass` (no new diagnostics)
- `verify:` `_guarded_definition_names() derives 7 guards, previously 0` -> `pass`

## Notes

All three presented as platform-specific and none were. They were invisible
because the campaign's serial pass is one pytest invocation over eight
modules: the first wedges past its ceiling, and on Windows the thread-based
timeout cannot interrupt `subprocess.wait`, so pytest dies with no summary
line and the remaining seven modules never run.

The MCP oracle never performed the recovery enrollment that profile creation
requires, while its sibling tax oracle did, so its create always exited
non-zero. It also discarded the child's stdout and stderr, leaving a bare
sentence -- a large part of why failures in that lane cost a full rerun to
read. The product was the correct side throughout; the oracle was stale.

The LLM extra-boundary lane still assumed the package re-export layer that was
retired. Its guard derivation ended by intersecting with `llm.__all__`, now
literally `()`, so it could only ever return empty and the caller's
`assert derived` failed on a tree where every guard was present. Its probe
imported from the inert namespace and died before reaching any surface, which
reads as a surface failing to refuse when the probe never ran.

`copytree(copy_function=os.link)` cannot link across volumes. The template is
built in the OS temp directory while the campaign pins its basetemp inside the
repository's `var/`; one filesystem on the runners, two on any machine whose
checkout is off the system drive.

## Notes on verification

The cross-volume fix is NOT verified. Its test wedged without a summary line
on a box carrying 142 python processes and seven concurrent CI runs, which is
the same structural failure described above. The change is lint-clean and the
fallback is per file, but nobody has watched that test pass.
