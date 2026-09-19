---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:22cafc7d3accd78b372902681296dd64c36292b702663d7a182d782f3b66a07d'
related:
  - "[[2026-09-15-runtime-verification-lane03-r02-binding-target-audit]]"
---

# `runtime-verification` audit: `lane03-r03 binding value resolution`

## Scope

Objective: show that one synthetic source observation at `720`/2024/`0A`, carrying `cuentas.valoracion = Decimal("1234.56")`, resolves through the published binding `modelo-720-prior-year-cuentas-valoracion-baseline` to exactly `Decimal("1234.56")` for target `720`/2025/`0A`. Session `lane03-r03-binding-value`, probe `L03-R03-P01`, executed once by the coordinator with no delegation and no retry. The binding and its target come from l03-r02-f01.

Fixed expectations, recorded before execution: target `720`/2025/`0A`; binding `modelo-720-prior-year-cuentas-valoracion-baseline`; source `720`/2024/`0A`; synthetic casilla `cuentas.valoracion`; input `Decimal("1234.56")`; expected binding value `Decimal("1234.56")`. These are software-behaviour expectations, not taxpayer evidence or verified legal authority.

Invocation grounding: I read the signatures before writing the script. `resolve_previous_filing_binding_values(revision, observations, *, filing_year, period, activity_start_date=None, excluded_binding_ids=None)` is at `src/cadrumo/domain/calculations/registry/bindings_previous_filing.py:455`. `RegistryModeloObservation(modelo, filing_year, period, observations, filing_period hydrated)` is at `src/cadrumo/domain/calculations/registry/bindings.py:203`. `CasillaObservation(casilla_id, value, legal_refs, source_refs, ...)` is at `src/cadrumo/domain/calculations/registry/bindings.py:115`; both `legal_refs` and `source_refs` require at least one entry.

The resolver walks every direct previous-filing binding in the revision (`bindings_previous_filing.py:475`). A binding with no matching filing resolves to unsatisfied and is skipped (`bindings_previous_filing.py:397` and `:444`). A matching filing that lacks a required source casilla raises `RegistryValidationError` (`bindings_previous_filing.py:335`). `required_source_casilla_ids` defaults to every declared source casilla. `excluded_binding_ids` is not a selector: its production caller passes bindings another authority owns (`src/cadrumo/application/calculations/binding_prefill.py:628`, `src/cadrumo/application/modelo/calculation_actions.py:851`). The probe therefore did not use it to hide the sibling bindings.

Checkout: branch `main`, HEAD `9fe7a274c5d67c57e8cad2d099f23a2024fabe66`, with a dirty worktree from concurrent contributors.

Observation window: 2026-09-15T18:36:09.832+02:00 to 2026-09-15T18:36:14.249+02:00.

Command: the script below, saved in session scratch storage (sha256 `243574B1A19826E70B256C7D7B7FD26842EEF1969E872D4D51896F5B66CF11DC`) and piped through `Get-Content -Raw` to `uv run --no-sync python -` from the worktree root in PowerShell. The script exits 0 for PROVEN, 2 for BLOCKED, and 1 for any other failure.

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

binding_id = "modelo-720-prior-year-cuentas-valoracion-baseline"
sibling_ids = (
    "modelo-720-prior-year-inmuebles-valoracion-baseline",
    "modelo-720-prior-year-valores-valoracion-baseline",
)
input_value = Decimal("1234.56")
expected_value = Decimal("1234.56")

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
        })
        revision = operation.revision_for_context("720", filing_year=2025, period="0A")
        emit({"stage": "selected-revision", "revision": str(revision.id)})

        matches = [binding for binding in revision.bindings if binding.id == binding_id]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one published binding; found {len(matches)}")
        binding = matches[0]
        dumped = binding.model_dump(mode="json")
        provider = dumped["provider"]
        temporal = provider.get("temporal", {})
        emit({
            "stage": "published-declaration",
            "binding_id": binding.id,
            "provider": provider,
            "aggregation": dumped["aggregation"],
            "legal_refs": dumped["legal_refs"],
            "source_refs": dumped["source_refs"],
        })
        if not (
            provider.get("kind") == "previous_filing"
            and provider.get("source_modelo") == "720"
            and provider.get("source_casilla_id") == "cuentas.valoracion"
            and temporal.get("kind") == "filing_year_offset"
            and temporal.get("years") == -1
            and temporal.get("source_periods") == ["0A"]
            and dumped["aggregation"].get("op") == "copy"
        ):
            raise RuntimeError("Published declaration differs from fixed case")

        # Synthetic software-behaviour input; not taxpayer evidence. Provenance
        # references are the published binding's own.
        observation = RegistryModeloObservation(
            modelo="720",
            filing_year=2024,
            period="0A",
            observations=(
                CasillaObservation(
                    casilla_id="cuentas.valoracion",
                    value=input_value,
                    legal_refs=tuple(binding.legal_refs),
                    source_refs=tuple(binding.source_refs),
                ),
            ),
        )
        emit({
            "stage": "synthetic-observation",
            "synthetic": True,
            "observation": observation.model_dump(mode="json"),
        })

        try:
            resolved = resolve_previous_filing_binding_values(
                revision,
                (observation,),
                filing_year=2025,
                period="0A",
            )
        except RegistryValidationError as exc:
            emit({
                "stage": "resolver-refused",
                "error_type": type(exc).__name__,
                "message": str(exc),
            })
            resolved = None

        if pin.logical_generation != descriptor.logical_generation:
            raise RuntimeError("Observed selector and operation generation differ")
        if path.read_bytes() != before:
            raise RuntimeError("Selector changed during observation")

        if resolved is None:
            emit({"signal": "BLOCKED"})
            exit_code = 2
        else:
            emit({
                "stage": "resolved-values",
                "resolved": {key: str(value) for key, value in resolved.items()},
                "selected_present": binding_id in resolved,
                "siblings_present": {sid: sid in resolved for sid in sibling_ids},
            })
            value = resolved.get(binding_id)
            if not (isinstance(value, Decimal) and value == expected_value and str(value) == "1234.56"):
                raise RuntimeError(f"Resolved value {value!r} differs from expected {expected_value!r}")
            emit({"signal": "PROVEN"})
            exit_code = 0
