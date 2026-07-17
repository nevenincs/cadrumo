---
name: 2026-04-17-pytest-only-testing-research
description: Current executable test-control and marker inventory grounding the real-behaviour pytest architecture
tags:
  - "#research"
  - "#pytest-only-testing"
date: 2026-04-17
modified: '2026-07-17'
related:
  - "[[2026-04-17-pytest-only-testing-adr]]"
  - "[[2026-06-05-test-topology-refactor-adr]]"
---

# Pytest-only testing research

## Question

Which test controls and marker topology are actually supported by the current
codebase and its binding quality rules?

## Executable inventory

- `src/cadrumo/tests/_marker_hook.py` requires exactly one of `unit`,
  `integration`, or `aeat_live` and exactly one accepted `hex_*` marker.
- `src/cadrumo/tests/conftest.py` performs the live-file banned-import scan
  before pytest marker deselection.
- `src/cadrumo/tests/live_gate.py` fails explicitly selected live tests whose
  central Settings-derived opt-in is absent.
- `src/cadrumo/tests/test_marker_integrity.py`,
  `test_mock_inventory.py`, `test_monkeypatch_inventory.py`,
  `test_no_skip_xfail.py`, and the other ratchets inspect the real repository
  test surface rather than relying on review convention.
- `pyproject.toml` registers only the accepted execution and architecture
  markers and bans unittest/mock imports through Ruff.
- `src/cadrumo/core/time/_clock.py` provides the production clock seam where a
  domain needs explicit time input; duration TTLs use real monotonic elapsed
  time.

## Dependency and usage findings

Exact source search found no legitimate consumers for `pytest-httpx`,
`pytest-rerunfailures`, or `syrupy`. One residual `time_machine` fixture in
the filing runtime TTL test was replaced with bounded real elapsed-time
behaviour, and the production TTL now uses `time.monotonic()`.

The four plugins were direct-only development dependencies. Removing them
from `pyproject.toml` and regenerating `uv.lock` removed exactly
`pytest-httpx`, `pytest-rerunfailures`, `syrupy`, and `time-machine` from the
resolved environment.

The repository already forbids the `flaky` marker, fake/stub classes,
monkeypatching, mocks, skips, and xfails. Retry, interception, snapshot
approval, and global clock mutation would therefore contradict executable
policy rather than extend it.

## Conclusion

The cohesive architecture is pytest-only and real-behaviour-only. Keep the
runner capabilities `pytest-asyncio`, `pytest-playwright`, `pytest-xdist`, and
`pytest-cov`; reject test-control substitutes. Use explicit production seams,
real local resources, authoritative evidence, bounded elapsed time, or
opt-in external reads according to the execution marker.
