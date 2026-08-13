---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:af1cee10a5c3fb1671d78f4e0d9bb189c0d6b9f8f92140a644e0d678b18fb998'
step_id: 'S13'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Record the canonical CSV shape ruled by the ADR amendment of 2026-08-10, superseding this row's prior instruction to record that no empirical replay was possible. That instruction rested on a falsified premise and the evidence exists in three independent forms. First, three real AEAT-issued CSVs captured from live Sede sessions and byte-identical across two capture rounds (FNBB57PE9KZ5TN4R, MZRSYDRL5JMPJPRT, TUD4V9XAUV7QJ8QV), each exactly 16 uppercase alphanumeric characters. Second, 34 distinct CSV tokens across the 60 committed parser-anchor fixture PDFs, every one 16 uppercase alphanumeric. Third, a default-lane regression at adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py lines 244-249 that already asserts isalnum and isupper and a length between 8 and 24 on every parsed fixture. Adopt core/_aeat_csv.py's 8-32 uppercase-alphanumeric contract as canonical and retire JustificanteCsv's 4-64-no-pattern bound rather than keeping it as a second opinion. State in the Step record that the 8-24 assertion already running is strictly inside 8-32, so the retype tightens the field without being able to break the parse path

## Scope

- `src/cadrumo/domain/justificante/`

## Description

- Re-read the accepted 2026-08-10 CSV amendment, the canonical identity reference, the live source, and the implementing history.
- Confirm three live-Sede values (`FNBB57PE9KZ5TN4R`, `MZRSYDRL5JMPJPRT`, and `TUD4V9XAUV7QJ8QV`), each sixteen uppercase alphanumerics and byte-identical across two capture rounds.
- Re-measure the committed corpus: 63 PDFs contain 60 parser-anchor sidecars, yielding 34 distinct `SANITIZED` CSV tokens; all 34 are sixteen uppercase alphanumerics.
- Confirm `core._aeat_csv` owns the 8-32 uppercase-alphanumeric contract and `core.identity.AeatCsv` consumes that contract before validation.
- Confirm historical commit `40c033eb9d` retyped `Justificante.csv` to `AeatCsv` and deleted the `JustificanteCsv` alias and package export; current source has no retired alias, shim, or re-export.

## Outcome

The canonical CSV shape is 8-32 uppercase alphanumeric characters, owned by `core._aeat_csv.py` and surfaced as `core.identity.AeatCsv`. The three real captures and the fixture population support the decision; the fixture roundtrip's 8-24 assertion is strictly inside the adopted 8-32 window, so the already-landed retype cannot reject a value that path proves it produces. No production edit was needed for this decision row because the canonical implementation landed in `40c033eb9d`; duplicating it would recreate the retired competing authority.

## Notes

Focused verification passed: 113 tests, Ruff, and Ty. The 63 fixture PDFs include three non-parser-anchor specimens; the executable roundtrip controls the 60 parser-anchor cases named by the plan. The Step does not close later CSV retypes, key enumeration, or boundary regressions; those remain separately open rows.
