---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:dfcee6fe7f3c23dcea846f2350f62c96f6b1dd3374053e7512f284092e719282'
step_id: 'S302'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Delete the tags-reply helper its only consumers cannot use

## Scope

- `src/cadrumo/tests/loopback_llm.py`

## Description

- Delete the helper and its export entry from the shared loopback test-support home.
- Sweep the whole source and dev trees for residual references, UNPIPED so the exit code is the signal, and pair the sweep with a positive control on a surviving sibling so a clean negative is evidence rather than a broken instrument.
- Confirm the committed diff carries the helper and nothing else, since a text rewrite of a file with mixed line endings can silently restate every line.

## Outcome

Thirteen lines removed, nothing added, and the working tree matches HEAD afterwards.

**The reason is recorded here because the caller count is not the argument.** Zero callers is evidence about a symbol, never about a capability, and this codebase confuses the two routinely — a surface with no wired consumer looks identical to a surface nobody needs. What makes this a deletion rather than a gap is stronger and narrower: the helper is UNUSABLE BY ITS ONLY PLAUSIBLE CONSUMERS.

It was shipped by the first consolidation pass for the three provisioning suites. The second pass established those suites cannot honestly use it, because their bodies feed deliberately MALFORMED payloads — an empty list, a null models key, a numeric name — to prove the discovery probe returns a typed unavailable rather than raising. A well-formed envelope builder cannot express any of those shapes. Routing them through one would have silently repaired the exact defect under test, which is the trap where a fixture ends up certifying the behaviour it was written to constrain.

So there is no future in which those three suites adopt it, and no fourth consumer was ever proposed. Keeping it would leave dead capacity inside a shared home, where it is worse than dead capacity elsewhere: a reader who finds the home reasonably assumes everything in it is the sanctioned way to do the thing it names.

**What this excludes.** Only the helper goes. The home keeps its plumbing, its two inference reply builders and its silenced access log, all of which have live callers. This says nothing about the discovery protocol itself — a future need for a well-formed inventory envelope is a new decision with a real consumer behind it, not a re-instatement of this one.

## Verification

Committed as `88d1e7e3f0`, thirteen deletions and zero insertions, working tree clean against HEAD afterwards. The diff carries exactly the export entry and the function block.

Residual sweep, run unpiped with the exit code captured directly, because a piped sweep reports the pipe's status and a zero-match run then looks identical to a crashed one:

    rg -c "ollama_tags_reply" -g '*.py' src dev     -> exit 1, zero matches
    rg -c "ollama_chat_reply" -g '*.py' src         -> exit 0, positive control

The control is not decoration. A clean negative is not evidence until the instrument has been shown still able to find something.

Gate run requested from the single test-run authority rather than executed here.

## Notes

Removing a public helper is a decision rather than a cleanup, which is why it took a row and its own commit instead of riding the consolidation. The row exists mostly so the next reader does not re-add it believing the migration missed a site.

The general lesson is the one that belongs beside the symbol-sweep clause rather than inside this row: when a dead-capacity finding is real, its evidence must be the REASON the capability cannot be reached, never the COUNT of who names it.