finally:
    owner.close()

sys.exit(exit_code)
```

Exit code: 2 (BLOCKED). No stderr. Complete emitted output:

```text
{"descriptor": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "reader_incarnation": "db788367a68c5649b8dc478a50c8babaadcab454208e9a641cb93ecfe39c272e", "stage": "operation-pin"}
{"revision": "2013-y-siguientes", "stage": "selected-revision"}
{"aggregation": {"op": "copy"}, "binding_id": "modelo-720-prior-year-cuentas-valoracion-baseline", "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "provider": {"grouping": null, "kind": "previous_filing", "required_source_casilla_ids": null, "source_casilla_id": "cuentas.valoracion", "source_casilla_ids": [], "source_modelo": "720", "temporal": {"kind": "filing_year_offset", "max_years": null, "source_periods": ["0A"], "years": -1}}, "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "stage": "published-declaration"}
{"observation": {"filing_period": {"code": "0A", "filing_year": 2024}, "filing_year": 2024, "modelo": "720", "observations": [{"absent_by_design": false, "casilla_id": "cuentas.valoracion", "formula_id": null, "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "op": null, "operand_casilla_refs": [], "operand_refs": [], "operand_values": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "value": "1234.56"}], "period": "0A"}, "stage": "synthetic-observation", "synthetic": true}
{"error_type": "RegistryValidationError", "message": "binding 'modelo-720-prior-year-valores-valoracion-baseline' requires observed casilla 'valores.valoracion' from '720'/2024/'0A'", "stage": "resolver-refused"}
{"signal": "BLOCKED"}
probe_exit=2
```

Generation comparison: the operation pin and the descriptor both report logical generation `2bdbfabc…2c66`, the same as lane02-r01 and lane03-r02. HEAD moved again since r02 (`6574d6e5…` to `9fe7a274…`), but the published generation did not change.

Final signal: BLOCKED. The public resolver refuses the whole call before it returns any binding value, so no value for the selected binding was observed.

## Findings

### l03-r03-f01 | medium | A single-casilla source observation cannot resolve the selected binding; a sibling's missing casilla refuses the whole call

Observed: revision `2013-y-siguientes` and the published binding matched the fixed case, including `copy` aggregation. The synthetic `RegistryModeloObservation` passed its typed contract. `resolve_previous_filing_binding_values` then raised `RegistryValidationError`: "binding 'modelo-720-prior-year-valores-valoracion-baseline' requires observed casilla 'valores.valoracion' from '720'/2024/'0A'". It returned no mapping, so neither the selected binding nor any other binding yielded a value. The selector stayed stable and the generation was unchanged.

Behaviour from source reading, consistent with the observation: the resolver iterates all direct previous-filing bindings of the revision. The sibling `valores` binding matched the same `720`/2024/`0A` filing. Its sole source casilla is required by default, so its absence is treated as a structural defect, not as an unsatisfied binding. The resolver has no supported way to resolve one binding while reporting its siblings as missing. The selected binding's own value may have been computed before the refusal, but the exception discards it, and nothing observable shows it.

This lane does not decide whether this refusal is correct for a real modelo 720 filing that legitimately omits a section, such as one with no securities or no real estate. Treating an omitted section as a required-casilla defect may or may not match the governing record design; that is a hypothesis for a grounded follow-up, not an observed defect.

### l03-r03-f02 | low | Housekeeping was already done by concurrent sessions

Observed: before this session acted, another session's commit `3877e71430` at 18:34:44 had removed the r02 template annotations and re-attested its stamp. After this record was scaffolded, a concurrent writer stripped its template comments and normalised its blank lines twice, which invalidated two direct body edits; this session did not run that fixer, and the body was then written through the vaultspec edit engine under the document lock. The CLI `check annotations` has no `--dry-run` flag. Its `--fix` path in `vaultspec_core/vaultcore/checks/annotations.py:184` rewrites every matching feature document under a per-document lock. The read-only diagnostic listed `2026-09-15-runtime-verification-lane01-r04-support-matrix-parity-audit.md`, an audit in flight in another session, so this session did not run `--fix`.

## Recommendations

Next evidence question (from l03-r03-f01): the smallest input that lets the public resolver return the selected binding's value is one synthetic `720`/2024/`0A` observation carrying all three required baseline casillas: `cuentas.valoracion = 1234.56` plus distinct non-zero synthetic values for `valores.valoracion` and `inmuebles.valoracion`. Does the selected binding then return exactly `1234.56`, with each sibling returning its own distinct value, so the values are not cross-wired? The sibling values must be labelled synthetic, must not be zeros standing in for absence, and the claim must stay limited to the selected binding.

A separate question, to be grounded in the official modelo 720 record design before any probe: should an observed 720 filing that legitimately omits a section be refused, or should that section's binding resolve to unsatisfied? That question is a behaviour decision, not an evidence lane.

Still unproven: value resolution for any binding, missing-source (no matching filing) behaviour, selection between competing observations, source revision correctness, CLI or calculation-engine consumption, and filing-grade correctness.
