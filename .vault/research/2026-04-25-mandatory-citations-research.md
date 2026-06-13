---
tags:
  - '#research'
  - '#mandatory-citations'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-22-citation-blocklist-adr]]"
---

# `mandatory-citations` research

Survey of the existing `LegalCitation` infrastructure, current population on the
18 landed rulesets, and the rationale for promoting "non-empty `legal_basis` on
every `computed=True` casilla" from a convention to a hard import-time
invariant. Closes the dependency edge for the eleven Tier-L per-modelo
verify-roundtrip issues (`#317`-`#327`) under EPIC `#316`.

## Findings

### 1. Source-of-truth for citation grammar

`LegalCitation` is a strict, frozen pydantic-v2 model declared in
`src/aeat/domain/modelos/_citations.py`. Its current shape:

| field | type | constraint |
|---|---|---|
| `source` | `LegalCitationSource` (StrEnum) | already a closed catalogue |
| `article` | `str` | `min_length=1` |
| `url` | `HttpUrl \| None` | optional, BOE / Manual práctico anchor |
| `quoted_text_es` | `str` | non-blank after strip |
| `retrieval_date` | `date` | when the citation was captured |
| `is_curated_summary` | `bool` | `True` for v1 citations |

`LegalCitationSource` enum members (defined in
`src/aeat/domain/modelos/_categories.py`):

- `LEY` — primary statutory law (Ley 35/2006 LIRPF, Ley 37/1992 LIVA, Ley
  27/2014 LIS, Ley 58/2003 LGT, etc.)
- `REAL_DECRETO` — primary statutory instrument (RD 439/2007 RIRPF, RD
  1624/1992 RIVA, RD 634/2015 RIS, etc.)
- `ORDEN_MINISTERIAL` — secondary annual / event-driven Orden HFP / HAC
- `REGLAMENTO` — secondary regulation
- `MANUAL_PRACTICO` — AEAT curated summary corpus
- `BOE` — raw BOE reference / preamble

The handover prompt's proposed catalogue (`BOE | RD | ORDEN | DIRECTIVA_UE
| LIRPF | LIVA | LIS | RIRPF | RIVA | RIS | LGT`) conflates two axes:
*source kind* (BOE, RD, Orden, Directiva UE) and *individual norms*
(LIRPF, LIVA, LIS, …). The existing enum uses the *source kind* axis, which
is the cleaner abstraction: an LIRPF citation is `(source=LEY, article="99")`,
LIVA is `(source=LEY, article="167")`, etc. Promoting individual norms to
enum members would force every law to be "known" at the enum site, which
cascades into a much larger maintenance contract.

`DIRECTIVA_UE` is not currently a member, and a grep across `src/aeat`
finds zero references to EU directives in any landed ruleset's
`legal_basis`. Spanish autónomo IRPF/IVA/IS rulesets in the v1 scope cite
Spanish primary statute (Ley + RD); EU directives only matter at the
upstream level (e.g. Sixth VAT Directive 2006/112/CE underpins LIVA, but
Modelo 303 cites LIVA directly, not the directive). Adding `DIRECTIVA_UE`
is therefore deferred — the existing 6-member catalogue is sufficient and
already enforced as a closed StrEnum.

### 2. Existing defenses

Two layers of defense already live in `src/aeat/models`:

**Blocklist (wave 69 of EPIC `#305`).** `_citation_registry.py` ships a
14-entry `_KNOWN_BAD_CITATIONS` tuple keyed on
`(source, article, role-substring)`. The `LegalCitation` model validator
in `_citations.py` rejects construction when a citation matches the
blocklist, with provenance pointing at the audit wave that first surfaced
the miscite. Ships behind a diacritic-folding match. Documented in
`[[2026-04-22-citation-blocklist-adr]]`.

**Source enum closure.** `LegalCitation.source: LegalCitationSource` is
already typed as the StrEnum, so freeform strings raise
`ValidationError` at construction.

The gap the audit finding (referenced in EPIC `#316`) flagged:
`CasillaDefinition.legal_basis: tuple[LegalCitation, ...] = ()` is
**optional**. A ruleset author can omit `legal_basis` entirely on a
computed casilla and ship — the blocklist only fires when a citation is
*present*. This makes it possible to merge a ruleset with zero legal
provenance, which renders the tax math unverifiable for an AEAT-inspector
scenario.

### 3. Current population on landed rulesets (back-fill volume estimate)

Sweep at `chore/339-mandatory-citations` HEAD (post-`dae0ff2`):

