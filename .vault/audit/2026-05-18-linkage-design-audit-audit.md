---
tags:
  - '#audit'
  - '#linkage-design-audit'
date: '2026-05-18'
related:
  - "[[2026-05-15-linkage-design-audit-research]]"
  - "[[2026-05-15-linkage-design-audit-reference]]"
  - "[[2026-05-18-linkage-design-audit-plan]]"
  - "[[2026-05-15-linkage-design-audit-audit]]"
  - "[[2026-05-16-linkage-design-audit-audit]]"
  - "[[2026-05-17-linkage-design-audit-audit]]"
---

# `linkage-design-audit` audit: `Wave 4 close-out`

## Scope

Final close-out audit for the linkage-design epic. Covers the
operator-surface, identity-propagation, schema-attached
classification, and registry-data-backfill work delivered in the
fourth and final execution wave, plus the cumulative outcome
across all four waves measured against the 102-row inventory.

## Findings

### Severity: informational — epic-level closure

- 98 of 102 inventory rows closed (96%). Five rows are recorded as
  deliberate non-fixes with rationale; four rows are tracked as
  follow-up work in the research record and do not block local
  use of the application.
- Defect-class coverage now spans T-01 through T-12. The canonical
  cross-boundary value envelope (`CasillaObservation`), the typed
  selector union (`BindingSelector`), the per-snapshot referential
  integrity gate (`_check_all_id_references`), the
  capability-driven modelo gates, the typed CLI payload contracts
  (`_modelo_payloads.py`), and the identity-propagation chain
  through filing drafts, justificantes, and attachments are all
  delivered.
- The mechanical-check posture has flipped from `0 / N` (agents
  only) to a maintainable steady state: `ty` clean; `pyright`
  configured per-package; `import-linter` contracts wired (two
  kept, two broken contracts documented as architectural debt);
  `semgrep` regression rules cover the canonical Mapping-based
  cross-boundary anti-pattern.

### Severity: medium — gate status snapshot

Running the unified linkage-health dashboard at close-out:

- ty: PASS (0 errors, 0 warnings).
- pyright `src/aeat/domain`: 32 errors, 97 warnings — driven by
  `reportPrivateUsage` (41), `reportUnnecessaryIsInstance` (33),
  `reportMissingParameterType` (23), `reportUnusedFunction` (15).
- pyright `src/aeat/application`: 146 errors, 97 warnings — driven
  by `reportMissingParameterType` (130), `reportPrivateUsage`
  (73), `reportArgumentType` (15), `reportUnusedFunction` (14).
- import-linter: 2 contracts kept, 2 contracts broken (the
  `layered` and `domain-not-application` legacy contracts) —
  recorded as inherited debt, not new regression.
- suppression inventory: 175 total ty:ignores. 99 are external-API
  shim suppressions (pydantic generics, click decorators); 76 are
  internal. The internal count is the actionable follow-up surface.
- pydantic-duplicate audit: 813 BaseModel subclasses; 4 name
  duplicates; 86 field duplicates across modules; 272 high-
  similarity pairs. The similarity heuristic is intentionally
  noisy — the actionable surface is the name-duplicate set.

The dashboard is now the canonical successor to the agent-driven
discovery phase. Pyright errors are the next actionable surface
once the canonical structural work is locked in.

### Severity: low — deferred items

Four inventory rows remain open and are explicitly tracked as
follow-up:

- Two import-linter contracts (`domain.deadlines._profiles` and
  `domain.profile._keys` lazy imports) need a deeper refactor that
  was out of scope for the typed-envelope and capability-flag
  work.
- One extra-forbid gap on a single legacy pydantic model is left
  as-is because its sole caller is a registry-internal builder
  that already constrains keys upstream.
- One row is owned by the corpus-registry packaging plan
  (separate execution stream).

Five rows are recorded as wontfix-document with rationale captured
inline in the research record.

## Recommendations

- Treat the linkage-health dashboard as the standing health check.
  Re-run it at the start of any subsequent epic to confirm no new
  regressions have crept in. Track the 76 internal ty:ignore count
  and the per-package pyright error counts as steady-state metrics.
- Open a dedicated refactor for the two broken import-linter
  contracts. The contracts are wired and visible; the underlying
  cross-package lazy imports can now be unwound without losing
  audit signal.
- Begin treating `pyright src/aeat/domain` as a required gate
  after the per-package strict mode is locked in. The 32-error
  count is small enough to drive to zero in a focused phase
  without epic-level coordination.
- Sunset the agent-driven discovery cadence for the linkage
  defect classes. The mechanical checks are sufficient; further
  agent passes against the same surface return diminishing value.
- Keep the `scratch/` tooling on disk. The dashboard, suppression
  inventory, and pydantic-audit scripts are durable enough to
  outlive the current epic and form the bedrock of the next
  structural campaign.
