---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:396fb4a908642fd72042ba98bf86fc814d3313a04934940fde9faa01b212b5c3'
step_id: 'S09'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Embed signed runtime evidence projections in authority artifacts

## Scope

- `src/cadrumo/domain/calculations/registry/authority_artifact.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/authority_artifact.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `src/cadrumo/domain/calculations/registry/authority.py`
- `M` `src/cadrumo/application/corpus_search/citation_lookup.py`
- `M` `src/cadrumo/application/filing/_export_xml_dictionary.py`
- `M` `src/cadrumo/application/filing/export_verification.py`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` -> `pass`
