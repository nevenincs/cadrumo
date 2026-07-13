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
- `src/cadrumo/tests/test_readme_cli_demo.py`

## Description

- Classify the root README as a primary tutorial with secondary explanation and reference navigation.
- Preserve the approved heading structure and pass its wireframe through a zero-context review covering all eight newcomer-understanding questions.
- Ground each affected section in the complete README, the binding naming ADR, the canonical product-identity object, package metadata, and the live CLI.
- Draft the naming and source-checkout corrections in isolation from the rest of the document.
- Correct the false `cadrumo` human-command claims while preserving `Cadrumo` prose, `CADRUMO` identity contexts, `cadrumo` machine identifiers, `aeat` CLI commands, and `AEAT` authority references.
- Apply the zero-context editorial review's minor terminology, acronym, accessibility, pronoun, and contraction findings without changing safety or legal meaning.
- Repair the README demo's stale title-case assertion so it continues to require the live identity-context `CADRUMO` help surface.
- Remediate audit `ecf62294ad` by anchoring that test to the exact first help line and by distinguishing profile-backed mutations and workspaces from read-only commands and the export path chosen by the operator.
- Verify the live version and help commands, README command conformance, README demo, relative links, Ruff lint and formatting, Ty, the mandatory nitpicky Sphinx build, and patch hygiene.

## Outcome

The README now distinguishes Cadrumo's machine identifiers from its permanent `aeat` human command and describes the observed `CADRUMO 0.2.1` identity output accurately. The existing information architecture, filing boundary, publication block, data-protection summary, licensing, and authority-qualified language remain intact.

Phase 1 classified the README as a primary tutorial with secondary explanation and reference navigation. In Phase 2, a zero-context wireframe reviewer answered yes to all eight newcomer-understanding questions: what Cadrumo is, the Cadrumo/AEAT distinction, installation and first command, the profile and local-storage model, the worked filing flow, the no-submission boundary, deeper documentation routes, and support and licensing context. Phase 3 approval derives from the user's explicit approval of the execution scope before implementation.

Phases 4 and 5 grounded and drafted each affected section against the complete README, binding naming ADR, canonical product identity, package metadata, storage and export behavior, and live CLI. Phase 6 technical review confirmed the `aeat` entry point, exact `CADRUMO` identity heading, product-identity tuple, profile-backed mutation boundary, read-only command behavior, and operator-selected export path. It verified two README demo tests, 72 documented-command integration tests, live version and help output, two relative links, Ruff lint and formatting, Ty, and patch hygiene.

Phase 7 used a zero-context editorial review. Its minor revisions defined command-line interface, expanded BOE, SHA-256, and CSV at first use, removed directional wording, clarified pronouns, split command outcomes, and preserved the filing and safety boundaries. The mandatory nitpicky warnings-as-errors Sphinx build passed its real build test in 212.97 seconds. Phase 8 final-document approval is still pending, so S68 is reopened and remains incomplete until the reviewed README is presented to and approved by the user.

## Notes

No external publication was attempted. No data was lost and no compatibility alias was introduced. Audit `ecf62294ad` is remediated except for the intentionally open Phase 8 final-document approval gate. The scoped plan check completed with the standing PLAN022 non-monotonic-order warning. The repository-wide vault check remains red on pre-existing structure errors and unrelated stem collisions; this step introduced none of those findings.
