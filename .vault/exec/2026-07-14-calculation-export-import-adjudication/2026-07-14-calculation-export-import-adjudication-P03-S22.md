---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S22'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Gate Modelo 360 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/360/`
- `.vault/reference/`

## Description

- Reconcile the Modelo 360 declaration-PDF candidate against the accepted live
  filed-declaration fallback mandate rather than the legacy fixture checkbox.
- Inspect the aligned canonical revision and record-design window,
  extraction-profile data, shared declaration parser, committed specimens, and
  real Modelo 360 tests.
- Preserve the exact `2010-04-01` start and open end without inventing an
  earlier candidate window.
- Apply the shared disposition precedence and authorize no speculative profile
  or Modelo-specific parser work.

## Outcome

### Modelo 360 declaration PDF, 2010-04-01 and following

- **Candidate:** Modelo 360 declaration-PDF extraction for the `AD-HOC`
  revision window from `2010-04-01` with an open end.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  requires the full declaration PDF as the fallback evidence path, requires
  that path to use registry extraction profiles, and requires Modelo-specific
  waves to add profile and parser coverage for their declaration PDFs. The
  legacy unchecked “Modelo 360 live/read fixture evidence” row is corroborating
  backlog history, not the mandate source.
- **Exact official authority:** `available`; the active
  `2010-y-siguientes` revision and reviewed AEAT record-design source
  `aeat-dr-360-2010` both apply from `2010-04-01` with no registered end date.
  The source's `layout_authority` classification establishes the exact
  candidate window; it does not substitute for real declaration bytes or prove
  filed-PDF geometry.
- **Canonical implementation state:** `gap`; `parse_declaracion_bytes` and exact
  registry-profile selection already provide the generic engine and hard-fail
  when no unique applicable profile exists, but Modelo 360 has no
  `extraction_profiles` data. The accepted fallback-path mandate makes this a
  required registry-data gap, not grounds for another parser path.
- **Real evidence or specimen:** `missing`; the bundled
  `01-360-orden-eha-789-2010.pdf` is the official record-design document, not a
  sanitized filed Modelo 360 declaration copy. Repository discovery found no
  sanitized filed Modelo 360 PDF and no declaration-parser corpus test for this
  Modelo.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 360.
- **Evidence block:** `true`; a sanitized filed Modelo 360 declaration PDF for
  the aligned authority window is unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`; mandate, exact-window authority, and the
  canonical required gap are proven, but real filed bytes are unavailable.
- **Next action:** obtain and sanitize a real filed Modelo 360 PDF, confirm its
  precise format applicability within the `2010-04-01`-and-following window,
  and only then author reviewed profile data plus real corpus coverage through
  the existing generic parser. Do not derive PDF coordinates from the record
  design and do not add Modelo-specific parser code.

## Notes

- A concurrent coordinator committed this record together with P02.S09 and
  closed both plan rows before independent review completed. The rows were
  reopened through the canonical CLI; this record is reclosed only after the
  reviewer accepted its substantive outcome.
- Intent-first Vaultspec RAG located the shared parser and exact profile
  selection boundary and the accepted 2026-05-04 live filed-declaration
  data-capture ADR that supplies the fallback mandate.
- Direct source inspection confirmed both revision `2010-y-siguientes` and
  source `aeat-dr-360-2010` begin on `2010-04-01`, and the Modelo 360 registry
  tree has no `extraction_profiles` directory. No earlier window was created
  because no earlier registry revision or authority window exists.
- Repository specimen and parser-test searches found no sanitized filed Modelo
  360 PDF and no Modelo 360 declaration-parser test. The committed
  `test_modelo_360_registry.py` and `test_modelo_360_adhoc_fidelity.py` suites
  are real Modelo 360 behavioral coverage of registry, schedule, read-only,
  parity, persistence, and two-year fidelity behavior, but they do not evidence
  PDF extraction.
- A bounded run of those two suites timed out after `64.1s` before pytest
  emitted a summary. The run is inconclusive, not a test failure or a passing
  result; no test or runtime source was changed in response.
- This Step writes only the adjudication record. It changes no production
  source, tests, registry data, shared Reference or audit, plan state, staging,
  or commits, and it leaves unrelated inherited worktree changes untouched.
