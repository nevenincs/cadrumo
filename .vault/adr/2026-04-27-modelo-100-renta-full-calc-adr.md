---
tags:
  - '#adr'
  - '#modelo-100-renta-full-calc'
date: '2026-04-27'
modified: '2026-06-13'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-04-21-modelo-100-renta-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-123-calc-verify-adr]]"
---



# `modelo-100-renta-full-calc` adr: full-form RENTA universe across 2024/2025/2026 | (**status:** `accepted`)

## Problem Statement

Issue `#317` (Tier-L per-modelo entry), `#341` (RENTA hardening
umbrella), `#342` / `#343` / `#344` (per-año hardening children) require
calc-verify-roundtrip coverage of the full Modelo 100 RENTA universe
across tax years 2024, 2025, 2026. The user's 2026-04-27 directive
expanded scope from the original "summary block (27 casillas)" framing
of `#317` to **comprehensive Spanish IRPF regulation codification**:
nine anexos (A through Ñ), three estimación régimenes for actividades
económicas, fifteen autonomous communities + Ceuta/Melilla, three tax
years. Estimated surface: ~1000+ deduction rules, ~500+ formula nodes.

The repository already carries a 27-casilla summary-block ruleset
(`modelo_100.summary.2025`) that landed via the 2026-04-21 prior
triplet. The summary ruleset's docstring explicitly reserves the
**default variant slot** (`modelo_100.<año>`) for the full-form
expansion this ADR scopes. M100 is also unique among Tier-L modelos in
dispatching via `aeat filing import --from-borrador` rather than
`--from-declaracion`. Both facts shape the architecture.

This ADR makes the architectural commitments needed to land the
megaproject across the implementation waves the plan will define.

## Considerations

The five sibling Tier-L per-modelo implementations (M111, M115, M123,
M130, M131, M303) establish a uniform pattern: one ruleset file per
year, casillas + formulas + parameters + citations as module-level
tuples, ID grammar `modelo_<code>.<año>`, year-scoped formula IDs,
shared `_CITATIONS` tuple referenced by every computed casilla. M100
exceeds that pattern's natural single-file scale by 5-10×. Naïvely
mirroring the sibling shape would produce 2000-4000 LOC per per-año
file, friction-loading review and rebase hygiene.

The formula DSL (`AddFormula`, `SubFormula`, `MulFormula`, `DivFormula`,
`MinFormula`, `MaxFormula`, `ClampPositiveFormula`, `PercentFormula`,
`BracketsFormula`, `RoundFormula`) does not support conditionals
(if-then-else). This shapes the per-CCAA encoding strategy: per-CCAA
deduction rules with heterogeneous eligibility cannot be expressed as
"if ccaa == X then formula_a else formula_b". Two viable workarounds:
per-CCAA distinct casilla IDs that the caller selectively populates, OR
per-CCAA distinct rulesets resolved via the existing variant slot.

The existing `Modelo100GenParams` synthetic generator carries
`casilla_values: Mapping[str, Decimal]` flexibly — already shaped for
multi-anexo expansion. The borrador extractor already follows a
casilla-list regex map (`_SUMMARY_CASILLAS`) that extends naturally to
multi-anexo. Both pieces avoid green-field rewrites.

The Pydantic v2 mandate (strict / frozen / extra=forbid) is
non-negotiable. Every new record-shaped type added to the M100 surface
(amortization table, inventory record, CCAA enum, life-shape fixture)
must be Pydantic v2.

The 2026 Orden HAC for M100 has not been published at retrieval
2026-04-27 (precedent: feb-mar 2027). The 2026 IRPF tarifa (estatal
art. 63 + ahorro art. 66 post Ley 7/2024), mínimos (arts. 57-60),
art. 20 reducción rendimientos del trabajo (post RD-Ley 4/2024), and
RIRPF art. 30 gastos de difícil justificación general 5%/2.000€ cap
are all stable for 2026. The rate must still remain revision data
because LIRPF DA 56 raised the 2023 rate to 7% for that tax period
only. Only Andalucía has published its 2026 Ley de Presupuestos
(Ley 8/2025) at retrieval; the other 14 ordinary CCAAs' 2026 deduction
values are unverifiable.

