---
tags:
  - '#adr'
  - '#mandatory-citations'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-mandatory-citations-research]]"
  - "[[2026-04-22-citation-blocklist-adr]]"
---

# `mandatory-citations` adr (**status:** `accepted`)

## Problem Statement

Tax math without legal citations is unverifiable. The existing
`CasillaDefinition.legal_basis` field is optional, which means a ruleset
author can ship a `computed=True` casilla with zero legal provenance and
still pass every existing import-time check. The wave-69 blocklist
(`KnownBadCitation`) only fires when a citation is *present but wrong*;
it does not catch the *missing-entirely* case. Issue `#339` (under EPIC
`#316` Thread 2) closes that gap by promoting "every computed casilla
carries at least one `LegalCitation`" from a convention to a hard
import-time invariant.

## Considerations

- **Validator placement.** Three candidates: model-level on
  `CasillaDefinition`, cross-validator on `Ruleset.model_post_init`,
  or both. Per the research doc, option A wins — fires earliest, covers
  every construction pathway (direct, replay, fixture), avoids redundant
  enforcement.
- **Source-enum closure.** The handover prompt's proposed catalogue
  (`BOE | RD | ORDEN | DIRECTIVA_UE | LIRPF | LIVA | LIS | RIRPF | RIVA
  | RIS | LGT`) conflates source-kind and individual-norm axes. The
  existing `LegalCitationSource` StrEnum is already a closed catalogue
  on the source-kind axis, with 6 members covering every citation in
  the 18 landed rulesets. `DIRECTIVA_UE` has zero current uses and is
  not promoted in this ADR — adding it now would be premature.
- **Back-fill volume.** A sweep at `chore/339-mandatory-citations` HEAD
  (post-`dae0ff2`) confirms 100% citation coverage on every
  `computed=True` casilla across the 18 landed rulesets. Volume is zero —
  the validator merely locks an existing convention.
- **Audit-CLI surface.** A non-default, dev-only `aeat audit rulesets
  citations` command with a strict pydantic `CitationCoverageReport`
  return shape. Forward-compatible with `#394`'s 13-root tree (where
  `audit` is a Kent-first root) and `#399`'s `--json` schema (the report
  serialises cleanly through `model_dump_json`).
- **Sibling-branch coordination.** Three branches all want to modify
  `cli/__init__.py` (own + `#398` + `#399`). A Phase 1 / Phase 2 split
  resolves the collision: Phase 1 ships the audit subpackage in
  isolation (testable via `CliRunner(audit_app)` without root
  registration); Phase 2 is a single follow-up commit (one line + one
  import) that lands after whichever sibling lands first.
- **Regression guard.** `#338` and `#340` recently landed mutation +
  integration test suites that walk every ruleset. Adding the validator
  must not break them; a dedicated `test_all_rulesets_have_citations.py`
  is the hard CI guard against future drift.

## Constraints

- Pydantic v2 strict mandate — every new model is `frozen=True,
  strict=True, extra="forbid"`. Validators raise; never return partial
  state.
- All Python modules live under `src/aeat/`. Tests are colocated.
- No mocks / patches / fakes / stubs. Real model instances throughout.
  The audit-CLI gap-path test uses pydantic's `model_construct`
  documented escape hatch to assemble a "missing-citation" fixture
  without bypassing the validator stack everywhere.
- Markers: `pytestmark = [pytest.mark.unit,
  pytest.mark.domain_submission]` at module level for every new test
  module.
- Errors inherit from `aeat.core.errors.AeatError`. `RulesetValidationError`
  already does (`RulesetValidationError -> FormulasError -> AeatError`)
  — reuse, don't add a sibling class.
- Trilingual + Windows-encoding. Audit-CLI output goes through
  `Translatable` at emission with `AEAT_OUTPUT_LANGUAGE` honored.
  Stdout/stderr reconfigured to UTF-8 explicitly to avoid the cp1252
  crash that bit `#389`.
- Public API discipline: callers import from `aeat.domain.formulas`,
  `aeat.domain.modelos`, `aeat.entrypoints.cli.audit` only — never from internal `_modules`.

## Implementation

### Validator on `CasillaDefinition`

Add a second `@model_validator(mode="after")` method to
`CasillaDefinition` (alongside the existing `_validate_shape`). The new
method raises `RulesetValidationError` when `self.computed is True and
self.legal_basis == ()`. Error message names the casilla identifier and
states the policy.

```python
@model_validator(mode="after")
def _require_legal_basis_for_computed(self) -> CasillaDefinition:
    if self.computed and not self.legal_basis:
        raise RulesetValidationError(
            f"casilla {self.casilla_id!r}: computed casillas require at least "
            f"one LegalCitation in legal_basis. Cite the BOE / RD / Orden "
            f"primary source that grounds this calculation."
        )
    return self
```

A `# TODO post-#398` comment near the `RulesetValidationError` import
flags the future error-code registration under the `INTEGRITY` category.

### Source-enum stance

No source change. Re-affirm via a focused unit test
(`test_citations_source_enum.py`) that:

- every member of `LegalCitationSource` is accepted as
  `LegalCitation.source`;
- a freeform string (e.g. `source="convenio"`) raises
  `pydantic.ValidationError`.

The test serves as living documentation that the closed-catalogue
constraint is in place.

### Audit subpackage

