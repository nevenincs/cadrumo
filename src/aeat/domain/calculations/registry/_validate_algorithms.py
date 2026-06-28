"""Algorithm provider and binding validation helpers.

Validates algorithm provider and binding sections declared on a
:class:`ModeloRevision` for legal and source reference closure.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._ids import CasillaId
from ._schema import LegalReference, ModeloRevision, SourceReference
from ._validate_helpers import _missing_refs


def validate_algorithm_provider_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for provider in revision.algorithm_providers:
        owner = f"algorithm provider {provider.id}"
        failures.extend(_missing_refs(prefix, owner, provider.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, provider.source_refs, source_refs, "source"))


def validate_algorithm_binding_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    providers: set[str],
    casillas: set[CasillaId],
    resolvable_values: set[str],
    parameters: set[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    for alg_binding in revision.algorithm_bindings:
        owner = f"algorithm binding {alg_binding.id}"
        failures.extend(_missing_refs(prefix, owner, alg_binding.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, alg_binding.source_refs, source_refs, "source"))
        if alg_binding.provider not in providers:
            failures.append(f"{prefix}: {owner} references unknown provider {alg_binding.provider!r}")
        if alg_binding.target_casilla_id not in casillas:
            failures.append(f"{prefix}: {owner} targets unknown casilla {alg_binding.target_casilla_id!r}")
        for input_name, input_value in alg_binding.inputs.items():
            if input_value not in resolvable_values:
                failures.append(f"{prefix}: {owner} input {input_name!r} references unknown value {input_value!r}")
        for output_name, output_value in alg_binding.output_casilla_ids.items():
            if output_value not in casillas:
                failures.append(f"{prefix}: {owner} output {output_name!r} references unknown casilla {output_value!r}")
        for constant in alg_binding.constants:
            if constant not in parameters:
                failures.append(f"{prefix}: {owner} references unknown constant {constant!r}")
