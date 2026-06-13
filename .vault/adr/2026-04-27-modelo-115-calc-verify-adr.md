---
tags:
  - '#adr'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
  - "[[2026-04-25-mutation-harness-extension-adr]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-115-calc-verify` ADR — child of EPIC `#316`

## Context

EPIC `#316` is the per-modelo Tier-L calc-verify-roundtrip
umbrella. Issue `#319` is the fourth delegation under that
umbrella, after `#321` (Modelo 130 — landed reference
implementation; PR #440 merged 2026-04-27), `#326` (Modelo 303 —
in flight), and `#322` (Modelo 131 — in flight). The three
foundational chores it depends on are landed on `main`:

- `#338` — mutation harness extension. The M115 surface is
  already covered: `test_operand_swap_mutation._modelo_115_fixture`
  exercises the casilla-06 sub_op chain; `test_percent_rate_mutation`
  ships `(MODELO_115_2024, "03", _f115_fixture())` and
  `(MODELO_115_2025, "03", _f115_fixture())` rows.
- `#339` — mandatory `LegalCitation` enforcement. Per the
  baseline `aeat audit rulesets citations` run, both
  `modelo_115.2024` and `modelo_115.2025` import at 100 %
  citation coverage (2 of 2 computed casillas).
- `#340` — Tier-L CLI integration coverage.
  `TestKentImportsModelo115Declaracion` ships four cases
  (English happy / Spanish happy / partial / discrepancy
  classifier).

The audit referenced in EPIC `#316` (2026-04-22 calc-verify-
roundtrip audit) flagged Modelo 115 as a Tier-L modelo with a
small computed surface (2 casillas) and an extant 2024 + 2025
ruleset pair. Per the M130 reference implementation just landed,
the per-modelo Tier-L bar requires:

1. Per-annum coverage 2024 / 2025 / 2026 (M115 needs a 2026
   ruleset).
2. Rule-delta manifest at
   `.vault/reference/2026-115-rule-delta.md`.
3. Extractor sibling classes for 2024 + 2026 so the registry
   resolves all three years (the M130 ADR §D5 + the post-merge
   PR-440 fix established this pattern).
4. External-anchored worked examples per year.
5. Per-year integration test parametrisation in
   `TestKentImportsModelo115Declaracion`.
6. L1 anchor decision + waiver if no public PDF.
7. Mutation harness rows for the 2026 ruleset.
8. `docs/coverage/modelos.md` row flip.

The research document
(`2026-04-27-modelo-115-calc-verify-research`) confirms three
load-bearing facts:

1. The 2024 → 2025 → 2026 rule delta on RIRPF art. 100 is
   **zero**. The 19 % retention rate on arrendamientos urbanos
   has been fixed since 2016. The BOE consolidated text last
   updated 2026-02-28 carries no modification notice for art. 100;
   none of the 2024 / 2025 / 2026 modificaciones touch the
   article.
2. The existing 2024 + 2025 rulesets already pass `#339`'s
   mandatory-citation validator. No back-fill is required for
   citation coverage.
3. The existing harness coverage (`#338`) already exercises
   M115 2024 + 2025 at `sub_op=1, percent_rate_param=1`. The 2026
   ruleset inherits the same fingerprint.

## Decision

### D1. 2026 ruleset is a structural clone of 2025

Author `src/aeat/domain/formulas/_rulesets/modelo_115_2026.py` as a clone
of the 2024 module's pattern: it imports `_CASILLAS_2025`,
`_CITATIONS_2025`, and `_FORMULAS_2025` from `modelo_115_2025`
and ships its own `_PARAMETERS` table with `effective_from=
2026-01-01` / `effective_to=2026-12-31`. The numerical content of
the `ParameterTable` is identical: `irpf.arrendamientos_rate =
Decimal("0.19")`.

**Why a re-import, not a redeclaration of `_FORMULAS`.** The M130
2026 ruleset declares its own `_FORMULAS` because casilla 04 of
M130 carries a year-scoped formula-id namespace that shows up in
ledger entries. M115 only has two formulas (casillas 03 and 06),
both currently declared in the 2025 module under
`modelo_115.2025.<reason>`. The existing 2024 ruleset already
re-imports `_FORMULAS_2025` rather than redeclaring them with a
`modelo_115.2024.*` namespace — i.e., the M115 module convention
diverges from M130's.

