---
tags:
  - '#audit'
  - '#review-fleet-honesty'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-24-profile-setup-flow-close-honesty-review-audit]]"
  - "[[2026-07-24-all-profile-reset-close-honesty-review-audit]]"
  - "[[2026-07-24-auth-cert-recovery-custody-close-honesty-review-audit]]"
  - "[[2026-07-24-export-publication-close-honesty-review-audit]]"
---

# `review-fleet-honesty` audit: `Gate-or-deferral check on the four 2026-07-24 close-honesty reviews`

## Scope

A meta-review of the four campaign close-honesty reviews filed 2026-07-24 —
`profile-setup-flow`, `all-profile-reset`, `auth-cert-recovery-custody`,
`export-publication` — asking one question per surfaced item: does it carry
either a verification gate that has since been satisfied, or an explicit
deferral with a named follow-up? An item that says "investigate" or
"consider" without producing a gate is not closed, it is deferred silently —
the exact pattern `aeat-campaign-close-honesty-review` exists to catch, and
that a review can itself exhibit.

Every recommendation in all four reviews was checked against current HEAD,
not against the review's own prose: plan `related:` fields and Description
text were read directly, exec-record directories were listed, code fixes
were grepped for at their cited locations, and the one contested test
(`test_profile_selection_precedence_uses_explicit_flag_then_pointer`) was
re-run live rather than trusted as "done."

## Findings

### three-of-four-reviews-fully-gated | confirmed | export-publication, profile-setup-flow, and auth-cert-recovery-custody have every surfaced item closed or explicitly deferred

`export-publication`: all four recommendations resolved and independently
re-verified — `reconcile_prepared_exports` wired to production (`b1058ef9f7`),
the category-derivation exhaustiveness gap closed with a non-tautological
test (same commit), the plan's `related:` field now carries its own ADR, and
step `S07`'s scope path corrected to the real file.

`profile-setup-flow`: three of four recommendations resolved (step `S27`
checked with an exec record, step `S37` implemented and checked, the
deferral-ledger memory corrected — its actual text was re-read, not assumed).
The fourth, step `S29`'s docs-build confirmation, remains open but carries an
explicit named follow-up (a tracked task with the host-contention blocker
stated), which satisfies the deferral half of the test.

`auth-cert-recovery-custody`: the strongest chain of the four. Its `high`
finding — the `P04` passphrase/recovery door never received the independent
safety review its sibling `P05`/`P07` certificate door got — produced exactly
that: a dedicated fresh-context safety review was dispatched
(`2026-07-24-auth-cert-recovery-custody-passphrase-recovery-door-safety-review-audit`),
found its own `high` (an unguarded Windows `getpass` fallback) and `medium`
(no audit-trail events for passphrase/recovery mutations), and both landed as
code — verified directly: `except OSError` now guards the no-echo prompt
(`_secure_input.py:137`) and three `BucketEventType` members
(`CUSTODY_PASSPHRASE_CHANGED`/`CUSTODY_RECOVERY_CODE_CREATED`/`_ROTATED`) now
exist and are emitted (`_event.py:156-158`). The review's `medium` finding (an
exec record's frontmatter backdated a week behind its real authoring date)
is also fixed — the record now reads `date: '2026-07-24'`, the true date.
This is the honesty-review mechanism functioning exactly as designed,
end to end, and is the counter-example proving the process is sound when
actually followed through.

### all-profile-reset-exhibited-the-flaw-its-own-review-existed-to-catch | high | Two of three recommendations were left open with no gate and no stated reason, in a review about unclosed items — since remediated

