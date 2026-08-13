---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:614449652e1ad569d34b704fddef64e523cdf584d723c41853b0bd3ee6b3a303'
step_id: 'S03'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# HUMAN GATE, owner: operator, no agent may self-stamp review_status. Operator reviews the S02 draft against the committed corpus and personally commits the entry with review_status=reviewed, confirmed by the legal-catalogue verification suite (verify_legal_reference / registry build validation) passing green against the merged entry. This Step blocks every Step that RESOLVES the catalogue entry, namely P02.S11, P03.S08 and P04.S09, plus the P01.S10 closeout that records it. It does NOT block P02.S04, P02.S05, P03.S06 or P03.S07, which depend only on the corpus committed in P01.S01

## Scope

- `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`

## Description

- Present the committed catalogue entry to the operator for personal
  adjudication, with the bundled corpus text quoted verbatim beside it and the
  verification result already computed, so the review is a read against
  evidence rather than a request to trust the drafting agent.
- Re-stamp `reviewed_by` from the agent-authored placeholder to the operator who
  performed the review, and move `reviewed_at` to the date the review happened.
- Rewrite the provenance note so it records what was checked instead of
  recording that a check was still outstanding.

## Outcome

The entry ships stamped by the reviewer who actually read it. Before this Step
the catalogue carried `review_status = "reviewed"` -- the type admits no other
value -- beside a `reviewed_by` reading "agent-authored; operator to re-stamp",
so the schema asserted a human review the field itself denied. That gap is the
whole reason the row was carried as a human gate rather than folded into the
drafting Step.

The operator confirmed the substance, not merely the process: the bundled
BOE-A-2015-10565 consolidated text states the window as "se entendera rechazada
cuando hayan transcurrido diez dias naturales desde la puesta a disposicion de
la notificacion sin que se acceda a su contenido", both `required_text` phrases
match it verbatim, and the article is the one that establishes the value rather
than a framework article that merely applies it.

What the review did NOT establish is recorded rather than papered over. The
note keeps the drafting agent's caveat that no exhaustive search was made for
an AEAT-procedure-specific plazo displacing the general regime; only RD
1363/2010 (which refers back to the general regime) and LGT art. 112
(notificacion por comparecencia, a different supuesto) were excluded. The
consolidated PDF also does not annotate which articles were amended, so the
entry claims today's operative text and nothing about the provision's history.

## Verification

    verify_legal_catalogue({"ley-39-2015:art-43.2": reference}, source_root=bundled_path())
    GREEN; reviewed_by= Gergely Wootsch <hello@gergely-wootsch.com> ; reviewed_at= 2026-08-13

    uv run --no-sync pytest .../test_catalogue_verification.py .../test_catalogue_verification_normatives.py .../test_catalogue_verification_fragments.py -q -p no:randomly
    77 passed in 26.01s

Operator sign-off commit: `e4efccaf1e`.

## Notes

The stamp is an attribution change on a filing-grade surface, so it was made in
its own commit with a message naming what the operator checked, rather than
folded into the consuming code. A later reader auditing why this value is
trusted lands on that commit and its evidence, not on a feature commit.
