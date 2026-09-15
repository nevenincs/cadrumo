---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:c91ffe529a456e4a1a4daf4c4f5a8a3b5b779c39c6a99235fda2b47cc799e97a'
related:
  - "[[2026-09-15-runtime-verification-lane03-r01-binding-target-audit]]"
---

# `runtime-verification` audit: `lane03-r02 binding target resolution`

## Scope

Objective: confirm that one published previous-filing binding resolves its dependency target through the real requirement resolver `previous_filing_observation_requirements`. Session `lane03-r02-binding-target`, probe `L03-R02-P01`, executed once by the coordinator with no delegation and no retry. The lane stops at dependency target resolution.

Correction of r01: lane03-r01 failed because its fixed binding id `modelo-720-prior-year-cuentas-valoracion` came from a test fixture, not from the published registry (l03-r01-f01). That was a defect in the probe specification. This lane corrects the id before execution to the authored id `modelo-720-prior-year-cuentas-valoracion-baseline`. The r01 run remains FAILED; this run does not rewrite it.

Fixed expectation: target `720`/2025/`0A`; binding `modelo-720-prior-year-cuentas-valoracion-baseline`; expected source `720`/2024/`0A`/`cuentas.valoracion`. This is an engineering expectation, not independently verified legal authority.

Checkout: branch `main`, HEAD `6574d6e55390424f216ca5f1b7efa9df8005d6cf`. HEAD differs from r01 (`c36b8555…`). The worktree was dirty with concurrent contributors' changes.

Observation window: 2026-09-15T17:49:26.265+02:00 to 2026-09-15T17:49:32.210+02:00.

Command: the script below, piped to `uv run --no-sync python -` from the worktree root in PowerShell. It is the r01 script with the binding id corrected and two early `flush=True` stages added (`operation-pin` and `selected-revision`). The provider-shape, source-coordinate, provenance and selector-stability assertions are unchanged. Provenance is checked against the published binding's own `legal_refs` and `source_refs`.

```python
import json

from cadrumo.domain.calculations.registry.authority import (
    bundled_authority_descriptor_path,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from cadrumo.domain.calculations.registry.bindings_previous_filing import (
    previous_filing_observation_requirements,
)

binding_id = "modelo-720-prior-year-cuentas-valoracion-baseline"
path = bundled_authority_descriptor_path()
before = path.read_bytes()
descriptor = AuthorityDescriptor.read(path)
owner = bundled_indexed_authority()

try:
    with owner.operation() as operation:
        pin = operation.pin()
        print(json.dumps({
            "stage": "operation-pin",
            "descriptor": str(path.resolve()),
            "descriptor_logical_generation": descriptor.logical_generation,
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
        }, sort_keys=True), flush=True)
        revision = operation.revision_for_context(
            "720", filing_year=2025, period="0A"
        )
        print(json.dumps({
            "stage": "selected-revision",
            "revision": str(revision.id),
        }, sort_keys=True), flush=True)
        matches = [
            binding for binding in revision.bindings
            if binding.id == binding_id
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one published binding; found {len(matches)}"
            )

        binding = matches[0]
        provider = binding.provider.model_dump(mode="json")
        print(json.dumps({
            "stage": "published-declaration",
            "descriptor": str(path.resolve()),
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "revision": str(revision.id),
            "binding": binding.model_dump(mode="json"),
        }, sort_keys=True), flush=True)

        temporal = provider.get("temporal", {})
        if not (
            provider.get("kind") == "previous_filing"
            and provider.get("source_modelo") == "720"
            and provider.get("source_casilla_id") == "cuentas.valoracion"
            and temporal.get("kind") == "filing_year_offset"
            and temporal.get("years") == -1
            and temporal.get("source_periods") == ["0A"]
        ):
            raise RuntimeError("Published declaration differs from fixed case")

        requirements = previous_filing_observation_requirements(
            revision, filing_year=2025, period="0A"
        )
        selected = [
            requirement for requirement in requirements
            if binding_id in requirement.binding_ids
        ]
        print(json.dumps({
            "stage": "resolved-requirements",
            "requirements": [
                requirement.model_dump(mode="json")
                for requirement in selected
            ],
        }, sort_keys=True), flush=True)

        if len(selected) != 1:
            raise RuntimeError(
                f"Expected one source requirement; found {len(selected)}"
            )

        result = selected[0]
        if not (
            result.source_modelo == "720"
            and result.filing_year == 2024
            and tuple(result.periods) == ("0A",)
            and "cuentas.valoracion" in result.source_casilla_ids
        ):
            raise RuntimeError("Resolved source differs from expected target")

        if not (
            set(binding.legal_refs).issubset(result.legal_refs)
            and set(binding.source_refs).issubset(result.source_refs)
        ):
            raise RuntimeError("Binding provenance lost in requirement")

        if pin.logical_generation != descriptor.logical_generation:
            raise RuntimeError("Observed selector and operation generation differ")
        if path.read_bytes() != before:
            raise RuntimeError("Selector changed during observation")

        print(json.dumps({"signal": "PROVEN"}, sort_keys=True))
finally:
    owner.close()
```

Exit code: 0. No stderr. Complete emitted output:

