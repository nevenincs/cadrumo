---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S30'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# DEFERRED as unmeasured rather than cleared, assess the five remaining pinned readers the host-pinning sweep never individually examined, which the closed item carried forward instead of resolving

## Scope

- `src/cadrumo/adapters/outbound/aeat`

## Description

- Identify the five by measurement rather than by memory, enumerating every production module in the adapter that names a numbered AEAT host.
- Separate the two things a reader can pin, the request origin it navigates to and the host set its guard admits, since the sweep moved only the second.
- Examine each of the five against both, and against whether a guard governs it at all.
- Record the assessment rather than changing five readers, since four of the five are correct and the fifth is a consistency question the module default deliberately leaves to its owner.

## Outcome

The five are identified and each is assessed. They are the production readers that build their request URL against a pinned numbered host: `sede/_declarations_fetch.py`, `sede/_notifications.py`, `sede/_declarations_observations.py`, `sede/_walker.py`, all on `www6`, and `verify/__init__.py` on `www2`.

The distinction the sweep left implicit is that a reader pins in two places. The sweep widened GUARDS to the AEAT apex so a dispatch to a sibling host is admitted; it did not change the ORIGIN any reader navigates to. All five remain origin-pinned, which is why they read as unexamined.

`_declarations_fetch` is sound and is the model for the others. Its pin is documented at the constant: entering unnumbered reaches no host, a wrong numbered host 404s, and this constant names one known to serve the route. It is an entry address and a fallback only — `_origin_of` records the host that actually answered, so stored evidence never claims a read happened where it did not. Its guard is apex-widened.

`_notifications` is structurally identical and its guard carries the same widening with the reasoning attached. Its origin pin carries none. Nothing is wrong with it; the reasoning `_declarations_fetch` records simply is not repeated where the same decision was made.

`_declarations_observations` is the one whose pin is load-bearing beyond navigation. Its listing host is the key that selects which registry cross-reference governs the read, so the constant is a policy lookup, and the resulting policy is built by `remote_state_policy_from_cross_reference` and therefore carries NO suffix widening. Its admitted set is whatever the registry declares, which for the M100 declarations surfaces is `www1` and `www6`. So the same listing read is governed by an apex-widened policy on the fetch side and an enumerated one on the observation side.

`_walker` is the only one of the five that no read-guard policy governs at all. It navigates the resumen URL directly at three sites and the module declares no policy and calls no assertion. It drives an already-authenticated page rather than reaching a new surface, which is why this is reported rather than treated as a defect, but it is the one whose pin nothing checks.

`verify/__init__.py` is the clearest result and it inverts the expected finding. It is the only one of the five whose guard has no suffix widening, and that is correct: it is a `public_read_surface` with `requires_authentication=False`. The whole load-balancer rationale is about an authenticated session being ASSIGNED a numbered host; an unauthenticated CSV cotejo read has no session to assign, so there is nothing to tolerate and widening it would loosen a guard for a reason that does not apply to it.

Nothing was changed. Four of the five are correct as they stand, and the fifth — the fetch/observation asymmetry — is a decision belonging to the declarations owner, since closing it means either widening a registry-built policy against the module default's explicit warning or narrowing the fetch guard against a live dispatch it was widened to admit.

## Notes

The row's criticism was that the item carried these forward unmeasured. They were measurable the whole time; what made them look otherwise is that "pinned reader" names two different pins, and the sweep's own closure spoke about guards while the residue was about origins. Stating which pin is meant is most of the work.

The `verify` result is the one worth keeping. It was the obvious candidate for the sweep to have missed — the single reader with no widening — and it turns out to be the single reader that must not have one. An assessment that had cleared the five by applying the sweep's rule uniformly would have loosened it.

This assessment is a read of the tree at one commit and asserts nothing about live behaviour. Which numbered hosts serve which route is not established here for any of the five, and the `_declarations_observations` enumeration is reported as what the registry declares, not as confirmation that those two hosts are the pool.
