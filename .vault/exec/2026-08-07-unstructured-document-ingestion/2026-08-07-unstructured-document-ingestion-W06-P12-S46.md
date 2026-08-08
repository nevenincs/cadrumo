---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b38bcd1d46f8d315020ff6156fbca01d2cdad749bf36326e4e202381f41c2c8b'
step_id: 'S46'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Add live contention detection at the dispatch choke point comparing the selected model declared requirement plus margin against free headroom and the runtime resident set, fail-closed on unreadable figures, gated by the live-machine refusal case plus an injected post-quiesce permit case, proven by mutation

## Scope

- `src/cadrumo/llm/_client.py`

## Description

- Wire the dispatch choke point into the existing contention authority, resolved through the application package's public facade at call time.
- Assess only where the model catalogue declares a memory requirement, following the established assessable-load reasoning rather than re-deciding it.
- Place the check inside the on-host admission slot and outside the retry loop.
- Add the contention refusal to the taxonomy, its registry row (non-retryable) and its four locale values, carrying the snapshot's own detail and remediation.
- Accept injected hardware and resident measurements on the client so both refusal arms and the permit arm are reachable without substituting the decision.

## Outcome

A dispatch that this machine has no measured room for is refused before the runtime is contacted, and the verdict is the one the doctor surface and the provision verbs already give. Nothing about the comparison, the safety margin, the fail-closed arm or the shortfall attribution is re-derived here; a second opinion at the dispatch point could disagree with the row an operator just read.

Placement carries two separate arguments. Inside the slot, because a reading taken before the slot is held can be invalidated by another request loading a model between the measurement and the dispatch. Outside the retry loop, because headroom does not return on a timer, so a refusal the loop could see would be re-sent on a schedule while the memory it waits for is still held. Both are also declared in the taxonomy: the refusal is registered non-retryable, so the derived retry predicate refuses it independently of where it sits.

What is injected is the MEASUREMENT, never the verdict. A test that supplied the answer would exercise none of the decision and would pass against a client that never consulted the authority.

## Verification

uv run --no-sync pytest src/cadrumo/llm/tests/test_dispatch_load_headroom.py -m unit -p no:randomly -n 0 -q
    11 passed in 9.49s

The two refusal arms are separated by cause rather than by the refusal alone, which matters because they share an exception type and both hold on this machine at once: free device memory sits below the operator threshold AND the runtime is usually down, so a live refusal proves neither on its own. A measured shortfall, an unmeasurable free figure, and a shortfall whose attribution could not be read are asserted as three distinct verdicts, and a post-quiesce reading admits the same request as the positive control.

A live-fire case asserts the dispatch AGREES with the authority's own verdict for this host rather than hardcoding one, because the verdict is a property of the box: a case asserting "refuses" would pass here and fail on a machine with headroom, and neither would be testing the wiring.

A fixture anchor asserts the model under test still declares a catalogue requirement, since a rename would make every refusal case pass by never running the check.

Proven by two mutations from external plugins. Removing the check turned 11 passes into 7 failures. Making an unmeasurable reading admit turned exactly the three fail-closed cases red and left the shortfall and permit cases green. The second mutation initially reported a false green: it patched the importing module's namespace while the dispatch resolves the authority through a function-local import, so it never reached the code. Re-targeted at the owning module it flipped, and the plugin now reports assessments=12 flipped=3 so a future run cannot repeat the mistake silently.

## Notes

One direction is deliberately not covered and is worth stating rather than burying: a model the catalogue makes no claim about is not assessed. Inventing a requirement would be worse than not checking, because an unknown requirement read as zero flows into the authority as the amount the model needs and returns ADMITTED on evidence nobody has. That is the reasoning the assessable-load accessor already records for every other caller. The consequence is that an operator running an uncatalogued local model gets no headroom check; closing it means either catalogueing the model or giving an override a way to declare its requirement. A case asserts the gap explicitly so it is visible rather than assumed.
