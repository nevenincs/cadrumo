---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:3168a1412b338e1594d90afced80cb870c715ec6b9a742ae198eb848d7f3dc41'
related:
  - "[[2026-09-15-runtime-verification-lane03-r04-complete-baseline-values-audit]]"
---

# `runtime-verification` audit: `lane03-r05 absent filing versus explicit zero`

## Scope

Objective: find out whether the public previous-filing resolver keeps two cases distinct for the three published modelo 720 baseline bindings. Case A has no prior-year source filing at all. Case B has one complete source filing whose three values are explicitly zero. Session `lane03-r05-absence-versus-zero`, probe `L03-R05-P01`: one script, two resolver calls inside one pinned authority operation, executed once by the coordinator with no delegation and no retry. The non-zero case (l03-r04-f01) and the incomplete-filing refusal (l03-r03-f01) were not re-run.

Fixed inputs: target `720`/2025/`0A`; revision selected through `operation.revision_for_context`; the same three bindings as r04, each found by its published provider target and required to declare source modelo `720`, `filing_year_offset` -1, source periods `["0A"]`, and `copy`. Case A passes an empty observation tuple. Case B passes one synthetic `720`/2024/`0A` observation with `cuentas.valoracion`, `valores.valoracion`, and `inmuebles.valoracion` each `Decimal("0.00")`, carrying each binding's own published refs. The inputs are synthetic software-behaviour values, not taxpayer evidence.

Hypothesis, recorded before execution and separate from acceptance: in `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py`, a binding with no matching filing raises `_PreviousFilingObservationAbsentError` (`:398`). `_resolve_binding_values` catches it and returns `None` (`:444`–`:449`), and `resolve_previous_filing_binding_values` skips `None` bindings (`:489`). Without an activity start date no zero vector is substituted (`:450`). Predicted Case A outcome: a mapping that omits all three bindings, with no refusal. I re-checked these line locations at the start of the session; they were unchanged from the r03 reading.

Acceptance: the membership of each binding id in each result is inspected explicitly, with no default value or truthiness test. Case B requires all three ids to be present, each a `Decimal` numerically equal to zero. The contract states no textual scale, so none is required. Absence counts as distinguishable if Case A refuses, or if it omits all three ids.

Checkout: branch `main`, HEAD `e849cda53563cda39ba96441b87eff3bde2783f7`, with a dirty worktree from concurrent contributors.

Observation window: 2026-09-15T18:52:23.268+02:00 to 2026-09-15T18:52:25.224+02:00.

Command: the script below, saved in session scratch storage (sha256 `1076C31717EAEF51A149A413E1DFEC3BC7223BDFCF864DEC792BE1E5FC911D85`) and piped through `Get-Content -Raw` to `uv run --no-sync python -` from the worktree root in PowerShell. It catches `RegistryValidationError` separately in each case; any other exception would propagate. It exits 0 for PROVEN, 1 for FAILED, and 2 for BLOCKED.

