---
tags:
  - '#exec'
  - '#registry-generator'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:7cdad8497bce591080cdb5447b71d84d7bfe12d61458333bc69de146829e2298'
step_id: 'S77'
related:
  - "[[2026-09-09-registry-generator-plan]]"
---

# Add a declaration locus for the off-host class beside `historical_exclusions.json`, carrying per-artefact provenance and the disposition recording why a BOE document sits in an AEAT-indexed tree; five M184 and one M270 Orden PDFs as record designs, the M186 anexo image as a form spec

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`

## Changes

- `A` `src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json`
- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run --no-sync python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`
