---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:0b31c228de81c2e04ca95a8c4c839056c56bfe925ca89efe72ed4bf044e0fe40'
step_id: 'S90'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Author the third-party notices attribution for the potion-multilingual-128M lineage distilled from BGE-m3 on the C4 ODC-BY corpus

## Scope

- `src/aeat/application/corpus_search/THIRD_PARTY_NOTICES.md`

## Description

- Author `THIRD_PARTY_NOTICES.md` at the repo root: the ODC-BY-mandated C4
  attribution for the potion-multilingual-128M model lineage (Model2Vec MIT,
  BGE-m3 MIT), the no-weights-ship statement, the shipped-vectors-are-own-
  outputs clarification, and the lexical stack notices (SQLite FTS5 public
  domain, snowballstemmer BSD-3).

## Outcome

Authored by the coordinator per the licence-gate research's attribution
requirement. Scoped deliberately to obligations NOT discharged by package
metadata; the ordinary dependency tree self-declares.

## Notes

None.
