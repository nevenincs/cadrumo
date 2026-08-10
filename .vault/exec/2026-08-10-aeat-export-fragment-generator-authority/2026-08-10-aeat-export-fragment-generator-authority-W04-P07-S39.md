---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5128a94e9cf725d32ad21170af74d2a558952a40655416bd4546a899a1d35f35'
step_id: 'S39'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Remove every executable and test dependency on the deleted Modelo 303 `2023-y-siguientes` revision across domain, application, adapter, CLI, and fixture surfaces. Route production callers through the law-determined period selector and use an explicit surviving revision only where the test subject requires a concrete identity. Delete compatibility aliases, bridges, fallback literals, and copied selector logic, and add a structural gate that fails if the retired id or an equivalent redeclared selector reappears outside the single intentional negative-refusal assertion

## Scope

- `src/cadrumo/`

## Description

- Remove every executable, test, CLI, adapter, fixture, and locale dependency on `2023-y-siguientes` from the live Modelo 303 surface.
- Restore the five distinct source-bound revisions and route callers through the canonical law-determined period selector, using a concrete surviving revision only where the subject under test requires it.
- Consolidate the shared Modelo 303 construct localization under the model-scoped key and remove each revision-scoped duplicate.
- Add the real structural regression gate `test_m303_retired_revision_cutover.py`; it refuses both the retired identifier and an equivalent local selector redeclaration outside its single negative assertion.
- Review the complete candidate independently, resolve the initial review's omitted consumer findings, and re-review the corrected candidate.

## Outcome

Commit `c44dc0a796cfca02209d6f1ef43e47fe8feae296` removes the retired Modelo 303 revision from every live production and test consumer without retaining an alias, bridge, copied selector, or fallback literal. Modelo 303 now exposes exactly `2009-y-siguientes`, `2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, `2025`, and `2026-y-siguientes`; the two 2024 revisions have disjoint official period partitions.

The structural scan over the full candidate reported `m303_legacy_hits=0`, `legacy_registry_entries=0`, and `duplicate_construct_owners=0`. The committed gate proves the retired identifier cannot return to the live surface while preserving its one intentional negative-refusal assertion. Independent Luna re-review reported no unresolved critical, high, or medium finding.

Focused proof included the direct locale manager behavior suite, Modelo 303 registry and aggregation suites, candidate-wide classifier, staged diff check, and manual inspection of every residual retired-id occurrence. Broader collection was blocked by unrelated peer work that raised an `IndentationError` in `src/cadrumo/domain/filing/_protocols.py`; that failure was neither suppressed nor attributed to this step.

## Notes

- Historical Vault records deliberately retain factual references to the retired revision as archival evidence. The live-code classifier excludes only those archival records and the one explicit gate assertion; it does not permit compatibility code.
- This step depends on S35 and S36 and is complete before the semantic-map and generated-tree work that follows it.
