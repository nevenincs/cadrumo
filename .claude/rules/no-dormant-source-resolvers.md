---
name: no-dormant-source-resolvers
trigger: always_on
---

# No dormant source resolvers; every binding source is routed or advised

Every `ModeloSourceResolver` merged to main MUST be enrolled in the live
calculate mesh (`merge_source_resolutions` in
`src/cadrumo/application/modelo/_calculation_actions.py`) or deleted. Every
registry binding `source` kind MUST be a member of the enrolled-or-explicitly-
deferred set (`_BUCKET_AGGREGATION_OWNED_SOURCES` union `DEFERRED_SOURCE_KINDS`,
enforced by `assert_no_novel_source_kinds`). And
`collect_unhandled_source_diagnostics` MUST run on the live calculate path, so an
unrouted source surfaces a non-blocking advisory — never a silent blank.

The safety net was once built and switched off: the diagnostic collector had no
live caller and the owned-sources set described the enrolled set while enforcing
nothing, so a new TOML binding with a novel `source` compiled and silently
resolved to blank. A blank produced by a dormant or missing resolver surfaces
zero findings.

## How

- **Good:** a resolver is enrolled in the live mesh tuple; the novel-source gate
  raises at calculate time for a binding whose `source` is in neither set; the
  diagnostic collector appends a non-blocking advisory for any declared-but-
  unrouted source.
- **Good:** a not-yet-built source kind is added to `DEFERRED_SOURCE_KINDS`
  (canonical in `application/aggregation/_source_mesh.py`) — explicitly deferred
  and advisory-visible.
- **Bad:** merging a fully-implemented resolver that is exported but never
  enrolled; it is dead capacity and its registry kind blanks silently.
- **Bad:** landing a new `source` kind without enrolling a resolver or
  registering it deferred, then silencing the resulting refusal via the
  manual-input allowlist.

Source: audit `2026-06-10-calculation-engine-foundations-audit` (F4); ADR
`2026-06-10-calculation-aggregation-taxonomy-adr`. Companion:
`no-silent-under-declaration`.