The user's directive expects a single PR closes `#317`/`#341`/`#342`/
`#343`/`#344`. The implementation work realistically spans multiple
sessions; the draft PR remains open across sessions. The multi-agent
review wave plan (gemini-code-assist + codex review subagent + claude
review subagent) bakes review checkpoints into the implementation
cadence rather than deferring all review to PR-end.

The user's directive also corrects a brief error: Ceuta and Melilla
deduction is **60%** per LIRPF art. 68.4 (post-Ley 6/2018), not 50%.
This is a STATE deduction applied on the total cuota íntegra, not a
CCAA deduction per LIRPF art. 46 bis. Ceuta and Melilla are ciudades
autónomas, not Comunidades Autónomas, and lack potestad LIRPF art.
46 bis.

## Constraints

- **Live AEAT submission permanently forbidden** (`#432` charter). M100
  work touches verification only.
- **No mocks / fakes / stubs / freezegun / pytest-mock.** Project-wide
  ban. Tests use real `CasillaDefinition` / `Ruleset` / `Formula`
  instances; real synthetic PDFs from `aeat.domain.testing`; real CLI
  invocation via Typer `CliRunner`.
- **No wave / phase numbering in source code or docstrings.** Wave
  markers belong in vault docs and commit messages only.
- **Pydantic v2 strict / frozen / extra=forbid** on every new record
  type.
- **Trilingual labels** — ES authoritative, EN explicit, HU encoded
  if reference rulesets do.
- **Cent-exact** — terminal `RoundFormula(2dp, ROUND_HALF_UP)` per
  formula; engine tolerance `Decimal("0.01")`.
- **No new CLI commands** beyond `aeat audit rulesets citations`
  already present.
- **All Python modules under `src/aeat/`** (project mandate).
- **Coverage floor 60%** on `src/aeat` preserved via `just test-cov`.
- **Conventional commits** with `(#317)` suffix.
- **GitHub Actions CI** active; do NOT add new workflow files.
- **Foral regimes (País Vasco / Navarra) out of scope** (`#424`).
- **Pre-2020 RENTA template support** out of scope (XFA limitation
  per the 2026-04-21 prior ADR).

## Implementation

### D1. File layout — sub-package per modelo, per-anexo modules per año

Author the full-form M100 surface as a sub-package within
`src/aeat/domain/formulas/_rulesets/`:

```
src/aeat/domain/formulas/_rulesets/
├── modelo_100_summary_2025.py             (existing — variant="summary")
├── modelo_100_2024.py                      (NEW — aggregator: imports anexos, builds RULESET)
├── modelo_100_2025.py                      (NEW)
├── modelo_100_2026.py                      (NEW)
└── modelo_100/                             (NEW sub-package)
    ├── __init__.py                          (re-exports per-anexo casillas + formulas)
    ├── _common.py                           (shared label/citation helpers, CCAA enum, Anexo enum)
    ├── _amortization.py                     (Pydantic AmortizationCategory + AssetClass enum + LIS art. 12 table)
    ├── _inventario.py                       (Pydantic InventoryRecord + ValuationMethod enum)
    ├── _ccaa.py                             (CCAA closed StrEnum + per-CCAA tarifa autonómica brackets)
    ├── anexo_a_<año>.py                     (datos personales, descendientes, ascendientes, discapacidad)
    ├── anexo_b1_<año>.py                    (rendimientos del trabajo)
    ├── anexo_b2_<año>.py                    (rendimientos del capital mobiliario)
    ├── anexo_c_<año>.py                     (rendimientos del capital inmobiliario)
    ├── anexo_d_normal_<año>.py              (actividades económicas E.D. normal)
    ├── anexo_d_simplificada_<año>.py        (E.D. simplificada — revision rate/cap)
    ├── anexo_d_modulos_<año>.py             (estimación objetiva)
    ├── anexo_e_<año>.py                     (ganancias y pérdidas patrimoniales)
    ├── anexo_f_<año>.py                     (bases imponibles + reducciones + mínimos personal/familiar)
    ├── anexo_g_<año>.py                     (cuotas íntegras, líquidas, deducciones estatales)
    ├── anexo_n_<año>.py                     (Anexo Ñ — deducciones autonómicas, 15 CCAAs aggregated)
    └── test_*.py                            (per-anexo per-año test files, co-located)
```

