---
tags:
  - '#plan'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_hash: 'sha256:89fe422060b737a74a62006ccae2a9a13eafac4f8135fee69536e1ee7469daed'
tier: L1
related:
  - '[[2026-08-09-unfalsifiable-test-sweep-reference]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-adr]]'
---
# `unfalsifiable-test-sweep` plan

## Description

## Steps

- [x] `S01` - Floor the dev UTF-8 corpus so a walk returning nothing fails instead of passing silently; `src/cadrumo/tests/test_utf8_enrollment_inventory.py`.
- [x] `S02` - Floor the production UTF-8 corpus independently of the ratchet, so draining the backlog cannot remove the only protection; `src/cadrumo/tests/test_utf8_enrollment_inventory.py`.
- [x] `S03` - Prove both floors bite by emptying each walker at runtime and confirming the corresponding floor fails; `src/cadrumo/tests/test_utf8_enrollment_inventory.py`.

## Parallelization

## Verification
