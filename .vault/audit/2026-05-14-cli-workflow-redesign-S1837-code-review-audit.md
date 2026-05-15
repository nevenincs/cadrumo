---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign-S1837` Code Review

S1837-001 | LOW | Topic catalogue CLI/rendering invariant does not scan nested package modules
The new AST invariant iterates only over direct `*.py` children of `src/aeat/application/topics`, so any future non-test module added below a subpackage of `application/topics` can import Typer, Click, Rich, `aeat.entrypoints`, central emitters, or call `print`/`echo` without being checked by this guard. S1837 is meant to ensure the topic catalogue code has no Typer application or command-local rendering path, and the ADR frames `application/topics` as a backend package consumed by registry-owned workflows. The invariant should scan the package tree, excluding test files and cache/build artefacts, so the boundary remains enforced for all non-test topic catalogue code.

S1837-RESOLUTION | INFO | S1837 package-tree scan remediated
The AST invariant now scans the full `application/topics` package tree through recursive discovery while excluding tests and `__pycache__` artefacts. Verification passed with ruff, ty, and the focused topic catalogue suite.
