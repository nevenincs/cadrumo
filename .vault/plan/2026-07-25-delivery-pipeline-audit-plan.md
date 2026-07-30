---
tags:
  - '#plan'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-30'
tier: L1
related:
  - '[[2026-07-24-delivery-pipeline-audit-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `delivery-pipeline-audit` plan

- [x] `S01` - D1, hold pypi-upload.yml under its narrow written charter naming the tracked deletion issue in its header comment, adding no new capability in the interim and keeping it behind CADRUMO_PUBLISH_ENABLED, tracked as GitHub issue 618; `.github/workflows/pypi-upload.yml`.
- [ ] `S02` - Retire the three PyPI Trusted Publishing registrations on pypi.org and delete the three now-orphaned GitHub environments pypi, pypi-data-manuals and pypi-data-official. The workflow and its conformance test were ALREADY deleted in e9e5acceb9 on 2026-07-27, authorised by the 2026-07-27-publication-lane-consolidation-adr with no sequencing precondition, so the original trigger-on-first-PyPI-publication condition is VOID and this row is operator-actionable now with no prerequisite; `.github/workflows/pypi-upload.yml, dev/packaging/tests/`.
- [x] `S03` - D2, relocate sync_aeat_record_design_corpus to dev/corpus in one atomic explicit-path commit tagged relocation:sync_aeat_record_design_corpus covering the module move, the new package init, the consumer import, and any self-naming strings, with collect-only observed clean immediately before the commit; `dev/packaging/sync_aeat_record_design_corpus.py, dev/corpus/`.
- [x] `S04` - D2 follow-up, relocate extract_manual_corpus_text under the same home as a second atomic commit tagged relocation:extract_manual_corpus_text sweeping the two justfile recipes, the sidecar-freshness tests, the self-referencing instructive strings, and the path comments in _validate_evidence and pyproject; `dev/packaging/extract_manual_corpus_text.py, dev/corpus/, justfile, pyproject.toml`.
- [x] `S05` - D3, raise the two companion pyprojects from Development Status 3 Alpha to 4 Beta so one cohort carries one posture; `packaging/cadrumo_data_manuals/pyproject.toml, packaging/cadrumo_data_official/pyproject.toml`.
- [x] `S06` - D3 gate, assert the Development Status classifier is identical across the three pyprojects so the next posture change is a one-fact edit plus gate rather than a silent fork; `dev/packaging/tests/`.
- [x] `S07` - D4, derive shipped-manifest author identity from PRODUCT_IDENTITY while preserving the pyproject legal author as a distinct fact, since the two are different claims and collapsing them loses the legal one; `packaging/, dev/packaging/`.
## Description

## Steps

## Parallelization

## Verification

## Context

Accepted ADR carrying no plan and no exec records.
