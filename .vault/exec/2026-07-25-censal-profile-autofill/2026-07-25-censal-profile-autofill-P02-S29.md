---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S29'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# DEFERRED pending an operator probe, decide whether the capture-path read guard's host set should follow the module default it documents, the answer turning on what AEAT actually serves rather than on anything the tree can settle

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede`

## Description

- Read the module default the row refers to, finding it is the absent host-suffix widening in `remote_state_policy_from_cross_reference` rather than a setting the censal guard overrides.
- Establish that the default carries its own carve-out for a surface whose reads span the numbered pool, so the question is whether the censal read is such a surface rather than whether the default is right.
- Confirm from the reader that it is: the route is entered through the host-agnostic selector and the answering host is read off the landed page, because AEAT assigns it per session.
- Find the carve-out's prescribed remedy already in use elsewhere, the declarations cross-references enumerating the pool on their own allowed hosts in registry TOML.
- Separate the settleable question from the unsettleable one rather than deferring both.
- Record the divergence, its reason, and the probe that would close it at the guard, not in a record.
- Re-run the reader and no-write gates, since the note sits in a package a static source scan reads.

## Outcome

Decided: the censal guard does NOT follow the module default, and the widening stays.

The top half of the question is settleable from the tree and is now settled. The default's own text carves out "a surface whose reads genuinely span AEAT's numbered pool", and the censal reader is measurably one — it enters through the host-agnostic selector, and `_resolve_dispatched_origin` exists precisely because the host is assigned rather than chosen. Following the default would refuse the reader's own successful landings.

The bottom half is not settleable and the reason is now precise rather than general. The carve-out prescribes enumerating the pool on `allowed_hosts`, which the declarations cross-references already do with `www1` and `www6`. That remedy is unavailable here because which numbered hosts serve the CENSAL route is a fact about AEAT that this tree carries no observation of, and it cannot be borrowed from the declarations set: the reader's own comment records that some numbered hosts do not serve this route and others refuse a session minted elsewhere.

The probe is named at the site: authenticate, run the censal read repeatedly, and collect the `host=` values the resolver logs at info until the pool repeats. That is an operator action against a live session, not something a committed test may require.

`uv run --no-sync pytest` over the censal reader and the sede no-write gate reported `62 passed in 9.73s`. `ruff check` reported `All checks passed!` and `ruff format --check` reported `1 file already formatted`.

## Notes

The row framed this as one question the tree cannot answer. It is two, and only the second is external. Recording it as wholly unsettleable would have left the next reader believing the divergence itself was unexamined, when the divergence is the default's own sanctioned case; what is unmeasured is only the narrower host list that would let the guard be tightened further.

The note deliberately states that the host guard is not the no-write wall. The forbidden-landing markers are, and they are unaffected by the host set. Without that sentence the widening reads as a loosening of the write refusal, which would make a later reader narrow it for a safety reason that does not apply — and narrowing it on the current evidence would refuse correct reads.

No probe result was invented. Nothing here claims which hosts serve the route; the tree is asserted to be silent on it, which is a different and checkable claim.
