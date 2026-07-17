---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Author the ley-37-1992 art-104 (art-104.Tres) legal entries with corpus_ref and required_text for the 6 real exclusions, correcting the stale subvenciones-no-vinculadas prose removed by Ley 3/2006

## Scope

- `src/aeat/_data/registry/aeat/legal/iva.toml`

## Description

- Extend the `ley-37-1992:art-104` legal entry `required_text` in `iva.toml` with the six art-104.Tres exclusion clauses (reglas 1a-6a) verbatim from the bundled consolidated LIVA (`ley-37-1992-art-104.html#a104`).
- Record in the entry `notes` that "subvenciones no vinculadas al precio" is NOT an art-104.Tres exclusion: Ley 3/2006 (BOE-A-2006-5691) removed subvenciones from the prorrata denominator entirely, so they are not computed rather than excluded.
- Stamp agent-authored `reviewed_by` provenance for operator re-review; keep `corpus_ref` pointed at the already-bundled authoritative file.

## Outcome

- Modified files: `src/aeat/_data/registry/aeat/legal/iva.toml`.
- The registry legal-grounding gate `test_registry_legal_grounding.py` cross-checks every new `required_text` clause against the bundled corpus after normalisation and passes (5 passed).
- `art-7` and `art-9` cross-reference entries already exist in `iva-flow.toml`; no new legal entry was needed.
- Committed as `1a1f443665`.

## Notes

- The corpus is UTF-8 and the citation-presence check normalises accents/case on both sides, so the verbatim accented clauses match after normalisation (the "1.º" ordinal normalises to "1.o").
- No fabricated exclusion: the six clauses are the exact reglas the bundled art-104.Tres states; subvenciones is deliberately absent.
