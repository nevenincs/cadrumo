---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:ae6a6afe30da6d03e2b00b6c7b4e813ebebe2354eaa5cbdf53c248d593a5a76b'
step_id: 'S09'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

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
