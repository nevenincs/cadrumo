---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:537531e70b2e87420985bfd7dbd69cf010616434737a9a218289430eddfaa320'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# `justfile-design` audit: `W04 documentation and domain recipe review`

## Scope

Audited the W04 justfile surface against the approved command taxonomy, the live
documentation/locale/TUI/release/database CLIs, and the declared mutation boundaries.
The review covered the final canonical recipe bodies and dry-run expansions; no
outward mutation, database upgrade, resident process, generator, or publication was
executed.

## Findings

### locale-value-quoting | low | Locale values must remain one CLI argument

The initial locale mutation recipe interpolated translated values without shell
quoting, which split values containing spaces before they reached the owning CLI.
The final recipe uses Just's shell-quoting function and its dry-run expansion preserves
the complete value as one argument. No open review issue remains.

### database-tooling-precondition | high | Pre-existing migration capability gap

The existing `dev-db-migrate` and `dev-db-upgrade` recipes already target Alembic,
but this checkout has no Alembic dependency, configuration, or migration tree. W04
adds the required semantic names with the same owning command and does not execute a
database mutation. The capability gap predates this change and remains a prerequisite
for exercising either recipe; no database upgrade was attempted during verification.

## Recommendations

Keep the explicit W04 recipe bodies as the canonical operator surface while the
displaced names remain only for the scheduled caller migration and retirement. Before
any operator uses the database recipes, provide and verify the repository's approved
isolated migration environment; W04 does not invent one.
