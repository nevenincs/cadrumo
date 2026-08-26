---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:cdfa1fc90f5636bf9093f152fc41caa19b4d2ed67ac7495a40df412a19ec7235'
step_id: 'S68'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct the close review's claim that the app-versus-config criterion is wholly unenforced: the operator-surface contract already binds every root-to-child family to a declared root

## Scope

- `.vault/audit/`

## Changes

- `verify:` `pytest test_operator_surface_contract_drift.py -m integration` -> `1 passed`
- `verify:` `python -c "...COMMAND_GRAPH..."` -> `20 root->child families, 65 leaf subjects`

## Notes

No code changed. This corrects an overstatement in this campaign's own close
review, found while scoping the gate the review said was missing.

S60 and the fifth addendum both state that the app-versus-config criterion is
"prose in an execution record, not a gate", and that "a future subject could be
mounted against it with nothing going red". The first clause is true of the
criterion's WORDING. The second clause is too strong, and I did not check before
writing it.

`application/operator_surface/_contract.py` already declares every mounted
family as a `MountedCommandFamily`, and that model carries **`root:
RootSurfaceName`** and **`operator_question: str`** -- the two things the census
I was about to build would have had to invent. Twenty families are declared,
twelve under `config` and eight under `app`.

It is enforced in both directions.
`test_operator_surface_contract_covers_the_live_tree` is a symmetric-difference
assertion with no allowlist: a `root -> child` group mounted by the CLI but
absent from the contract fails, and so does a contract family with no live
mount. It carries an anti-vacuity floor because the lazy-Typer tree is a
documented false-green vector. It passes.

So a new top-level FAMILY cannot be mounted without someone declaring which root
it belongs to and what operator question it answers. That is most of what the
missing gate was supposed to buy.

**What remains genuinely unenforced is narrower than claimed, and worth stating
precisely.** The contract binds families at `root -> child` granularity -- twenty
of them. The criterion was judged over sixty-five leaf SUBJECTS. A new subject
nested inside an existing family (`app ledger inventory movement`, say) is not
covered by the symmetric difference, because its family is already declared.

The correction matters more than the residue. Had this stood, the campaign would
have handed its successor a gate to build that largely exists, and the operator's
standing instruction to lead with semantic discovery is exactly what surfaced it
-- one search for a subject-classification census returned `_manifest.py` twice
before any code was written.
