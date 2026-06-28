---
tags:
  - '#exec'
  - '#core-authority'
step_id: S83
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W09.P25.S83 - core-to-application edges enumeration and fix

## Outcome

Enumerated all 13 core-to-application import edges per MIGRATE-007, RELOC-026, Rule 1.

The import-reference audit shows:
- **2 production edges** — `core/resources/_repos/topics.py:10` (TYPE_CHECKING) and `:20` (local_scope) both importing from `aeat.application.topics`
- **11 test edges** — in core test files (function-body lazy imports)

**Production edges decision:** `TopicCatalogueRepository` in `core/resources/_repos/topics.py` wraps `application.topics.load_topic_catalogue`. `TopicCatalogue` is an application-layer type; moving the repository to application/ would sever this core edge. However, `application/` is currently owned by W08 — any edit to application/ is BLOCKED. Flagged as a follow-up item for W08 closeout.

**Test edges from S82 (already fixed):** The `core/i18n/test_output_language.py` move in S82 also eliminated the 2 top-level application imports from that file (which accounted for 2 of the 11 test edges). The remaining 9 test edges are function-body lazy imports in `test_profile.py` and `test_profile_catalogue.py` — these test the registration pattern (core slot filled by application at startup) and belong in `core/` by design.

## BLOCKED

`core/resources/_repos/topics.py` production fix requires moving `TopicCatalogueRepository` to `application/` or moving `TopicCatalogue` to `domain/` or `core/`. Both paths touch `application/` files owned by W08.

## Commit

Covered by `8f10fa9ea` (same commit as S82).

## Files touched

No additional files beyond S82.

## Verification

Core suite: same 8 pre-existing failures. 0 new failures introduced by W09.
