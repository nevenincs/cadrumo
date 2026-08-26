---
generated: true
tags:
  - '#index'
  - '#first-filer-attestation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:38111146417c9e35bda06b3bd02e6097bef841351bee9397f3d271512736452a'
related:
  - '[[2026-06-12-first-filer-attestation-adr]]'
  - '[[2026-06-12-first-filer-attestation-research]]'
  - '[[2026-06-13-first-filer-attestation-adr]]'
  - '[[2026-06-13-first-filer-attestation-plan]]'
---

# `first-filer-attestation` feature index

Auto-generated index of all documents tagged with `#first-filer-attestation`.

## Documents

### adr

- `2026-06-12-first-filer-attestation-adr` - `first-filer-attestation` adr: `censo-grounded activity-start scoping` | (**status:** `superseded`)
- `2026-06-13-first-filer-attestation-adr` - `first-filer-attestation` adr: `operator-declared activity-start scoping (supersedes G313 grounding)` | (**status:** `accepted`)

### exec

- `2026-06-13-first-filer-attestation-P01-S01` - Add the NO_PRIOR_OBLIGATION_PRE_ACTIVITY provenance facet kind enum to the cross-period clean-state vocabulary while gate-proving it never enters _OFFICIAL_SOURCE_KINDS
- `2026-06-13-first-filer-attestation-P01-S02` - Add the typed NoPriorObligationProvenance model carrying activity_start_date, provenance kind (operator-declared vs censo-corroborated), and optional censo snapshot id
- `2026-06-13-first-filer-attestation-P01-S03` - Add the suppressed no_prior_obligation facet field plus its clean-property treatment to CrossPeriodDependencyEvidence so a scoped-out requirement is explicit and non-silent
- `2026-06-13-first-filer-attestation-P01-S04` - Add the pure period-strictly-before-activity-start predicate over a declared date routed through Period boundary authority, unit-testing that the alta-containing period is NOT before-start
- `2026-06-13-first-filer-attestation-P02-S05` - Apply the activity-start scoping filter to previous_filing-origin requirements in cross_period_dependency_requirements so a period strictly before the declared alta is dropped from the derived graph
- `2026-06-13-first-filer-attestation-P02-S06` - Apply the same activity-start scoping filter to registry-relation-origin requirements so the suppression is uniform across both previous_filing and relation_source_requirements origins
- `2026-06-13-first-filer-attestation-P02-S07` - Stamp each suppressed requirement with the no-prior-obligation provenance facet and resolve its binding value through the existing absent-by-design path to a provenance-marked Decimal zero rather than an unstamped carry
- `2026-06-13-first-filer-attestation-P02-S08` - Thread the declared activity_start_date parameter into evaluate_cross_period_clean_state and cross_period_dependency_requirements without letting callers pass an ad hoc dependency set, preserving registry-derived guard semantics
- `2026-06-13-first-filer-attestation-P03-S09` - Thread workflow_profile.activity_start_date from the verification-action caller into _cross_period_clean_state_verdict_for_work_unit and onward to evaluate_cross_period_clean_state, reusing the exact field the deadline engine consumes
- `2026-06-13-first-filer-attestation-P03-S10` - Emit a non-blocking advisory verification finding when a suppression rests on an operator-declared-but-uncorroborated activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open
- `2026-06-13-first-filer-attestation-P03-S11` - Fail closed with a blocking finding that prompts the operator to record the activity-start date when the profile carries no activity_start_date at all, so the gate never silently opens
- `2026-06-13-first-filer-attestation-P04-S12` - Add a real-storage test proving an empty pre-activity span produces no cross-period blocker (absent-by-design) and verify completes on current-period merits for a genuine first filer
- `2026-06-13-first-filer-attestation-P04-S13` - Add a real-storage test proving the alta-containing period stays in scope as the first obligation and is NOT suppressed
- `2026-06-13-first-filer-attestation-P04-S14` - Add a real-storage test proving the activity-start scoping applies uniformly to both previous_filing and relation_source_requirements origins
- `2026-06-13-first-filer-attestation-P04-S15` - Add an anti-tautology proof that a REAL prior filing post-dating the declared alta still produces a cross-period blocker and still demands official AEAT evidence
- `2026-06-13-first-filer-attestation-P04-S16` - Add a real-storage test proving the gate fails closed when the profile carries no activity_start_date and that the non-blocking advisory surfaces when a declared date scopes a requirement out
- `2026-06-13-first-filer-attestation-P04-S17` - Add a regression asserting no_prior_obligation provenance never enters _OFFICIAL_SOURCE_KINDS and the first local filing still persists under the non-official app_filing source kind

### plan

- `2026-06-13-first-filer-attestation-plan` - `first-filer-attestation` `operator-declared activity-start scoping of cross-period requirements` plan

### research

- `2026-06-12-first-filer-attestation-research` - `first-filer-attestation` research: `first-period filer dead end: censo-grounded vs attested no-prior-obligation`
