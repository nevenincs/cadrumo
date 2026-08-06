"""Algorithm provider and binding validation helpers.

Validates algorithm provider and binding sections declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` for legal and source
reference closure.

Provider declarations define deterministic callable contracts; binding
declarations connect those contracts to
:class:`~cadrumo.domain.calculations.registry.CasillaId` inputs and outputs. Both
must carry :class:`~cadrumo.domain.calculations.registry.LegalReference` and
:class:`~cadrumo.domain.calculations.registry.SourceReference` grounding enforced by
the :class:`~cadrumo.domain.calculations.registry._validate_evidence.EvidenceValidator`.

See Also:
    :func:`cadrumo.domain.calculations.registry._validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that calls these algorithm validators.
    :func:`cadrumo.domain.calculations.registry._validate_reference_sections.check_algorithm_binding_refs`
        General id-reference checker for algorithm-binding references.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._ids import CasillaId
from ._schema import AlgorithmProviderDefinition, LegalReference, ModeloRevision, SourceReference
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs


def _format_schema_keys(values: set[str]) -> str:
    return ", ".join(repr(value) for value in sorted(values))


def validate_algorithm_provider_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append provider reference and source-tier failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` contributes
    :class:`~cadrumo.domain.calculations.registry._schema.AlgorithmProviderDefinition`
    rows. Each provider must cite known legal/source refs and carry
    ``official_source_guidance`` evidence.
    """
    for provider in revision.algorithm_providers:
        owner = f"algorithm provider {provider.id}"
        failures.extend(_missing_refs(prefix, owner, provider.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, provider.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, provider.source_refs, "official_source_guidance"))


def validate_algorithm_binding_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    provider_by_id: Mapping[str, AlgorithmProviderDefinition],
    casillas: set[CasillaId],
    resolvable_values: set[str],
    parameters: set[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append binding reference, schema-shape, and source-tier failures.

    The supplied :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
    provides the algorithm bindings. The validator checks each
    :class:`~cadrumo.domain.calculations.registry._schema.AlgorithmBindingDefinition`
    against its
    :class:`~cadrumo.domain.calculations.registry._schema.AlgorithmProviderDefinition`,
    declared :class:`~cadrumo.domain.calculations.registry.CasillaId` values,
    resolvable input values, constants, and evidence-grounding requirements.
    """
    for alg_binding in revision.algorithm_bindings:
        owner = f"algorithm binding {alg_binding.id}"
        failures.extend(_missing_refs(prefix, owner, alg_binding.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, alg_binding.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_source_tier(prefix, owner, alg_binding.source_refs, "official_source_guidance")
        )
        provider = provider_by_id.get(alg_binding.provider)
        if provider is None:
            failures.append(f"{prefix}: {owner} references unknown provider {alg_binding.provider!r}")
        else:
            declared_inputs = set(provider.allowed_input_schema)
            bound_inputs = set(alg_binding.inputs)
            missing_inputs = declared_inputs - bound_inputs
            unknown_inputs = bound_inputs - declared_inputs
            if missing_inputs:
                failures.append(
                    f"{prefix}: {owner} omits provider input(s) {_format_schema_keys(missing_inputs)}",
                )
            if unknown_inputs:
                failures.append(
                    f"{prefix}: {owner} maps input(s) {_format_schema_keys(unknown_inputs)} "
                    f"not declared by provider {alg_binding.provider!r}",
                )

            declared_outputs = set(provider.output_schema)
            bound_outputs = set(alg_binding.output_casilla_ids)
            missing_outputs = declared_outputs - bound_outputs
            unknown_outputs = bound_outputs - declared_outputs
            if missing_outputs:
                failures.append(
                    f"{prefix}: {owner} omits provider output(s) {_format_schema_keys(missing_outputs)}",
                )
            if unknown_outputs:
                failures.append(
                    f"{prefix}: {owner} maps output(s) {_format_schema_keys(unknown_outputs)} "
                    f"not declared by provider {alg_binding.provider!r}",
                )
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
