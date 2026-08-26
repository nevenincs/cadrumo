---
tags:
  - '#audit'
  - '#registry-m200-export-fragments'
date: '2026-06-02'
modified: '2026-08-26'
body_hash: 'sha256:7dfd318e8412dd0a6874e6f5fd18119c5cec4a766fa1fb41ac6c3c5e5d58b539'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
  - "[[2026-06-02-registry-hardening-m200-export-pressure-audit]]"
---

# `registry-m200-export-fragments` Code Review

## M200EXP-001 | PASS | Residual pressure split uses generic merge semantics

The split repeats the existing directory-mode export fragment pattern: first
fragments retain full layout and record metadata, and second fragments repeat
only the layout id and record id before appending field tables. No loader,
schema, or M200-specific behavior was added.

## M200EXP-002 | PASS | Field sequence preservation was independently checked

The original committed field id order from `HEAD` was compared with the
concatenated `.part-001.toml` and `.part-002.toml` field ids for all ten split
records. The corrected field-header-scoped parity check preserved every field
id and order.

## M200EXP-003 | PASS | Reviewability pressure is materially reduced

The largest M200 export file dropped from the residual pressure band to 885
lines, with no M200 export rows above 600 characters. Focused reviewability,
directory-mode merge, and committed-registry tests passed.

## M200EXP-004 | LOW | Initial splitter regex was repaired before staging

The first mechanical splitter used an over-escaped matcher and produced
imbalanced parts. The line-count output exposed the issue before tests or
staging, and the generated second parts still contained the original field run,
allowing deterministic repair. No follow-up action remains.
