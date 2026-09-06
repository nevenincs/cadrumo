---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:8f9b82c70bc37382835ed13c196a9b312d4a8141083704d2f4b94b1d0aeca285'
step_id: 'S66'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Apply the declared optional-source-url distinction to the field that needed it: the model licence source url carried a bare string default of empty with no length bound at all, which is precisely the case the alias documents, so it now carries the alias and the thousand-and-twenty-four character bound applies where previously any length passed, while the empty string still validates so absence on the wire is unaffected

## Scope

- `src/cadrumo/core/model_catalogue.py`

## Changes

- `M` `src/cadrumo/core/model_catalogue.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core` -> `pass`
- `verify:` empty accepted, 1024 accepted, 1025 refused

## Notes

The candidate field was chosen against the alias's own stated criterion rather
than by name. `calendar_models` already spells its optional URL as
`SourceUrl | None`, which the alias docstring explicitly contrasts itself with
and which is correct for a model that carries absence as `None`. The alias is
for a surface that spells absence as the EMPTY STRING, and `ModelLicence` was
the field doing that with no bound at all.