Each `anexo_<X>_<año>.py` exports two tuples and one parameter table:
`CASILLAS`, `FORMULAS`, `PARAMETERS_<ANEXO>`. The per-año aggregator
(`modelo_100_<año>.py`) composes these into the public `RULESET:
Ruleset` constant. Co-located tests follow the established
`test_modelo_<NNN>_<año>.py` pattern but per-anexo:
`test_anexo_b1_2025.py` etc.

This is the **first sub-package within `_rulesets/`**. The
justification — scale (anexo × año × régimen × CCAA exceeds any prior
modelo by 5-10×) — is documented in the research doc §3 and §8.

### D2. Per-CCAA modeling — per-CCAA aggregate casillas in shared Anexo Ñ module

The DSL's lack of conditionals forces per-CCAA distinct casilla IDs.
Implementation:

- One shared `anexo_n_<año>.py` module per año hosting all 15 CCAAs.
- `CCAA` closed `StrEnum` in `modelo_100/_ccaa.py` with members
  `ANDALUCIA`, `ARAGON`, `ASTURIAS`, `BALEARES`, `CANARIAS`, `CANTABRIA`,
  `CASTILLA_LA_MANCHA`, `CASTILLA_Y_LEON`, `CATALUNA`, `COMUNIDAD_VALENCIANA`,
  `EXTREMADURA`, `GALICIA`, `MADRID`, `MURCIA`, `LA_RIOJA` (15 ordinary CCAAs).
- Per CCAA, **a CCAA-aggregate-deduction casilla**: `0622_AND`,
  `0622_ARA`, `0622_AST`, ..., `0622_RIO`. The caller populates only
  the CCAA's casilla matching their tax residence; the others remain
  zero. The state-level casilla `0622` (deducciones autonómicas total)
  is computed as `add_op(0622_AND, 0622_ARA, ..., 0622_RIO)` — only one
  is non-zero in any real filing.
- Per-CCAA deduction rules expressed via per-CCAA sub-casillas. E.g.
  Andalucía's nacimiento-de-hijo deduction is casilla `D_AND_NACIMIENTO`
  with formula `min_op(percent(rate, base), cap)`. The CCAA-aggregate
  `0622_AND` sums all `D_AND_*` casillas.

For the 5 highest-population CCAAs (Madrid, Cataluña, Andalucía,
Comunitat Valenciana, Castilla y León), the per-CCAA tarifa autonómica
general (LIRPF art. 74) was originally scoped to be encoded as a
`BracketsFormula` in `anexo_g_<año>.py` with per-CCAA bracket parameter
tables in `modelo_100/_ccaa.py`.

**Deferred (post-Wave-10)**: per the claude vaultspec-code-review's H2
finding, the per-CCAA tarifa autonómica progressive scales are not
implemented in this PR's wave set. Anexo G's casillas 0551 (cuota
íntegra autonómica general) and 0561 (autonómica ahorro) ship as
**caller-supplied inputs** — the caller computes the per-CCAA tarifa
externally per the rule-delta reference manifest's per-CCAA bracket
tables.

The progressive_tarifa() helper at `anexo_g_2025.py` is generic enough
to be parameterized with per-CCAA bracket tables in a follow-up wave;
the helper signature accepts any `tuple[tuple[str, str | None, str], ...]`
shape. A future per-CCAA wave authors `_ccaa.py` per-CCAA `ParameterTable`
entries and adds per-CCAA dedicated 0551/0561 formulas mirroring the
estatal pattern. The scaffolding (`_ccaa.py` + `progressive_tarifa()`
helper) is in place; the wiring is the deferred work.

**Ceuta + Melilla** is **NOT a CCAA** at this layer — it's a
state-level deduction per LIRPF art. 68.4. Encoded in `anexo_g_<año>.py`
as casilla `0612_CEUTA_MELILLA` with formula
`percent(lit("0.60"), <cuota proporcional rentas obtenidas>)`. The
caller supplies the proportional cuota base.

### D3. Amortization table — Pydantic model + closed StrEnum

`modelo_100/_amortization.py`:

