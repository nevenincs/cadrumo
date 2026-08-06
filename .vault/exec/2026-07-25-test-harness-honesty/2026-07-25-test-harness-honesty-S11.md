---
tags:
  - '#exec'
  - '#test-harness-honesty'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:7d19016124c6c52dad9e9069e0e62b62ee40d89b4a1ceb7cf1ff7c08bb55f6e7'
step_id: 'S11'
related:
  - "[[2026-07-25-test-harness-honesty-plan]]"
---

# Reconcile the duplication disposition record against a fresh live scan

## Scope

- `dev/audit/duplication_dispositions.toml`

## Description

- Run the live scan at current HEAD and confirm the gate is still red.
- Read each unrecorded clone group in full rather than trusting the span report.
- Judge each group against the substitutability pre-filter and record a verdict.
- Update the advisory `meta` and `summary` counts to match the new inventory.

## Outcome

The gate was red on three groups, not the one the plan recorded. The record had
drifted further while nothing was watching it, which is a direct consequence of
the reachability defect closed under `S12`: this gate lives in a directory no
lane collects, so its red state was invisible from the moment it appeared.

Each group carries an individually reasoned verdict.

The two sede readers match on their import preamble, the same residue two
existing entries already record for the oracle and ledger-projection pairs.
Both import the same navigation substrate because both are sede readers; what
follows the preamble diverges, and a preamble cannot be deduplicated without the
re-export shim the architecture rules forbid.

The cross-file TUI pair is constraint-divergent and excluded by the
substitutability pre-filter. The two dialogs disagree on what an edit means: one
starts a masked field empty and dismisses with the raw input, the other
pre-fills and routes save through a validating submit so a refusal can render in
a slot the first has no equivalent for. Consolidating in either direction would
add masking where it is unwanted or drop validation where it is load-bearing.

The intra-file TUI clone is the honest one. Its shared modal chrome genuinely is
substitutable, and the entry says so in those words rather than dressing the
residue up as intentional. It is recorded as advisory debt rather than
consolidated because it is another campaign's live surface and because a
declarative widget tree reads worse behind helper generators. The entry states
explicitly that it is not a verdict against the extraction, so the owning
campaign can take it on its own terms.

## Notes

The plan cautioned that this code is peer-owned and needs its owner rather than
a silent classification by a sweep. That caution is honoured in form and not
just in outcome: no classification here is a blanket, each names the specific
divergence or the specific residue it rests on, and the one group that could be
consolidated is labelled as such rather than being quietly filed under
intentional to make the count look better.

The gate moved from one failure to twenty-two passing on exactly these three
entries, which is the demonstration that each is load-bearing rather than
incidentally satisfied by an existing entry. That mattered here specifically:
coverage is keyed per file-set as a multiset, so a self-clone and an unrelated
cross-file clone touching the same file are distinct entries, and a careless
reading would have assumed one covered the other.

The `meta` and `summary` counts are advisory and no test reads them. They were
updated anyway, because the file's own header explains what they mean and
leaving them stale would be a quiet lie in a record whose entire purpose is
honest accounting.

Semantic code discovery was unusable throughout and every claim rests on direct
reads of the cited spans.
