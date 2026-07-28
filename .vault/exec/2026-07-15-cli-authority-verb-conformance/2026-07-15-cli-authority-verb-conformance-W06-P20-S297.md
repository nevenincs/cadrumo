---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S297'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S297 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Give every corpus-scanning emptiness gate a non-zero subject floor, or prove per gate that its corpus cannot silently empty, since 87 in-surface gates assert an offender list empty without proving they scanned anything and a path rename would green them while the forbidden condition survives and ## Scope

- `src/cadrumo/`
- `dev/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Give every corpus-scanning emptiness gate a non-zero subject floor, or prove per gate that its corpus cannot silently empty, since 87 in-surface gates assert an offender list empty without proving they scanned anything and a path rename would green them while the forbidden condition survives

## Scope

- `src/cadrumo/`
- `dev/`

## Description

- Run both the ad-hoc candidate scanner and the canonical vacuity screen; classify corpus-scanning emptiness gates as genuine (directory/module walks that silently empty on a rename) versus false positives (fixed-path reads that raise loudly, deliberate absence assertions, detector controls, and gates already floored by a same-corpus sibling).
- Add two floored corpus helpers to the CLI backend-boundary gate and floor the application-plus-entrypoints walk inline, covering six walk-gates that assert an offender list empty with no proof the walk reached the CLI surface.
- Floor the modelo-CLI-module corpus at its source helper, covering four decomposition guards that iterate it.
- Floor the runtime-text-file corpus of the retired-command-phrase gate, the two source-and-docs scan corpora of the retired-custody and retired-reset spelling gates, and the tracked-executable corpus of the single-jscpd-runner gate.
- Fix a live vacuity defect the new floor exposed: the retired-command-phrase gate computed its repository root one directory too shallow, so it had been scanning zero files and passing vacuously since inception; correct the root depth and resolve the one benign match it then surfaced (a module docstring documenting the retired command path) by rewording the prose.
- Mutation-check every floor by collapsing its corpus in a throwaway probe and confirming the gate fails on the floor rather than passing.

## Outcome

PARTIAL — a coherent sub-family closed, Step left OPEN with a named residue boundary.

Command (the touched gates, run together):

`uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_backend_boundary.py src/cadrumo/entrypoints/cli/tests/test_architecture_boundaries.py src/cadrumo/entrypoints/cli/tests/test_retired_cli_literals.py src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py dev/audit/tests/test_duplication.py -m "integration or unit" -p no:cacheprovider -q`

Collected and passed: 61 (non-zero). Exit line: `61 passed in 32.95s`. HEAD at run: `c7a7c6eee70ede281f35d696c0ffe68b2201eb33`.

Floored (12 gate functions across 5 files), each mutation-verified to fail on a collapsed corpus:

- Backend-boundary gate: two floored corpus helpers plus one inline floor cover the deleted-profile-import walk (the calibration case), the duplicate-aggregation-CLI walk, the censo-foundation walk, the registry-corpus-ownership walk, the observability-wrapper walk, and the process-language test-file walk. Floors fire at 0 files (mutation confirmed on the helper and on a consumer).
- Architecture-boundaries gate: floor at the modelo-CLI-module corpus helper covers the legacy-root-import, raw-id-regex, legacy-selector, and centralized-addressing guards. Floor fires at 0 modules (mutation confirmed).
- Retired-command-phrase gate: floor at the runtime-text-file corpus. Floor fires at 0 files (mutation confirmed) — and it caught a genuine pre-existing defect (see Notes).
- Retired-custody and retired-reset spelling gates: floor after the shared source/locale/doc scan. Both floors fire at 0 files (mutation confirmed).
- Single-jscpd-runner gate: floor at the tracked-executable corpus. Floor fires at 0 files (mutation confirmed).

Excluded after reading (verified false positives of the heuristic):

- Backend-boundary fixed-path gates (`read_text` over hardcoded tuples) and the removed-module `.exists()` gates: a rename raises loudly or the tuple is a literal, so neither can silently empty.
- Architecture-boundaries single-file reads of the legacy root: a rename raises through the AST resolver.
- Educational-docs cited-verb and relative-link gates: a same-module sibling asserts the shared docs corpus is non-empty, so the corpus cannot silently empty.
- Doc-privacy tracked/untracked ban gates: the root is `git rev-parse --show-toplevel` (raises on a non-repo) and the module carries planted-leak anti-tautology controls, so the corpus cannot silently empty.
- Duplication coverage-read gate: a deliberate empty-tuple input to a property test, not a corpus scan.

## Notes

- The retired-command-phrase gate was a live instance of the exact defect this Step hunts: its repository-root literal was one directory too shallow, so its two runtime surfaces resolved to non-existent paths and it scanned zero files while passing green. The new floor surfaced it; correcting the root then surfaced one benign match — a module docstring stating the old command path is retired — resolved by rewording so the literal no longer appears while the meaning is preserved. This is a production-source edit inside the campaign surface, made only after confirming no peer WIP on the file.
- The floored consumers in the backend-boundary and architecture-boundaries gates inherit their floor from a called helper; the ad-hoc candidate scanner is function-scoped and cannot see an out-of-function floor, so it will still list those consumers. That is expected and is why the mutation-check, not the scanner, is the proof.
- RESIDUE (Step left OPEN). The completed boundary is the corpus-scanning emptiness gates in the CLI/entrypoints surface plus the `dev/audit` single-jscpd-runner gate. NOT yet read or actioned: the remaining in-surface candidates under `src/cadrumo/tests/` (the canonical vacuity screen flags ~40 there, e.g. the marker-integrity, mock-inventory, monkeypatch-inventory, import-hygiene, no-skip-xfail, compatibility-lifecycle, and codebase-size-budget gates), under `src/cadrumo/application/user_profile/` and `bucket_maintenance/` (mostly behavioural recovery tests, likely false positives, unconfirmed), and the remaining `src/cadrumo/entrypoints/cli/tests/` conformance gates (json-schema, documented-command, determinism, registry-cli-live). Each needs the same read-then-classify pass before touching. A follow-up run should start from the canonical vacuity screen worklist (`python -m dev.audit.vacuity_screen`) intersected with the in-surface trees.