```python
from enum import StrEnum
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class AssetClass(StrEnum):
    OBRA_CIVIL_GENERAL = "obra_civil.general"
    OBRA_CIVIL_PAVIMENTOS = "obra_civil.pavimentos"
    # ... ~30 entries from LIS art. 12.1.a) tabla
    OTROS_ELEMENTOS = "otros.elementos"

class AmortizationCategory(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    asset_class: AssetClass
    coef_max_pct: Decimal
    period_max_years: int

LIS_ART_12_TABLE: tuple[AmortizationCategory, ...] = (
    AmortizationCategory(asset_class=AssetClass.OBRA_CIVIL_GENERAL,
                         coef_max_pct=Decimal("2.00"), period_max_years=100),
    # ... ~30 entries
)
```

Used by Anexo D normal + simplificada formulas to validate caller-
supplied amortization values against the legal max. Constants
exhaustively cover the LIS art. 12.1.a) table verbatim per the research
doc §7.11.

### D4. Inventory valuation — Pydantic record + closed StrEnum

`modelo_100/_inventario.py`:

```python
class ValuationMethod(StrEnum):
    FIFO = "fifo"
    PMP = "pmp"  # precio medio ponderado
    COSTE_MEDIO = "coste_medio"

class InventoryRecord(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    method: ValuationMethod
    initial_value: Decimal
    final_value: Decimal
```

LIS art. 17 explicitly **forbids LIFO**; the closed enum enforces this
by construction.

### D5. Per-régimen split — three sub-modules per año for Anexo D

`anexo_d_normal_<año>.py`, `anexo_d_simplificada_<año>.py`,
`anexo_d_modulos_<año>.py`. Each module hosts its régimen's casillas +
formulas. The per-año aggregator (`modelo_100_<año>.py`) imports all
three and composes into one `RULESET`. The caller's filing declares
the régimen via the existing `Modelo100GenParams` shape; only the
matching régimen's casillas have non-zero values in any real filing.

E.D. simplificada's gastos de difícil justificación cap (RIRPF art. 30,
plus LIRPF DA 56 for 2023) is encoded as a revision-specific
`min_op(percent(rate_param, rendimiento_neto_pos), cap_param)` on the
`D_SIMPLIFICADA_GASTOS_DIFICIL_JUSTIF` casilla. Current non-exception
revisions use 5%/2.000€, while 2023 uses DA 56's 7% rate.

### D6. Per-annum strategy — structural clone via re-import + 2026 conservative inheritance

Mirror the **landed sibling Tier-L pattern** for structural clones:
each year file imports `CASILLAS` and `CITATIONS` from the canonical
2025 module via `from .anexo_<X>_2025 import CASILLAS, CITATIONS`, and
declares its own year-scoped `FORMULAS` tuple (with formula IDs of the
form `modelo_100.<año>.<reason>`) plus its own `EFFECTIVE_FROM` /
`EFFECTIVE_TO` date constants. This matches what `modelo_111_2024.py`,
`modelo_115_2024.py`, `modelo_123_2024.py`, `modelo_130_2024.py`, and
`modelo_131_2024.py` do (verified by inspection on
`origin/main` 2026-04-27).

**Rationale for re-import over full inline re-author**: the sibling
pattern was established by 5 prior Tier-L PRs and represents the
project's actual convention. Year-scoping is preserved at the
**formula ID** level (each year has its own `modelo_100.<año>.<reason>`
identifier the engine ledger uses for traceability) rather than at the
casilla level. The casilla definitions and citations are intentionally
shared because they describe statutory entities (LIRPF arts. 17-20,
22-26, etc.) that are invariant across years when no BOE amendment
exists; duplicating them across 3 years would create maintenance drift
risk without audit-traceability gain.

**Corrected 2026-04-28** per gemini-code-assist HIGH finding on
`anexo_b1_2024.py:29` and `anexo_b1_2026.py:32`: the original ADR text
"full re-author per año (NOT inheritance)" was inconsistent with the
landed sibling pattern. This amendment aligns the ADR text with the
sibling-pattern reality the implementation actually follows.

The 2026 ruleset's citations carry the BOE consult-date pin
`&p=20260228&tn=1` indicating consolidated text consult at 2026-02-28.
Citation summaries note "valor heredado de 2025 al no haberse publicado
modificación BOE para ejercicio 2026 a fecha 2026-02-28" for any value
that depends on year-specific publication.

