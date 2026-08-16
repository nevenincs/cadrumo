---
generated: true
tags:
  - '#index'
  - '#unfalsifiable-test-sweep'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:2761943637cccd9340ee029e5b534a259b4a53bac9edbcff736b964e0dfc4bb7'
related:
  - '[[2026-08-09-unfalsifiable-test-sweep-S01]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-S02]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-S03]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-adr]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-plan]]'
  - '[[2026-08-09-unfalsifiable-test-sweep-reference]]'
---

# `unfalsifiable-test-sweep` feature index

Auto-generated index of all documents tagged with `#unfalsifiable-test-sweep`.

## Documents

### adr

- `2026-08-09-unfalsifiable-test-sweep-adr` - `unfalsifiable-test-sweep` adr: `A corpus scan carries its own floor` | (**status:** `accepted`)

### exec

- `2026-08-09-unfalsifiable-test-sweep-S01` - Floor the dev UTF-8 corpus so a walk returning nothing fails instead of passing silently
- `2026-08-09-unfalsifiable-test-sweep-S02` - Floor the production UTF-8 corpus independently of the ratchet, so draining the backlog cannot remove the only protection
- `2026-08-09-unfalsifiable-test-sweep-S03` - Prove both floors bite by emptying each walker at runtime and confirming the corresponding floor fails

### plan

- `2026-08-09-unfalsifiable-test-sweep-plan` - `unfalsifiable-test-sweep` plan

### reference

- `2026-08-09-unfalsifiable-test-sweep-reference` - `unfalsifiable-test-sweep` reference: `Census of tests that cannot fail`
