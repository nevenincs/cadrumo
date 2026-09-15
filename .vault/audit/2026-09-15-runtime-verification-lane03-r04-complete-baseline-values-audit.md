---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:ac29fde6c5646c0730bf5c2548e9effa978eda3797a25e896a73e7614c1dc7bc'
related:
  - "[[2026-09-15-runtime-verification-lane03-r03-binding-value-audit]]"
---

# `runtime-verification` audit: `lane03-r04 complete baseline value resolution`

## Scope

Objective: resolve the three published modelo 720 prior-year baseline bindings from one complete synthetic source observation, and confirm that each binding returns its own exact value. Session `lane03-r04-complete-baseline-values`, probe `L03-R04-P01`, executed once by the coordinator with no delegation and no retry.

Relationship to r03: lane03-r03 observed that the resolver refuses the whole call when a matching `720`/2024/`0A` source filing lacks a required sibling casilla (l03-r03-f01). That refusal remains an observed behaviour; this lane does not re-run or relabel it. This lane supplies all three required casillas, with distinct non-zero values, so that any mixing or aggregation across sibling bindings would show up.

Fixed expectations, recorded before execution: target `720`/2025/`0A`; source `720`/2024/`0A`; one binding per source casilla, each with previous-filing source modelo `720`, `filing_year_offset` of -1 years, source periods `["0A"]`, and `copy` aggregation. Inputs and expected binding values: `cuentas.valoracion` `Decimal("1234.56")`, `valores.valoracion` `Decimal("2345.67")`, `inmuebles.valoracion` `Decimal("3456.78")`. All inputs are synthetic software-behaviour values, not taxpayer evidence or verified legal authority.

Checkout: branch `main`, HEAD `e849cda53563cda39ba96441b87eff3bde2783f7`, with a dirty worktree from concurrent contributors.

Observation window: 2026-09-15T18:46:32.405+02:00 to 2026-09-15T18:46:36.266+02:00.

Command: the r03 script adapted as below, saved in session scratch storage (sha256 `829D99AA0ACCC88501EE7106918F145B8416FE32C117E46FECD087AB53F63B82`) and piped through `Get-Content -Raw` to `uv run --no-sync python -` from the worktree root in PowerShell. It finds each binding by its published provider target, not by id. It builds one observation using each binding's own published refs and calls `resolve_previous_filing_binding_values` once on the unmodified published revision, without `excluded_binding_ids`. It exits 0 for PROVEN, 1 for FAILED, and 2 for BLOCKED.

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

R03_LOGICAL_GENERATION = "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66"

# Synthetic software-behaviour inputs; not taxpayer evidence.
SYNTHETIC_VALUES = {
    "cuentas.valoracion": Decimal("1234.56"),
    "valores.valoracion": Decimal("2345.67"),
    "inmuebles.valoracion": Decimal("3456.78"),
}

path = bundled_authority_descriptor_path()
before = path.read_bytes()
descriptor = AuthorityDescriptor.read(path)
owner = bundled_indexed_authority()
exit_code = 1


def emit(payload):
    print(json.dumps(payload, sort_keys=True, default=str), flush=True)


