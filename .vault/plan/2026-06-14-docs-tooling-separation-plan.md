---
tags:
  - '#plan'
  - '#docs-tooling-separation'
date: '2026-06-14'
modified: '2026-06-15'
tier: L1
related:
  - '[[2026-06-14-docs-tooling-separation-adr]]'
  - '[[2026-06-14-docs-tooling-separation-research]]'
---


# `docs-tooling-separation` plan

## Description

Execute the terminology package relocation per the ADR as one atomic
`relocation:aeat.terminology` commit. The data stays at
`src/aeat/_data/terminology/`; only the package code, its tests, and the
references to it move.

## Steps

- [x] `S01` - Move the package: `git mv src/aeat/terminology dev/docs/terminology_handbook` (code, tests, fixtures); `rewrite the moved modules' `from ..core...` imports to `from aeat.core...`; `dev/docs/terminology_handbook`.
- [x] `S02` - Repoint consumers: update every `dev/docs/` importer and test of `aeat.terminology` to the new package path; `dev/docs/`.
- [x] `S03` - Move and repoint the production-CLI conformance test `test_terminology_redeclaration_conformance.py` into the dev tooling; `dev/docs/terminology_handbook/tests`.
- [x] `S04` - Update tree-scanning gates: drop the `aeat.terminology._*` rows in `test_docstring_return_type_links` and the `aeat.terminology._errors` allowlist row in `test_exception_base_hygiene`; `leave the wheel-bundle gate unchanged; `src/aeat/.../tests`.
- [x] `S05` - Regenerate autodoc stubs (`python -m dev.docs.apidocs scaffold`), removing the `docs/api/aeat.terminology*.rst` orphans and the `aeat.rst` toctree node; `docs/api`.
- [x] `S06` - Reconcile data references: remove the two dead `code:aeat.terminology*` targets in `relevance/relevance.json`; `update the `curation-ratchet.json` `python -m aeat.terminology` source string to the new module path; `src/aeat/_data/terminology`.
- [x] `S07` - Verify and land: clean `pytest --collect-only -q`, `python -m dev.docs.apidocs scaffold --check`, the terminology/glossary/wheel-bundle and edited tree-scan gates green; `commit atomically tagged `relocation:aeat.terminology`; plan + ADR + research`.
## Verification

```text
uv run --no-sync pytest --collect-only -q
uv run --no-sync python -m dev.docs.apidocs scaffold --check
uv run --no-sync pytest dev/docs/terminology_handbook/tests dev/docs/tests/test_glossary_reference.py dev/docs/terminology/tests src/aeat/tests/test_wheel_bundles_corpus_and_registry.py src/aeat/tests/test_docstring_return_type_links.py src/aeat/core/errors/tests/test_exception_base_hygiene.py -q
```
