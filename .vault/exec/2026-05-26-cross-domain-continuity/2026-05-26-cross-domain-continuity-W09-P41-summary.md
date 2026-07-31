---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
body_hash: 'sha256:fcce552a42f2818baa16a109e18b456351463839a4bdb52b3fbc8a6a27b66d7c'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W09.P41` summary

- Modified: `src/aeat/application/modelo/_work_plazo.py`, the public modelo facade, CLI payload/rendering projection, four locale catalogues, IVA exemption schema/classification, and prorrata rollup routing.
- Modified: real deadline, CLI, IVA-domain, transaction, aggregation, ledger-binding, and prorrata regression suites.
- Created: execution records for S355 and S444; S343's historical record now carries a dated corrective-execution supplement.

## Description

This corrective slice applies the two accepted legal decisions without claiming a statutory result the application cannot evidence. S343 replaces the former Article 27 pseudo-assessment with an explicit deadline posture and an unassessed conditional rate preview. The preview carries a rate reference date rather than an asserted presentation date; the no-preview path states no recargo or interest liability is determined.

S355 removes the false `ART_20_UNO_26` member and its sole special prorrata-numerator route. The generic `DOMESTIC_EXEMPT` path remains the lawful default. S444 then proves the result through the live rollup: a 300 EUR generic exempt operation increases total and without-deduction volume by 300 EUR while deductible volume is unchanged. It also loads both supported Modelo 303 revision paths and confirms neither exposes casilla 61, a compatibility target, or a casilla-61 binding.

Independent review found and resolved one low fallback-wording issue in S343; S355 and S444 were approved with no findings. Focused verification passed: 42 Article 27/deadline/CLI/locale tests, 115 IVA/prorrata/transaction/ledger-binding tests, and 16 prorrata/registry-proof tests. Targeted Ruff and formatting checks passed for each step.

The full statutory Article 27 assessment remains deliberately deferred until its approved evidence, historical-regime, and interest-input prerequisites exist. This summary does not claim the entire W09.P41 phase or campaign is complete: S351 remains an intentional future contract-tightening item, while the plan retains its separately tracked documentation, external-publication, maintenance, and terminal-checkpoint work.
