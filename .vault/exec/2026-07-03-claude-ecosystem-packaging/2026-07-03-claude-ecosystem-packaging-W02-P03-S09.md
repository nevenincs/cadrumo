---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S09'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Scaffold the aeat-data distribution build with its own pyproject reading the same source tree, force-including the corpus binaries under an aeat_data package with mirrored relative paths and ## Scope

- `packaging/aeat_data/pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Scaffold the aeat-data distribution build with its own pyproject reading the same source tree, force-including the corpus binaries under an aeat_data package with mirrored relative paths

## Scope

- `packaging/aeat_data/pyproject.toml`

## Description

- Scaffold the `packaging/aeat_data` hatchling project declaring the `aeat-data` distribution.
- Add a `hatch_build.py` build hook that force-includes only the corpus binaries from the one shared source tree, remapped to `aeat_data/_data/corpus/...` — the exact layout the `S13` corpus locator seam resolves.
- Pin the distribution's version to a synced literal locked to the root package version (parity-gated by `S11`).
- Add the Apache-2.0 license declaration and a README.
- Commit `354ff2e8dd`.

## Outcome

- Companion wheel measures approximately 139 MB and packages exactly 190 corpus binaries.
- Full sdist and wheel roundtrip builds succeed.

## Notes

No incidents. No skipped work.
