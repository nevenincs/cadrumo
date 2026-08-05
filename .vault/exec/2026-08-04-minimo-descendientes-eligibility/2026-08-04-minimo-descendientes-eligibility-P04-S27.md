---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c2071b8d8ba9d551b07631f000b95f8e5b2fce9b28965517b070470c5bd55357'
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

The parameter has no consumer at this Step, and that is intended rather than an omission. The domain slice that reads it lands separately, which keeps the regulatory figure reviewable on its own evidence before any code depends on it.

## Notes

The grounding relayed into this Step was half wrong, and the error surfaced during implementation. Limb one, the flat cuantia, is verbatim statute. Limb two, the exclusion of the deceased from the survivor ordering, is NOT in the statute at all -- that wording exists only in the AEAT manual's cuantias section. The brief relayed both as statutory because it inherited an earlier agent's grounding without checking which instrument carried which limb. Limb two is now pinned as a required_text on the manual citation, so it has a registry home and fails loudly if the passage moves.

Two facts surfaced here that changed the following Step rather than this one. The manual states the menor-3 increment applies where the descendant died during the period, so the flat figure replaces the TRANCHE only and the supplement still accrues -- a whole-entitlement reading would have under-granted, which is the opposite error to the one the campaign was closing. And the clause fixes 1.150 euros for ascendientes in the same sentence, so the legal entry is written as the single authority for both with an explicit instruction not to mint a second.

The scope clause named only the parameter and legal directories, but the drift gate requires an allowlist entry for any parameter no domain-layer reader consumes. Six entries were added and the reason documented in place: that gate scans only the domain layer, so an application-layer consumer is structurally invisible to it, and every sibling tranche is already listed for the same reason. The entries sit on identical footing before and after the consuming Step lands.

Verification was not a bare green. The citation checks ran through the production validators with a positive control substituting an absent sentinel phrase, and the control failed on all six parameters and on the legal entry -- so the probes are not vacuous. Both limbs were confirmed present in all six bundled manuals, so the served window is uniform.

The registry lane was not clean and the two failures were foreign, named here so a
later reader does not re-triage them. A complexity-baseline breach sits in a
relation-source validator under active peer edit, and a loader fingerprint case
sits in a loader under active peer edit; that second one is scoped entirely to
temporary-directory fixtures which never load the legal or source catalogues, so
this Step's data cannot reach it. Neither was absorbed.
