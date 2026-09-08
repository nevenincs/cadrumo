---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:8e13218b75f1b1cb3094afa692e256fc0343d29a129b349b1430375c6da644a6'
step_id: 'S134'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the Modelo-specific embed adjudication ledger, campaign-owner carve-outs, and machinery/dead classifications while retaining the mechanically derived regulatory-literal census as a zero-target gate

## Scope

- `development registry embed analysis`
- `adjudication TOML`
- `CLI/reporting`
- `detector tests`
- `and quality aggregation`

## Changes

- `R` `dev/registry/analysis/modelo_embed_classification.py` -> `dev/registry/analysis/modelo_embed_scan.py`
- `D` `dev/registry/analysis/modelo_embed_classification.toml`
- `D` `dev/registry/tests/test_modelo_specific_embed_classification.py`
- `A` `dev/registry/tests/test_modelo_specific_embed_scan.py`
- `A` `dev/quality/modelo_regulatory_embeds.py`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `M` `.vault/adr/2026-06-10-modelo-enum-hardening-adr.md`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_modelo_specific_embed_scan.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/modelo_embed_scan.py dev/registry/tests/test_modelo_specific_embed_scan.py dev/quality/modelo_regulatory_embeds.py dev/quality/suite.py` -> `pass`

## Notes

The zero-target gate reports 97 live regulatory embeds. They are executable follow-on work, not accepted residue; the gate remains red until each finding moves to its owning registry or locale authority.
