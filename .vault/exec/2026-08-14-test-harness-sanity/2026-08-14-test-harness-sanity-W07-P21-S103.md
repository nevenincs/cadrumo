---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:3536741002ee8703533d4e0d27a1099e1bd0fed122d4b20381b8c71e62de9487'
step_id: 'S103'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Give the re-export-bridge gate a declared reach over the test tree instead of silent exclusion

## Scope

- `dev/quality/import_hygiene_scan.py`
- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Confirm the scan skipped every test path, and check whether that skip was ever justified.
- Tag each detected module with whether it is test-tree rather than discarding it.
- Split the reported counts so the test-tree population is stated rather than absent.
- Keep the production population and its zero baseline exactly as before.
- Prove the tagging is load-bearing in both directions.

## Outcome

The scan skipped anything under a test path before running any of its checks, with no stated rationale, from the first commit that introduced the file. A neighbouring family in the same module does document why it exempts tests, which makes the silence here look like an oversight rather than a boundary.

Un-blinded, the test tree holds fifteen detected modules where the report previously showed nothing: five genuine consumer bridges, four package-configuration files re-importing fixtures for discovery, and four matches from a naming heuristic that fires on an unrelated substring. The production population is unchanged at zero and its strict baseline still holds.

Whether the five survive is a separate question, deliberately left open. The defect fixed here is the silence: a gate whose reach is narrower than the rule it enforces reports a clean tree it never inspected.

## Notes

The new assertion is a floor rather than a tally, so ordinary churn cannot force an update to a constant, and it checks the tag against the structural definition in both directions so a mis-tag fails either way. Both directions were mutation-proven: forcing every module to look non-test reproduces the original blindness, and forcing a single known bridge to look non-test is caught by the reverse check, which is the targeted-evasion case a one-directional assertion would miss.

The four configuration files were not carved out, even though they are arguably a different concept from a hand-authored consumer bridge. Pre-judging that would have hidden the population again under a different justification.
