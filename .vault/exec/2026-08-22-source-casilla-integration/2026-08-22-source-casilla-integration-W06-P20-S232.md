---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b3f3a91cc3cd87eb14dda7ec8790752570ee595324ba5f1f8614f862837b8e39'
step_id: 'S232'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# After Modelo 188's exact historic design eras are selected, determine whether any required external value lifecycle exists and add no source kind, binding, casilla, or census candidate until official fact-to-destination evidence settles it.

## Scope

- `.vault/research/`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/_data/registry/aeat/modelos/188/`

## Description

- Used semantic discovery, then inspected the M188 registry, official corpus, temporal audit, calculation tests, filing surface, source-connectivity mesh, and producer namespaces.
- Reconstructed the 1999 original and 2007, 2015, 2017, and 2023 official record-design era evidence from hash-pinned BOE primary sources.
- Confirmed that the active registry selects only `2023-y-siguientes/0A`, refuses 2019--2022, and exposes five direct-manual summary casillas with no bindings, formulas, extraction profiles, or export layout.
- Searched exact M188 carriers, resolvers, storage, census, filing producers, parser paths, and source-owned exports; none establishes a canonical external fact lifecycle.
- Rewrote factual research as a no-current-candidate evidence boundary and removed the accidental, reference-free M188 ADR swept by mixed commit `7928b1f7b1`.
- Preserved the manual summaries and the independently governed temporal and export boundaries; made no runtime, registry, binding, source-kind, or census change.

## Outcome

S232 records an evidence-backed **no current source-connectivity candidate** for M188. This is not a conclusion that M188 tax facts are inapplicable. Official materials establish required filing destinations and a repeated type-2 perceptor record, but current evidence does not establish a canonical external source fact and holder, native grain, source-to-destination map, acquisition and absence semantics, encrypted non-lossy owner, or replayable provenance.

The five genuine manual `resumen` casillas `01`--`05` remain direct operator inputs and are not promoted into a perceptor-row lifecycle. File presentation, post-filing consultation, record-design coordinates, and generic repeated-record transport remain filing/read or structural surfaces, not source evidence. M188 remains selected only for `2023-y-siguientes/0A`; 2019--2022 remain refused pending separately governed historic-era selection.

A future step may reopen only with all of: exact hash-pinned historic selection where needed; an official canonical source and holder with native row identity plus absence, duplicate, and correction semantics; a reviewed single-era type-1/type-2 destination and derivation/aggregation/sign/unit/rounding map; encrypted non-lossy ownership with replayable provenance; and separately governed producer/map/render/generated-byte evidence for any export connection.

## Notes

- Mixed provenance: commit `7928b1f7b1` swept blank S232 research/exec scaffolds and an accidental draft ADR with unrelated shared-worktree paths. Exact reference scan found no inbound reference to that ADR; this step deletes only that incorrect file and replaces only the S232 bodies.
- Focused registry gates: `test_modelo_188_resumen_matches_its_design.py` plus `test_modelo_187_188_194_registry.py` passed, 18 tests total.
- Ruff passed for those same test files. Bounded Vault feature checks are recorded with this step; unrelated shared-worktree warnings are not adjudicated here.
