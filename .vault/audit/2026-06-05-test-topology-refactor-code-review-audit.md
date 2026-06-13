---
tags:
  - '#audit'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` Code Review

## TTR-001 | RESOLVED | Relocated tests initially broke package-relative imports

Collection initially failed after moving naked test modules into `tests` directories because many modules still used relative imports calculated for the old location. The repair swept import depths and sibling private imports, then reran collection until `src/aeat` collected successfully.

## TTR-002 | RESOLVED | Mechanical import rewrite produced malformed lines

One mechanical repair pass concatenated rewritten import lines with following source lines. The malformed lines were repaired and `ruff check src/aeat --fix` passed afterward.

## TTR-003 | RESOLVED | Documentation bootstrap regressed

The closeout documentation lane exposed docs tooling tests that still used retired pytest markers. Those tests now use the active `unit` plus `hex_core` or `hex_entrypoint` vocabulary, and the focused docs-build hygiene lane passed with the long Sphinx build deselected. The full Sphinx build still reports broader dirty docs/source warnings outside the test-topology marker cleanup.

## TTR-004 | RESOLVED | RAG code indexing did not terminate within short command windows

The resident RAG service stayed healthy and semantic code search returned current relocated surfaces. An initial full index request exceeded the 180 second tool timeout while code jobs continued in the service. Pausing the watcher let the queue drain; a subsequent `index --type all --port 8766` completed through MCP with vault +5/+4/-0 and codebase +1/+5/-0, and the watcher was restarted.

## Review Outcome

No critical or high issues remain in the committed test-topology closeout slice. Residual warnings are tracked as workspace-level or broader docs/source issues rather than hidden in passing step records.
