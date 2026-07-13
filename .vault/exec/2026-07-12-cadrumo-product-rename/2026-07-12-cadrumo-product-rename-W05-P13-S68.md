---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S68'
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
     The S68 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rewrite product branding, badges, install commands, and authority-qualified prose and ## Scope

- `README.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite product branding, badges, install commands, and authority-qualified prose

## Scope

- `README.md`

## Description

- Classify the root README as a primary tutorial with secondary explanation and reference navigation.
- Preserve the approved heading structure and pass its wireframe through a zero-context review covering all eight newcomer-understanding questions.
- Ground each affected section in the complete README, the binding naming ADR, the canonical product-identity object, package metadata, and the live CLI.
- Draft the naming and source-checkout corrections in isolation from the rest of the document.
- Correct the false `cadrumo` human-command claims while preserving `Cadrumo` prose, `CADRUMO` identity contexts, `cadrumo` machine identifiers, `aeat` CLI commands, and `AEAT` authority references.
- Apply the zero-context editorial review's minor terminology, acronym, accessibility, pronoun, and contraction findings without changing safety or legal meaning.
- Repair the README demo's stale title-case assertion so it continues to require the live identity-context `CADRUMO` help surface.
- Verify the live version and help commands, README command conformance, README demo, relative links, formatting, lint, and patch hygiene.

## Outcome

The README now distinguishes Cadrumo's machine identifiers from its permanent `aeat` human command and describes the observed `CADRUMO 0.2.0` identity output accurately. The existing information architecture, filing boundary, publication block, data-protection summary, licensing, and authority-qualified language remain intact.

The zero-context wireframe reviewer found that a newcomer would understand all eight required topics. The editorial reviewer returned minor revisions only; those revisions defined command-line interface, expanded BOE, SHA-256, and CSV at first use, removed directional wording, clarified pronouns, and split command outcomes. Technical review confirmed the package entry point and identity tuple against live behavior.

Verification passed with two README demo tests, 59 documented-command conformance tests, Ruff lint, Ruff format, the relative-link check, live `aeat --version` and `aeat --help`, and `git diff --check`.

## Notes

No external publication was attempted. No data was lost, no compatibility alias was introduced, and no known review finding remains open in this step. The scoped plan check completed with the standing PLAN022 non-monotonic-order warning. The repository-wide vault check remains red on 319 pre-existing structure errors and unrelated stem collisions; this step introduced none of those findings.