```text
import aeat.domain.formulas._rulesets — ALL_RULESETS = 18 entries

| ruleset_id              | casillas | computed | missing-citation-on-computed |
|-------------------------|----------|----------|------------------------------|
| modelo_100.summary.2025 | 12       | 4        | 0                            |
| modelo_111.2024         | 11       | 4        | 0                            |
| modelo_111.2025         | 11       | 4        | 0                            |
| modelo_115.2024         | 6        | 2        | 0                            |
| modelo_115.2025         | 6        | 2        | 0                            |
| modelo_123.2024         | 11       | 4        | 0                            |
| modelo_123.2025         | 11       | 4        | 0                            |
| modelo_130.2024         | 19       | 9        | 0                            |
| modelo_130.2025         | 19       | 9        | 0                            |
| modelo_131.2024         | 15       | 6        | 0                            |
| modelo_131.2025         | 15       | 6        | 0                            |
| modelo_180.2024         | 4        | 1        | 0                            |
| modelo_180.2025         | 4        | 1        | 0                            |
| modelo_200.2024         | 16       | 3        | 0                            |
| modelo_202.2025         | 9        | 3        | 0                            |
| modelo_303.2024         | 33       | 12       | 0                            |
| modelo_303.2025         | 33       | 12       | 0                            |
| modelo_390.2025         | 8        | 3        | 0                            |
| TOTAL                   | 243      | 89       | 0                            |
```

**Back-fill volume is zero.** Every one of the 89 computed casillas
across all 18 landed rulesets already declares a non-empty
`legal_basis`. The current convention has been honored throughout EPIC
`#305` (wave 69 onwards) and its successors — the modelo-130 sweep below
is representative:

- `casilla 03` (Rendimiento neto) → `legal_basis=_CITATIONS[:1]` (RD
  439/2007 art. 110).
- `casilla 04` (Pago fraccionado 20%) → same.
- `casilla 09` (Pago fraccionado 2%) → same.
- … and so on for every computed `casilla`.

This means the issue's effective scope reduces from "back-fill 11
rulesets" to "lock the convention as a hard import-time invariant and
ship a regression guard so future drift fails CI loudly".

### 4. Validator placement options

Three placement candidates were considered:

**A. `@model_validator(mode="after")` on `CasillaDefinition`** — fires at
casilla construction time. Catches every pathway: direct construction in
ruleset modules, `Ruleset.model_copy(update={"casillas": (...)})` mutation,
fixture-built `CasillaDefinition` for tests.

**B. Cross-validator inside `Ruleset.model_post_init`** — fires only at
ruleset construction. Misses transient `CasillaDefinition` instances
built outside a ruleset (e.g. for unit tests, replay paths, casilla-only
helpers).

**C. Both A and B.** Defense in depth, but B is redundant when A is
present — A fires before B can ever observe the casilla.

**Decision:** option A. The validator is local to the casilla, fires at
the earliest possible moment, and naturally flows into an existing
validator (`_validate_shape`) that already runs `model_validator
(mode="after")` on the same model. Adding a second validator-method is
idiomatic and keeps responsibilities sharp.

### 5. `RulesetValidationError` reuse

`src/aeat/core/errors/_*` declares `RulesetValidationError` with MRO
`RulesetValidationError -> FormulasError -> AeatError -> Exception`.
Reusing this class is the only correct choice — it is the established
exception type for "structural invariant violated by a ruleset" and the
class the existing `Ruleset.model_post_init` already raises for
duplicate-casilla / undeclared-formula / cycle scenarios. The error
message must include the casilla identifier to support the audit-CLI
report.

A future post-`#398` rebase will register a code under the `INTEGRITY`
category for this exception class; for now a `# TODO post-#398` marker
is sufficient.

### 6. Audit-CLI design

The handover mandates a non-default, dev-only `aeat audit rulesets
citations` command that:

- iterates `aeat.domain.formulas._rulesets.ALL_RULESETS`;
- per ruleset, computes a `CitationCoverageReport` (`computed`,
  `with_citation`, `coverage_percent`, `missing_casillas`);
- emits a per-modelo + ejercicio summary, terminated by an aggregate
  line;
- exits non-zero if any ruleset is below 100% coverage on
  `computed=True` casillas;
- handles UTF-8 on Windows (Spanish article references include
  diacritics: "actividades agrícolas", "régimen de estimación", etc.).

A dedicated `aeat.entrypoints.cli.audit` subpackage is the natural home — and aligns
with the future `#394` 13-root tree where `audit` is a Kent-first root.
Phase 1 ships the subpackage and command; Phase 2 (a single follow-up
commit after `#398` or `#399` lands) wires `app.add_typer(audit_app, …,
hidden=True)` onto `src/aeat/entrypoints/cli/__init__.py`.

The CLI's helper `validate_citation_coverage(ruleset)` is a pure function
returning a strict pydantic model (`CitationCoverageReport`,
`frozen=True, strict=True, extra="forbid"`). This shape is forward-
compatible with `#399`'s `--json` output schema work — the report
already serialises cleanly through `model_dump_json`.