```text
{"descriptor": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "reader_incarnation": "20e5044693f1876f8e4425a67d78196a450924272b4c9950fb4d5c8a04d2d904", "stage": "operation-pin"}
{"revision": "2013-y-siguientes", "stage": "selected-revision"}
{"binding": {"aeat_prefilled": false, "aggregation": {"op": "copy"}, "applicability": {"kind": "all_revision_contexts"}, "authorship": {"kind": "authored"}, "id": "modelo-720-prior-year-cuentas-valoracion-baseline", "legal_refs": ["ley-58-2003:da-18", "rd-1065-2007:art-42-bis", "orden-hap-72-2013:art-2"], "provider": {"grouping": null, "kind": "previous_filing", "required_source_casilla_ids": null, "source_casilla_id": "cuentas.valoracion", "source_casilla_ids": [], "source_modelo": "720", "temporal": {"kind": "filing_year_offset", "max_years": null, "source_periods": ["0A"], "years": -1}}, "source_citations": [{"required_text": ["bienes y derechos situados en el extranjero"], "source_ref": "aeat-modelo-720-procedure"}], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "terminal_origins": [], "value": {"channel": "decimal", "data_type": "money", "row_grouping": null, "typed_enum": null}}, "descriptor": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "reader_incarnation": "20e5044693f1876f8e4425a67d78196a450924272b4c9950fb4d5c8a04d2d904", "revision": "2013-y-siguientes", "stage": "published-declaration"}
{"requirements": [{"aggregation_op": null, "binding_ids": ["modelo-720-prior-year-cuentas-valoracion-baseline", "modelo-720-prior-year-inmuebles-valoracion-baseline", "modelo-720-prior-year-valores-valoracion-baseline"], "dependency_role": null, "dependency_treatment": "factual_evidence", "filing_periods": [{"code": "0A", "filing_year": 2024}], "filing_year": 2024, "legal_refs": ["ley-58-2003:da-18", "orden-hap-72-2013:art-2", "rd-1065-2007:art-42-bis", "rd-1065-2007:art-42-ter", "rd-1065-2007:art-54-bis"], "periods": ["0A"], "required_source_casilla_ids": ["cuentas.valoracion", "inmuebles.valoracion", "valores.valoracion"], "source_casilla_ids": ["cuentas.valoracion", "inmuebles.valoracion", "valores.valoracion"], "source_modelo": "720", "source_presence_groups": [], "source_refs": ["aeat-dr-720", "aeat-modelo-720-procedure"], "target_bindings": []}], "stage": "resolved-requirements"}
{"signal": "PROVEN"}
probe_exit=0
```

Generation comparison: the operation pin and the descriptor both report logical generation `2bdbfabc…2c66`, the same value lane02-r01 recorded. Both lanes observed the same published generation, although HEAD moved between them.

Final signal: PROVEN.

## Findings

### l03-r02-f01 | low | Published binding resolves to the expected prior-year source target

Observed: revision `2013-y-siguientes` was selected for `720`/2025/`0A`. It contains exactly one binding with id `modelo-720-prior-year-cuentas-valoracion-baseline`. That binding's provider matches the fixed shape: `previous_filing`, source modelo `720`, source casilla `cuentas.valoracion`, `filing_year_offset` of -1 years, source periods `["0A"]`. `previous_filing_observation_requirements` returned exactly one requirement carrying this binding id, with source modelo `720`, filing year 2024, periods `["0A"]`, and `cuentas.valoracion` in both `source_casilla_ids` and `required_source_casilla_ids`. This confirms the behavior; it is not a defect. It resolves the question l03-r01-f01 left open.

### l03-r02-f02 | low | Coalesced requirement preserves the binding's published provenance

Observed: the resolver merged the requirements of three bindings (`cuentas`, `inmuebles`, `valores` valoración baseline) into one requirement. The requirement's `legal_refs` are a superset of the corrected binding's three legal refs, and its `source_refs` equal the binding's `aeat-dr-720` and `aeat-modelo-720-procedure`. The published binding carries `aeat-dr-720` even though its authored declaration names only `aeat-modelo-720-procedure` as an additional source ref. Hypothesis, not verified: the hydrator inherits `aeat-dr-720` from revision-level provenance.

Not asserted: after coalescing, the requirement no longer shows which legal ref belongs to which casilla. The requirement also reports `dependency_role` null, `aggregation_op` null, and empty `target_bindings` and `source_presence_groups`. Whether those empty values are correct for this context was not tested.

### l03-r02-f03 | low | Reader incarnation differs across processes at a fixed generation

Observed: lane02-r01 recorded reader incarnation `17ad67e0…51d8`; this run recorded `20e50446…d904`; both used logical generation `2bdbfabc…2c66`. This partly answers l02-r01-f02: the incarnation is not stable across separate processes at the same generation. Whether it changes per reader within one process is still unproven.

## Recommendations

This run closes dependency-target verification for this one binding at generation `2bdbfabc…2c66`. Next evidence question (from l03-r02-f01): given one synthetic 2024 `720`/`0A` source observation that carries `cuentas.valoracion`, does the binding resolve to exactly that value through the canonical value path? Prove missing-source behavior separately afterwards.

Still unproven: whether the source filing is available, how its revision is selected, monetary value resolution, missing-source and absent-versus-zero behavior, per-casilla provenance after coalescing, and consumption by the CLI or calculation engine. The fixture-description finding l03-r01-f02 remains open for a separate maintenance task; this lane did not touch the fixture.