For per-CCAA Anexo Ñ deductions in 2026: implement using 2025 values
as baseline (only Andalucía's 2026 deltas are verifiable). A follow-up
issue tracks per-CCAA 2026 Ley publication; deltas land as
`chore(rulesets/m100): refresh CCAA <X> 2026 deductions per Ley XX/2026
(#follow-up)`.

### D7. Round-trip strategy — extend existing borrador dispatch

M100 dispatches via `aeat filing import --from-borrador`. The full-form
work preserves this:

- Synthetic generator (`tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_100_generator.py`)
  is already shaped flexibly with `casilla_values: Mapping[str, Decimal]`.
  Extend `_BOXES` to cover full-form casillas across multiple pages.
- Borrador extractor (`src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`)
  needs per-año + multi-anexo extension. Add three new sibling extractors:
  `Modelo100V2024Extractor`, `Modelo100V2025Extractor`,
  `Modelo100V2026Extractor` with full-form casilla regex maps.
  Existing `Modelo100SummaryV2025Extractor` retained for the summary
  variant path.
- Round-trip: `generator(params) → PDF → borrador extractor → casilla
  map == expected_casillas` for at least one full-form case per año.

### D8. L1 anchor — Renta-Web-Open simulation outputs

Per the 2026-04-21 prior ADR, AEAT's Renta Web Open (publicly accessible,
no cert) generates filled "vista previa" PDFs for arbitrary synthetic
inputs. Target: ≥ 5 anchors per año covering distinct life shapes:

- L1.A: employee single, Madrid CCAA, no descendientes.
- L1.B: employee married + 2 kids, Cataluña CCAA, vivienda en alquiler.
- L1.C: autónomo E.D. simplificada, Comunidad Valenciana CCAA, no
  descendientes.
- L1.D: autónomo E.D. normal, Andalucía CCAA, capital inmobiliario
  (1 finca alquilada).
- L1.E: autónomo módulos, Castilla y León CCAA, ganancias patrimoniales
  pequeñas.

Each anchor lands at `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_100/<año>/<life-shape>.pdf`
with `_manifest.json` carrying SHA-256. **Manual step:** the human
operator (or a follow-up issue) actually visits Renta Web Open and
saves the PDFs; the ruleset/test code is ready to consume them when
they land. Until then, L1 anchor coverage is waived per the rule-delta
manifest, with synthetic L3 round-trip as the verification path.

### D9. Integration test — extend existing Kent class

Extend `tests/integration/test_kent_workflows.py::TestKentImportsModelo100SummaryBorrador`
or add sibling class `TestKentImportsModelo100FullBorrador`. Per-year
parametrize cases. Module-level marker per the brief:
`pytestmark = [pytest.mark.unit, pytest.mark.domain_submission, pytest.mark.fixture_tier_l3]`
matching sibling Tier-L pattern. Three mandatory cases:

1. `test_happy_path_english_<año>` — clean PDF → `VERIFIED` in EN.
2. `test_happy_path_spanish_default_<año>` — same, Spanish output.
3. `test_drift_triggers_needs_review_<año>` — tampered casilla →
   `NEEDS_REVIEW` with classified discrepancy.

Optional 4th case (`test_discrepancy_classified_correctly`) lands when
the M100 discrepancy classifier matures.

### D10. Cent-exact rounding policy

Every `formula()` body wrapped in terminal `RoundFormula(digits=2,
ROUND_HALF_UP)` (the `formula()` helper does this implicitly). No
intermediate rounding. Division uses `quantize="0.0001"` four-decimal
precision before the 2dp terminal round. Engine audit tolerance
`Decimal("0.01")`. This matches every sibling Tier-L modelo.

### D11. Multi-agent review wave plan

After each major implementation wave (per-anexo or per-régimen
completion), push to draft PR and:

1. Wait for `gemini-code-assist` auto-comment (active on this repo per
   memory `github_actions_disabled.md`).