Diverging from the existing M115 convention to introduce
year-scoped formula-ids on 2026 only would create asymmetry in
the 2024 / 2025 / 2026 trail. The rule-delta narrative is "no
change at all" — preserving the project-internal symmetry matters
more than mirroring M130's namespace. **Decision.** Re-import
`_FORMULAS_2025` verbatim. The `formula_id` strings remain
`modelo_115.2025.retenciones` and
`modelo_115.2025.resultado_a_ingresar` even when the formula is
audited against the 2026 ruleset; this is consistent with the
existing 2024 ruleset pattern and is acceptable because the
ledger entry shape is keyed on `casilla_id`, not on
`formula_id`'s year suffix.

Register `MODELO_115_2026` in
`src/aeat/domain/formulas/_rulesets/__init__.py` and add it to
`ALL_RULESETS`.

### D2. Extractor sibling classes for 2024 + 2026

Per the M130 PR-440 post-review fix, the declaración extractor
registry currently keys M115 only on `(modelo="115", año=2025,
revision="2025.01")`. A 2024 or 2026 PDF would resolve via
`detect_template_revision` to `(115, 2024, "2024.01")` or
`(115, 2026, "2026.01")` and fail with
`NoExtractorRegisteredError`.

**Decision.** Add `Modelo115V2024Extractor` and
`Modelo115V2026Extractor` sibling subclasses of
`Modelo115V2025Extractor` (which is already itself a thin
subclass of `GenericDeclaracionExtractor`). Each sibling pins
only the `template_revision` ClassVar; the extraction logic is
inherited verbatim because the form layout is unchanged across
all three years. Register both new classes in
`src/aeat/adapters/inbound/declaracion/_extractors/__init__.py::_REGISTERED_CLASSES`.

> **Correction — 2026-05-21.** The per-modelo `DeclaracionExtractor` ABC,
> `GenericDeclaracionExtractor`, the `_extractors/` class registry, and all
> per-modelo extractor subclasses described in this section were subsequently
> deleted. Declaración extraction is now driven entirely by registry
> `declaracion_pdf` extraction profiles resolved from the `TemplateRevision`
> detected by `detect_template_revision`. The extractor-class mechanism
> described here no longer exists. See ADR
> `2026-05-21-declaracion-extraction-architecture-adr`.

### D3. Rule-delta manifest

Author `.vault/reference/2026-115-rule-delta.md` with the same
section structure as `2026-130-rule-delta.md`:

- Statutory grounding (BOE citation table).
- Per-year numerical state (rate, casilla counts, IVA-exclusion
  flag).
- 2024 → 2025 diff narrative (no amendment).
- 2025 → 2026 diff narrative (no amendment; cite the BOE
  consolidated text last update 2026-02-28 and explicitly note
  RD 253/2025 touches art. 69, not art. 100).
- Mutation-harness fingerprint table.
- L1 public-anchor waiver (see D4).
- Citation completeness table.
- Audit trail.

Tag `#reference, #modelo-115-calc-verify`. Wiki-link to research
+ ADR + plan + 2026-130-rule-delta.

### D4. L1 anchor decision — waiver

**Decision.** No real public Modelo 115 declaración PDF is
hash-pinned under
`tests/fixtures/pdf_corpus/l1_public_anchors/modelo_115/`.

**Rationale.** Same reasoning as M130's waiver. Modelo 115 is
the *lessee's* quarterly autoliquidación of an IRPF retención
private to a specific NIF + quarter; AEAT does not publish any
specimen Modelo 115 declaración as a normative exemplar. The
Manual práctico de IRPF carries worked numerical examples of
art. 100 but those are textual exemplars, not the printed PDF
declaración. The closest available public anchor is the AEAT
Modelo 115 instructions PDF, which has no NIF / quarter / CSV.
The L3 synthetic generator round-trip already covers every
casilla under the project's fixture-tier discipline.

The waiver section in the rule-delta manifest documents the
same two closure triggers as M130: (1) AEAT publishes a
normative specimen, or (2) a contributor obtains explicit
consent for a fully-scrubbed real declaración.

### D5. External-anchored worked example for 2026

