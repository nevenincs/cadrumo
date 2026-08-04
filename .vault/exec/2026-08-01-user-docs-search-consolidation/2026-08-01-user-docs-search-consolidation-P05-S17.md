---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:b3f4cdf14872997ef91bf0aefd1189e4954cfc6cc83fd2d18a395ae30ed3941c'
step_id: 'S17'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-search-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-08-01-user-docs-search-consolidation-plan placeholders are machine-filled by
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
     The Add the legal per-kind parity gate proving anchor existence and destination-grounding coverage for every projected provision record and ## Scope

- `dev/docs/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the legal per-kind parity gate proving anchor existence and destination-grounding coverage for every projected provision record

## Scope

- `dev/docs/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Ground the accepted consolidation ADR, active P05 plan, S14/S15 audits, and
  S14/S15 execution records with `uvx vaultspec-rag` vault search.
- Ground the existing glossary, casilla, and CLI parity gates plus the legal
  renderer, legal projection, search record, and unified record with semantic
  code search and `get_code_file`, then confirm current symbols with `rg`.
- Add the real registry-backed LEGAL projection parity gate for unique unified
  records, renderer-owned page/anchor targets, page-level exceptions, and
  destination BOE grounding in the emitted legal RST.
- Preserve the source-only boundary: do not run tests, builds, Pagefind, live
  probes, sweeps, deployment, or reindexing.

## Outcome

Implemented the S17 legal per-kind parity gate in `dev/docs/tests/test_legal_anchor_parity.py`.
The gate exercises `project_legal_search_records()`, `render_legal_reference()`,
and `to_search_record()` against the live registry-backed source, asserts
substantive count parity and unique LEGAL identities, matches every projected
target to the renderer inventory, validates emitted anchors or legitimate
page-level targets, and verifies each authored BOE permalink in both the
destination grounding inventory and destination RST link source.

Static implementation checks passed: AST parsing of the new test, execution-
record readback, `git diff --check`, and conflict-marker scans over the two
owned paths. No runtime or test result is claimed.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The broken MCP `search_codebase` alias remains tracked in vaultspec-rag issue
#350; no reindex or bypass was used. Runtime/test/build acceptance is deferred
explicitly by instruction and remains unresolved. Unrelated peer WIP,
including S16, was preserved and is not part of this change.
