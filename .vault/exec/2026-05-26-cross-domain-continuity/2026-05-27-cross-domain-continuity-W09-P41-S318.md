---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S318
plan: "[[2026-05-26-cross-domain-continuity-plan]]"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S318 — verification provenance (legal_refs/source_refs)

## What was done

Threaded casilla and predicate provenance through the verification
finding pipeline so every `MISSING_REQUIRED_CASILLA` finding now carries
the registry's own `legal_refs` and `source_refs`, and every
`BLOCKING_RULE` finding carries the predicate's `legal_refs`.

### Domain model change

`src/aeat/domain/modelos/_verification_report.py`:

- Added `legal_refs: tuple[str, ...] = ()` and `source_refs: tuple[str,
  ...] = ()` to `ModeloVerificationFinding`. Both default to empty tuple
  so existing persisted reports deserialise without migration.

### Application logic change

`src/aeat/application/modelo/_actions.py`:

- `_collect_revision_verification_findings` refactored to load the
  registry snapshot directly via `authority.snapshot(...)` instead of
  two separate helper calls, giving it access to full `CasillaDefinition`
  objects.
- `_missing_required_casilla_finding` now accepts a
  `casilla_def: CasillaDefinition | None = None` parameter and populates
  `legal_refs` / `source_refs` from the definition when provided.
- `_evaluate_verification_predicates` adds `legal_refs=tuple(str(r) for r
  in predicate.legal_refs)` to every `BLOCKING_RULE` finding.

### CLI emit change

`src/aeat/entrypoints/cli/_modelo.py`:

- `_verification_report_payload` adds `"legal_refs"` and `"source_refs"`
  lists to each finding dict in the JSON output.
- `_verification_report_lines` emits `finding_legal_refs\t...` and
  `finding_source_refs\t...` lines for non-empty fields in the
  tab-separated output.

### Tests

`src/aeat/application/modelo/test_verification_substance.py`:

- `test_missing_required_casilla_finding_carries_registry_provenance`:
  integration test against a real M130 verify run (omitting casilla 02),
  asserts finding `legal_refs` and `source_refs` match oracle values read
  from the TOML registry, not hand-computed.
- `test_missing_casilla_finding_legal_refs_empty_when_casilla_def_absent`:
  anti-tautology unit test calling `_missing_required_casilla_finding`
  with `casilla_def=None`; asserts both provenance tuples are empty,
  proving the real threading path is load-bearing.

## Commits

- `eddd19047` — S318: thread casilla legal_refs/source_refs into verification findings
- `6dcc19d64` — S318 tests: provenance-threading integration + anti-tautology unit proofs

## Gate results

- `pytest test_verification_substance.py`: 14 passed
- `ruff check` + `ruff format --check`: clean on all four files