try:
    with owner.operation() as operation:
        pin = operation.pin()
        emit({
            "stage": "operation-pin",
            "descriptor": str(path.resolve()),
            "descriptor_logical_generation": descriptor.logical_generation,
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "matches_r03_generation": pin.logical_generation == R03_LOGICAL_GENERATION,
        })
        revision = operation.revision_for_context("720", filing_year=2025, period="0A")
        emit({"stage": "selected-revision", "revision": str(revision.id)})

        binding_by_casilla = {}
        declarations = {}
        for casilla_id in SYNTHETIC_VALUES:
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
            emit({
                "stage": "binding-candidates",
                "source_casilla": casilla_id,
                "binding_ids": [binding.id for binding, _ in candidates],
            })
            if len(candidates) != 1:
                raise RuntimeError(
                    f"Expected exactly one published binding targeting {casilla_id}; found {len(candidates)}"
                )
            binding, dumped = candidates[0]
            provider = dumped["provider"]
            temporal = provider.get("temporal", {})
            declarations[binding.id] = {
                "source_casilla": casilla_id,
                "provider": provider,
                "aggregation": dumped["aggregation"],
                "legal_refs": dumped["legal_refs"],
                "source_refs": dumped["source_refs"],
            }
            if not (
                provider.get("source_modelo") == "720"
                and temporal.get("kind") == "filing_year_offset"
                and temporal.get("years") == -1
                and temporal.get("source_periods") == ["0A"]
                and dumped["aggregation"].get("op") == "copy"
            ):
                emit({"stage": "published-declarations", "declarations": declarations})
                raise RuntimeError(f"Published declaration for {binding.id} differs from fixed case")
            binding_by_casilla[casilla_id] = binding
        emit({
            "stage": "published-declarations",
            "binding_to_source_casilla": {b.id: c for c, b in binding_by_casilla.items()},
            "declarations": declarations,
        })

        observation = RegistryModeloObservation(
            modelo="720",
            filing_year=2024,
            period="0A",
            observations=tuple(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=value,
                    legal_refs=tuple(binding_by_casilla[casilla_id].legal_refs),
                    source_refs=tuple(binding_by_casilla[casilla_id].source_refs),
                )
                for casilla_id, value in SYNTHETIC_VALUES.items()
            ),
        )
        emit({
            "stage": "synthetic-observation",
            "synthetic": True,
            "source": {"modelo": "720", "filing_year": 2024, "period": "0A"},
            "values": {casilla_id: str(value) for casilla_id, value in SYNTHETIC_VALUES.items()},
            "observation": observation.model_dump(mode="json"),
        })

        refusal = None
        try:
            resolved = resolve_previous_filing_binding_values(
                revision,
                (observation,),
                filing_year=2025,
                period="0A",
            )
        except RegistryValidationError as exc:
            refusal = {"error_type": type(exc).__name__, "message": str(exc)}
            resolved = None

        generation_stable = pin.logical_generation == descriptor.logical_generation
        selector_stable = path.read_bytes() == before
        emit({
            "stage": "selector-stability",
            "generation_matches_descriptor": generation_stable,
            "selector_bytes_unchanged": selector_stable,
        })
        if not (generation_stable and selector_stable):
            emit({"signal": "BLOCKED", "reason": "selector or generation changed during observation"})
            exit_code = 2
        elif resolved is None:
            emit({"stage": "resolver-refused", **refusal})
            emit({"signal": "BLOCKED"})
            exit_code = 2
        else:
            emit({
                "stage": "resolved-values",
                "resolved": {key: str(value) for key, value in resolved.items()},
            })
            checks = {}
            for casilla_id, expected in SYNTHETIC_VALUES.items():
                binding_id = binding_by_casilla[casilla_id].id
                value = resolved.get(binding_id)
                checks[binding_id] = {
                    "expected": str(expected),
                    "observed": None if value is None else str(value),
                    "observed_type": type(value).__name__,
                    "exact": isinstance(value, Decimal) and value == expected and str(value) == str(expected),
                }
            emit({"stage": "value-checks", "checks": checks})
            if all(check["exact"] for check in checks.values()):
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
{"descriptor": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "matches_r03_generation": true, "reader_incarnation": "fb65343ea0118b9c763a2a731e8ea3dd267cc82772bede139449f4031bd888b7", "stage": "operation-pin"}
{"revision": "2013-y-siguientes", "stage": "selected-revision"}
{"binding_ids": ["modelo-720-prior-year-cuentas-valoracion-baseline"], "source_casilla": "cuentas.valoracion", "stage": "binding-candidates"}
{"binding_ids": ["modelo-720-prior-year-valores-valoracion-baseline"], "source_casilla": "valores.valoracion", "stage": "binding-candidates"}
{"binding_ids": ["modelo-720-prior-year-inmuebles-valoracion-baseline"], "source_casilla": "inmuebles.valoracion", "stage": "binding-candidates"}
{"binding_to_source_casilla": {"modelo-720-prior-year-cuentas-valoracion-baseline": "cuentas.valoracion", "modelo-720-prior-year-inmuebles-valoracion-baseline": "inmuebles.valoracion", "modelo-720-prior-year-valores-valoracion-baseline": "valores.valoracion"}, "declarations": {"modelo-720-prior-year-cuentas-valoracion-baseline": {"aggregation": {"op": "copy"}, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "provider": {"grouping": null, "kind": "previous_filing", "required_source_casilla_ids": null, "source_casilla_id": "cuentas.valoracion", "source_casilla_ids": [], "source_modelo": "720", "temporal": {"kind": "filing_year_offset", "max_years": null, "source_periods": ["0A"], "years": -1}}, "source_casilla": "cuentas.valoracion", "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"]}, "modelo-720-prior-year-inmuebles-valoracion-baseline": {"aggregation": {"op": "copy"}, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-54-bis", "orden-hap-72-2013:art-2"], "provider": {"grouping": null, "kind": "previous_filing", "required_source_casilla_ids": null, "source_casilla_id": "inmuebles.valoracion", "source_casilla_ids": [], "source_modelo": "720", "temporal": {"kind": "filing_year_offset", "max_years": null, "source_periods": ["0A"], "years": -1}}, "source_casilla": "inmuebles.valoracion", "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"]}, "modelo-720-prior-year-valores-valoracion-baseline": {"aggregation": {"op": "copy"}, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-ter", "orden-hap-72-2013:art-2"], "provider": {"grouping": null, "kind": "previous_filing", "required_source_casilla_ids": null, "source_casilla_id": "valores.valoracion", "source_casilla_ids": [], "source_modelo": "720", "temporal": {"kind": "filing_year_offset", "max_years": null, "source_periods": ["0A"], "years": -1}}, "source_casilla": "valores.valoracion", "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"]}}, "stage": "published-declarations"}
{"observation": {"filing_period": {"code": "0A", "filing_year": 2024}, "filing_year": 2024, "modelo": "720", "observations": [{"absent_by_design": false, "casilla_id": "cuentas.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "1234.56"}, {"absent_by_design": false, "casilla_id": "valores.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-ter", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "2345.67"}, {"absent_by_design": false, "casilla_id": "inmuebles.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-54-bis", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "3456.78"}], "period": "0A"}, "source": {"filing_year": 2024, "modelo": "720", "period": "0A"}, "stage": "synthetic-observation", "synthetic": true, "values": {"cuentas.valoracion": "1234.56", "inmuebles.valoracion": "3456.78", "valores.valoracion": "2345.67"}}
{"generation_matches_descriptor": true, "selector_bytes_unchanged": true, "stage": "selector-stability"}
{"resolved": {"modelo-720-prior-year-cuentas-valoracion-baseline": "1234.56", "modelo-720-prior-year-inmuebles-valoracion-baseline": "3456.78", "modelo-720-prior-year-valores-valoracion-baseline": "2345.67"}, "stage": "resolved-values"}
{"checks": {"modelo-720-prior-year-cuentas-valoracion-baseline": {"exact": true, "expected": "1234.56", "observed": "1234.56", "observed_type": "Decimal"}, "modelo-720-prior-year-inmuebles-valoracion-baseline": {"exact": true, "expected": "3456.78", "observed": "3456.78", "observed_type": "Decimal"}, "modelo-720-prior-year-valores-valoracion-baseline": {"exact": true, "expected": "2345.67", "observed": "2345.67", "observed_type": "Decimal"}}, "stage": "value-checks"}
{"signal": "PROVEN"}
probe_exit=0
```

Generation comparison: the operation pin and the descriptor both report the full logical generation `2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66`, identical to the full value recorded by lane03-r03. The script compared the full strings (`matches_r03_generation: true`). HEAD moved since r03 (`9fe7a274…` to `e849cda5…`), but the published generation did not change.

Final signal: PROVEN.

## Findings

### l03-r04-f01 | low | Complete synthetic source observation routes each baseline value to its own binding

Observed: in revision `2013-y-siguientes`, exactly one published previous-filing binding targets each source casilla:

- `modelo-720-prior-year-cuentas-valoracion-baseline` targets `cuentas.valoracion`.
- `modelo-720-prior-year-valores-valoracion-baseline` targets `valores.valoracion`.
- `modelo-720-prior-year-inmuebles-valoracion-baseline` targets `inmuebles.valoracion`.

Each declares source modelo `720`, `filing_year_offset` -1, source periods `["0A"]`, and `copy` aggregation. For one synthetic `720`/2024/`0A` observation carrying all three casillas, `resolve_previous_filing_binding_values` returned exactly three entries, each a `Decimal` equal in value and string form to its own input: `1234.56`, `2345.67` and `3456.78`. No value was mixed across siblings and none was summed. The selector bytes were unchanged, and the pin's generation matched the descriptor. This confirms the behaviour; it is not a defect.

Observed scope boundary: the returned mapping contained only these three bindings, so no other direct previous-filing binding in the revision resolved from this observation. Why each other binding went unresolved was not examined.

### l03-r04-f02 | low | Refusal of an incomplete matching filing (r03) and success with a complete filing (r04) bracket the required-casilla contract

Observed across lanes, at the same generation: a matching `720`/2024/`0A` filing that lacks one required sibling casilla refuses the whole call with `RegistryValidationError` (l03-r03-f01). The same filing with all three casillas resolves every binding exactly (l03-r04-f01). The case where the entire source filing is absent has not been observed in either lane. Source reading suggests such a binding resolves to unsatisfied and is skipped, but that remains unobserved.

## Recommendations

Next evidence question (from l03-r04-f02): with no `720`/2024/`0A` observation at all, for target `720`/2025/`0A`, does `resolve_previous_filing_binding_values` return a mapping that omits all three baseline bindings, rather than zeros or a refusal? Does that absence stay distinguishable from a proven zero?

Still unproven: whether a real modelo 720 filing may legally omit a section and how that should be represented; behaviour when the entire source filing is absent; selection between competing observations; source revision correctness; CLI and calculation-engine consumption; and filing-grade correctness.
