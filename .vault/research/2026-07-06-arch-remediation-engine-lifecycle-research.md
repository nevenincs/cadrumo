---
tags:
  - '#research'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-adr]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-aeat-architecture-review-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace arch-remediation-engine-lifecycle with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `arch-remediation-engine-lifecycle` research: `program-track decision research bridge`

This research bridges the accepted engine-lifecycle ADR to the persistence audit
finding and program-track evidence that motivated it. It is a vault lifecycle
record only: it does not change session semantics, engine caching, or storage
runtime behavior.

## Findings

### Decision input

The persistence audit found SQLAlchemy engine identity and bucket-session
identity were separate globals. Tests repeatedly disposed engines to keep cache
state aligned with active-profile switches, showing lifecycle ownership had
leaked to callers.

The accepted ADR chose to bind bucket-routed engine disposal to the
bucket-session lifecycle while keeping creation lazy. It rejected both the
status quo and fresh-engine-per-access churn.

### Accepted constraints

The ADR preserves encryption behavior, session expiry semantics, readiness
codes, explicit database URL routing, and use-time guards. The shared
secure-SQL test harness and ephemeral bucket path are part of the migration
surface because they exercise the lifecycle boundary directly.

### Current closure evidence

The arch-remediation program refresh records every track plan complete; the
engine-lifecycle plan reports 11 of 11 steps closed by `vaultspec-core vault
plan status`. No current ratchet failure is attached to this track.

### Recommendation

Keep this research bridge as the evidence node for the accepted ADR. Future
changes that alter engine/session ownership, expiry, or explicit-URL routing
should supersede or amend the ADR rather than treating this bridge as new
implementation authority.
