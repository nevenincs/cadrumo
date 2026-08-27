---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:432b82a6ca4745b88de73355d13ccb2fad585a63b7992f0dbc886a3440dcc19b'
step_id: 'S15'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Partition the citation sources so every citation is bounded on exactly one axis, require a provision id on statutory citations, derive each statutory window from its provision's effective span intersected with the supported filing window, and give the three statutorily-uncited profiles the article their rule rests on quoted verbatim from the bundled corpus

## Scope

- `src/cadrumo/domain/categories/ and src/cadrumo/_data/registry/aeat/categories/profiles.toml`

## Changes

- `M` `src/cadrumo/domain/categories/_proportionality.py`
- `M` `src/cadrumo/domain/categories/_registry.py`
- `M` `src/cadrumo/_data/registry/aeat/categories/profiles.toml`
- `A` `src/cadrumo/domain/categories/tests/test_provision_window_bounds_citations.py`
- `M` `src/cadrumo/domain/categories/tests/test_citation_edition_window.py`
- `M` `src/cadrumo/domain/categories/tests/test_proportionality.py`
- `M` `src/cadrumo/domain/categories/tests/test_citation_authority.py`
- `verify:` `pytest src/cadrumo/domain/categories src/cadrumo/domain/iva src/cadrumo/domain/renta/tests` -> `pass`

## Notes

Which article establishes each of the three previously uncited profiles is an
agent tax review against the bundled consolidated LIRPF, recorded as such beside
each citation in the TOML. It is the part of this change that most needs operator
re-stamping, and the audit says so.