### 7. Sibling-branch coordination

| branch                          | territory                                                   | collision  | mitigation                                                                   |
|---------------------------------|-------------------------------------------------------------|------------|------------------------------------------------------------------------------|
| `feature/239-aeat-verify`       | `aeat.adapters.outbound.aeat.sede`, `aeat.adapters.outbound.aeat.auth._clave_movil`                      | none       | n/a                                                                          |
| `feature/398-error-code-registry` | `aeat.core.errors._registry`, `cli/__init__.py` decorator     | indirect   | TODO marker on `RulesetValidationError`; defer cli/__init__.py to Phase 2    |
| `feature/399-json-output-contract` | `aeat.entrypoints.cli._schemas`, `_exit_codes`, `_log_levels`, `cli/__init__.py` | indirect | TODO marker on audit-CLI `--json`; defer cli/__init__.py to Phase 2          |
| `feature-338-mutation-harness-extension` (landed via PR #429) | mutation tests | none       | tests must stay green — verify on every commit                              |
| `feature-340-kent-workflows-expansion` (landed via PR #430) | integration tests | none      | tests must stay green — verify on every commit                              |

The Phase 1 / Phase 2 split is the canonical mechanism for avoiding the
3-way `cli/__init__.py` collision (own + #398 + #399). Phase 1 makes the
subpackage importable in isolation (`from aeat.entrypoints.cli.audit import
audit_app; CliRunner(audit_app)` — works without root registration);
Phase 2 is one line plus an import, deferred until whichever sibling
lands first.

### 8. Trilingual + Windows-encoding considerations

The audit-CLI output renders modelo names ("Modelo 130", "IVA Modelo
303") and Spanish article fragments verbatim ("artículo 110.1.c",
"actividades agrícolas, ganaderas, forestales y pesqueras"). Per the
project's mandate, user-facing strings flow through the `Translatable`
pattern at emission with `AEAT_OUTPUT_LANGUAGE` honored (default `es`).
The casilla-specific `notes_es` field (Spanish-only by design — it is an
internal author note, not a user-facing string) stays as a literal.

Windows console encoding has bitten the project once already (#389 —
Windows cp1252 crash on non-ASCII output). The audit command's entry
point must reconfigure stdout/stderr to UTF-8 explicitly, and a
regression test must exercise the path with diacritics in the rendered
output.

### 9. Test surface

Four new test modules:

- `src/aeat/domain/formulas/test_casilla_validator.py` — unit tests for the
  CasillaDefinition validator (passing case, failing case for
  `computed=True` + empty `legal_basis`, informational-casilla skip).
- `src/aeat/domain/modelos/test_citations_source_enum.py` — confirms the
  closed-enum constraint (every member accepted; freeform strings
  rejected). Documents that the enum is already closed.
- `src/aeat/entrypoints/cli/audit/test_citations_cmd.py` — `CliRunner(audit_app)`
  invocation; happy-path 100% coverage; failure exit-code on simulated
  gap (via a fixture ruleset built in-test); UTF-8 regression for the
  Windows path.
- `src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py` —
  hard regression guard. Imports `ALL_RULESETS`, asserts 100% coverage on
  every `computed=True` casilla.

Markers per the project mandate:
`pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]` at
module level.

No mocks, no patches, no fakes. Real `CasillaDefinition` /
`LegalCitation` / `Ruleset` instances. The fixture for the audit-CLI
gap-path test builds an in-test partial `Ruleset` whose `casillas`
include a `computed=True` row with empty `legal_basis` — but *that
instance must skip the new validator to construct in the first place*.
This is resolved by building the fixture from `model_construct(...)`,
the documented pydantic v2 escape hatch for "I want a model instance
without running validators". Using `model_construct` here is honest:
the gap-path is a fixture for the audit reporter, not a real ruleset.

### 10. Summary of decisions

- **Validator placement:** `@model_validator(mode="after")` on
  `CasillaDefinition`, raising `RulesetValidationError` with a casilla-
  identifying message.
- **Source enum:** keep the existing 6-member `LegalCitationSource`. No
  `DIRECTIVA_UE` (zero current uses). Document that `LegalCitation.source`
  is already a closed StrEnum.
- **Back-fill:** zero work — every existing computed casilla already
  carries a citation.
- **Audit CLI:** new `aeat.entrypoints.cli.audit` subpackage; `audit rulesets
  citations` command; not registered on root in Phase 1.
- **Regression guard:** `test_all_rulesets_have_citations.py` imports
  `ALL_RULESETS` and asserts 100% coverage; future drift fails CI.
- **Sibling coordination:** Phase 2 commit (one line + import) deferred
  until `#398` or `#399` lands.
