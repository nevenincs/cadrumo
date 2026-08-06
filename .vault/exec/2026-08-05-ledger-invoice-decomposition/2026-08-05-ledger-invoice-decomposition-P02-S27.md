---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2f7515fe268b8207aa29f98581af78027337ccca8d12240c2259e5ec6c257ac8'
step_id: 'S27'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Correct the six-entry LIVA batch document_id to its BOE identifier as one coherent change, then hand it to the operator for re-stamp

## Scope

- `src/cadrumo/_data/registry/aeat/legal`

## Description

- Measure the batch: six entries in `iva.toml` carry `document_id = "Ley 37/1992"` while the same file uses the canonical `BOE-A-1992-28740` elsewhere for the same law.
- Confirm the fix needs no external authority: each affected entry's own `permalink` already names `BOE-A-1992-28740`, so the entry contradicts itself and supplies both halves of the evidence.
- Correct all six in one change, since a partial fix would leave an operator-stamped batch internally inconsistent.
- Confirm no other non-canonical `document_id` remains anywhere under the legal tree, so the batch was the whole class rather than a sample of it.
- Add a self-evidencing gate asserting every catalogue entry's `document_id` agrees with the BOE identifier in its own `permalink`.
- Mutation-prove the gate: restore one entry to the old spelling, confirm it reddens, restore, verify with a post-hoc diff.

## Outcome

Commit `f922a49023`, two files: six identifier corrections and a 51-line gate.

Verified after the change: `test_registry_legal_grounding.py` 11 passed. The
agent-facing resolve surface the review flagged now agrees with itself —
`ley-37-1992:art-68` returns `document_id = BOE-A-1992-28740`, matching its
permalink.

The defect was live but latent. The citation-group projection keys off the
reference-id prefix rather than the document id, so nothing downstream was wrong
today — correct only incidentally. What changed the risk was the grounding
commit that made art. 68 a citation agents will actually resolve, turning a
dormant inconsistency into a wrong answer on a surface with a reader.

The gate is self-evidencing rather than a hardcoded expectation: each entry
supplies both halves and it only asserts they agree. Entries whose permalink
names no BOE document are skipped, since they make no claim to contradict.

Two anti-vacuity assertions guard the scan itself — it must reach at least fifty
entries and span more than one document. Without those, a matcher that silently
stopped reaching the catalogue would keep passing while checking nothing, which
is the failure mode this campaign found four separate times elsewhere.

## Notes

**Operator re-stamp still outstanding.** The six entries carry
`review_status = "reviewed"`, `reviewed_by = "operator"`, `reviewed_at = 2026-08-01`.
Those stamps were deliberately left untouched: they attest the legal content —
the required-text phrases and article numbers — not the document identifier, and
re-stamping is the operator's act, not an agent's. The correction is recorded
here so the re-stamp can be made against a known change rather than a diff
someone has to reconstruct.

**A separate doubt travels with that re-stamp**, raised by the S21 code review
and not addressed here: an `effective_from` value that may be off by one on a
related entry. It was deliberately recorded as a doubt rather than changed,
because dating a provision's entry into force is a legal judgement.

**Scope note.** The Step text says "hand it to the operator for re-stamp"; the
handing-over is this record plus the campaign report, not a separate artefact.

**Discovery credit.** Found by the S21 code review, which measured the defect as
non-load-bearing in the group projection but live per-article on
`CitationLookup.resolve`. It had been recorded only in a commit message — a
channel no catalogue reader ever sees, which is why it needed a Step rather than
a note.
