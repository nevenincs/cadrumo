---
name: no-dormant-source-resolvers
trigger: always_on
---

# No dormant source resolvers; every binding source is routed or advised

## Rule

Every `ModeloSourceResolver` merged to main MUST be enrolled in the live calculate
mesh (`merge_source_resolutions` in
`src/aeat/application/modelo/_calculation_actions.py`) or deleted; every registry
binding `source` kind MUST be a member of the enrolled-or-explicitly-deferred set
(`_BUCKET_AGGREGATION_OWNED_SOURCES` ∪ `DEFERRED_SOURCE_KINDS`, enforced by
`assert_no_novel_source_kinds`); and `collect_unhandled_source_diagnostics` MUST
run on the live calculate path so an unrouted source surfaces a non-blocking
advisory — never a silent blank.

## Why

Audit `2026-06-10-calculation-engine-foundations-audit` finding F4 found the
safety net built and switched off: `collect_unhandled_source_diagnostics` had no
live-calculate caller, and `_BUCKET_AGGREGATION_OWNED_SOURCES` described the
enrolled set but enforced nothing — a new TOML binding with a novel `source`
compiled and silently resolved to blank, an estimated 50–70 silently-skipped
bindings across 7+ source kinds. A blank produced by a dormant or missing
resolver surfaces zero findings, violating `no-silent-under-declaration`. The
ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §6) made
closing this non-negotiable.

## How

- Good: a resolver is enrolled in the live `merge_source_resolutions((...))`
  tuple (`_calculation_actions.py:633`); `assert_no_novel_source_kinds`
  (`_calculation_actions.py:802`) raises `ModeloAggregationBindingError` at
  calculate time if a binding's `source` is in neither the owned nor the deferred
  set; `collect_unhandled_source_diagnostics` (`_calculation_actions.py:688`)
  appends a non-blocking advisory for any declared-but-unrouted source.
- Good: a not-yet-built source kind is added to `DEFERRED_SOURCE_KINDS` (canonical
  in `application/aggregation/_source_mesh.py`) — explicitly deferred, advisory-
  visible — never added to the `manual_input` allowlist (which would re-silence
  it).
- Bad: merging a fully-implemented `.resolve()` resolver that is exported but
  never enrolled in the mesh tuple — it is dead capacity and its declared registry
  kind blanks silently.
- Bad: landing a new `source` kind in registry TOML without enrolling a resolver
  or registering it deferred — the novel-source gate refuses it loudly, which is
  correct; silencing it via the manual allowlist is the violation.
