---
tags:
  - '#plan'
  - '#modelo-111-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-111-calc-verify-adr]]"
  - "[[2026-04-27-modelo-111-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---

# `modelo-111-calc-verify` plan

Implementation plan for issue `#318` (Tier-L per-modelo
calc-verify-roundtrip for Modelo 111 across 2024 / 2025 / 2026).
Mirrors the M130 reference implementation under `#321`.

## Proposed Changes

Land the M111 Tier-L bar via:

1. A new 2026 ruleset (`modelo_111_2026.py`) — structural clone of
   2024 / 2025 with year-pinned effective range. (ADR §D1.)
2. Sibling 2024 + 2026 extractor classes — close the post-PR-440
   registry gap. (ADR §D2.)
3. New 2024 + 2026 colocated test files — worked examples + no-drift
   regressions. (ADR §D3 / §D6 / §D7.)
4. Mutation-harness extension for `modelo_111.2026`. (ADR §D5.)
5. New rule-delta manifest at `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`
   with the L1 anchor waiver. (ADR §D9 / §D10.)
6. Coverage table flip in `docs/coverage/modelos.md`. (ADR §D12.)

## Tasks

- **Phase 1 — vault docs (DONE before code)**
  1. Research artefact authored.
  1. ADR authored + reviewed against CLAUDE.md.
  1. This plan authored.

- **Phase 2 — 2026 ruleset + harness extension**
  1. Author `src/aeat/domain/formulas/_rulesets/modelo_111_2026.py` mirroring
     the 2024 module (re-import `_CASILLAS`, `_CITATIONS`, `_FORMULAS`
     from `modelo_111_2025`; declare own `_PARAMETERS` with 2026
     effective range; `ruleset_id = "modelo_111.2026"`).
  1. Register `MODELO_111_2026` in
     `src/aeat/domain/formulas/_rulesets/__init__.py` (import + `ALL_RULESETS`
     + `__all__`).
  1. Extend `test_mutator_kill_rate.py::EXPECTED_COUNTS` with the
     `modelo_111.2026` row (`sub_op=1, percent_rate_param=2`).
  1. Extend `test_percent_rate_mutation.py::_ruleset_cases` with two
     entries (`MODELO_111_2026:09` + `MODELO_111_2026:12`).
  1. Extend `test_operand_swap_mutation.py` with one `pytest.param`
     for `MODELO_111_2026:30` reusing `_modelo_111_fixture`.
  1. Run `uv run pytest src/aeat/domain/formulas/_rulesets/ -k 111` —
     baseline green.
  1. Run `uv run aeat audit rulesets citations` — verify
     `modelo_111.2026` shows `OK` at 100 % coverage.

- **Phase 3 — sibling extractor classes**
  1. Edit `src/aeat/adapters/inbound/declaracion/_extractors/modelo_111_v2025.py`:
     add `Modelo111V2024Extractor` + `Modelo111V2026Extractor`
     subclasses with `template_revision` ClassVar pinned to their
     respective years (revisions `2024.01` and `2026.01`).
  1. Update `__all__` to export all three classes.
  1. Update the module docstring to document the multi-year layout
     stability.
  1. Edit `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`: import the
     two new classes and add them to `_REGISTERED_CLASSES`.
  1. Run `uv run pytest src/aeat/adapters/inbound/declaracion/` — baseline green.

- **Phase 4 — rule-delta manifest**
  1. Create `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` mirroring
     `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md`: statutory grounding
     table + per-year delta table + diff narrative + citation
     completeness + mutation-harness fingerprint + L1 waiver + audit
     trail.
  1. Tag `#reference, #modelo-111-calc-verify`. Wiki-link from research
     + ADR.

- **Phase 5 — colocated 2024 + 2026 test files**
  1. Author `src/aeat/domain/formulas/_rulesets/test_modelo_111_2024.py` —
     mirrors `test_modelo_111_2025.py` with a 2024-distinct fixture +
     `test_2024_no_drift_from_2025` regression + external-anchored
     worked example.
  1. Author `src/aeat/domain/formulas/_rulesets/test_modelo_111_2026.py` —
     mirrors `test_modelo_130_2026.py` shape with a 2026-distinct
     fixture + `test_2026_no_drift_from_2025` regression +
     external-anchored worked example.
  1. Run `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_111_2024.py
     src/aeat/domain/formulas/_rulesets/test_modelo_111_2026.py -v` — all
     green.

- **Phase 6 — coverage table flip**
  1. Edit `docs/coverage/modelos.md`: flip M111 row to ✅ on
     applicable columns + update the `provenance` line citing this
     PR (`Closes #318`).

- **Phase 7 — verification**
  1. `just lint` — green.
  1. `just typecheck` — green.
  1. `just test` — green.
  1. `just hooks` — green.
  1. `uv run aeat audit rulesets citations` — confirm 100 % coverage
     including the new `modelo_111.2026` row.
  1. Run mandatory code review via `vaultspec-code-review` skill.

