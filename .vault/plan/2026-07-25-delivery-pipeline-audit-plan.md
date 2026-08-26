---
tags:
  - '#plan'
  - '#delivery-pipeline-audit'
date: '2026-07-25'
modified: '2026-07-30'
body_hash: 'sha256:69e1bb35d5d0850cbc4946f9da55f48b24c21446e7ec38b4c328cb5b020960d9'
tier: L1
related:
  - '[[2026-07-24-delivery-pipeline-audit-adr]]'
  - '[[2026-07-24-delivery-pipeline-audit-audit]]'
---
<!-- RETIRED: S02 -->

# `delivery-pipeline-audit` plan

- [x] `S01` - D1, hold pypi-upload.yml under its narrow written charter naming the tracked deletion issue in its header comment, adding no new capability in the interim and keeping it behind CADRUMO_PUBLISH_ENABLED, tracked as GitHub issue 618; `.github/workflows/pypi-upload.yml`.
- [x] `S03` - D2, relocate sync_aeat_record_design_corpus to dev/corpus in one atomic explicit-path commit tagged relocation:sync_aeat_record_design_corpus covering the module move, the new package init, the consumer import, and any self-naming strings, with collect-only observed clean immediately before the commit; `dev/packaging/sync_aeat_record_design_corpus.py, dev/corpus/`.
- [x] `S04` - D2 follow-up, relocate extract_manual_corpus_text under the same home as a second atomic commit tagged relocation:extract_manual_corpus_text sweeping the two justfile recipes, the sidecar-freshness tests, the self-referencing instructive strings, and the path comments in _validate_evidence and pyproject; `dev/packaging/extract_manual_corpus_text.py, dev/corpus/, justfile, pyproject.toml`.
- [x] `S05` - D3, raise the two companion pyprojects from Development Status 3 Alpha to 4 Beta so one cohort carries one posture; `packaging/cadrumo_data_manuals/pyproject.toml, packaging/cadrumo_data_official/pyproject.toml`.
- [x] `S06` - D3 gate, assert the Development Status classifier is identical across the three pyprojects so the next posture change is a one-fact edit plus gate rather than a silent fork; `dev/packaging/tests/`.
- [x] `S07` - D4, derive shipped-manifest author identity from PRODUCT_IDENTITY while preserving the pyproject legal author as a distinct fact, since the two are different claims and collapsing them loses the legal one; `packaging/, dev/packaging/`.
## Description

On 2026-07-30, 1 open row (S02) was removed from this plan and migrated to
2026-07-30-open-work-consolidation-plan, which now carries it as part of one
ordered flow authorised by 2026-07-30-open-work-consolidation-adr. This row
was migrated, not delivered: the reduced row count reflects a change of
carrier, not a narrowing of scope.

## Steps

## Parallelization

## Verification

## Context

Accepted ADR carrying no plan and no exec records.
