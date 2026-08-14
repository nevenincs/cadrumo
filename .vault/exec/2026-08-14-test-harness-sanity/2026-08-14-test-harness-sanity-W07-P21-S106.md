---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:6b3d65f91721e1fdae2b6ec5bc005accbe1f8200ff86719d0761d2eaf93e90d1'
step_id: 'S106'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Detect one fixture behaviour living under many names by keying the census on body rather than name

## Scope

- `dev/quality/fixture_census.py`
- `dev/quality/tests/test_fixture_census.py`

## Description

- Add an `AliasedBehaviour` record and index fixtures a second time on `normalized_body_sha256` instead of `effective_name`.
- Expose `aliased_behaviours`, returning every body digest whose group carries more than one distinct effective name, with its names and sites.
- Report the count on the census CLI line beside the existing fixture and factory totals.

## Outcome

Measured over 536 fixtures: **13 behaviours living under more than one name, spanning 68 definitions and 38 distinct names.** The worst cluster is 7 names across 7 definitions, every one a singleton; the next is 6 names across 17 definitions.

The defect this closes is structural rather than an oversight. The census grouped by `effective_name` first, so a renamed twin fell outside its comparison by construction — running it more often could never have surfaced this class. Review could not catch it either: a reviewer would have to already know the other six names to see that a name is not unique. And a grep for any one of those names returns a single site and reads as canonical.

Inverting the key is the entire fix: group by body digest, flag any group holding more than one name.

## Notes

The detector deliberately reports aliasing **without** recommending a merge, because an identical body is not a substitutability test. In that 7-name cluster every owner-global digest differed, and scope and autouse differed too, so a flat merge would have unified behaviour while every test still passed. The remedy is one parameterised home plus consistent naming, which belongs to the following Step.

This record was authored after the row was already checked. A checked row with no execution record makes delivered-as-specified and recorded-but-not-implemented wear the same checkbox, which is the failure the record exists to prevent; the gap is closed here rather than carried forward silently.
