---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:50afc35256517cbc356a399019b3b1d92fcefe387d5032b2956dbe01dd646446'
step_id: 'S59'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Stop the bundled-design worklist counting a settled adjudication as backlog, by reading the registry's own declaration. DONE 2026-08-28. The gate reported 9 of 218 designs not fully read, of which 5 were Modelo 184 BOE ordenes REFUSED for not opening at wire position 1. Those five are not work: M184's export layouts cite ONLY `aeat-dr-184-2023-2024` and `aeat-dr-184-2025`, the AEAT diseÃ±os that open at position 1 and parse cleanly; no layout cites a `boe-dr-184-*` source; the five carry `design_authority == 'provenance_only'` in registry data (they are the orden that APPROVES the modelo, carrying its design as an annex); and `test_modelo_184_registry.py` states the refusal is intentional and load-bearing. The provenance_only set is EXACTLY those 5 sources, a 1:1 match with the refusals. Excluded them from the WORKLIST only -- they are still enumerated, parsed and classified, so the module's never-silence property still holds over the whole corpus -- and DERIVED the excluded set from `design_authority` in the catalogue rather than hardcoding filenames, the same discipline the fixture-provenance rule requires. Made the exclusion self-policing in both directions: the set must be NON-EMPTY (or the filter is a rigorous-looking no-op if the declaration is ever dropped) and every member must STILL refuse, because the registry names the promotion criterion exactly -- strict parsing producing complete records from position 1 -- so a provenance-only design that starts parsing cleanly fails and demands re-adjudication instead of hiding behind the exemption. Leaves the 4 GENUINE parser gaps listed: modelo 165 and three modelo 181 TABLE partial reads

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S59.md`
- `verify:` `.venv\\Scripts\\python.exe -m pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py::test_no_bundled_design_is_unreadable_or_only_partly_read src/cadrumo/domain/calculations/registry/tests/test_every_bundled_design_is_read_or_reported.py::test_every_provenance_only_design_still_refuses_and_is_a_promotion_candidate src/cadrumo/domain/calculations/registry/tests/test_modelo_184_registry.py::test_modelo_184_raw_boe_design_eras_are_hash_pinned_and_explicitly_not_mapped` -> fail

## Notes

Implementation provenance is immutable commit `6586ebdc5f`; it contains no
captured historical pytest output, so this record makes no historical execution
claim.

The fresh focused run did not enter the S59 test bodies: all seven cases errored
in the shared runtime fixture with `ModuleNotFoundError: No module named
'cadrumo.adapters.persistence.master_key'`, imported from
`src/cadrumo/adapters/persistence/storage/_profile_login_session.py`. The two
S59 target files have concurrent import-only worktree edits, which were not
modified here.

