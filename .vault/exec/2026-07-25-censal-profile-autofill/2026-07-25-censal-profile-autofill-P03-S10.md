---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S10'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Verify the whole path live end to end in three phases, a pull onto a blank profile that adopts, a second unchanged pull that is a no-op, and a third pull after the operator edits an adopted value that reports the divergence rather than overwriting it

## Scope

- `src/cadrumo/application/live/tests`

## Description

- Batch three independent live questions into one authenticated session so the
  operator is interrupted once, the Cl@ve approval window being a hard two
  minutes and not adjustable.
- Guard the profile before any write: assert the active bucket matches the
  logged-in probe bucket and that the record's display name is the probe label,
  both read from live state rather than from the login that selected it.
- Prove the guard refuses by pointing it at a wrong bucket before trusting it.
- Acquire the session through the shared live-read gate, driving only the access
  selector's authorize control.
- Read the censal consulta and capture the reader's own log records, so the
  dispatch verdict rests on emitted evidence rather than on the read succeeding.
- Request the declarations listing on the unnumbered origin and record the
  status and the landed host.
- Run the three phases against the real profile, restoring the edited value and
  its provenance afterwards.

## Outcome

All three questions answered against a live authenticated session.

DISPATCH IS PROVEN, not assumed. The reader logged
`censal read dispatched to host=www6.agenciatributaria.gob.es` — a numbered
host, so the origin resolution genuinely dispatches and the reader has not been
living on its unnumbered fallback. A successful read alone could never have
established this, because the fallback returns a working origin too.

THE UNNUMBERED ORIGIN DOES NOT SERVE THE DECLARATIONS LISTING. Requested with a
valid session, it answered 404 and landed on the requested host rather than
bouncing. So that reader cannot be unpinned by swapping the origin; it needs an
access-selector entry, which is a larger change than the host-unpinning task was
scoped for. The agent holding that task declined to guess and was right to: the
one-line change would have broken a working reader.

THE THREE PHASES BEHAVE. A pull onto the blank profile adopted the three
adoptable paths; an unchanged re-pull was a no-op in both directions; and after
the operator edited an adopted value, the third pull reported it as a divergence,
did not adopt over it, and left the operator's value standing. Phase three is the
only one that exercises the adjudication path, and it is the reason the row was
amended to three phases.

Phase one adopted three paths rather than four. The fiscal identity is projected
for the ownership check and never adopted, and this run confirms that end to end
rather than only in unit tests.

## Notes

THE INSTRUMENT BUILT TO CATCH A FALSE GREEN SHIPPED WITH ONE. The dispatch
verdict has three outcomes — the reader never ran, the fallback ran, or dispatch
is proven — and the first version collapsed the first two into one. On an
attempt where the approval timed out it printed "dispatch line absent, fallback
ran", which is a claim about code that never executed. The evidence that
distinguishes them, a count of zero captured log records, was on the same screen
and unread. The guard has to apply to the guard, and the failure was not a
missing check but an unread one.

Reader-never-ran is now reported as NO RESULT rather than as a finding, and a
first attempt this session ended exactly that way — an authentication refusal at
the representation gate, reported as no result rather than dressed as evidence.

That refusal also cost a diagnostic. The exception carries the landing URL in its
context and the harness printed only the message, discarding the one field that
says where the flow actually was. Fixed before re-firing rather than after, which
is what made the second attempt worth the operator's time.

A SELECTOR VALIDATION HELD BUT DID NOT COVER THIS PATH. The four representation
selectors were each proven to match exactly one element in real markup, through
the censal access-selector dispatch. The authentication provider drives its own
gate at a different call site with its own wait, and that is where the refusal
occurred. The earlier finding was true about a narrower frame than the reliance
placed on it, which is worth stating because the alternative was treating
"the selectors are sound" as covering a path it never tested.

One failure was the harness rather than the product: the probe called the
reconciliation without the read-identity argument that the ownership refusal
now takes, a signature that changed under it during the session. The first two
questions had already completed and the corrected re-run reused the live session
without a second prompt, so the operator was interrupted once as intended.

A cosmetic mismatch worth someone's attention independently: the reader logs that
the selector dispatch did not reach the censal path, while the dispatch in fact
succeeded and the read completed. The progress check does not recognise its own
success, so it would not report a real dispatch failure either.
