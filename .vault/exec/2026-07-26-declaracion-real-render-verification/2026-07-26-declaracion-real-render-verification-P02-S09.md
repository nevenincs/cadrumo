---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:8f26b38efb65ea09493954497e9f00586e8a8637ebe58e1b4fcceb3703319cb9'
step_id: 'S09'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Register route R11 for the 19 specimen-less profiles as evidence gaps rather than passes, naming what each would need to become decidable

## Scope

- `.vault/audit`

## Description

- Enumerated every real_corpus and aeat_published_facsimile
  fixture sidecar under the justificante and manual-annex fixture
  trees and read its declared provenance.
- Attributed each specimen year to its owning revision using that
  revision own valid_from / valid_to / period_selector, per
  profile rather than per modelo.
- Built the full register: for each specimen-less profile, named the
  match strategy in use, the extra route blocked beyond the shared
  set (R6 for bbox_anchored profiles, R10 for modelos with a sibling
  revision), and the specimen class that would close the gap.

## Outcome

Measured exactly 7 profiles with a specimen and 22 without, attributed
per profile rather than per modelo. This diverged from the dispatch
brief expected count of 19 and was reported as measured rather than
reconciled to that expectation. The team lead confirmed independently
that 19 was wrong, attributed per modelo, crediting a modelo
specimen to every one of its revisions, and that 22, attributed per
profile, is correct -- a profile is what gets exercised, not a
modelo. The governing ADR declaracion-real-render-verification also
states "twenty-two of twenty-nine profiles have no specimen at all",
but this is not a second source: the ADR adopted that figure from this
Step's own measurement, the same way the team lead adopted it in
place of their own count of 19. Citing it back as corroboration would
manufacture agreement out of one observation.

The sharpest consequence: 100/2024 and 100/2025 carry no specimen
of their own despite Modelo 100 being one of the four modelos with
real-corpus evidence, so two of its five revisions cannot be verified
against a real render yet. This was relayed by the team lead to the
peer verifying P01 as a scope correction.

Every specimen-less profile is recorded as an evidence gap per the
governing ADR D3 ("an untestable profile is an evidence gap, never a
pass"), never as a pass by omission.

Findings and full detail: see the specimen-less static route audit
document for this feature, section
r11-evidence-gap-register-measures-22-specimen-less-profiles-not-19
and its full register table.

## Notes

None beyond the corrected expected-count discussion above, which is
the reason this record exists rather than a quiet reconciliation.
