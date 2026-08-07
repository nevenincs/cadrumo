# Pull and calculate share one aggregation path

A casilla's value MUST be produced by the same aggregation logic whether reached
via the live `calculate` path or the Sheets-pull path. Both surfaces share one
resolver set, and a regression proves they agree for a shared revision.

The two surfaces both persist to the SAME revision, so a
calculate-then-export or export-then-calculate cycle could yield divergent,
conflicting casilla values with no detection at save time — a correctness hazard
distinct from the silent-blank class.

## How

- **Good:** the relation prefill resolver delegates to
  `resolve_relations_from_local_store` in
  `src/cadrumo/application/calculations/_relation_prefill.py` — the exact
  function the Sheets-pull path calls — so both transports run one resolver.
  Parity is enforced by
  `application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`.
- **Bad:** a pull-path assembler that computes a casilla one way while the live
  calculate path computes it another.
- **Bad:** shipping a new aggregation surface on only one transport; the parity
  regression must cover any casilla both paths can persist.

Source: audit `2026-06-10-calculation-engine-foundations-audit` (F5).