Following the M130 ADR §D2 pattern, the 2026 ruleset test ships
**at least one**
`test_external_worked_example_rirpf_art_100_2026` case whose
expected values are derived from the statute (RIRPF art. 100 —
19 % rate) rather than from the ruleset's `ParameterTable`. The
fixture is the distinct scenario described in the research doc:

- Q3 2026 lessee with three landlords: 01=3, 02=24 000,00,
  03=4 560,00 (= 19 % × 24 000), 04=250,00, 05=100,00,
  06=4 710,00 (= 03 + 04 − 05).

A typo in the ruleset's `irpf.arrendamientos_rate` parameter
would fail this test even if the per-year `_provided()` happy
fixture incidentally carries the same back-derived value.

### D6. No-drift assertion

Mirror `test_modelo_130_2026.py::test_2026_no_drift_from_2025`:
audit a single fixture against both the 2025 and 2026 rulesets;
assert the resulting ledger entries are identical. The M115 2026
ruleset is a re-import-clone of 2025, so this assertion holds by
construction; the test exists to prevent silent divergence in
any future amendment.

### D7. Per-year ruleset test marker

The existing M115 ruleset tests use `pytest.mark.unit,
pytest.mark.domain_local_state` (per the project marker
convention documented in M130 ADR §D4). The new 2026 test file
follows the same convention. The issue body's reference to
`pytest.mark.domain_submission` is treated the same way the M130
ADR treats it: per-ruleset tests stay on `domain_local_state`
because formula rulesets ship as data with no AEAT-write
boundary; `domain_submission` is reserved for harness tests that
exercise the aggregate mutation surface across rulesets.

### D8. Per-year integration parametrisation

Mirror M130's `test_per_year_happy_path_verified` parametrised
case (lines 224..256 of the M130 class). Add the same
parametrised case to `TestKentImportsModelo115Declaracion`,
parametrised over `["2024", "2025", "2026"]`. Each parameter
value generates a synthetic PDF with `año=int(ejercicio)` /
`ejercicio=ejercicio` / `template_revision=f"{ejercicio}.01"` and
asserts the CLI verdict resolves to `VERIFIED`. This case is the
direct exercise of the new sibling extractor classes (D2) and
the new 2026 ruleset (D1).

The existing four cases (English happy / Spanish happy /
partial / discrepancy classifier) are preserved verbatim.

### D9. Mutation harness coverage tables

Three harness files require additions per the 2026 ruleset's
structural fingerprint:

- `test_mutator_kill_rate.py::EXPECTED_COUNTS` — add
  `"modelo_115.2026": {sub_op: 1, percent_rate_param: 1, ...}`.
- `test_percent_rate_mutation.py::_ruleset_cases` — add
  `(MODELO_115_2026, "03", _f115_fixture())`.
- `test_operand_swap_mutation.py` — add the 2026 case
  reusing `_modelo_115_fixture` per the wave-75a fixture
  plumbing pattern (M130 2026 follows the same shape).

The fixtures are reused unchanged because the 2026 ruleset is
structurally identical to 2024 / 2025.

### D10. Cent-exact rounding policy

The terminal `RoundFormula(digits=2, ROUND_HALF_UP)` ships in
the `formula(...)` helper — every `FormulaDefinition` is wrapped
in this terminal round at construction time. This is the
project-wide single-rounding invariant; the 2024 + 2025 rulesets
already conform; the 2026 ruleset inherits the same wrapping.

Boundary tests at the 0,01 € detection floor are part of the
mutation harness (`#338` detection floor `|delta| ≥ 0.02 €`).
M115 has no statutory thresholds (no minoración brackets, no
deduction caps), so dedicated threshold-edge cases per RIRPF
art. 100 are not applicable; the existing wave-67g/68 boundary
discipline + the new external-anchored worked example provide
sufficient cent-exact coverage.

### D11. Coverage docs flip

`docs/coverage/modelos.md` row 13 (`| 115 | ... |`) currently
reads:

```
| 115 | ✅ | ✅ (6 casillas) | ✅ (2024 + 2025) | ❌ | ❌ | ⏳ #235 | N/A | partial | ❌ | partial | 🚧 | ✅ (2025 MVP) | ❌ | ❌ |
```

