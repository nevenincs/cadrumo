---
tags:
  - '#adr'
  - '#modelo-111-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-111-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-111-calc-verify` ADR — child of EPIC `#316` | (**status:** `rejected`)

## Rejection (2026-05-21)

This ADR is **rejected**. Its D13 decision asserts the Modelo 111
ruleset covers "four computed casillas (09, 12, 28, 30) — the two
fixed-rate retentions (premios + arrendamiento ganancias at 19 %)".
That premise is factually wrong against AEAT authority.

Verified against the AEAT Modelo 111 official instructions and the
live registry: casillas `09` and `12` are *retenciones e ingresos a
cuenta sobre rendimientos de actividades económicas* (dinerarios /
en especie) — declarant-reported manual-input totals at variable
rates (15 % profesionales, 7 % new professionals, 2 % agrícolas /
forestales, 1 % estimación objetiva — never a single 19 %). They are
neither premios nor arrendamiento, and they are not a percentage of
casillas `08` / `11`. Modelo 111 is a withholding-*declaration* form:
per-rubro retention amounts are declarant facts, not form-computed.
The only computed M111 casillas are the totals (`28`) and the
resultado (`30`), both already correctly in the registry.

Authoring `09 = 19 % × 08` per this ADR would overwrite correctly
declared inputs with wrong figures. The ADR's D5/D6 sections also
reference the post-PR-440 declaración extractor registry, which the
hexagonal restructure has since deleted. No further action is taken
on this ADR; the registry Modelo 111 is correct as-is. See the
branch-reconciliation audit for the discovery context.

## Context

EPIC `#316` is the per-modelo Tier-L calc-verify-roundtrip umbrella.
Issue `#318` is the M111 delegation under that umbrella, mirroring
the M130 reference implementation under `#321` (LANDED 2026-04-27 via
PR-440). The three foundational chores it depends on (`#338` mutation
harness extension, `#339` mandatory `LegalCitation` enforcement,
`#340` Tier-L CLI integration coverage) are landed on `main`.

The audit referenced in EPIC `#316` (2026-04-22 calc-verify-roundtrip
audit) flagged Modelo 111 as a Tier-L modelo (full per-annum coverage
+ calc-verify + round-trip required). The companion research artefact
(`2026-04-27-modelo-111-calc-verify-research`, wiki-linked from the
`related:` frontmatter) confirms five load-bearing facts:

1. The 2024 → 2025 → 2026 rule delta on the LIRPF arts. 99-101 +
   RIRPF arts. 99-100 retention surface is **zero**. RD 253/2025
   (the only 2025 modification to the RIRPF) touched art. 69, not
   arts. 99-100. The RIRPF consolidated text (last update
   2026-02-28) and the LIRPF consolidated text (last update
   2026-03-21) carry no 2025 / 2026 amendment notice that touches
   the rate-bearing articles.
2. The existing 2024 + 2025 rulesets pass `#339`'s mandatory-citation
   validator (`uv run aeat audit rulesets citations` reports
   `OK modelo_111.2024 ... coverage=100.00%` and
   `OK modelo_111.2025 ... coverage=100.00%`).
3. The wave-67a citation audit corrected the prior premios + the
   prior arrendamientos mappings; both are now in
   `src/aeat/domain/modelos/_citation_registry.py` as `KnownBadCitation`
   blocklist rows.
4. The existing harness coverage exercises M111 2024 + 2025 at
   `sub_op = 1, percent_rate_param = 2`. The 2026 ruleset inherits
   the same fingerprint — single new row per harness table.
5. M111 has the **same post-PR-440 extractor-registry gap** M130 had
   pre-`#321` post-fix: only the 2025 template revision is registered
   in `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`. The 2024 and
   2026 sibling extractor classes need to land in this PR so the
   registry resolves all three years.

The current per-issue gaps are:

- **No 2026 ruleset** registered.
- **No 2026-111 rule-delta manifest** documenting the 2024 → 2025 →
  2026 delta with BOE citations + the L1 waiver.
- **No L1 anchor decision** for Modelo 111.
- **No colocated 2024 ruleset test file** (M130 closed the same gap
  in `#321`).
- **No colocated 2026 ruleset test file** (this issue creates it).
- **Sibling 2024 + 2026 extractor classes** not registered — the
  registry rejects 2024 / 2026 PDFs.

## Problem Statement

Land Modelo 111 against the Tier-L calc-verify-roundtrip bar across
2024 / 2025 / 2026 without disturbing the existing M111 surface (the
2024 + 2025 rulesets are clean and citation-complete) and without
duplicating ruleset data (the formula-id namespace is shared across
M111 years by deliberate design — distinct from M130's year-scoped
formula-ids).

