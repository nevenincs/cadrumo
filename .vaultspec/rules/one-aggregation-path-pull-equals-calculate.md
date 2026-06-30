---
name: one-aggregation-path-pull-equals-calculate
---

# Pull and calculate share one aggregation path

## Rule

A casilla's value MUST be produced by the same aggregation logic whether reached
via the live `calculate` path or the Sheets-pull path; both surfaces share one
resolver set, and a regression proves they agree for a shared revision.

## Why

Audit `2026-06-10-calculation-engine-foundations-audit` finding F5 found
disconnected-surface drift: the Sheets-pull assemblers and the live calculate path
both persisted to the SAME revision, so a calculate-then-export or
export-then-calculate cycle could yield divergent, conflicting casilla values with
no detection at save time — a correctness hazard distinct from the silent-blank
class. Sharing one resolver set (the relation enrollment the aggregation-taxonomy
ADR mandated) eliminates the two-surface drift risk so the two transports cannot
disagree.

## How

- Good: `RelationPrefillSourceResolver.resolve` delegates to
  `resolve_relations_from_local_store`
  (`src/aeat/application/calculations/_relation_prefill.py:279`), the exact same
  function the Sheets-pull path calls
  (`entrypoints/cli/_config/_google_sync_calc.py:130`), so both transports run one
  resolver.
- Good: parity is enforced by
  `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
  — a regression that the pull path and the calculate path produce identical
  casilla values for a shared revision.
- Bad: a pull-path `assemble_*` helper that computes a casilla one way while the
  live calculate path computes it another — a calculate↔export cycle then drifts
  the persisted revision with no save-time detection.
- Bad: shipping a new aggregation surface on only one of the two transports — the
  parity regression must cover any casilla both paths can persist.
