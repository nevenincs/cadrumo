---
tags:
  - '#reference'
  - '#registry-test-signal'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3d1720969b7fcb1cddad3fc281fb61601f3ce68db23fdf9e5d89c3ea97c68ead'
related: []
---



# `registry-test-signal` reference: lane-aware pytest signal reduction

## Summary

The existing command runner already owns canonical, tokenized evidence beneath
`.logs/test-runs` and supports processors that retain raw child output while emitting a
small JSON envelope. The pytest summary processor is therefore the correct reduction
boundary; `run.json` should retain its generic invocation-metadata contract while the
processed result is emitted to stdout and appended to `run.log`.

Semantic lanes cannot be inferred from pytest terminal summaries. The former registry
aggregate ran `test-calculations` as a dependency, and a red calculation recipe prevented
registry conformance from running. Its reported two pytest summaries were the parallel and
serial calculation passes, not calculations and conformance. The repository's
`dev.test_runs.lanes` transport establishes the intended execution rule: named lanes run
sequentially, later lanes still run after an earlier failure, and the first nonzero status
is preserved.

Lane attribution should use explicit JSON start and finish markers emitted by the lane
transport. Human prose such as `> lane` is not a machine contract. The processor can then
emit bounded progress records and report expected, completed, failed, and not-run lanes.
This follows the accepted decision that verdict granularity follows determinism: parallel
calculations, serial calculations, and registry conformance remain separately visible.

Pytest terminal summaries remain authoritative for outcome totals. Xdist progress lines
must not increment totals because the same test identity can occur again in short-summary
output. They are useful only for deduplicated affected-file hotspots. Repeated terminal
exception rows shaped as `E   ExceptionType: message` can be collapsed into deterministic
root-cause signatures, sorted by descending count then lexical identity, and capped using
the command runner's existing hotspot limit.

The captured registry failure demonstrates the value of this reduction: thousands of
collection errors collapse to a handful of import signatures, dominated by one repeated
missing-symbol import. A useful final envelope therefore carries per-lane outcome counts,
completion state, top affected files, and capped root-cause signatures while leaving every
traceback and test identity in the durable raw log.