2. Dispatch a **codex review subagent** via the Agent tool with prompt
   "review the diff of branch
   `feature/317-modelo-100-renta-full-calc` vs origin/main focusing on
   [current wave's surface]; check tax-correctness against BOE sources,
   formula DSL idiomaticity, citation completeness; report findings".
3. Dispatch a **claude review subagent** via the Agent tool
   (`vaultspec-code-reviewer` if available, else `general-purpose`)
   for the same scope.
4. Capture cross-perspective findings in the per-wave exec record.
5. Address findings before next wave.

Triggered after waves (by anexo): A+B1, B2+C, D (the biggest), E+F, G,
Ñ, round-trip, final.

### D12. Rolling audit checkpoints

After each implementation wave, before moving to the next:

- `aeat audit rulesets citations` shows 100% on every M100 ruleset
  added so far.
- `just lint && just typecheck && just hooks` green.
- `just test src/aeat/domain/formulas/_rulesets/modelo_100/` green.
- Mutation kill-rate ≥ 90% on newly-added M100 nodes.
- Per-wave exec record under
  `.vault/exec/2026-04-27-modelo-100-renta-full-calc/wave-<N>-<topic>-exec.md`
  captures audit results.

### D13. Pacing — multi-session implementation, single PR

The implementation work realistically spans multiple agent sessions.
The draft PR opens after the first complete anexo lands locally
(per the brief). Subsequent sessions resume on the same branch and
extend the same draft PR. The PR title and body reference all 5
issues:
`feat(formulas,declaracion,tests): MEGAPROJECT — Modelo 100 RENTA full-form
calc-verify-roundtrip 2024/2025/2026 (#317, #341, #342, #343, #344)`.

The plan (Wave 3 deliverable) sequences waves to maximize per-wave
durability — each wave's commit set is independently green and could
in principle merge alone if the user later opts to split the PR.

## Rationale

### Why a sub-package, not flat per-año files (D1)

A flat per-año approach mirrors the sibling Tier-L pattern at the cost
of 2000-4000 LOC per file. Review tractability degrades; rebase friction
compounds; per-anexo PR-review loses focus. The sub-package pattern
trades a one-time "first sub-package within `_rulesets/`" cost for
sustained per-anexo modularity. The aggregate per-año `modelo_100_<año>.py`
remains a thin module that composes the anexos — the existing import
pattern in `_rulesets/__init__.py` is unchanged.

### Why per-CCAA distinct casilla IDs, not per-CCAA distinct rulesets (D2)

The variant slot (`modelo_100.<ccaa>.<año>`) was considered. Rejected
because (a) a single Kent filing has ONE CCAA — the engine would resolve
17 candidate rulesets and pick one; that's not how `Ruleset.covers`
works; (b) the verification flow runs once per filing, not 17 times;
(c) maintainers reading `aeat audit rulesets citations` would see 51
M100 rulesets registered, obscuring the legal-completeness signal.

The per-CCAA distinct casilla approach keeps a single per-año
`modelo_100.<año>` ruleset with 15 CCAA-aggregate casillas. Caller
populates one CCAA's casilla; engine sums all 15 (14 zeros + 1 real).
Audit reports show one ruleset per año with 100% citation coverage —
a clean signal.

### Why Pydantic models for amortización + inventario (D3, D4)

Both data structures have closed taxonomies (LIS art. 12 table is a
finite list; LIS art. 17 valuation methods are exhaustively three).
Pydantic + closed `StrEnum` make this self-documenting and
type-safe; ParameterTable would force the structure into stringly-keyed
entries that lose type information.

### Why three Anexo D sub-modules (D5)

The BOE template publishes distinct casillas per régimen. Encoding all
three régimenes in one module would mix concerns and force the caller
to leave most casillas zero. Three sub-modules align module structure
to BOE template structure. Mirror precedent: the existing M131 (módulos)
and M130 (estimación directa) live in separate ruleset files for the
same reason.

### Why structural clone via re-import (D6)

Mirror the landed sibling Tier-L pattern. Year-scoping at the
**formula ID** level (`modelo_100.<año>.<reason>`) is load-bearing for
audit ledger traceability; the casilla definitions and citations are
shared because they describe statutory entities invariant across
years when no BOE amendment exists. The verbose-but-explicit re-author
alternative was rejected because the 5 prior sibling Tier-L PRs all
use re-import, and duplicating ~50 casilla definitions × 3 years would
create maintenance drift risk without audit-traceability gain.

### Why extend the borrador dispatch (D7)

M100's unique `--from-borrador` dispatch is established in landed code.
Extending it preserves backwards compatibility with the existing
`TestKentImportsModelo100SummaryBorrador` integration test and keeps
the CLI surface consistent. Switching M100 to `--from-declaracion`
would break the existing summary path with no compensating benefit.

### Why ≥5 L1 anchors per año, with synthetic-only fallback (D8)

Renta Web Open is the canonical L1 source per the 2026-04-21 prior
ADR. Five life shapes covers the realistic Kent diversity (employee
single / married / autónomo simplificada / autónomo normal / autónomo
módulos). Until the manual step lands the PDFs, synthetic L3 round-trip
provides verification evidence — the same fallback the M123 ADR
accepts.

### Why multi-agent review per wave, not just at PR-end (D11)

PR-end review on a 30-module megaproject is too late for wave-1
findings to influence wave-2 architecture. Per-wave review surfaces
cross-cutting concerns (citation pattern drift, DSL idiom drift, BOE
URL hygiene) when they're cheapest to fix. Cost: one review pass per
wave (~5 waves × 3 reviewers = 15 reviews). Benefit: cumulative quality
floor + early architecture validation.

### Why pace as multi-session, single PR (D13)

The user's directive expects "ONE PR closes all five". Splitting into
multiple PRs would re-introduce the umbrella+children friction the
megaproject directive expressly removes. Multi-session single PR
preserves the PR-as-narrative property while honoring the realistic
implementation budget. The plan sequences waves so each wave's commit
set is independently green.

## Consequences

### Positive

- Coherent end-to-end M100 RENTA coverage in one PR; closes 5 issues
  simultaneously; single review locus.
- Sub-package layout scales to the eventual full IRPF surface (Anexo
  H/I/J etc. that the 2026-04-21 ADR scoped out can land via the same
  pattern when needed).
- Pydantic-first amortización + inventario surface keeps Spanish IRPF
  regulation self-documenting in the codebase.
- Per-CCAA aggregate casilla pattern transfers to other autonomic-
  cesion modelos (e.g. M714 Patrimonio) without re-architecture.
- Multi-agent review wave plan provides systematic cross-perspective
  coverage; gemini-code-assist's auto-review on each push compounds.

### Negative / risks

- Sub-package within `_rulesets/` is a NEW pattern. Risk of friction
  with future Tier-L authors expecting flat-per-año. Mitigation: the
  sub-package is M100-specific; sibling modelos retain flat-per-año
  by default; the M100 sub-package is documented in the rule-delta
  manifest and the per-año aggregator's docstring.
- 51 (15 CCAA × 1 CCAA-aggregate-casilla × 3 años) per-CCAA casillas
  in `_CASILLAS` tuple may stress the engine's casilla lookup
  performance on M100. Mitigation: profiled benchmark in Wave 11; if
  >100ms per-audit, switch to per-CCAA distinct rulesets via variant
  slot.
- 2026 CCAA values use 2025 as baseline pending publication. Risk of
  stale citations when CCAAs publish their 2026 leyes. Mitigation:
  per-CCAA follow-up issues opened post-merge; rule-delta manifest
  flags `validated_for_year` per row.
- Implementation duration spans multiple sessions. Risk of stale draft
  PR + branch divergence from main. Mitigation: rebase before each
  session; per-wave commits are independently green.
- L1 anchor manual step (Renta Web Open) is a human-in-the-loop
  carve-out from the otherwise-fully-automated mandate. Mitigation:
  synthetic L3 round-trip remains the verification path; L1 anchors
  are aspirational.

### Forward implications (post-merge)

- Per-anexo expansion (Anexo H planes pensiones, Anexo I deduccion
  doble imposición internacional, Anexo J actividades agrícolas) can
  land via the same sub-package pattern as needed.
- Per-CCAA 2026 Ley publication triggers follow-up issues that land
  per-CCAA refresh chores using the established `chore(rulesets/m100)`
  prefix.
- The `CCAA` closed enum becomes the canonical project-wide enum for
  autonomic-cession modelos (M100 + M714 + future).
- The amortización + inventario Pydantic surface becomes reusable for
  Modelo 200 (IS) when that modelo's calc-verify lands.

## Amendment (2026-05-21): art.66 ahorro-base estatal escala authored as registry data

The shipped M100 registry carried casillas `0536`
(`irpf_escala_sobre_base_ahorro_estatal`), `0538`
(`irpf_escala_sobre_minimo_ahorro_estatal`), and `0540`
(`irpf_cuota_base_liquidable_ahorro_estatal`) with `ley-35-2006:art-66`
in their `legal_refs`, but no formula produced them and no art.66
`bracket_table` parameter existed. Downstream formulas already consumed
`0540` (`0542` tipo medio de gravamen estatal del ahorro; `0545` cuota
íntegra estatal) as if populated — a latent defect that left the
savings-base contribution to the cuota íntegra estatal silently zero.

This amendment records that the IRPF art.66 ahorro-base **estatal**
progressive scale (escala del ahorro, parte estatal) is now authored
as registry data, structurally mirroring the already-shipped
general-base estatal escala (`renta-{year}-escala-estatal-base-general`
+ its `lookup_bracket` / `subtract` formulas).

- **Parameter** — `renta-{year}-escala-estatal-base-ahorro`, a
  `bracket_table` with `bracket_axis = "filing_period"` and
  `legal_refs = ["ley-35-2006:art-66"]`. Brackets are BOE/AEAT-grounded
  per ejercicio (see below).
- **`[0536]`** — `lookup_bracket([0510]
  base liquidable del ahorro, renta-{year}-escala-estatal-base-ahorro)`:
  the estatal escala applied to the base liquidable del ahorro.
- **`[0538]`** — `lookup_bracket([0522]
  mínimo personal y familiar imputado a la base del ahorro,
  renta-{year}-escala-estatal-base-ahorro)`: the same escala applied to
  the mínimo allocated to the savings base (art.66.1.2.º minoración).
- **`[0540]`** — `subtract([0536], [0538])`: cuota correspondiente a la
  base liquidable del ahorro, parte estatal. This now feeds `0542` and
  `0545` with a non-zero value.

The art.66 estatal savings brackets are grounded against the AEAT
*Manual práctico de Renta*, section "Gravamen de la base liquidable
del ahorro — Gravamen estatal — Normativa: Art. 66.1 Ley IRPF", and
the BOE consolidated text of art.66 Ley 35/2006 (BOE-A-2006-20764).
The tariff was amended across ejercicios — Ley 11/2020 (effective
2021), Ley 31/2022 (effective 2023), Ley 7/2024 (effective 2025) —
and each year's brackets are grounded to that year's manual:

- **2020** (3 brackets): 0–6.000 @ 9,5%; 6.000–50.000 @ 10,5%;
  >50.000 @ 11,5%.
- **2021–2022** (4 brackets, Ley 11/2020 added the >200.000 tier):
  0–6.000 @ 9,5%; 6.000–50.000 @ 10,5%; 50.000–200.000 @ 11,5%;
  >200.000 @ 13%.
- **2023–2024** (5 brackets, Ley 31/2022 added the >300.000 tier):
  0–6.000 @ 9,5%; 6.000–50.000 @ 10,5%; 50.000–200.000 @ 11,5%;
  200.000–300.000 @ 13,5%; >300.000 @ 14%.
- **2025** (5 brackets, Ley 7/2024 raised the top tier): 0–6.000 @
  9,5%; 6.000–50.000 @ 10,5%; 50.000–200.000 @ 11,5%;
  200.000–300.000 @ 13,5%; >300.000 @ 15%.

The calc-verify oracle is the worked example on AEAT Manual Renta 2025
Parte 1, page 954 ("Don A.B.C., residente en Aragón"): base liquidable
del ahorro 2.800 EUR, mínimo absorbed in full by the general base —
"Gravamen estatal 2.800 x 9,50% = 266". Expected values are
AEAT-published (the manual worked example plus the "Incremento en
cuota íntegra estatal" column at each breakpoint), not author-computed,
satisfying the no-tautological-calculation-tests rule. The decision
and scope of this ADR are otherwise unchanged.

The art.76 ahorro-base **autonómica** escala (casillas `0537`/`0539`/`0541`, parameter `renta-{year}-escala-autonomica-base-ahorro`, `legal_refs = ["ley-35-2006:art-76"]`) is now likewise authored for ejercicios 2020–2025; the AEAT Manual de Renta confirms the art.76 autonómica savings scale is bracket-identical to the art.66.1 estatal savings scale every year, and the page-954 worked example oracle "Gravamen autonómico 2.800 x 9,50% = 266" grounds `0541`.
