---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:8c21bb610a1efeeb17ec154879ae5d40327080dc7e693e332b536ef0bbf26c19'
step_id: 'S47'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Separate two unreached read paths that look identical and are not: the deudas landing guard and path prefixes are staged and fail-closed by design, because the live deudas service records that no specimen of the AEAT consulta page exists and the shared read-landing wall refuses every landing while a surface declares no read pages, so nothing calls the guard precisely because no live read is attempted; whereas the IVA remote-state loaders sit beside a capture that IS reached, so state is captured and cannot be retrieved and the acquisition-manifest surface records nothing, with no fail-closed rationale

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The IVA remote-state entry is the fifth instance of capture-with-no-retrieval.
What makes it a finding rather than a staged surface is the contrast with the
deudas entry recorded in the same Step: deudas has a stated fail-closed reason
and no live read is attempted, while the IVA capture succeeds and the state
simply cannot be read back.
