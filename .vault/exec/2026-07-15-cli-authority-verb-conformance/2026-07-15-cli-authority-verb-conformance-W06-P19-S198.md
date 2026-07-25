---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S198'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run repository ratchets for skips, test doubles, monkeypatching, tautology, markers, and discovery drift

## Scope

- `src/cadrumo/tests/`

## Description

Run the repository ratchets for skips, test doubles, monkeypatching, tautology, markers and
discovery drift.

## Outcome

FAILED. Three of nine ratchets red, every violating file committed at HEAD and owned by
concurrent campaigns.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider --tb=line` over the nine
ratchet modules for test inventory, marker integrity, relative imports, skip and xfail, mock
inventory, monkeypatch inventory, broad exception raises, bare except, and tautology.
Collected 115, 112 passed, 3 failed, exit line `3 failed, 112 passed in 109.44s`, exit code 1, at
HEAD `1844ef2ea0`. All three reproduce at HEAD `c293706ce3`.

Marker integrity: three modules place their module-level marker after a conditional statement
rather than first, in the TUI theme test, a calculations relation-prefill grounding test, and a
filing registry-snapshot freshness test.

Mock inventory: two banned stub helper definitions, both in the filing registry-snapshot
freshness test.

Monkeypatch inventory: eight monkeypatch sites, all in that same filing test, patching a
resources accessor.

The skip and xfail ratchet, the tautology ratchet, the test-inventory ratchet, the relative-import
ratchet, the broad-raise ratchet and the bare-except ratchet are all green.

## Notes

All three failing files are clean in the working tree and were committed on the same day by
other campaigns: the TUI screens door work, the pagos-fraccionados zero-fold work, and the
registry-snapshot pinning work. None is this feature's surface.

The filing test is the substantive one: it combines two banned test doubles with monkeypatching of
a production accessor inside a deterministic test, which is precisely the shortcut the project's
quality rules bar. It is carried into the unrelated-failure record under S208 rather than fixed
here.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.
