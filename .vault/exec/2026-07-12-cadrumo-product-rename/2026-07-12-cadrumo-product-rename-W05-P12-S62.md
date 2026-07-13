---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S62'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S62 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Change command-help authorities to Cadrumo while preserving AEAT counterparty language and ## Scope

- `src/cadrumo entrypoint help authorities` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Change command-help authorities to Cadrumo while preserving AEAT counterparty language

## Scope

- `src/cadrumo entrypoint help authorities`

## Description

- Adopt the existing CLI/help rename WIP and reject the unapproved executable reversal.
- Retarget runtime program names, argv detection, suggestions, command citations, module prose, and direct CLI tests to Cadrumo.
- Preserve AEAT terminology for authority settings, adapters, portals, legal evidence, registry taxonomy, and retired-state refusal.
- Add referent-aware residue checks and exercise real Cadrumo version/help structures.

## Outcome

The Python-owned CLI and help authorities now expose one `cadrumo` executable
and Cadrumo product identity. Runtime program names, lazy-group ownership,
installed-script lookup, command suggestions, source-command provenance, and
structural command parsers use the same spelling. No locale catalogue was
edited; those translations remain assigned to the following locale steps.

AEAT remains where it denotes the Spanish tax authority, authenticated sessions,
official portals and evidence, legal corpus and registry identifiers, filing
counterparty behavior, or historical retired-product state detected for refusal.

## Notes

The user explicitly authorized adopting and cross-committing the broad existing
CLI WIP. During execution, four tests suffered concurrent whole-file character
substitution corruption with no meaningful peer diff. Their committed HEAD
bytes were reconstructed through `apply_patch`, then only intentional S62
Cadrumo hunks were reapplied. No corrupted bytes remain.

Ruff formatting and lint, whitespace validation, and focused executable residue
checks passed. A real in-process `cadrumo --version` returned `cadrumo 0.1.1`.
Sixteen focused startup, suggestion, lazy-tree, and architecture tests passed;
one architecture test remains red on an unrelated pre-existing raw-ID regex in
`_modelo_work_runs_cli.py`. A broader 136-test help run produced 102 passes and
34 expected dependency failures: localized help still comes from S63-S67-owned
catalogues, core error-registry suggestions remain outside this Step, and the
shared virtual environment has not reinstalled the renamed console script.
Those failures were not hidden with skips, mocks, or weakened thresholds.

Formal review against the committed product-rename ADR found no unresolved
finding in the owned source diff and confirmed that no locale YAML was changed.
