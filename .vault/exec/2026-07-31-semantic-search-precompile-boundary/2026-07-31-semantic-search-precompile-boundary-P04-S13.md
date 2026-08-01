---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:7634f5229bbd2ed29d440d2fc9a4dfa09846d4e9fc5b695d898c6366eccea30b'
step_id: 'S13'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run the corpus-search and command-search suites sequentially plus full collect-only, and record the gate outputs in the exec records and ## Scope

- `src/cadrumo/application/corpus_search/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the corpus-search and command-search suites sequentially plus full collect-only, and record the gate outputs in the exec records

## Scope

- `src/cadrumo/application/corpus_search/tests/`

## Description

- Read the project pytest configuration first to establish what a bare invocation actually selects, rather than assuming a path argument runs the tests under it.
- Run the corpus-search and command-search trees SEQUENTIALLY with an explicit marker override, retaining short tracebacks.
- Run the MCP tree sequentially under the same override, because the parallel run holds serial-marked tests out while still reporting green.
- Run full-tree collect-only and confirm zero collection errors.
- Measure the default-marker selection against the override selection to quantify what a routine run does not cover.

## Outcome

All gates green. Real counts and real commands, captured to disk in full and read back, never truncated in-pipe.

Corpus-search plus command-search, sequential: `pytest src/cadrumo/application/corpus_search src/cadrumo/application/command_search -n0 -m "not external_tool and not os_keychain" --tb=short -q` reports `49 passed in 24.00s`.

MCP tree, sequential: `pytest src/cadrumo/entrypoints/mcp -n0 -m "not external_tool and not os_keychain" --tb=short -q` reports `306 passed in 425.12s (0:07:05)`. The serial count of 306 is the honest one; a parallel run reports 288 while holding serial-marked tests out, so the parallel number alone would have been a false green.

Full-tree collect-only: `pytest --collect-only -q` reports `15109/18493 tests collected (3384 deselected) in 44.42s`, exit 0, with ZERO collection errors. The deselection is the configured default marker, not a failure; a scan of the log for collection errors and import errors returns only test NAMES containing the substring, no actual error lines.

Collateral gates, run under the same discipline: the harness rule-surface drift gate reports `6 passed in 4.81s`; `python -m dev.docs.apidocs scaffold --check` reports "Stub tree is conformant. No drift detected."; `python -m dev.docs.apidocs audit` reports 1246 source modules against 1246 stubs with 0 missing, 0 orphan, 0 stale; `python -m cadrumo.locales scaffold --check` reports ok for ca, en, es, and hu.

Selection measurement, recorded because it changes how a later reader should treat a green run: with the DEFAULT marker the two search trees collect 45 of 49 tests, deselecting exactly the four `test_command_ranking_golden.py` integration tests; the override collects all 49. The routine unit lane therefore does not exercise the ranking gate. The integration lane does. This is carried as a finding in the close honesty review.

## Notes

The default `addopts` carries `-m 'unit and not external_tool and not os_keychain'`, so a bare `pytest <path>` would have under-selected and could have reported a clean run that never touched the integration tests. Every run above therefore passed an explicit marker override, and the counts above are the selected-and-executed counts, not "no tests ran".

Incident, self-inflicted: the first two background runs were launched through the Bash tool using the PowerShell `Out-File` cmdlet for capture. Both died at exit 127 with empty logs and had to be relaunched with POSIX redirection, costing one cycle. No result was misread as a consequence, because a zero-byte log was treated as a failed capture rather than as a passing run, but the wasted cycle is recorded rather than omitted.

No skipped work, no xfail, no scaffolds left in code.