## Considerations

- **Statutory delta is zero**: 19 % rates on premios + arrendamiento
  ganancias are unchanged 2024 → 2025 → 2026. Structural-clone
  pattern from M130 reference applies.
- **Existing M111 namespace pattern**: 2024 ruleset re-imports
  `_FORMULAS` from 2025 with `modelo_111.2025.<reason>` formula-ids
  (no year-scoping). M130 diverges (year-scoped per ruleset).
- **Extractor registry gap** identical to the post-PR-440 fix on
  M130 — must close in this PR.
- **Integration test class** at `TestKentImportsModelo111Declaracion`
  is already at the Tier-L bar (4 cases via `#340`). No extension.
- **L1 anchor**: M111 is an autoliquidación tied to a specific NIF;
  AEAT does not publish specimen M111 declaraciones. Waiver
  required, mirroring M130.
- **Soft collisions** with three sibling Tier-L branches in flight on
  three shared files (`tests/integration/test_kent_workflows.py`,
  `docs/coverage/modelos.md`, `src/aeat/domain/formulas/_rulesets/__init__.py`).

## Constraints

- Test discipline: `[pytest.mark.unit, pytest.mark.domain_local_state]`
  for per-ruleset DAG tests; `[pytest.mark.unit,
  pytest.mark.domain_submission]` for aggregate mutation harness.
  No mocks / fakes / stubs / freezegun.
- No wave/phase numbering in source code or docstrings.
- No live-AEAT-write surfaces. Live submission PERMANENTLY FORBIDDEN.
- Pydantic v2 strict for any new model.
- Coverage floor 60 % preserved; lint / typecheck / test / hooks
  green before each commit.

## Decision

### D1. 2026 ruleset is a structural clone of 2024 / 2025

Author `src/aeat/domain/formulas/_rulesets/modelo_111_2026.py` as a clone of
the 2024 module: it imports `_CASILLAS`, `_CITATIONS`, `_FORMULAS`
from `modelo_111_2025` (the canonical year), declares its own
`ParameterTable` with `effective_from=2026-01-01` /
`effective_to=2026-12-31`, and pins its own `ruleset_id =
modelo_111.2026`.

The numerical content of the `ParameterTable` is identical to 2024 /
2025: `irpf.premios_rate = 0.19`,
`irpf.ganancias_arrendamiento_rate = 0.19`. This mirrors the existing
2024 → 2025 clone pattern.

**Formula-id namespace**: keep the existing M111 pattern (re-import
`_FORMULAS` from `modelo_111_2025`, formula-ids stay
`modelo_111.2025.<reason>`). Diverging to year-scoped formula-ids
would break ledger-key continuity with the existing audit history;
the M130 year-scoped pattern is documented as a deliberate per-modelo
divergence, not drift. A future cohort sweep can align them; not in
scope here.

Register `MODELO_111_2026` in `src/aeat/domain/formulas/_rulesets/__init__.py`
and add it to `ALL_RULESETS`.

### D2. Sibling 2024 + 2026 extractor classes — post-PR-440 fix

Author two thin subclasses inside
`src/aeat/adapters/inbound/declaracion/_extractors/modelo_111_v2025.py`:

- `Modelo111V2024Extractor(Modelo111V2025Extractor)` —
  `template_revision = ("111", 2024, "2024.01")`.
- `Modelo111V2026Extractor(Modelo111V2025Extractor)` —
  `template_revision = ("111", 2026, "2026.01")`.

Both inherit `Modelo111V2025Extractor.casilla_ids` verbatim — the M111
form layout is unchanged across 2024 → 2025 → 2026 (Orden
HAP/2194/2013 is the latest M111 form-layout amendment; no 2025 /
2026 BOE amendment to the M111 form layout has been published).

Register both classes in `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`
(import + `_REGISTERED_CLASSES` tuple).

This is the **direct lesson from PR-440 review**: the M130 reference
shipped only the 2025 extractor class initially and the post-merge
review surfaced that 2024 / 2026 PDFs were rejected by the registry
(`NoExtractorRegisteredError`). M111 has the identical shape and we
land the fix in the same PR.

### D3. External-anchor strategy — mirror the 2025 worked example

The existing
`test_modelo_111_2025.py::test_external_worked_example_rirpf_99` ships
an external-anchored worked example whose rates come from the LIRPF /
RIRPF statute — not from the ruleset's `ParameterTable`. We mirror
this pattern in the new 2024 + 2026 test files:

- **2024 worked example** — same shape as 2025 with a distinct
  numerical scenario (different premios + arrendamiento bases) to
  avoid mirror-fixture coupling.
