---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step16-exec]]'
---


# `calculation-truth-registry` Code Review

PHASE2-STEP16-001 | HIGH | Declaration calculation still fabricated taxpayer identity

Resolved. Declaration calculation now refuses an active profile without `tax.id`
instead of creating a placeholder tax ID and persisting it into a draft.

PHASE2-STEP16-002 | MEDIUM | Required export header value was not editable through profile commands

Resolved. The profile-key registry now exposes `surnames`, matching the
registry export-layout header key required by current supported layouts. The
declaration export path still forwards only explicit active-profile values.

PHASE2-STEP16-003 | LOW | CLI calculation test selected only the currently calculable modelo

Resolved. The CLI surface now also covers two negative behaviours: missing
profile `tax.id` is rejected, and a registry modelo requiring additional source
inputs fails at the calculation boundary.

PHASE2-STEP16-004 | LOW | Duplicate Spanish locale blocks remain outside this focused change

Open. The Spanish locale file contains duplicate declaration sections from the
existing locale surface. The new declaration error key was added where the
active lookup can resolve it, but full locale deduplication remains a separate
locale normalization task to avoid colliding with concurrent locale work.