Flip to ✅ on every column this issue completes (per-annum
coverage 2024 / 2025 / 2026, calc-verify, integration-test,
citation-coverage, mutation-coverage). Add a provenance line
citing this PR (`Closes #319`). Coordinate with sibling branches
`#326` (M303) and `#322` (M131) at PR-open time — each branch
flips its own row, textual union resolves cleanly.

### D12. Out of scope

Per STEP 5 of the handover prompt:

- Other Tier-L modelos (`#321` LANDED; `#326`, `#322` in flight;
  `#317`, `#318`, `#320`, `#323`, `#324`, `#325`, `#327` future
  pickups).
- Tier-S (`#328`-`#331`) and Tier-R (`#332`-`#337`).
- Sub-umbrellas `#341` (RENTA M100 deep dive), `#345` (IVA
  complexity hardening).
- Modelo 111 (`#318`), Modelo 180 (`#323`).
- Ceuta / Melilla 60 % overlay (caller-gated; future issue).
- Live-submit forbidden enforcement sweep (`#432`, in flight).
- Any new CLI commands or root-level Typer changes.
- Any modification to `aeat.adapters.persistence.storage` / `aeat.domain.financial` (`#216`
  territory).

## Consequences

### Positive

- Modelo 115 reaches the Tier-L bar on calc-verify-roundtrip
  across 2024 / 2025 / 2026.
- The smallest IRPF Tier-L modelo lands as the second per-modelo
  delegation after the M130 reference, demonstrating the pattern
  scales from the 19-casilla M130 surface to the 6-casilla M115
  surface with mechanical edits.
- Extractor-registry symmetry is restored — every supported
  ejercicio (2024 / 2025 / 2026) resolves to a working extractor
  for both M130 and M115; the asymmetric outcome of issue `#321`
  is closed.
- The rule-delta manifest pattern is reinforced (a per-modelo
  reference file the audit + ADR + plan all wiki-link to).
- The L1 waiver pattern is reinforced for modelos AEAT does not
  publish as normative exemplars.

### Negative / risks

- **Two new sibling extractor classes** widen the
  `_REGISTERED_CLASSES` tuple. Mitigation: each subclass is a
  five-line pin of the `template_revision` ClassVar; no new
  extraction logic. *(Superseded 2026-05-21: the extractor-class
  mechanism was deleted; see correction note in D2.)*
- **Coordinated `_rulesets/__init__.py` edit** soft-collides
  with `#326` (M303 2026) and `#322` (M131 2026) when those
  land. Mitigation: union-merge resolves the soft collision
  because each branch's edit is addition-only on a different
  `MODELO_*` symbol. The PR body lists which siblings landed
  before this one so the reviewer expects the union.
- **`docs/coverage/modelos.md` row flip** also soft-collides
  with the same two siblings. Mitigation: each branch flips its
  own row; line-level union is clean.
- **Test parametrisation count** grows by 1 case (per-year
  parametrised test) and 1 module (`test_modelo_115_2026.py`)
  with ≈ 5 cases. Negligible CI runtime impact.

### Out of scope

See D12 above.

## References

- `2026-04-27-modelo-115-calc-verify-research` — research
  findings.
- `2026-04-27-modelo-130-calc-verify-adr` — sibling ADR for
  the reference implementation; this issue mirrors its
  structure.
- `2026-04-25-mandatory-citations-adr` — `#339` mandatory-
  citation enforcement (consumed here).
- `2026-04-25-mutation-harness-extension-adr` — `#338`
  mutation harness extension (consumed here).
- `2026-04-25-kent-workflows-expansion-adr` — `#340` Tier-L
  CLI integration coverage (extended here).
- `2026-04-27-modelo-130-rule-delta-reference` — sibling rule-delta manifest authored
  under `#321`; `2026-115-rule-delta.md` mirrors its shape.
- EPIC `#316` — per-modelo calc-verify-roundtrip umbrella.
- Issue `#319` — this issue.
- RD 439/2007 art. 100 — `BOE-A-2007-6820` (consolidated text
  last update 2026-02-28).
- LIRPF art. 99 + 101.8 + 68.4 — `BOE-A-2006-20764`.
- Orden EHA/1658/2009 — `BOE-A-2009-10295` (Modelo 115 layout).