```python
import json
import sys
from decimal import Decimal

from cadrumo.domain.calculations.registry.authority import (
    bundled_authority_descriptor_path,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from cadrumo.domain.calculations.registry.bindings import (
    CasillaObservation,
    RegistryModeloObservation,
)
from cadrumo.domain.calculations.registry.bindings_previous_filing import (
    resolve_previous_filing_binding_values,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

R04_LOGICAL_GENERATION = "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66"
SOURCE_CASILLAS = ("cuentas.valoracion", "valores.valoracion", "inmuebles.valoracion")
# Synthetic software-behaviour inputs; not taxpayer evidence.
ZERO = Decimal("0.00")

path = bundled_authority_descriptor_path()
before = path.read_bytes()
descriptor = AuthorityDescriptor.read(path)
owner = bundled_indexed_authority()
exit_code = 1


def emit(payload):
    print(json.dumps(payload, sort_keys=True, default=str), flush=True)


def run_case(name, revision, observations):
    try:
        resolved = resolve_previous_filing_binding_values(
            revision,
            observations,
            filing_year=2025,
            period="0A",
        )
    except RegistryValidationError as exc:
        outcome = {"kind": "refused", "error_type": type(exc).__name__, "message": str(exc)}
        emit({"stage": f"case-{name}", **outcome})
        return outcome
    outcome = {
        "kind": "mapping",
        "resolved": {key: {"value": str(value), "type": type(value).__name__} for key, value in resolved.items()},
    }
    emit({"stage": f"case-{name}", **outcome})
    outcome["raw"] = resolved
    return outcome


try:
    with owner.operation() as operation:
        pin = operation.pin()
        emit({
            "stage": "operation-pin",
            "descriptor": str(path.resolve()),
            "descriptor_logical_generation": descriptor.logical_generation,
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "matches_r04_generation": pin.logical_generation == R04_LOGICAL_GENERATION,
        })
        revision = operation.revision_for_context("720", filing_year=2025, period="0A")
        emit({"stage": "selected-revision", "revision": str(revision.id)})

        binding_by_casilla = {}
        for casilla_id in SOURCE_CASILLAS:
            candidates = []
            for binding in revision.bindings:
                dumped = binding.model_dump(mode="json")
                provider = dumped["provider"]
                if provider.get("kind") != "previous_filing":
                    continue
                if provider.get("source_casilla_id") == casilla_id or casilla_id in (
                    provider.get("source_casilla_ids") or []
                ):
                    candidates.append((binding, dumped))
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected exactly one published binding targeting {casilla_id}; found {len(candidates)}"
                )
            binding, dumped = candidates[0]
            provider = dumped["provider"]
            temporal = provider.get("temporal", {})
            if not (
                provider.get("source_modelo") == "720"
                and temporal.get("kind") == "filing_year_offset"
                and temporal.get("years") == -1
                and temporal.get("source_periods") == ["0A"]
                and dumped["aggregation"].get("op") == "copy"
            ):
                raise RuntimeError(f"Published declaration for {binding.id} differs from fixed case")
            binding_by_casilla[casilla_id] = binding
        binding_ids = tuple(binding_by_casilla[c].id for c in SOURCE_CASILLAS)
        emit({
            "stage": "published-bindings",
            "binding_to_source_casilla": {binding_by_casilla[c].id: c for c in SOURCE_CASILLAS},
        })

        # Case A: no source filing at all.
        case_a = run_case("A-absent-filing", revision, ())

        # Case B: one complete source filing with explicit zeros.
        zero_observation = RegistryModeloObservation(
            modelo="720",
            filing_year=2024,
            period="0A",
            observations=tuple(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=ZERO,
                    legal_refs=tuple(binding_by_casilla[casilla_id].legal_refs),
                    source_refs=tuple(binding_by_casilla[casilla_id].source_refs),
                )
                for casilla_id in SOURCE_CASILLAS
            ),
        )
        emit({
            "stage": "synthetic-zero-observation",
            "synthetic": True,
            "observation": zero_observation.model_dump(mode="json"),
        })
        case_b = run_case("B-explicit-zero", revision, (zero_observation,))

        generation_stable = pin.logical_generation == descriptor.logical_generation
        selector_stable = path.read_bytes() == before
        emit({
            "stage": "selector-stability",
            "generation_matches_descriptor": generation_stable,
            "selector_bytes_unchanged": selector_stable,
        })

        a_membership = (
            {bid: bid in case_a["raw"] for bid in binding_ids} if case_a["kind"] == "mapping" else None
        )
        b_membership = (
            {bid: bid in case_b["raw"] for bid in binding_ids} if case_b["kind"] == "mapping" else None
        )
        b_zero_exact = (
            case_b["kind"] == "mapping"
            and all(
                bid in case_b["raw"]
                and isinstance(case_b["raw"][bid], Decimal)
                and case_b["raw"][bid] == Decimal("0")
                for bid in binding_ids
            )
        )
        if case_a["kind"] == "refused":
            a_form = "refused"
        elif not any(a_membership.values()):
            a_form = "omitted"
        elif all(a_membership.values()):
            a_form = "present"
        else:
            a_form = "partial"
        distinguishable = b_zero_exact and a_form in ("refused", "omitted")
        emit({
            "stage": "interpretation",
            "case_a_form": a_form,
            "case_a_membership": a_membership,
            "case_b_membership": b_membership,
            "case_b_all_exact_zero": b_zero_exact,
            "absence_distinguishable_from_zero": distinguishable,
        })

        if not (generation_stable and selector_stable):
            emit({"signal": "BLOCKED", "reason": "selector or generation changed during observation"})
            exit_code = 2
        elif b_zero_exact and distinguishable:
            emit({"signal": "PROVEN"})
            exit_code = 0
        else:
            emit({"signal": "FAILED"})
            exit_code = 1
finally:
    owner.close()

sys.exit(exit_code)
```

Exit code: 0. No stderr. Complete emitted output:

