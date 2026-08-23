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
Materialize the dynamic exact root, group, and leaf live tree, traverse every locale key, and resolve every public deferred target with its role contract.
Attest that every loaded first-party module originates inside the selected installed target and no development module loads.
Run an adversarial independent review and remediate every finding.

## Outcome

Direct wheel, direct sdist, and sdist-to-wheel archives carry every independently discovered production specification module and no retired command cache or development generator. Each installed artifact independently materializes the exact CommandSpec/live-tree path set, covers root, group, and leaf nodes, resolves all supported-locale translation keys, and imports role-correct public handlers, schemas, value types, parsers, completion callbacks, factories, converters, and machine-secret models.

The installed lanes publish identical sorted spec-key and derived-path projections, so equal-sized but divergent artifact authorities cannot pass.

Build source provenance is the clean tracked archive. Installed probes suppress ambient site processing, process only their artifact target, run outside the checkout, and reject any first-party origin outside that target.

## Notes

The initial review found role-blind target validation and incomplete recognition of bare CommandSpec export names. Both were corrected, with a planted missing-module negative added before acceptance. A second review found unknown future deferred-target roles could silently pass; validation now refuses every unrecognized role and proves that refusal with a planted target.

During the final run, a concurrent committed graph extension increased the archived census from 361 to 363 and exposed a stale fixed-count assertion. The assertion was corrected to compare the dynamic exact live set and cross-lane node/kind projections, without touching the concurrent implementation. The integration gate is intentionally serial and build-heavy because it produces and installs three real artifact forms.

The final full matrix passed in 320.42 seconds. Ruff and ty passed, and the independent convergence review recorded critical 0, high 0, medium 0, and low 0.
