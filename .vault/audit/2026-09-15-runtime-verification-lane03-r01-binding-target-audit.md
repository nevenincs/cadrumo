---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:f6affb205da7fbb96e2a9e2046bd6c27a348ac7b8b6321bb8ba3da76518daeba'
related:
  - "[[2026-09-15-runtime-verification-lane02-r01-authority-read-audit]]"
---

# `runtime-verification` audit: `lane03-r01 binding target resolution`

## Scope

Objective: prove that one published previous-filing binding resolves, through `previous_filing_observation_requirements`, to a source modelo, filing year, period, and casilla fixed before the run. Session `lane03-r01-binding-target`, probe `L03-R01-P01`, executed once. The lane stops at dependency target resolution; value resolution is out of scope.

Checkout: branch `main`, HEAD `c36b855520f7664f57d3d5517097ab6cccefbfb9`. The worktree was dirty with concurrent contributors' changes, so the observation covers the working tree, not a clean commit.

Observation window: 2026-09-15T16:41:16.694+02:00 to 2026-09-15T16:41:43.840+02:00.

Fixed expectation: target modelo `720`, filing year 2025, period `0A`, binding id `modelo-720-prior-year-cuentas-valoracion`; expected source modelo `720`, filing year 2024, period `0A`, casilla `cuentas.valoracion`. The expectation came from the test fixture in `src/cadrumo/domain/calculations/registry/tests/test_previous_filing_binding_source_casilla_ids.py:32`. It is an engineering expectation, not independently verified legal authority.

Command: the standalone Python script from the lane03-r01 brief, piped to `uv run --no-sync python -` from the worktree root. It opens `bundled_indexed_authority()`, pins an operation, selects the revision for `720`/2025/`0A`, and requires exactly one binding with the fixed id before printing anything.

Exit code: 1. Emitted output:

```text
Traceback (most recent call last):
  File "<stdin>", line 29, in <module>
RuntimeError: Expected exactly one published binding; found 0
probe_exit=1
```

Generation comparison: not observed. The probe raised before the `published-declaration` stage, so it emitted no logical generation, reader incarnation, or revision id. Lane02-r01 recorded generation `2bdbfabc…2c66`. This run cannot be tied to that artifact.

Final signal: FAILED. The cause is a stale case expectation (F01), not a confirmed resolver defect. The resolver was not exercised.

## Findings

### l03-r01-f01 | medium | Fixed binding id is a test-fixture id, not the authored registry id

Observed: the published revision selected for `720`/2025/`0A` contains no binding with the id `modelo-720-prior-year-cuentas-valoracion`. Read-only source inspection after the probe found that id only in the synthetic fixture at `src/cadrumo/domain/calculations/registry/tests/test_previous_filing_binding_source_casilla_ids.py:36`. The fixture's docstring calls it "the real Modelo 720 prior-year cuentas valoracion baseline binding". The authored registry declares `modelo-720-prior-year-cuentas-valoracion-baseline` at `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings/0001-declarations.toml:330`.

The authored provider matches the fixed case exactly: `previous_filing`, source modelo `720`, `filing_year_offset` of -1 years, source periods `["0A"]`, source casilla `cuentas.valoracion`. The provenance does not match. The authored binding cites `ley-58-2003:da-18`, `rd-1065-2007:art-42-bis`, and `orden-hap-72-2013:art-2`, with source ref `aeat-modelo-720-procedure`. The fixture cites `ley-58-2003:disposicion-adicional-decimoctava` and `aeat-dr-720-2013`.

Hypothesis, not observed: the `-baseline` binding is present in the published generation, under revision `2013-y-siguientes`, for this context. Source and publication are separate boundaries, and this run observed neither the published binding list nor the generation.

### l03-r01-f02 | low | Test fixture misdescribes itself as the real registry binding

Observed: the fixture's id and legal/source references differ from the authored declaration, yet its docstring presents it as the real binding. Tests built on it therefore do not show that the authored `-baseline` declaration satisfies the same contract. This is a test-honesty finding. It does not show a runtime defect.

## Recommendations

Next evidence question (from l03-r01-f01): does the published generation contain `modelo-720-prior-year-cuentas-valoracion-baseline` for `720`/2025/`0A`? If it does, does `previous_filing_observation_requirements` resolve it to source `720`/2024/`0A` including `cuentas.valoracion`, with that binding's own legal and source refs preserved? Answer this with a re-issued brief that fixes the authored id before the run. Do not edit this lane's expectation after the fact.

Still unproven: publication of the authored binding, the generation any lane03 observation consumes, requirement coalescing, source-filing existence and revision selection, value resolution, and CLI or calculation-engine consumption. F02 needs a scoped fix decision by the fixture's owner (align the fixture with the authored declaration, or drop the "real" claim). It needs no probe.
