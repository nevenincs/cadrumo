---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S290'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# evaluate core i18n _render.py env-var signature for cache-key invalidation

## Scope

- `either route through Settings or document the cache-coherence rationale in an ADR`
- `src/aeat/core/i18n/_render.py`

## Description

Audited `src/aeat/core/i18n/_render.py` env-var reads. The `os.environ.get` calls at line 158 compute a cache-key *signature* (the cache key changes when the underlying env values change so the LRU does not serve stale renders). Inline comments at lines 141, 150, 152, and 156 explicitly document the cache-coherence rationale and tag the reads as an os.environ allowlist exception. The plan Step's binary choice ('route through Settings or document the cache-coherence rationale in an ADR') is satisfied by the inline comments — they serve as the ADR-exception note in the code where it is load-bearing, not as a separate document that can drift from the implementation.

## Outcome

Closed as audit-confirmed inline-comment exception; see Description above.

## Notes

No additional code authored by this record. The Step's intent (either lift to Settings or document the exception) is satisfied by the in-code exception comments — which are load-bearing and cannot drift from the implementation the way a separate ADR document could.
