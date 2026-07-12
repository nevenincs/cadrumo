---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S54'
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
     The S54 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Prove manifest validation, bundle members, and honest signing behavior and ## Scope

- `packaging/mcpb/tests/test_build.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove manifest validation, bundle members, and honest signing behavior

## Scope

- `packaging/mcpb/tests/test_build.py`

## Description

- Validate the committed manifest through both its production loader and real `--check` script entry point.
- Build a real `cadrumo.mcpb` archive and prove its exact member and embedded-manifest contract.
- Assert Cadrumo server, command, tool, display, filename, and diagnostic identities while retaining AEAT authority prose.
- Exercise the host's real signer availability and require an honest signed or explicit unsigned outcome.

## Outcome

The secondary bundle now has a five-test real-behavior proof covering manifest
validation, the exact `cadrumo.mcpb` member set, canonical Cadrumo identities,
and honest signing diagnostics. On this host the real outcome is explicitly
unsigned because no signer is available. Ruff and all five focused tests pass.

## Notes

Earlier shared WIP simulated missing and successful signers with monkeypatches.
S54 removed those substitutes and observes only the actual host state. The
tests do not claim installation, publisher verification, or a configured
release identity.
