---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S68'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S68 and 2026-07-15-distribution-installation-readiness-plan placeholders are machine-filled by
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
     The Verify English and Spanish MCP product descriptions in plugin, marketplace, MCPB, and client-display metadata while preserving English-only model-facing descriptions and ## Scope

- `dev/packaging/verify_distribution_identity.py`
- `src/cadrumo/agent/_workspace.py`
- `packaging/mcpb/manifest.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify English and Spanish MCP product descriptions in plugin, marketplace, MCPB, and client-display metadata while preserving English-only model-facing descriptions

## Scope

- `dev/packaging/verify_distribution_identity.py`
- `src/cadrumo/agent/_workspace.py`
- `packaging/mcpb/manifest.json`

## Description

- Materialise the production Claude plugin and marketplace trees in an isolated
  directory and read their client-display description fields.
- Read the MCPB short and long product descriptions without changing the source
  manifest or generators.
- Require one explicit English section and one explicit Spanish section in every
  user-facing MCP product-description field.
- Record separate capability, safety, privacy, on-host storage, human confirmation,
  and never-files-live verdicts for each language.
- Exclude model-facing tool, prompt, resource, and argument descriptions from the
  localization target.
- Exercise the verifier through direct production imports and its command-line entry
  point.

## Outcome

The verification implementation passes focused Ruff and five focused real-behavior
tests. The production command exits `1`, as required for the current distribution, and
writes a retained report whose SHA-256 is
`6102d5a48d3c162b95776757ec813e271721d9713d9200463188f3ec9f375205`.

The report inventories five real client-display fields: the generated Claude plugin
description, generated marketplace description, marketplace-served plugin description,
and the MCPB `description` and `long_description` fields. Every field contains
unlabelled English copy, no explicitly labelled English section, and no Spanish section.
The MCPB long description carries all six claims in English; the other shorter surfaces
carry only subsets. No field has English/Spanish claim parity, so the product-description
verdict is false.

The inspection did not change any identifier, description, generator, manifest, or
artifact. Model-facing operational descriptions remain English-only and outside this
verification target.

## Notes

This row remains unchecked. The accepted identity decision explicitly makes this step
verification-only and requires a failed bilingual result to remain open for a separately
approved translation and artifact migration. The retained report lives under the ignored
distribution-readiness evidence tree; its command status and digest are recorded above.

A formal code-review agent was invoked after the focused gates, then bounded and
interrupted when it did not return a disposition within the execution window. No formal
review pass is claimed in this record; the pending review remains a handoff gate before
the verifier can be treated as release-blocking evidence.