```text
{"descriptor": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "matches_r04_generation": true, "reader_incarnation": "58c8da4666e1e366b6c137865cbca1f7291879dd878a2c636fda27576859ed74", "stage": "operation-pin"}
{"revision": "2013-y-siguientes", "stage": "selected-revision"}
{"binding_to_source_casilla": {"modelo-720-prior-year-cuentas-valoracion-baseline": "cuentas.valoracion", "modelo-720-prior-year-inmuebles-valoracion-baseline": "inmuebles.valoracion", "modelo-720-prior-year-valores-valoracion-baseline": "valores.valoracion"}, "stage": "published-bindings"}
{"kind": "mapping", "resolved": {}, "stage": "case-A-absent-filing"}
{"observation": {"filing_period": {"code": "0A", "filing_year": 2024}, "filing_year": 2024, "modelo": "720", "observations": [{"absent_by_design": false, "casilla_id": "cuentas.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "0.00"}, {"absent_by_design": false, "casilla_id": "valores.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-ter", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "0.00"}, {"absent_by_design": false, "casilla_id": "inmuebles.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-54-bis", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "0.00"}], "period": "0A"}, "stage": "synthetic-zero-observation", "synthetic": true}
{"kind": "mapping", "resolved": {"modelo-720-prior-year-cuentas-valoracion-baseline": {"type": "Decimal", "value": "0.00"}, "modelo-720-prior-year-inmuebles-valoracion-baseline": {"type": "Decimal", "value": "0.00"}, "modelo-720-prior-year-valores-valoracion-baseline": {"type": "Decimal", "value": "0.00"}}, "stage": "case-B-explicit-zero"}
{"generation_matches_descriptor": true, "selector_bytes_unchanged": true, "stage": "selector-stability"}
{"absence_distinguishable_from_zero": true, "case_a_form": "omitted", "case_a_membership": {"modelo-720-prior-year-cuentas-valoracion-baseline": false, "modelo-720-prior-year-inmuebles-valoracion-baseline": false, "modelo-720-prior-year-valores-valoracion-baseline": false}, "case_b_all_exact_zero": true, "case_b_membership": {"modelo-720-prior-year-cuentas-valoracion-baseline": true, "modelo-720-prior-year-inmuebles-valoracion-baseline": true, "modelo-720-prior-year-valores-valoracion-baseline": true}, "stage": "interpretation"}
{"signal": "PROVEN"}
probe_exit=0
```

Generation comparison: the operation pin and the descriptor both report the full logical generation `2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66`, identical to lane03-r04's full value (`matches_r04_generation: true`). HEAD was unchanged since r04.

Final signal: PROVEN.

## Findings

### l03-r05-f01 | low | With no source filing, the resolver omits the bindings; with explicit zeros, it returns them

Observed: in Case A (empty observations) `resolve_previous_filing_binding_values` returned an empty mapping without raising, and none of the three baseline binding ids was a member. In Case B (one complete `720`/2024/`0A` observation with explicit zeros) it returned exactly those three ids, each a `Decimal` with value `0.00`, numerically equal to zero. The selector was stable and the generation unchanged. At this resolver, therefore, an absent source filing shows up as omission and a proven zero as presence with a zero value; the two are distinguishable by key membership alone. The outcome matched the pre-run hypothesis.

This does not judge whether omission is the right representation. The absence is implicit: the returned mapping carries no marker, reason, or diagnostic saying a required prior-year filing was missing. A consumer that reads the mapping with a zero default would erase the distinction.

### l03-r05-f02 | low | Lane03 resolver evidence now covers the three required-casilla input states

Observed across lanes at generation `2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66`:

- No matching filing: bindings omitted, no refusal (l03-r05-f01).
- Matching filing missing a required casilla: the whole call is refused with `RegistryValidationError` (l03-r03-f01).
- Complete filing with non-zero values: each value routed exactly to its own binding (l03-r04-f01).
- Complete filing with explicit zeros: each binding present with `Decimal` zero (l03-r05-f01).

All four are observations at the resolver boundary only.

## Recommendations

Next evidence question (from l03-r05-f01): does the immediate consumer of `resolve_previous_filing_binding_values` keep omitted required bindings marked incomplete, or does it convert them to zero or to a complete result?

Still unproven: any downstream consumer's handling of omission (including the application prefill path and the calculation engine); CLI output and diagnostics; whether omission is the intended contract; whether real modelo 720 filings may legally omit sections; selection between competing observations; source revision correctness; and filing-grade correctness.
