---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step11-exec]]'
---



# `calculation-truth-registry` Code Review

PHASE2-STEP11-001 | HIGH | Borrador tests used a local profile object instead of a registry schema object

`test_modelo_100_summary.py` defined its own profile dataclass and passed it
to `parse_borrador`. Resolved by using `ExtractionProfileDefinition` from the
registry schema in parser tests.

PHASE2-STEP11-002 | MEDIUM | Filing-grade parsing mode did not require a registry profile

`parse_borrador` accepted `extraction_profile=None` and still returned an
observation, which is valid for observed-data parsing but not for coverage
validation. Resolved by adding `BorradorParseMode.REGISTRY_PROFILE`, which
requires a registry extraction profile and fails before parsing when absent.

PHASE2-STEP11-003 | LOW | Names still implied summary/completeness authority

The fixed casilla tuple was removed, but several names still carried the old
summary wording. Resolved by renaming the extractor class to observed-value
terminology and adding `BorradorObservation` as the primary schema name.
The filing-named alias and export were removed; callers now consume
`BorradorObservation` directly.
