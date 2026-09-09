---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:794bf4120e4a5c77b5051641f78cb8b3f8f1723f73838e0b891e98c0f5b9db03'
step_id: 'S19'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Register confirmed apoderamientos legal-taxonomy facts

## Scope

- `src/cadrumo/domain/auth/apoderamientos/catalogue.py`

## Changes

- `M` `.vault/research/2026-09-09-facts-registry-discovery-blast-radius-research.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P07-S19.md`
- `verify:` `uv run pytest -n 0 src/cadrumo/domain/auth/apoderamientos/tests/test_catalogue.py -q` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/domain/auth/apoderamientos/catalogue.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/domain/auth/apoderamientos/catalogue.py` -> `pass`

## Notes

The provider was not enrolled. The shipped catalogue declares an intentionally
bootstrap-scoped vocabulary and carries no authoritative publication identity,
legal references, effective dates, or source citations that confirm an
externally controlled legal taxonomy. The existing loader, repository cache,
parser, data, and public facade remain unchanged. Enrollment requires a future
authoritative external taxonomy with temporal provenance; Wave 3 has no
facts-backed apoderamientos migration or retirement condition.
