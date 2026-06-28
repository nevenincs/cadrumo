---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Source Grounding Review

## Review Scope

- `registry/aeat/legal/irpf.toml`
- `corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html`
- `src/aeat/domain/calculations/registry/test_workbook_parity.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Findings

- No blocking findings in the focused source-grounding patch.
- The registry source catalogue now verifies 20 official source artefacts,
  including Modelo 131 record designs for 2019-2023, 2024, 2025, and 2026.
- The current AEAT Modelo 131 instructions page is persisted in the official
  corpus and source-catalogued for calculation citations.
- Workbook scanner coverage proves the committed Modelo 131 workbooks are
  record-design layout authority and explicitly not executable calculation
  parity evidence.
- General catalogue integrity coverage now validates the whole committed
  registry tree, legal corpus required text, source hashes and byte counts,
  modelo reference closure, and AEAT record-design manifest consistency.

## Residual Risk

- Modelo 131 TOML registry authoring, calculation tests, extraction profiles,
  export linkage, live filed-data capture, and teardown remain pending rows in
  the plan ledger.
