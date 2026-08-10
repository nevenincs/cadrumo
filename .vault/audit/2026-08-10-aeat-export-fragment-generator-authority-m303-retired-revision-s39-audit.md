---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f3ee395833b9aa88c5497c7dcc070dbb27f7331c4b1ea2059e7e28184525e989'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `Modelo 303 retired-revision S39 closure review`

## Scope

Audited the S39 deletion of Modelo 303 `2023-y-siguientes` across the registry, domain, application, adapter, CLI, fixtures, and locales. The audit checked the no-legacy policy rather than accepting a passing behavior-only suite: a surviving identifier, compatibility bridge, copied selector, or revision-scoped localization duplicate is a failure.

## Findings

### s39-initial-consumer-omissions | medium | full-surface review found residual consumers outside the first migration set

The first independent review found old concrete revision references in application, CLI, registry, and fixture tests and two revision-scoped copies of the shared construct localization. The corrected candidate migrated every named consumer to the law-selected or explicit surviving revision, deleted the duplicate locale leaves through `LocaleManager`, and added each formerly omitted path to the structural scope.

### s39-no-legacy-reentry | low | corrected candidate has no unresolved retired-id or duplicate-selector finding

The complete candidate scan found zero live M303 retired-id hits, zero legacy registry entries, and zero duplicate construct owners. The reviewer independently confirmed the six intended revisions and the disjoint 2024 early and late partitions. The re-review found no unresolved critical, high, or medium issue.

## Recommendations

- Retain `test_m303_retired_revision_cutover.py` as the negative re-entry gate whenever Modelo 303 consumer surfaces or revision-selection behavior changes.
- Route future Modelo 303 consumers through the existing period selector; do not create a convenience revision literal or a second selector implementation.
