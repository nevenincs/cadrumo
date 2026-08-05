---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:4cffe0e11da194bb9f4d5d0db5481b1ff3fdd45c07cff88098130fa1f4adb494'
step_id: 'S27'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Author the Art. 61 norma 4a flat figure as its own registry money parameter

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/`
- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Author the fallecimiento money parameter across all six served revisions, 2020 through 2025.
- Author its legal-catalogue entry anchored to the bundled corpus.
- Add the orphan-parameter allowlist entries the drift gate requires, with the reason recorded in place.

## Outcome

The parameter exists in every served revision with its legal entry, and is deliberately NOT bound to the first birth-order tranche despite both figures being 2.400 euros in every current revision.

That non-binding is the decision the Step exists to make. The two are legally distinct figures that merely coincide today, so binding them would silently move the death amount if a future reform moved the tranche. A coincidence of values is not a shared authority. This is the second such refusal on this campaign, after two constants that share the year 2023 for unrelated reasons were also kept apart.

## Notes

The grounding I was handed was half wrong and the implementing agent caught it. Limb one, the flat cuantia, is verbatim statute. Limb two, the exclusion of the deceased from the survivor ordering, is NOT in the statute at all -- that wording exists only in the AEAT manual's cuantias section. The brief relayed both as statutory because it inherited an earlier agent's grounding without checking which instrument carried which limb. Limb two is now pinned as a required_text on the manual citation, so it has a registry home and fails loudly if the passage moves.

Two facts surfaced here that changed the following Step rather than this one. The manual states the menor-3 increment applies where the descendant died during the period, so the flat figure replaces the TRANCHE only and the supplement still accrues -- a whole-entitlement reading would have under-granted, which is the opposite error to the one the campaign was closing. And the clause fixes 1.150 euros for ascendientes in the same sentence, so the legal entry is written as the single authority for both with an explicit instruction not to mint a second.

The scope clause named only the parameter and legal directories, but the drift gate requires an allowlist entry for any parameter no domain-layer reader consumes. Six entries were added and the reason documented in place: that gate scans only the domain layer, so an application-layer consumer is structurally invisible to it, and every sibling tranche is already listed for the same reason. The entries sit on identical footing before and after the consuming Step lands.

Verification was not a bare green. The citation checks ran through the production validators with a positive control substituting an absent sentinel phrase, and the control failed on all six parameters and on the legal entry -- so the probes are not vacuous. Both limbs were confirmed present in all six bundled manuals, so the served window is uniform.
