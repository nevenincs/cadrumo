---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning and ## Scope

- `src/aeat tests`
- `src/aeat/locales`
- `docs/how-to` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning

## Scope

- `src/aeat tests`
- `src/aeat/locales`
- `docs/how-to`

## Description

- Add `src/aeat/application/tests/test_provisioning.py`: real-behavior tests for the three dependency probes — unreachable Ollama (unavailable + remediation, never raises), Playwright cache absent/present/missing-root, subprocess providers return typed statuses without raising.
- Add a doctor issue-path test to `test_config_capabilities.py`: `aeat config check` exits 2 and surfaces an `llm_vision is on` issue when the capability is opted in but Ollama is unreachable (the green path was covered by S08).
- Confirm the capability/doctor/provisioning locale keys are complete and parity/honesty green (capability CLI keys landed in S06–S08; wizard capability keys landed in S11).
- Deliver the onboarding how-to doc under S14 (`docs/how-to/onboarding.md`), cross-referenced here as the doc portion of this step.

## Outcome

The probe surface and the doctor issue path now carry real-behavior coverage (10 tests, no mocks); locale catalogues are parity- and honesty-clean. The how-to onboarding doc is delivered and conformance-checked under S14. Committed as `c9051fc88` (tests) and `6bf45d03e` (doc).

## Notes

The how-to doc deliverable is shared with S14; it is authored and committed there to keep the docs change atomic. This step's own commit covers the tests + the locale-completeness verification.
