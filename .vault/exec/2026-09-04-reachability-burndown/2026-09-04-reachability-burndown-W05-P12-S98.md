---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:fbeb5be93280288455fd48c2532f30e242bfaeb85dd23ed2dc0ec6ee701d664a'
step_id: 'S98'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Rank the whole residue by how well its modules hide it, since a partially-live module argues against a reader noticing the one path that is not reached, and act on the highest-stakes entry: sixteen open findings sit in modules that are at least sixty percent live, led by a custody port facade at ninety-seven percent and the sectoral withholding rate set at ninety, whose professional and statutory neighbours all reach the inference while it alone is consulted by nothing, so a retencion matching two or one percent is classified by whatever general rule applies rather than as a sectoral apartado.

## Scope

- `src/cadrumo/domain/transactions/retencion_parameters.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/domain/transactions/retencion_parameters.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest src/cadrumo/domain/transactions/tests/` 237 passed
- `verify:` the four ledger gates 25 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

Ranking the residue by how well its module hides it turns a flat backlog into an
ordered one. Sixteen open findings sit in modules at least sixty percent live,
and the ranking is the useful part -- it says where a reader is most likely to
be misled, which is not the same as where the largest cluster is.

The ordered list, live fraction first:

* 97% `application.user_profile.custody_ports` -- one port facade
* 95% `application.live.filed_data_capture` -- two producers replaced by defaults
* 93% `application.operator_surface.models`, `application.modelo.operation_definitions`
* 90% `domain.transactions.retencion_parameters` -- the sectoral rate set
* 89% `application.user_profile.cotejo_apply`
* 88% `adapters.persistence.storage.custody.capsule`
* 87% `domain.calculations.registry.handoffs`
* 83% `domain.iva.prorrata` -- annotated in the previous step
* 82% `domain.calculations.registry.censo_modelos`, `application.live.iva_remote_state`
* 77% `core.corpus_manifest.manifest` -- annotated two steps ago
* 75% `adapters.persistence.storage.schema_lineage`
* 74% `domain.calculations.registry.live_parity`
* 73% `application.repair_integrity`
* 60% `application.modelo._review_package_review_only_workspace`

The sectoral withholding set was taken first on stakes rather than rank. Its
professional and statutory siblings and the supported-rate ceiling all reach the
withholding inference; it alone is consulted by nothing, so a retención matching
2 % or 1 % is classified by whatever general rule applies rather than as an
art. 95.4/95.5/95.6.1.º apartado. The docstring now says so.

No gate was added for this shape. Checking it mechanically would mean matching
prose for a marker phrase, which is the brittleness rejected for the
docstring-claim scan; the ranking is a worklist, not a rule.
