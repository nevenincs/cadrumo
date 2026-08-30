"""Previous-filing source validation helpers.

Validates that every ``previous_filing``
:class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloDefinition` resolves to a
known source modelo and that its declared
:class:`~cadrumo.core.CasillaId` values exist in the
matching source revisions.

See Also:
    :mod:`cadrumo.domain.calculations.registry.bindings_previous_filing`
        Selector parsing into canonical source modelo, period, and casilla ids.
    :mod:`cadrumo.domain.calculations.registry.validate_source_casilla_ids`
        Shared source-revision membership check and non-canonical diagnostics.
    :mod:`cadrumo.domain.calculations.registry.validate_relation_sources`
        Sibling closure validation for relation source selectors.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ....core.aggregation import BindingSourceKind
from ._validate_source_casilla_ids import source_casilla_id_reference_failure
from .bindings_previous_filing import previous_filing_source_reference
from .errors import RegistryValidationError
from .schema import DataBindingDefinition, ModeloDefinition


def validate_previous_filing_binding_closure(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    """Validate previous-filing source closure for registry modelos.

    Args:
        modelos: Iterable of
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
            entries whose ``previous_filing`` bindings are checked.
        modelos_by_id: Mapping of modelo id to
            :class:`~cadrumo.domain.calculations.registry.ModeloDefinition`
            used to resolve each binding's source modelo.
    """
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for binding in revision.bindings:
                if binding.source != BindingSourceKind.PREVIOUS_FILING:
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
    """Validate one previous-filing binding against its source modelo.

    The supplied :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition`
    is parsed by
    :func:`cadrumo.domain.calculations.registry.bindings_previous_filing.previous_filing_source_reference`,
    then each matching source revision is checked through
    :func:`cadrumo.domain.calculations.registry.validate_source_casilla_ids.source_casilla_id_reference_failure`.
    """
    failures: list[str] = []
    try:
        source_reference = previous_filing_source_reference(binding)
    except RegistryValidationError as exc:
        failures.append(f"{binding_scope} has malformed previous-filing selector: {exc}")
        return failures

    source_modelo_id = source_reference.source_modelo
    source_modelo = modelos_by_id.get(source_modelo_id)
    if source_modelo is None:
        failures.append(f"{binding_scope} references unknown source modelo {source_modelo_id!r}")
        return failures

    matching_revisions = tuple(
        source_revision
        for source_revision in source_modelo.revisions.values()
        if not source_reference.required_periods
        or set(source_reference.required_periods).issubset(set(source_revision.period_selector.periods))
    )
    if not matching_revisions:
        failures.append(
            f"{binding_scope} matches no source revisions in modelo {source_modelo.id} "
            f"for periods {source_reference.required_periods!r}",
        )
        return failures

    if not source_reference.source_casilla_ids:
        return failures

    for source_revision in matching_revisions:
        for source_casilla_id in source_reference.source_casilla_ids:
            failures.extend(
                source_casilla_id_reference_failure(
                    source_revision,
                    source_casilla_id,
                    source_scope=f"{binding_scope} source revision {source_revision.id!r}",
                    missing_failure=(
                        f"{binding_scope} source casilla id {source_casilla_id!r} is not defined by any "
                        f"period-compatible {source_modelo.id} revision {source_revision.id!r}"
                    ),
                ),
            )
    return failures
