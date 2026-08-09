---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d2948b900361d245b07ce80366a6cc701283761b8b3baee583b1f5f5bb2fa5fc'
step_id: 'S51'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Record the deliberate decision not to ground the two censal fiscal-ID refusals, whose grounded label would propagate a known-wrong legal citation

## Scope

- `src/cadrumo/application/user_profile/_censo_sync.py`

## Description

- Examined the two censal-read refusals the behaviour census surfaced, which name the fiscal identifier in prose rather than through the schema.
- Resolved what this campaign's own mechanism would render for that field, and compared the result against the current prose.
- Decided against grounding them, and recorded why.

## Outcome

**Recorded, not actioned.** The two refusals keep their prose.

The mechanism would render `identity.tax_id` as "Tax ID (NIF/NIE/CIF)" followed by its registry citations - and those citations include `orden-hac-1347-2024:art-4`, the annual módulos order, which is documented under the preceding feature as a real, corpus-verified WRONG citation on the declarant-identity cluster and is deliberately out of scope for correction.

So grounding these two would trade a marginal gain for a real loss. The existing prose already names the fact an operator has to supply, in words they can act on, and both messages already carry a concrete command. What grounding would add is a label barely more precise than the prose - and a wrong legal citation, on two further operator-facing surfaces that do not carry it today.

This is the same trade the governing ADR flagged as a consequence of the mechanism, but the balance falls the other way here. Where a refusal previously showed a raw identifier, grounding was a clear net gain even carrying the bad citation, because a raw path is unusable. Where it already shows usable prose, spreading the citation is the dominant effect.

Stated plainly so a later reader does not "finish the job": these two sites are consistent with the campaign's intent, not an oversight, and grounding them becomes correct as soon as the citation defect is fixed.

## Verification

No code change. The disposition rests on a resolved fact rather than an assumption: the rendering was computed through the real schema and real registry authority, and the citation it contains was read from that output rather than inferred from the audit describing it.

## Notes

The prose in both messages is already actionable, and one of them carries the remediation command, so neither is unactionable in the sense this campaign exists to fix.
