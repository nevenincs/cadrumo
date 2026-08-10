---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1d51206bdd444366047c7cc5d9352c7b41299ca9f2cc79693de7ede40d0c7169'
step_id: 'S320'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the overstated redaction rationale carried in the streamed-progress fix, which claims the funnel masks filesystem paths when it masks only embedded identifiers

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Correct the claim where a reader of the code will meet it, since a commit body cannot be amended.
- State what the policy does and does not do, rather than deleting the sentence and leaving a gap.
- Own the error rather than attributing it to the worker who executed the change.

## Outcome

The commit that introduced the streamed-progress primitive described the leaked material as full local filesystem paths and called them exactly the material the funnel exists to mask. **Measured, the policy substitutes embedded tax identities and opaque record identifiers and leaves the surrounding path intact.**

The leak was real and the fix is correct. The rationale claimed a protection that does not exist, **in the direction that made the finding sound worse**, and it reached a commit message that outlives the conversation.

The primitive's docstring now states what is masked and what is not, and names the narrower true claim: identity and opaque-identifier masking on a channel that had none.

## Verification

    changed lines            9, all docstring prose
    executable lines changed 0
    lint                     clean

## Notes

**The failure was structural rather than careless, and saying so makes it transferable.** The probe output carrying the disconfirming evidence had already been read when the claim was written — the path was plainly visible surviving the substitution while the identity inside it was replaced. Reading past evidence one has already seen is the ordinary shape; carelessness is the rare one.

**It was caught by the executor of the change, not by its author**, on a review that was not looking for it.

**The correction lives in three places deliberately**: this record, the sibling record for the fix itself, and the module docstring. The vault is removable development scaffolding by its own rules, so a caveat that lives only there is one deletion away from a clean-looking history.
