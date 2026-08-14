---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e125cc45de611ff45cd7ab108ba8edf3e64b386a4819c6168366eb130d0815aa'
step_id: 'S89'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Run marker banned-import topology ownership and no-monkeypatch gates

## Scope

- `src/cadrumo/tests`

## Description

- Run the fast test-framework ratchet lane covering discovery, markers, skip and xfail, test doubles, mutation, broad raises, bare except, and tautology drift.
- Capture every failure with its identity rather than a tally.
- Attribute each failure to the change that introduced it before treating it as this campaign's.

## Outcome

One hundred and fifty-five of one hundred and sixty-four cases pass. Nine fail, and none of them was introduced by this campaign, which was established by attribution rather than assumed.

The mutation-inventory gate is red on a single site in a registry test that another campaign committed after this campaign restored that gate. This campaign's own four reported sites carry no mutation machinery, verified directly. The site is deliberate and documented in place: it redirects the bundled registry root because the default-root branch carrying the defect cannot be reached without editing the shipped tree. Resolving it needs a production seam in a domain this campaign does not own.

The marker-integrity module fails six ways, on hexagonal marker placement, statement ordering, credential-store membership pinning, live-token usage, and two campaign-metadata prohibitions. The identical six were measured at session start before any change here. The tautology ratchet names one comparison of two distinct literal error codes in an invoices test; the test-double ratchet names definitions elsewhere. All belong to other campaigns' code.

The topology and banned-import halves this campaign owns are green: the repository root applies both the marker contract and the live-import policy once, and the child collection hook that duplicated the marker walk no longer exists.

## Notes

The distinction worth keeping is between a gate this campaign broke and a gate this campaign restored that someone else later re-broke. The second is still a red gate, and the campaign's stated criterion that the mutation inventory passes with no allowlist or suppression is therefore not met on this tree. Recording it as another campaign's debt is accurate but does not make the criterion met, and the temptation to read a green subset as a green gate is exactly what that criterion exists to refuse.