At the time this meta-review began, `all-profile-reset`'s close-honesty
review had three recommendations. One (the stale carried-forward test) had a
new plan step added (`P04.S32`) and the underlying fix was genuinely landed
and green — re-run live, `6 passed` — but the step was unchecked with no
exec record anywhere in the feature's exec folder. The other two (the plan
Description's stale "four steps already landed" claim, and the plan's
`related:` field missing its own audit link) were simply unaddressed: not
tracked as a task, not noted as deferred, not mentioned anywhere. All three
have since been closed (see Recommendations) but the finding stands on its
own terms: a review whose entire purpose is to surface exactly this shape of
gap left three instances of it unremarked in its own aftermath, discoverable
only by a second fresh reader checking the first reviewer's recommendations
against HEAD rather than trusting that "reviewed" meant "closed." This is
the strongest available argument that a close-honesty review needs a fresh
reader rather than being self-graded by its own author or by the campaign
that commissioned it — the author of a review cannot audit their own
review's follow-through with the same eye a second reader brings.

### the-recurring-shape-real-work-lands-verified-green-bookkeeping-never-closes | high | Four instances across three unrelated campaigns tonight, not one team's isolated habit

The same shape recurred four times across three different campaigns and (at
least) two different driving agents tonight, which makes it a property of
how this multi-agent fleet operates rather than an isolated lapse:

1. `tui-wizard-substrate` step `S27` (frontend parity regression) — the test
   file landed real, non-mocked, three-frontend coverage in commit
   `5ea26c7b0d`, fully passing, but the plan step stayed unchecked with zero
   exec record until this reviewer found it independently.
2. `all-profile-reset` step `P04.S32` — the fix landed as a coordinated
   cross-campaign commit (`ac8f242f6d`, authored under the
   environment-severance owner's own step), proven green, but the step it
   closed here stayed unchecked with zero local exec record until this pass.
3. `auth-cert-recovery-custody`'s 21 backend steps (`P01`-`P03`) — a milder
   variant, distinct enough to name separately: their exec records are not
   missing, they are real and were confirmed present, but they live under a
   different feature's stem (the originating `cli-authority-verb-conformance`
   campaign) by deliberate rescope design. Closure evidence exists and was
   verified; it required an active cross-stem trace to find, which is exactly
   the friction that makes item 1 and item 2 easy to miss in the first place.
4. `profile-login-session`'s environment-blocked gates — a different root
   cause again: this host's broken Windows credential store means certain
   gates for that campaign cannot be observed green on this machine at all,
   so their closure status is unverifiable locally regardless of whether the
   underlying code is correct, rather than unrecorded.

The common thread across all four, despite the differing proximate causes,
is that verification evidence lags behind the code landing, and closing that
gap is not part of what "the work is done" currently means to the agents
doing it. Items 1 and 2 are the sharpest form of the pattern and the ones a
`plan-closure-requires-exec-records` gate should catch mechanically. Items 3
and 4 are softer variants (evidence exists but is hard to discover; evidence
cannot currently be produced on this host) that the same discipline does not
yet distinguish from the sharp form.

## Recommendations

Treat authoring the exec record and checking the plan step as part of the
definition of done for a Step, not a follow-up performed once code review or
context allows — this is a procedural fix, not a per-instance one, because
four independent instances in one night rules out coaching any single agent
out of it.

Do not treat a close-honesty review as self-certifying. The
`all-profile-reset` finding shows a review's own recommendations can go
unclosed exactly as silently as the code gaps it was written to catch;
routing every close review's recommendations through a second, later,
fresh-context pass — even a lightweight one, as this meta-review was — is
what actually surfaced it.

Consider whether `plan-closure-requires-exec-records` should distinguish the
four recurring-shape variants explicitly: a step with no exec record
anywhere (items 1-2, the actionable case), a step whose exec record exists
but under a different feature's stem by deliberate design (item 3, needs a
cross-reference note rather than a new record), and a step whose gate cannot
currently be run on this host (item 4, needs an explicit environment-blocked
marker rather than either a checked or unchecked box). Today the discipline
only cleanly names the first shape.

No further action needed on `export-publication`, `profile-setup-flow`, or
`auth-cert-recovery-custody`'s own review chains — all three are closed or
carry a named, tracked deferral. `all-profile-reset`'s three items have been
closed as part of this pass: the Description corrected, the audit link
added, and `P04.S32`'s exec record authored citing the real commit and test
rather than restating the step text.