- **2026 worked example** — distinct numerical scenario from both
  2024 and 2025 (Q3 2026 retenedor with both rate buckets +
  non-zero complementaria deduction on casilla 29 so the
  resultado-a-ingresar arithmetic exercises the full DAG).

The 2026 file additionally ships a `test_2026_no_drift_from_2025`
regression mirroring the M130 pattern. The 2024 file ships a
`test_2024_no_drift_from_2025` symmetric regression.

### D4. Per-year ruleset test marker

The existing `test_modelo_111_2025.py` uses
`pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]`.
The new 2024 + 2026 test files inherit the same marker pair. The
issue body's instruction (`pytest.mark.domain_submission`) targets
the *aggregate* mutation-surface harness tests; per-ruleset DAG tests
use `domain_local_state`. This split is enforced across the rulesets
directory and matches the M130 reference (`#321` ADR §D4).

### D5. Mutation-harness extension

Three harness files require a single new row each per the 2026
ruleset's structural fingerprint:

- `test_mutator_kill_rate.py::EXPECTED_COUNTS` — add
  `"modelo_111.2026": {sub_op: 1, percent_rate_literal: 0,
   percent_rate_param: 2, percent_rate_compound_skipped: 0,
   percent_rate_casilla_ref_skipped: 0,
   brackets_threshold_non_terminal: 0, mul_div_scalar: 0}`.
- `test_percent_rate_mutation.py::_ruleset_cases` — add
  `(MODELO_111_2026, "09", _f111_premios_fixture())` and
  `(MODELO_111_2026, "12", _f111_arrendamiento_fixture())`.
- `test_operand_swap_mutation.py` — add one `pytest.param` for
  `MODELO_111_2026:30` reusing `_modelo_111_fixture`.

Fixtures are reused unchanged because the 2026 ruleset is structurally
identical to 2024 / 2025.

### D6. 2024 colocated test file — close the M130-equivalent gap

Author `src/aeat/domain/formulas/_rulesets/test_modelo_111_2024.py` mirroring
the 2025 file's structure with a 2024-distinct fixture (different
basal amounts to avoid mirror-fixture coupling against 2025). Tests:
happy path + external-anchored worked example + 2024-vs-2025 no-drift
regression + premios-typical + zero-boundary + premios-typo +
ruleset-id-and-effective-range.

### D7. 2026 colocated test file

Author `src/aeat/domain/formulas/_rulesets/test_modelo_111_2026.py` mirroring
the M130 2026 reference (`test_modelo_130_2026.py`): happy path +
2026-vs-2025 no-drift + external-anchored worked example +
premios-typical + zero-boundary + premios-typo + ruleset-id-and-
effective-range.

### D8. Round-trip strategy

Per the engine's `audit_against` contract, a verification pass returns
`VERIFIED` when every `computed=True` casilla supplied to `provided`
matches the engine's re-derivation within `0.01 €` and no
discrepancies surface. The synthetic-generator → extractor →
`verify_declaracion(filing, ruleset)` round-trip closes when the
generic-quarterly generator emits a clean PDF, the extractor returns
`ExtractionStatus.COMPLETE`, and the verification returns `VERIFIED`.
The integration tests in `TestKentImportsModelo111Declaracion`
exercise this path.

### D9. L1 public-anchor waiver

M111 is the autónomo's quarterly *autoliquidación* of retenciones
practicadas a perceptores. Every real M111 filing is a private
autoliquidación tied to a specific NIF + quarter. AEAT does not
publish any specimen M111 declaración as a normative exemplar.

**Decision**: file an explicit waiver in
`.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` mirroring the M130 waiver.
The Tier-L bar is met via the L3 synthetic generator + extractor
round-trip + the integration test class. The waiver expires on either
of (a) AEAT publishing a normative specimen M111 (no precedent), or
(b) a contributor obtaining explicit consent from a real retenedor
to contribute a fully-scrubbed M111 declaración as an L1 anchor under
the project's privacy + scrubbing discipline.

### D10. Rule-delta manifest

Author `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md` with the structure
established by `2026-04-27-modelo-130-rule-delta-reference.md`: statutory grounding table +
per-year delta table + diff narrative + citation completeness +
mutation-harness fingerprint + L1 waiver + audit trail.

Tag `#reference, #modelo-111-calc-verify`. Wiki-link from the
research + ADR + plan documents.

### D11. Cent-exact rounding policy

The terminal `RoundFormula(digits=2, ROUND_HALF_UP)` ships in the
`formula(...)` helper — every `FormulaDefinition` is wrapped in this
terminal round at construction time. The 2026 ruleset inherits the
same wrapping by construction. Boundary tests at the 0.01 € detection
floor are part of the mutation harness (`#338` floor is `|delta| ≥
0.02 €`).