- **Phase 8 — exec summary + PR**
  1. Author `.vault/exec/2026-04-27-modelo-111-calc-verify/2026-04-27-modelo-111-calc-verify-summary-exec.md`
     with per-year casilla inventory, mutation kill-rate, BOE source
     list, scope decision, sibling-coordination notes.
  1. Push branch and open PR.

## Parallelization

Phases are intentionally sequential because each builds on the
previous (the ruleset must exist before the harness can extend it,
the rule-delta manifest cites the test-file regressions etc.). Within
Phase 5 the two test files can be authored in parallel; within Phase
2 the `__init__.py` registration must follow the new ruleset module's
authoring.

## Verification

### Mission-success criteria

This issue lands when **every** bullet below is true:

1. **2026 ruleset exists + registered**: `MODELO_111_2026` resolves
   via `aeat.domain.formulas._rulesets.ALL_RULESETS`, has
   `effective_from=2026-01-01`, `effective_to=2026-12-31`, and
   identical numerical content to 2024 / 2025.
2. **Sibling extractors registered**: `Modelo111V2024Extractor` and
   `Modelo111V2026Extractor` resolve via
   `aeat.adapters.inbound.declaracion._extractors.get_extractor` for the respective
   `(modelo, año, revision)` tuples.
3. **Citation coverage 100 % including 2026**:
   `uv run aeat audit rulesets citations` reports
   `OK modelo_111.2026 ... coverage=100.00%`.
4. **Mutation kill-rate ≥ 90 % on M111 nodes**: the per-class harness
   fingerprint matches `EXPECTED_COUNTS`; aggregate kill-rate stays
   at 100 % on the populated M111 surface.
5. **Per-year DAG tests green**: `test_modelo_111_2024.py` +
   `test_modelo_111_2025.py` + `test_modelo_111_2026.py` all pass.
6. **Round-trip closes**: the M111 integration test class passes
   (4 cases via `#340`).
7. **L1 waiver documented**: `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`
   carries the explicit waiver section.
8. **Coverage table flipped**: `docs/coverage/modelos.md` M111 row
   shows ✅ on applicable columns with provenance.
9. **Code-review skill clean**: every safety invariant from STEP 2 of
   the handover prompt is satisfied.
10. **`just lint && just typecheck && just test && just hooks`** all
    green; coverage floor 60 % preserved.

### Plan-self-review checklist (CLAUDE.md mandate)

- ✅ All Python modules under `src/aeat/`.
- ✅ Public-API discipline: imports from `aeat.<subpkg>` only.
- ✅ Pydantic v2 strict on any new model (no new models in this
  issue — re-uses existing `Ruleset`, `CasillaDefinition`,
  `LegalCitation` shapes).
- ✅ Errors inherit from `aeat.core.errors.AeatError` (no new errors
  raised by this issue).
- ✅ Logging via `aeat.core.logging.get_logger(__name__)` only (no new
  log surfaces).
- ✅ Tests pytest-only; no mocks / fakes / stubs / freezegun.
- ✅ Pytest markers `[pytest.mark.unit, pytest.mark.domain_local_state]`
  at module level for per-ruleset DAG tests.
- ✅ No live tests touched.
- ✅ Trilingual labels: ES default + EN explicit; HU placeholder
  preserved.
- ✅ Live-AEAT-write surfaces untouched. Live submission
  PERMANENTLY FORBIDDEN.
- ✅ No wave / phase numbering in source code or docstrings.
- ✅ Google-style docstrings + full type hints.
- ✅ `ty` (not mypy) and `prek` (not pre-commit) enforced via `just`.
- ✅ Conventional commits.

### Risk mitigation

- **Risk**: Mutating `EXPECTED_COUNTS` without extending the harness
  → kill-rate test fails loudly.
  **Mitigation**: every harness extension is paired with the new row
  in the same commit; the test fails immediately if the per-class
  test does not cover the new node.
- **Risk**: Sibling soft collisions on three shared files at PR-open
  time. **Mitigation**: documented in the exec summary + PR body for
  manual textual union at merge time; the mechanical nature of the
  unions (different rows / different classes / different ruleset
  imports) means the merge is straightforward.
- **Risk**: BOE consolidated-text retrieval via WebFetch may not
  return the article body. **Mitigation**: the existing `#321`
  research relied on the same BOE consolidated-text URL with the same
  outcome — the citation registry's wave-67a corrections and the
  RIRPF/LIRPF consolidated-text last-update dates are sufficient
  primary-source evidence; the rule-delta manifest documents this
  explicitly.

### What this plan deliberately does NOT do

- It does not migrate M111 to the M130-style year-scoped formula-id
  namespace. (ADR §D1 — preserved as an out-of-scope cohort decision.)
- It does not auto-compute the variable-rate retentions on apartados
  I / II / V / VI. (ADR §D13 — sub-EPIC `#305-Modelo-111-full`
  territory.)
- It does not add an L1 real-PDF anchor. (ADR §D9 — waiver in the
  rule-delta manifest.)
- It does not introduce a dedicated M111 generator. (Research §Synthetic
  generator — the generic-quarterly generator suffices.)
