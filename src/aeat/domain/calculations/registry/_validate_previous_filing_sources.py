"""Previous-filing source validation helpers.

Validates that every ``previous_filing`` binding declared on a
:class:`ModeloDefinition` resolves to a known source modelo and
that its declared outputs exist in the matching source revisions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._schema import DataBindingDefinition, ModeloDefinition
from ._validate_source_outputs import revision_output_ids


def validate_previous_filing_binding_closure(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for binding in revision.bindings:
                if binding.source != "previous_filing":
                    continue
                failures.extend(
                    _validate_previous_filing_binding(
                        binding,
                        binding_scope=f"{prefix}: binding {binding.id!r}",
                        modelos_by_id=modelos_by_id,
                    ),
                )
    return failures


def _validate_previous_filing_binding(
    binding: DataBindingDefinition,
    *,
    binding_scope: str,
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    failures: list[str] = []
    source_modelo_id = binding.selector.get("source_modelo")
    if not isinstance(source_modelo_id, str):
        failures.append(f"{binding_scope} must declare string selector source_modelo")
        return failures
    source_modelo = modelos_by_id.get(source_modelo_id)
    if source_modelo is None:
        failures.append(f"{binding_scope} references unknown source modelo {source_modelo_id!r}")
        return failures

    source_periods = _binding_source_periods(binding)
    matching_revisions = tuple(
        source_revision
        for source_revision in source_modelo.revisions.values()
        if not source_periods or set(source_periods).issubset(set(source_revision.period_selector.periods))
    )
    if not matching_revisions:
        failures.append(
            f"{binding_scope} matches no source revisions in modelo {source_modelo.id} for periods {source_periods!r}",
        )
        return failures

    source_outputs = _binding_source_outputs(binding)
    if not source_outputs:
        return failures

    revision_outputs = set().union(*(revision_output_ids(source_revision) for source_revision in matching_revisions))
    for source_output in source_outputs:
        if source_output not in revision_outputs:
            failures.append(
                f"{binding_scope} source output {source_output!r} is not defined by any "
                f"period-compatible {source_modelo.id} revision",
            )
    return failures


def _binding_source_periods(binding: DataBindingDefinition) -> tuple[str, ...]:
    source_periods = binding.selector.get("source_periods")
    if isinstance(source_periods, tuple) and all(isinstance(period, str) for period in source_periods):
        return source_periods
    period = binding.selector.get("period")
    if isinstance(period, str):
        return (period,)
    return ()


def _binding_source_outputs(binding: DataBindingDefinition) -> tuple[str, ...]:
    source_casillas = binding.selector.get("source_casillas")
    if isinstance(source_casillas, tuple) and all(isinstance(casilla, str) for casilla in source_casillas):
        return source_casillas
    source_output = binding.selector.get("source_output")
    if isinstance(source_output, str):
        return (source_output,)
    return ()