### D12. Coverage docs flip

Flip the M111 row in `docs/coverage/modelos.md` to ✅ on the columns
this issue completes (per-annum coverage 2024 / 2025 / 2026,
calc-verify, integration-test, citation-coverage, mutation-coverage).
Add a provenance line citing this PR (`Closes #318`) and noting the
sibling concurrent branches.

### D13. Scope decision — keep the existing M111 surface

The current M111 ruleset covers four computed casillas (09, 12, 28,
30) — the two fixed-rate retentions (premios + arrendamiento
ganancias at 19 %) plus the sum + resultado. The variable-rate
retentions (trabajo + actividades económicas + retribuciones en
especie + cesión de imagen) are user-supplied on casillas 03, 06, 15,
18 because their rates depend on tabla inputs + categoría-profesional
mapping (out of scope for the formula DSL — sub-EPIC
`#305-Modelo-111-full`).

**Decision in this issue**: do **not** extend the M111 ruleset to
auto-compute the variable-rate retentions. The Tier-L bar is met by
the existing 4-computed-casillas surface; the formula DAG covers
exactly the formula-DAG-derivable surface. The PR body documents this
scope boundary so a future per-perceptor issue lands cleanly.

## Implementation

Phased commit sequence (each commit independently green via
`just lint && just typecheck && just test && just hooks`):

1. `feat(rulesets): add modelo 111 2026 ruleset (BOE primary-sourced
   retention rates) (#318)` — author 2026 ruleset + register.
2. `feat(declaracion): register modelo 111 2024 + 2026 sibling
   extractors (#318)` — sibling extractor classes + registry.
3. `docs(reference): add 2026-111 rule-delta manifest (#318)` —
   manifest + L1 waiver.
4. `test(formulas): per-year worked examples for modelo 111 (#318)` —
   colocated 2024 + 2026 test files; harness extensions for 2026.
5. `docs(coverage): modelos.md flip modelo 111 to verified (#318)` —
   coverage table flip + provenance line.

## Rationale

This decision mirrors the M130 reference implementation under `#321`
section-by-section, with two deliberate per-modelo divergences:

- **Formula-id namespace** (D1) — keep M111's existing shared-formula-id
  pattern instead of M130's year-scoped pattern. Migrating M111 to
  year-scoped IDs is a separate cohort decision that can ride
  elsewhere.
- **Synthetic generator path** — M111 uses the
  `_generic_quarterly_generator` (no per-modelo generator file)
  because the 21-casilla flat layout fits the generic shape. M130
  ships a bespoke generator because of its two-apartado split.

Both divergences are documented in the rule-delta manifest as
deliberate per-modelo style choices, not drift.

## Consequences

### Positive

- M111 reaches the Tier-L bar on calc-verify-roundtrip across
  2024 / 2025 / 2026.
- The post-PR-440 extractor-registry gap is closed in the same PR.
- The 2024 colocated test file closes the same gap M130 closed.
- Mutation kill-rate stays at 100 % on the populated M111 surface.
- `aeat audit rulesets citations` reports `OK` on the new 2026 row.

### Negative / risks

- M111 formula-id namespace divergence from M130 is preserved (D1 +
  Rationale). Future cohort sweep can align them.
- Soft collisions with three sibling per-modelo Tier-L branches in
  flight on three shared files. Mitigation: documented for PR-open
  coordination; textual union at merge-time is mechanical.

### Out of scope

- Other Tier-L modelos (#317, #319, #320, #322, #323, #324, #325,
  #326, #327).
- Tier-S (#328-#331) and Tier-R (#332-#337).
- Sub-umbrellas #341 (RENTA M100), #345 (IVA complexity).
- Per-perceptor M111 retention table (sub-EPIC `#305-Modelo-111-full`).
- Modelo 190 (informative annual summary of M111 retentions).
- Live-submit forbidden enforcement sweep (`#432`, in flight).
- Storage / financial-input territory (`#216`, in flight).
- Any new CLI commands or root-level Typer changes.

## References

Wiki-linked vault docs: see the `related:` frontmatter for the
research, the M130 reference ADR, and the M130 rule-delta manifest.

External references:

- EPIC `#316` — per-modelo calc-verify-roundtrip umbrella.
- Issue `#318` — this issue.
- Issue `#321` — M130 reference implementation (LANDED).
- LIRPF (Ley 35/2006) arts. 99, 101.2, 101.7 — `BOE-A-2006-20764`.
- RIRPF (RD 439/2007) arts. 99, 100 — `BOE-A-2007-6820`.
- Orden HAP/2194/2013 (M111 form layout) — `BOE-A-2013-12489`.
