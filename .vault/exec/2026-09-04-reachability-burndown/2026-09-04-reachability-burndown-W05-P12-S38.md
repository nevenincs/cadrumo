---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:20c61142e455296568b18ea33919aac9aa214267360e17c0b828ecf545dad2db'
step_id: 'S38'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Recount the residue by code reference rather than by word match, after finding that the triage resolved a consumer by searching file text and so counted names mentioned in inert-namespace docstrings as production consumers; those docstrings are navigational maps naming every contract in the package, making the error systematic and one-directional because it inflated the healthiest-looking bucket, and correcting it moves referenced-by-production from 66 to 17 and the residue from 69 to 83 percent test-only; also count conftest as test infrastructure, which it is despite matching neither the tests directory nor the test prefix

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests -m "" -n 0` -> `pass`

## Notes

Three investigations closed negative and are recorded so they are not reopened.
There is no transitive-deadness cluster: no finding is referenced only from
inside another finding, once reference sites are resolved to their enclosing
definition. The package initialisers are genuinely inert, so the symbols they
appear to reference are named in prose, not re-exported. And the names those
docstrings advertise are not gateable: of ten that resolve nowhere, five are a
sentence correctly recording that the sandbox lifecycle verbs WERE REMOVED, and
the rest are attribute-access false positives.
