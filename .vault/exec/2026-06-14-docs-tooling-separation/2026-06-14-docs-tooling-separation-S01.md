---
tags:
  - '#exec'
  - '#docs-tooling-separation'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S01'
related:
  - "[[2026-06-14-docs-tooling-separation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-tooling-separation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-06-14-docs-tooling-separation-plan placeholders are machine-filled by
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
     The Move the package: `git mv src/aeat/terminology dev/docs/terminology_handbook` (code, tests, fixtures) and ## Scope

- `rewrite the moved modules' `from ..core...` imports to `from aeat.core...`
- `dev/docs/terminology_handbook` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the package: `git mv src/aeat/terminology dev/docs/terminology_handbook` (code, tests, fixtures)

## Scope

- `rewrite the moved modules' `from ..core...` imports to `from aeat.core...`
- `dev/docs/terminology_handbook`

## Description

This record covers the whole atomic relocation (plan Steps S01 through S07),
landed as one commit tagged `relocation:aeat.terminology`.

- Complete the package move `src/aeat/terminology` to
  `dev/docs/terminology_handbook` (code, tests, fixtures). The directory move
  and the conformance-test move had already landed in commit `abc9a56bc` but
  left every downstream surface unreconciled; this commit finished it.
- Rewrite every cross-package import in the relocated modules from
  relative-to-aeat (`from ..core`, `from ..domain`, `from ..entrypoints`) to
  absolute (`from aeat.core`, `from aeat.domain`, `from aeat.entrypoints`),
  including function-local imports. Intra-package single-dot relative imports
  left unchanged. Repoint `__main__`/`cli` usage strings and docstring
  cross-references to the new module path.
- Repoint external dev consumers `_concept_cards`, `_synonym_cli`,
  `_synonym_mining`, and their tests to relative `..terminology_handbook` /
  `...terminology_handbook` imports. The four consumers
  (`glossary_reference`, `_sweep`, `test_glossary_reference`,
  `test_pagefind_inject`) the peer commit had already repointed needed no
  further change.
- Move-and-repoint the redeclaration conformance test into the dev tooling and
  bind it to `aeat.core.paths` and the new package. It asserts a docs-quality
  invariant over `docs/**` prose driven by the Handbook, so it belongs with the
  Handbook in dev tooling.
- Drop the eight `aeat.terminology._*` baseline rows from the return-type-links
  gate, the `TerminologyError` allowlist entry from the exception-base hygiene
  gate, and the three `src/aeat/terminology` writer entries from the
  sensitive-persistence-policy gate (all three gates AST-walk `src/aeat`, so the
  rows became stale once the package left that tree).
- Regenerate autodoc stubs: 14 orphan `docs/api/aeat.terminology*.rst` removed
  and the `aeat.rst` toctree updated; `scaffold --check` clean.
- Reconcile data references: remove the two dangling `code:aeat.terminology` /
  `code:aeat.terminology._loader` relevance targets and repoint the
  curation-ratchet audit command string. The authoring tree under
  `src/aeat/_data/terminology/` stays shipped; the relocated loader reads it via
  `aeat.core.resources.bundled_path`.

## Outcome

Relocation complete. Verification all green: `pytest --collect-only -q` clean
(15812 collected, zero collection errors); `scaffold --check` reports no drift;
the relocated loader reads the in-place bundled data (115 concepts);
`ruff check` and `ruff format --check` clean on the staged set; the targeted
suite (handbook tests, the three edited tree-scan gates, the wheel-bundle gate,
glossary-reference, the docs-search terminology tests, and the
sensitive-persistence gate) all pass (199 passed). Committed as
`d6250dcf5`.

## Notes

The directory move and conformance-test move had already landed in peer commit
`abc9a56bc` with imports and downstream surfaces unreconciled, leaving the
package in a broken (un-importable) state at `HEAD`; this commit completes the
relocation rather than initiating it. The commit subject names that prior
commit.

`dev/docs/tests/test_palette_ranking.py` is an untracked peer WIP file that
imports `aeat.terminology._enums`; its import was repointed in the working tree
so it resolves against the relocated package, but it was deliberately left
unstaged (committing an untracked peer file would absorb in-flight peer work).

The `# Compiled by the strict loader in aeat.terminology` provenance headers in
the ~75 shipped `src/aeat/_data/terminology/concepts/*.toml` fragments still
name the old module path. The data stays in place per the decision and
re-serialising all fragments would be a data change outside scope; the loader
ignores comments, so this is cosmetic and left for natural re-serialisation.
