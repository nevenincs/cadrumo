---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:55fb196d827097f7cff97bd2cdee475a11d7de0b0839119523adb0e72f0ddbf8'
step_id: 'S24'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Declare the supported-filing-years catalogue in the registry authoring tree, replacing every Python-resident year set including SUPPORTED_EJERCICIOS, and refuse the entire registry load when any declared year has any obliged modelo without its required grade, resolvable revision or evidence-backed cells for every period, enumerating every gap with modelo, period and missing prerequisite, advisory-first until the flip

## Scope

- `src/cadrumo/_data/registry/aeat/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Locate supported-year, horizon, catalogue, selector, cadence, and M303
  authorities through Vaultspec RAG, whole-file reads, and exact symbol sweeps.
- Add one typed supported-filing-years declaration to the existing shared
  registry catalogue compiler, refusing missing and duplicate declarations.
- Remove `SUPPORTED_EJERCICIOS` and feed M303 production compilation from the
  typed shared catalogue.
- Derive the advisory completeness projection through existing revision
  selectors, `select_revision`, source applicability, and period matching.
- Prove exact gap coordinates, catalogue shape, M303 parity, and synthetic
  authority compatibility with focused tests and Ruff.

## Outcome

The registry authoring tree now owns one supported filing-year declaration for
2022 through 2026. Production Python owns no competing supported-year tuple.
The authority surfaces 1,158 advisory gaps, each with modelo, filing year,
period, and missing prerequisite. Enforcement remains advisory exactly as the
plan requires until S20 performs the separately authorised blocking flip.

Focused verification completed before the implementation commit: Ruff passed
on all touched production and test files; the new supported-year test module
passed 8 tests; the authority module passed its original 10 tests after its
synthetic registry fixture received the required declaration. A later combined
rerun exposed an existing compiled-cache payload created against the pre-change
schema; no cache-version change was retained because that follow-up was outside
the requested traceability-only close and the implementation commit already
landed independently.

## Notes

The canonical-home/redeclaration audit records the RAG queries, exact sweep,
and the distinct role of test-local year matrices. No selector, cadence map,
period parser, loader family, horizon resolver, or compatibility bridge was
added. Implementation landed in `d7a4413227`; the initial audit scaffold landed
in `b8afc0f05e` and is completed by this record commit.
