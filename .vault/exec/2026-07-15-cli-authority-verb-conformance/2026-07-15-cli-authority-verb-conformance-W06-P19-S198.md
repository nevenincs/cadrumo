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

## Re-measurement at HEAD bc80aa2808 (all nine ratchet modules)

FAILED. Four of nine ratchets red. All four violations committed by concurrent campaigns;
none is owned by this feature surface. The three failures from the original reading
(TUI theme marker, calculations relation-prefill marker, filing registry-snapshot mock+patch)
were all fixed by their owning campaigns before this re-run.

Command: `uv run --no-sync pytest` over the nine ratchet modules: `test_no_skip_xfail.py`,
`test_mock_inventory.py`, `test_monkeypatch_inventory.py`, `test_no_tautology.py`,
`test_filename_live_marker_lint.py`, `test_test_inventory.py`, `test_relative_imports_only.py`,
`test_no_broad_exception_raises.py`, `test_no_bare_except.py`.
Collected 99, 95 passed, 4 failed, exit line `4 failed, 95 passed in 63.64s`, exit code 1,
at HEAD `bc80aa2808`.

Monkeypatch inventory: `dev/deploy/tests/test_publish_authority.py` uses `monkeypatch` fixture.
Committed by `b6a10f9105 feat(deploy): bind the docs publish authority to the delivery environment`.
Peer-owned (deploy campaign).

Relative imports: `src/cadrumo/entrypoints/mcp/tests/test_stdio_lifetime.py:478` uses
`import cadrumo` (absolute intra-package import). Committed by
`faa8643ece feat(mcp): anchor the stdio server's lifetime to its client`.
Peer-owned (MCP campaign).

Mock inventory: `dev/docs/apidocs/tests/test_manager.py` and `dev/docs/tests/test_api_stubs.py`
contain banned stub helper definitions. Committed by
`9f59f32595 fix(gates): make the stub drift check see the terminators its own writer translated`.
Peer-owned (docs/apidocs campaign).

Skip/xfail: `src/cadrumo/entrypoints/mcp/tests/test_stdio_lifetime.py:608,734` contain
skip shortcuts. Same file and same commit as the relative-imports failure.
Peer-owned (MCP campaign).

The five clean ratchets (tautology, test inventory, broad exception raises, bare except,
marker integrity) confirm the ratchet corpus reaches real modules. None of the four failures
is in this feature's modules.
