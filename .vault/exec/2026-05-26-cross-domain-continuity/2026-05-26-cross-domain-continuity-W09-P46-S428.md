---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
body_hash: 'sha256:6123c101cb71d5be976a1ff929b4a3395bcfd28192c87ad7dbfd87333e99a8de'
step_id: 'S428'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Add typed period classification and ordinal projections, then route M130 quarterly projection, declaration-period binding resolution, and workflow quarter detection through them instead of raw token maps or string shape checks

## Scope

- `src/aeat/core/ src/aeat/application/modelo/ src/aeat/**/tests/`

## Description

- Ground the work with `vaultspec-rag`, then read the core `Period` owner, Modelo projection, declaration-period binding resolution, workflow gate, and their focused tests.
- Add typed `Period` projections for ordinary-quarter classification, quarter ordinal, and informational declaration-period ordinal.
- Preserve the established declaration ordinal vocabulary: standard quarters, months, annual `0A`, and instalments `1P` through `3P`; leave extended, event, ad-hoc, and `4P` tokens without a declaration ordinal.
- Route Modelo 130 projection selection, ordering, and output tokens through typed `Period` values and `quarter_ordinal` rather than a local token set or first-character ordinal parsing.
- Route declaration binding resolution through `Period.declaration_period_ordinal` and workflow deadline lookup through `Period.is_quarterly`.
- Add real typed-period, bundled-registry declaration resolution, workflow non-quarter, and end-to-end CLI projection coverage.

## Outcome

Ordinary quarterly semantics now have one typed core authority. The Modelo 130 projection cannot treat an extended token that merely looks quarter-shaped as a quarter, declaration metadata retains its previous supported ordinals, and workflow lookup only consults a quarterly deadline shape for an ordinary quarter. No fake, mock, stub, patch, or monkeypatch was used.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/_period.py src/aeat/application/modelo/_projection.py src/aeat/application/modelo/_binding_resolution.py src/aeat/application/modelo/_workflow_gate.py src/aeat/core/tests/test_period.py src/aeat/application/modelo/tests/test_semantic_role_resolution.py src/aeat/application/modelo/tests/test_actions.py`
- `uv run --no-sync pytest src/aeat/core/tests/test_period.py src/aeat/application/modelo/tests/test_semantic_role_resolution.py src/aeat/application/modelo/tests/test_actions.py::test_workflow_period_resolves_quarter_from_registry_deadline_shape src/aeat/application/modelo/tests/test_actions.py::test_workflow_period_does_not_reinterpret_nonquarter_periods -q` — 52 passed.
- `uv run --no-sync pytest -o "addopts=-n auto --dist=loadfile --tb=short -m integration --strict-markers" src/aeat/entrypoints/cli/tests/test_modelo_projection.py -q` — 5 passed.
- Independent review approved the core classification/ordinal contract, all three consumer migrations, the non-quarter safeguards, and the real-behavior test coverage.

## Notes

The broader `test_actions.py` invocation has one unrelated existing failure: `test_registry_snapshot_unresolved_finding_is_localised` does not pass the now-required `invoice_repository` argument to `_collect_revision_verification_findings`; the other 84 selected tests passed. `vault check annotations --feature cross-domain-continuity` has one pre-existing warning for the plan's remaining HTML template comment. The plan checkbox is intentionally unchanged pending independent review.
