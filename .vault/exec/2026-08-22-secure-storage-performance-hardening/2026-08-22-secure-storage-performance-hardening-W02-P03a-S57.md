---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2aee82d7ab0be90f1fa38d9c7d31a64a7273d013cb9b169cabbba1090a249871'
step_id: 'S57'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S57 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Prove direct-wheel, direct-sdist, and sdist-to-wheel contents and installed behavior include every production CommandSpec module, exclude both command JSON names and development generators, and materialize the complete localized root, group, and leaf surface with resolvable public handler and schema targets and ## Scope

- `src/cadrumo/tests/test_wheel_content_boundary.py and dev/packaging/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove direct-wheel, direct-sdist, and sdist-to-wheel contents and installed behavior include every production CommandSpec module, exclude both command JSON names and development generators, and materialize the complete localized root, group, and leaf surface with resolvable public handler and schema targets

## Scope

- `src/cadrumo/tests/test_wheel_content_boundary.py and dev/packaging/`

## Description

Extract the tracked Git revision into an isolated build root.
Build and inspect the direct wheel and direct source distribution.
Build a second wheel explicitly from the produced source distribution and inspect it independently.
Discover every distributed production CommandSpec declaration module from the tracked source and require exact artifact inclusion.
Exclude both retired command JSON basenames, both deleted generator basenames, and development-quality paths from every archive.
Install each artifact into a separate target and probe it under `python -S` outside the checkout.
Materialize the exact 361-node root, group, and leaf live tree, traverse every locale key, and resolve every public deferred target with its role contract.
Attest that every loaded first-party module originates inside the selected installed target and no development module loads.
Run an adversarial independent review and remediate every finding.

## Outcome

Direct wheel, direct sdist, and sdist-to-wheel archives carry every independently discovered production specification module and no retired command cache or development generator. Each installed artifact independently materializes the exact CommandSpec/live-tree path set, covers root, group, and leaf nodes, resolves all supported-locale translation keys, and imports role-correct public handlers, schemas, value types, parsers, completion callbacks, factories, converters, and machine-secret models.

Build source provenance is the clean tracked archive. Installed probes suppress ambient site processing, process only their artifact target, run outside the checkout, and reject any first-party origin outside that target.

## Notes

The initial review found role-blind target validation and incomplete recognition of bare CommandSpec export names. Both were corrected, with a planted missing-module negative added before acceptance. The integration gate is intentionally serial and build-heavy because it produces and installs three real artifact forms.