```text
src/aeat/entrypoints/cli/audit/
├── __init__.py           # audit_app + rulesets_app + citations command
├── _helpers.py           # validate_citation_coverage + CitationCoverageReport
└── test_citations_cmd.py # CliRunner-driven happy/sad/UTF-8 path
```

`CitationCoverageReport(BaseModel, frozen=True, strict=True,
extra="forbid")` carries:

- `modelo: ModeloCode` — strict-typed via existing enum.
- `effective_from: date`, `effective_to: date | None` — ruleset span.
- `ruleset_id: str` — full identifier for grouping.
- `total_computed: int`, `with_citation: int`, `coverage_percent: float`.
- `missing_casillas: tuple[str, ...]` — empty when fully covered.

`validate_citation_coverage(ruleset)` is a pure function. The CLI
command iterates `ALL_RULESETS`, builds reports, prints a per-ruleset
line + an aggregate, and exits non-zero on any gap. Stdout/stderr are
reconfigured to UTF-8 at command entry.

A `# TODO post-#399` comment near the report model flags the future
`--json` output-schema registration.

### Phase 1 vs Phase 2 split

Phase 1 (this ADR's scope): everything above, **without** modifying
`src/aeat/entrypoints/cli/__init__.py`. The audit subpackage is fully testable in
isolation via `from aeat.entrypoints.cli.audit import audit_app;
CliRunner(audit_app)`.

Phase 2 (deferred, single follow-up commit, post-merge of `#398` or
`#399`): one-line registration

```python
from . import audit as audit_module
...
app.add_typer(
    audit_module.audit_app,
    name="audit",
    help="Audit helpers (dev-only).",
    hidden=True,
)
```

### Regression guard

`src/aeat/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`
imports `ALL_RULESETS` and asserts coverage percentage = 1.0 on every
ruleset. The validator already raises at import time, so this test is
defense-in-depth against any future ruleset that bypasses the validator
via `model_construct` without restoring the invariant.

### Documentation

`docs/coverage/pipeline.md` gains a "LegalCitation enforcement" row in
the cross-cutting observables table, marked ✅ once this ships.

## Rationale

The validator-on-CasillaDefinition + regression-guard combination is
the smallest change that closes the gap structurally. Alternatives
considered:

- **Pre-commit grep gate** (every ruleset must have a `legal_basis=`
  on every `computed=True`): rejected — ruleset modules are computed,
  not declarative-only; a `legal_basis=()` literal would defeat the
  grep.
- **Process-only author checklist**: rejected — the citation-blocklist
  ADR already established that process-only rules don't prevent
  what authors don't think to double-check.
- **Cross-validator on `Ruleset.model_post_init` only**: rejected —
  misses `CasillaDefinition` instances built outside a `Ruleset` (test
  fixtures, replay paths, helpers).
- **Both A and B**: rejected — B is redundant given A.

Source-enum extension to `DIRECTIVA_UE` is deferred because: (a) zero
current uses; (b) the v1 modelo scope cites Spanish primary statute
exclusively; (c) adding now would be premature optimisation that the
issue does not require. If a future ruleset (e.g. Modelo 369 OSS / IOSS)
needs to cite Council Directive 2006/112/EC directly, that's a single
enum addition with no further architectural commitment.

## Consequences

### Short-term (Phase 1, this PR)

- The validator fails import on any future ruleset that ships a
  `computed=True` casilla without `legal_basis`. The 18 landed rulesets
  pass unchanged.
- The `aeat audit rulesets citations` command is importable from
  `aeat.entrypoints.cli.audit` but not yet on the root Typer.
- `#338`'s mutation harness and `#340`'s integration tests stay green
  (no behavioural change to existing computed casillas).
- The dependency edge for `#317`-`#327` (eleven Tier-L per-modelo
  verify-roundtrip issues) closes — those issues now start from a
  baseline where every computed casilla is provably traceable to a BOE
  primary source.

### Medium-term (Phase 2 follow-up)

- A single 1-line + 1-import commit registers the audit command on the
  root Typer. Lands after `#398` or `#399` (whichever first), via a
  rebase. No architectural decisions in Phase 2.
- Post-`#398` rebase additionally registers an `ErrorCode` for
  `RulesetValidationError` under the `INTEGRITY` category.
- Post-`#399` rebase wires an `OutputSchema` for the audit-CLI command
  enabling `--json` rendering.

### Long-term

- Forward-compatible with `#394`'s 13-root Kent-first tree: when the
  new tree activates behind `AEAT_KENT_CLI_PREVIEW=1`, the `audit` root
  *is* this command surface (extended over time with non-dev surfaces).
- Establishes a precedent for "import-time invariants on computed
  artefacts" that subsequent EPIC `#316` work can reuse — e.g., a
  parallel guard on parameter-table provenance.

### Non-goals

- Stopping every possible citation error. The blocklist
  (`[[2026-04-22-citation-blocklist-adr]]`) handles the
  *present-but-wrong* case; this ADR handles the *missing-entirely*
  case. The combination is necessary, not exhaustive — a future
  positive-registry of `(source, article) → BOE-title` would close the
  remaining "wrong article, never-flagged" gap, but that's a separate
  decision deferred to a future ADR.
- A full machine-readable Spanish-tax knowledge base. The
  `LegalCitation.quoted_text_es` field stays a curated summary, not a
  parsed BOE article body.
- Live AEAT verification. Out of scope; tracked under `#239`.
